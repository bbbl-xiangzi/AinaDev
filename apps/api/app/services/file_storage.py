"""Local or private S3 storage. Public attachments and RAG originals use separate prefixes."""
import mimetypes
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings


class ObjectResponse(StreamingResponse):
    def __init__(self, *args, body, **kwargs):
        self.object_body = body
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Also runs when the client disconnects before the generator is started.
            self.object_body.close()


def checked_key(key: str) -> str:
    if not key or "\\" in key or any(ord(c) < 32 for c in key):
        raise ValueError("Invalid storage key")
    if any(p in ("", ".", "..") for p in key.split("/")):
        raise ValueError("Invalid storage key")
    return key


def client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3", endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=60,
                      retries={"max_attempts": 3}, s3={"addressing_style": "path"}),
    )


def save(kind: str, key: str, source) -> str:
    if kind not in ("uploads", "rag"):
        raise ValueError("Invalid storage namespace")
    checked_key(key)
    if settings.storage_backend == "s3":
        object_key = f"{kind}/{key}"
        client().upload_fileobj(source, settings.s3_bucket, object_key)
        return f"s3://{settings.s3_bucket}/{object_key}"
    root = Path(settings.upload_dir if kind == "uploads" else settings.rag_docs_dir).resolve()
    dest = (root / key).resolve()
    if not dest.is_relative_to(root):
        raise ValueError("Invalid storage path")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as output:
        shutil.copyfileobj(source, output)
    return str(dest)


def _rag_key(ref: str) -> str:
    parsed = urlsplit(ref)
    if parsed.scheme != "s3" or parsed.netloc != settings.s3_bucket or parsed.query or parsed.fragment:
        raise ValueError("Invalid document reference")
    key = checked_key(parsed.path.removeprefix("/"))
    if not key.startswith("rag/"):
        raise ValueError("Invalid document namespace")
    return key


def _local_document(ref: str) -> Path:
    # Preserve existing database paths when using the local backend or migrating.
    path = Path(ref)
    if not path.is_file():
        path = Path(settings.upload_dir) / ref
    if not path.is_file():
        raise FileNotFoundError("Document not found")
    return path


@contextmanager
def document_path(ref: str):
    if ref.startswith("s3://"):
        key = _rag_key(ref)
        with tempfile.TemporaryDirectory(prefix="ainadev-rag-") as temp:
            path = Path(temp) / Path(key).name
            client().download_file(settings.s3_bucket, key, str(path))
            yield path
    else:
        yield _local_document(ref)


def _object_response(key: str, filename: str, private: bool):
    from botocore.exceptions import ClientError, BotoCoreError

    try:
        obj = client().get_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        raise HTTPException(404 if code in ("NoSuchKey", "404", "NotFound") else 503,
                            "文件不存在" if code in ("NoSuchKey", "404", "NotFound") else "文件存储暂不可用") from None
    except BotoCoreError:
        raise HTTPException(503, "文件存储暂不可用") from None
    body = obj["Body"]

    def chunks():
        try:
            yield from body.iter_chunks(chunk_size=64 * 1024)
        finally:
            body.close()

    media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    inline = not private and media in ("image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp")
    return ObjectResponse(chunks(), body=body, media_type=media, headers={
        "Content-Length": str(obj["ContentLength"]),
        "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(filename, safe='')}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store" if private else "public, max-age=3600",
    })


def public_response(key: str):
    try:
        checked_key(key)
    except ValueError:
        raise HTTPException(404, "文件不存在") from None
    # Always force the public prefix; callers cannot address private originals.
    return _object_response(f"uploads/{key}", Path(key).name, False)


def private_response(ref: str, filename: str):
    if ref.startswith("s3://"):
        return _object_response(_rag_key(ref), filename, True)
    try:
        path = _local_document(ref)
    except FileNotFoundError:
        raise HTTPException(404, "文件不存在或已被清理") from None
    return FileResponse(path, filename=filename, headers={"Cache-Control": "private, no-store"})
