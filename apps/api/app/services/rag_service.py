"""RAG 服务：文档解析、切片、embedding、混合检索。"""
import asyncio
import re
from app.services.file_storage import document_path
from pathlib import Path

import trafilatura
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import RagChunk, RagDocument
from app.services.llm import LLMConfig, embed_texts


# ---------- 文档解析 ----------
async def parse_document(path: str | None, url: str | None, file_type: str, original_name: str) -> str:
    """按类型解析为纯文本。"""
    if file_type == "url":
        if not url:
            raise ValueError("URL 为空")
        # SSRF 防护：抓取前再次校验目标地址
        from app.core.net_safety import assert_safe_url

        assert_safe_url(url, "导入地址")
        fetched = trafilatura.fetch_url(url)
        if not fetched:
            raise ValueError("URL 抓取失败")
        text_content = trafilatura.extract(fetched, include_comments=False, include_tables=True) or ""
        if not text_content.strip():
            raise ValueError("URL 未提取到正文")
        return text_content

    if not path:
        raise ValueError("文件不存在")
    return await asyncio.to_thread(_parse_file, path, file_type)


def _parse_file(path: str, file_type: str) -> str:
    with document_path(path) as local_path:
        if file_type == "pdf":
            from pypdf import PdfReader

            reader = PdfReader(local_path)
            parts = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(parts)

        if file_type == "docx":
            import docx

            doc = docx.Document(local_path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

        if file_type in ("md", "txt"):
            return Path(local_path).read_text(encoding="utf-8", errors="ignore")

        raise ValueError(f"不支持的文件类型: {file_type}")


# ---------- 切片 ----------
def chunk_text(text: str, chunk_size: int = 600, overlap: int = 80) -> list[str]:
    """标题感知切片：优先按 Markdown 标题分节聚合；无标题则按段落聚合；超长段落硬切。

    - chunk_size 600 / overlap 80：长文档会切出多个块，提升向量检索召回粒度。
    - 标题行随所在节保留，便于定位出处。
    """
    # 规范化空白
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    # 按 Markdown 标题行（^#{1,6} ）切分为「节」，标题行保留在节内
    lines = text.split("\n")
    sections: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if re.match(r"^#{1,6}\s", line) and cur:
            sections.append(cur)
            cur = []
        cur.append(line)
    if cur:
        sections.append(cur)

    chunks: list[str] = []
    for sec in sections:
        sec_text = "\n".join(sec).strip()
        if not sec_text:
            continue
        # 节内按空行分段聚合
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", sec_text) if p.strip()]
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= chunk_size:
                current = f"{current}\n\n{para}" if current else para
            else:
                if current:
                    chunks.append(current)
                if len(para) > chunk_size:
                    # 长段落硬切
                    for i in range(0, len(para), chunk_size - overlap):
                        chunks.append(para[i : i + chunk_size])
                    current = ""
                else:
                    current = para
        if current:
            chunks.append(current)
    return chunks


# ---------- 入库 ----------
async def embed_and_store_chunks(
    db: AsyncSession,
    doc: RagDocument,
    chunks: list[str],
    cfg: LLMConfig,
    titles: list[str] | None = None,
) -> int:
    """切片 → embedding → 入库（JSONB/pgvector + 可选 Weaviate + tsvector 全文索引列）。"""
    vectors = await embed_texts(cfg, chunks)
    stored_ids: list[int] = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        row = RagChunk(
            document_id=doc.id,
            category_id=doc.category_id,
            chunk_index=i,
            title=(titles[i] if titles else None),
            content=chunk,
            embedding=vec,
            meta_data={"filename": doc.filename, "chunk_index": i},
        )
        db.add(row)
        await db.flush()
        stored_ids.append(row.id)
    # 先落库 chunks（独立事务），避免后续 tsvector 失败污染
    await db.flush()
    doc.status = "ready"
    doc.chunk_count = len(chunks)
    await db.commit()

    # Weaviate 同步（独立向量库；失败仅告警不阻塞主流程）
    if settings.vector_backend == "weaviate":
        from app.services.weaviate_service import upsert_chunk

        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            await upsert_chunk(
                chunk_id=stored_ids[i], document_id=doc.id, category_id=doc.category_id,
                chunk_index=i, title=(titles[i] if titles else None),
                content=chunk, filename=doc.filename, vector=vec,
            )

    # tsvector 全文索引：仅当数据库已安装 zhparser 扩展时更新；否则静默跳过（走 ILIKE 兜底）
    try:
        has_zh = await db.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'zhparser'"))
        if has_zh:
            await db.execute(
                text(
                    "UPDATE rag_chunks SET tsvector = to_tsvector('zh', content) "
                    "WHERE document_id = :doc_id AND tsvector IS NULL"
                ).bindparams(doc_id=doc.id)
            )
            await db.commit()
    except Exception:
        await db.rollback()  # 扩展缺失/权限不足时不影响主流程
    return len(chunks)


async def rebuild_chunks(db: AsyncSession, doc_id: int, cfg: LLMConfig) -> None:
    """删除并重建索引（换 embedding 模型后使用；含 Weaviate 清理与重写）。"""
    doc = await db.get(RagDocument, doc_id)
    if not doc:
        return
    chunks = await db.scalars(select(RagChunk).where(RagChunk.document_id == doc_id).order_by(RagChunk.chunk_index))
    rows = chunks.all()
    texts = [c.content for c in rows]
    vectors = await embed_texts(cfg, texts)

    if settings.vector_backend == "weaviate":
        from app.services.weaviate_service import delete_document_chunks, upsert_chunk

        await delete_document_chunks(doc_id)
        for row, vec in zip(rows, vectors):
            row.embedding = vec
            await upsert_chunk(
                chunk_id=row.id, document_id=doc.id, category_id=doc.category_id,
                chunk_index=row.chunk_index, title=row.title, content=row.content,
                filename=doc.filename, vector=vec,
            )
    else:
        for row, vec in zip(rows, vectors):
            row.embedding = vec
    await db.commit()


# ---------- 混合检索 ----------
def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


async def _vector_search(db: AsyncSession, category_id: int, qvec: list[float], top: int) -> list[tuple[int, float]]:
    """向量检索：pgvector（生产）或 JSONB+numpy（Windows/降级）或 Weaviate（独立向量库）。"""
    from app.config import settings

    if settings.vector_backend == "weaviate":
        from app.services.weaviate_service import search_vectors

        return await search_vectors(category_id, qvec, top)

    if settings.vector_backend == "pgvector":
        rows = await db.execute(
            text(
                """
                SELECT id, 1 - (embedding <=> :qvec::vector) AS sim
                FROM rag_chunks
                WHERE category_id = :cid
                ORDER BY embedding <=> :qvec::vector
                LIMIT :top
                """
            ).bindparams(qvec=str(qvec), cid=category_id, top=top)
        )
        return [(r.id, float(r.sim)) for r in rows]

    # numpy 兜底：全表取向量（按栏目过滤），余弦相似度
    import numpy as np

    rows = await db.execute(text("SELECT id, embedding FROM rag_chunks WHERE category_id = :cid").bindparams(cid=category_id))
    q = np.asarray(qvec, dtype=np.float32)
    scored: list[tuple[int, float]] = []
    for r in rows:
        vec = np.asarray(r.embedding, dtype=np.float32)
        if vec.shape != q.shape or not vec.any():
            continue
        qn = np.linalg.norm(q)
        vn = np.linalg.norm(vec)
        if qn == 0 or vn == 0:
            continue
        scored.append((r.id, float(np.dot(q, vec) / (qn * vn))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top]


async def _fts_search(db: AsyncSession, category_id: int, query: str, top: int) -> list[tuple[int, float]]:
    """全文检索：zhparser（生产）或 ILIKE 兜底。"""
    from app.config import settings

    if settings.fulltext_mode == "zhparser":
        rows = await db.execute(
            text(
                """
                SELECT id, ts_rank_cd(tsvector, plainto_tsquery('zh', :q)) AS r
                FROM rag_chunks
                WHERE category_id = :cid AND tsvector @@ plainto_tsquery('zh', :q)
                ORDER BY r DESC
                LIMIT :top
                """
            ).bindparams(q=query, cid=category_id, top=top)
        )
        return [(r.id, float(r.r)) for r in rows]

    # ILIKE 兜底：按命中词数加权
    rows = await db.execute(
        text(
            "SELECT id, content FROM rag_chunks WHERE category_id = :cid AND (content ILIKE :p1 OR content ILIKE :p2)"
        ).bindparams(cid=category_id, p1=f"%{query[:100]}%", p2=f"%{query[:50]}%")
    )
    return [(r.id, 1.0) for r in rows][:top]


async def hybrid_search(
    db: AsyncSession,
    category_id: int,
    query: str,
    top_k: int = 20,
    vector_top: int = 20,
    fts_top: int = 20,
) -> list[dict]:
    """向量 + 全文 → RRF 融合，返回 [{chunk, score, rank}]（score 为 RRF 融合分 0~1 归一化）。"""
    scores: dict[int, dict] = {}

    # 先取 query 的 embedding
    from app.services.model_service import get_default_llm_config

    cfg = await get_default_llm_config(db)
    qvec = (await embed_texts(cfg, [query]))[0]

    # 1) 向量检索
    for rank, (cid, sim) in enumerate(await _vector_search(db, category_id, qvec, vector_top)):
        scores[cid] = {"chunk_id": cid, "rrf": _rrf_score(rank), "sim": sim}

    # 2) 全文检索
    for rank, (cid, _r) in enumerate(await _fts_search(db, category_id, query, fts_top)):
        entry = scores.setdefault(cid, {"chunk_id": cid, "rrf": 0.0, "sim": None})
        entry["rrf"] += _rrf_score(rank)

    # 3) 归一化 top-k
    ranked = sorted(scores.values(), key=lambda x: x["rrf"], reverse=True)[:top_k]
    if ranked:
        max_rrf = ranked[0]["rrf"] or 1.0
        for item in ranked:
            item["score"] = round(item["rrf"] / max_rrf, 4)
    return ranked


async def fetch_chunks(db: AsyncSession, chunk_ids: list[int]) -> list[RagChunk]:
    if not chunk_ids:
        return []
    return list(await db.scalars(select(RagChunk).where(RagChunk.id.in_(chunk_ids))))
