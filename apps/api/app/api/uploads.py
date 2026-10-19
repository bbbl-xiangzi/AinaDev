"""附件上传 API：图片/文档，格式与大小限制后台可调（site_configs）。"""
import asyncio
import tempfile
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import SiteConfig, User
from app.services import file_storage

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# 默认配置（site_configs 覆盖）：允许类型 + 单文件上限
DEFAULT_ALLOWED_TYPES = "png,jpg,jpeg,gif,webp,pdf,doc,docx,xls,xlsx,txt,md,csv,zip,mp4,webm"
DEFAULT_MAX_SIZE_MB = 100

IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}
DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "txt", "md", "csv"}
ARCHIVE_EXT = {"zip", "tar", "gz", "rar", "7z"}


async def _get_config(db: AsyncSession) -> tuple[set[str], int]:
    """读取上传配置（站点可调，缺省用默认值）。"""
    rows = list(await db.scalars(select(SiteConfig).where(SiteConfig.key.in_(["upload_allowed_types", "upload_max_size_mb"]))))
    cfg = {r.key: r.value for r in rows}
    allowed = {t.strip().lower() for t in cfg.get("upload_allowed_types", DEFAULT_ALLOWED_TYPES).split(",") if t.strip()}
    try:
        max_mb = int(cfg.get("upload_max_size_mb", DEFAULT_MAX_SIZE_MB))
    except ValueError:
        max_mb = DEFAULT_MAX_SIZE_MB
    return allowed, max(1, min(max_mb, 500))


def _check_magic(content: bytes, ext: str) -> bool:
    """真实文件头校验：图片/PDF/ZIP 容器类必须匹配魔数，文本类放行。"""
    if ext == "mp4":
        if len(content) < 16 or content[4:8] != b"ftyp":
            return False
        size = int.from_bytes(content[:4], "big")
        if size < 16 or size > len(content):
            return False
        brands = [content[8:12]] + [content[i:i+4] for i in range(16, size, 4)]
        return any(b in {b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash"} for b in brands)
    if ext == "webm":
        return content.startswith(b"\x1a\x45\xdf\xa3") and b"\x42\x82\x84webm" in content[:4096]
    if ext in ("png",):
        return content[:8] == b"\x89PNG\r\n\x1a\n"
    if ext in ("jpg", "jpeg"):
        return content[:3] == b"\xff\xd8\xff"
    if ext in ("gif",):
        return content[:6] in (b"GIF87a", b"GIF89a")
    if ext == "webp":
        return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if ext == "bmp":
        return content[:2] == b"BM"
    if ext == "pdf":
        return content[:4] == b"%PDF"
    if ext in ("zip",):
        return content[:2] == b"PK"
    if ext in ("doc", "docx", "xls", "xlsx"):
        # OLE (D0 CF 11 E0) 或 ZIP 容器（docx/xlsx 是 zip）
        return content[:4] in (b"\xd0\xcf\x11\xe0", b"PK\x03\x04")
    # txt/md/csv 等文本类不做魔数校验
    return True


def _file_type(ext: str) -> str:
    if ext in {"mp4", "webm"}:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in DOC_EXT:
        return "document"
    if ext in ARCHIVE_EXT:
        return "archive"
    return "other"


def _save_upload(key, source):
    return file_storage.save("uploads", key, source)


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed, max_mb = await _get_config(db)

    filename = (file.filename or "file").strip()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 .{ext}，允许：{', '.join(sorted(allowed))}")

    # 存储：uploads/yyyy/mm/uuid.ext
    now = datetime.now(timezone.utc)
    rel_dir = Path(f"{now:%Y%m}") / f"{now:%m}"
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    # Bound memory use for videos; spill to a temporary file rather than buffer the whole upload.
    size = 0
    with tempfile.TemporaryFile() as source:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_mb * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"文件超过大小限制（{max_mb}MB）")
            await asyncio.to_thread(source.write, chunk)
        source.seek(0)
        if not _check_magic(source.read(4096), ext):
            raise HTTPException(status_code=400, detail=f"文件内容与扩展名不匹配（.{ext}），已拒绝")
        source.seek(0)
        await asyncio.to_thread(_save_upload, f"{rel_dir.as_posix()}/{stored_name}", source)

    url = f"/uploads/{rel_dir.as_posix()}/{stored_name}"
    return {
        "url": url,
        "name": filename,
        "size": size,
        "type": _file_type(ext),
    }
