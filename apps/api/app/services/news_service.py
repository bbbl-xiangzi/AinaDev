"""每日 AI 资讯：RSS/API 抓取 → 全文转 MD + 图片本地化 → AI 导读 → 发布到指定栏目。"""
import logging
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup, Tag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AiNewsSource, Post, User
from app.services.llm import chat_completion
from app.services.model_service import get_default_llm_config

logger = logging.getLogger(__name__)

LEAD_PROMPT = """你是企业 AI 资讯编辑。用 80-120 字中文写一段导读，点出这篇资讯的核心事件与价值（主体、做了什么、为什么重要）。
输出纯导读文本，不要标题、不要列表、不要客套。"""

# 图片下载限制：单张 8MB，每条资讯最多 12 张
IMG_MAX_BYTES = 8 * 1024 * 1024
IMG_MAX_PER_ARTICLE = 12
IMG_ALLOWED = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml"}


async def _download_image(img_url: str, base_url: str) -> str | None:
    """下载远程图片到 uploads，返回本地 /uploads/... URL；失败返回 None。"""
    from app.core.net_safety import is_safe_url

    full = urljoin(base_url, img_url)
    if not full.startswith(("http://", "https://")):
        return None
    ok, _reason = is_safe_url(full)
    if not ok:
        logger.warning("image download blocked (ssrf): %s", full)
        return None
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; AinaBot/1.0)"}) as client:
            resp = await client.get(full)
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype not in IMG_ALLOWED:
                return None
            data = resp.content
            if len(data) > IMG_MAX_BYTES or len(data) < 200:
                return None
            ext = mimetypes.guess_extension(ctype) or ".jpg"
            if ext == ".jpe":
                ext = ".jpg"
            now = datetime.now(timezone.utc)
            rel_dir = Path(f"{now:%Y%m}") / f"{now:%m}"
            target_dir = Path(settings.upload_dir).resolve() / rel_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            stored = f"{uuid.uuid4().hex}{ext}"
            (target_dir / stored).write_bytes(data)
            return f"/uploads/{rel_dir.as_posix()}/{stored}"
    except Exception as e:
        logger.warning("image download failed %s: %s", full, e)
        return None


def _inline_text(el: Tag) -> str:
    """提取行内文本，保留粗体/斜体/链接。"""
    out = ""
    for node in el.children:
        if isinstance(node, str):
            out += node
        elif node.name in ("strong", "b"):
            out += f"**{node.get_text(strip=True)}**"
        elif node.name in ("em", "i"):
            out += f"*{node.get_text(strip=True)}*"
        elif node.name == "a":
            href = node.get("href", "")
            txt = node.get_text(strip=True)
            if href and txt:
                out += f"[{txt}]({href})"
            else:
                out += txt
        elif node.name == "br":
            out += "  \n"
        else:
            out += node.get_text()
    return re.sub(r"\s+", " ", out).strip()


async def html_to_markdown(html: str, base_url: str) -> str:
    """HTML 正文转 Markdown；图片下载到本地并替换为本地 URL。"""
    soup = BeautifulSoup(html or "", "html.parser")
    # 移除脚本/样式/广告
    for t in soup(["script", "style", "iframe", "noscript"]):
        t.decompose()

    img_count = 0
    lines: list[str] = []

    for el in soup.children:
        if isinstance(el, str):
            txt = el.strip()
            if txt:
                lines.append(txt)
            continue
        if not isinstance(el, Tag):
            continue
        name = el.name.lower()

        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            lines.append("\n" + "#" * (level + 1) + " " + el.get_text(strip=True))
        elif name == "p":
            # 先处理段落内图片
            for img in el.find_all("img"):
                if img_count >= IMG_MAX_PER_ARTICLE:
                    img.decompose()
                    continue
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    local = await _download_image(src, base_url)
                    img_count += 1
                    if local:
                        img.replace_with(f"\n\n![{img.get('alt','')}]({local})\n\n")
                    else:
                        img.decompose()
            txt = _inline_text(el)
            if txt:
                lines.append(txt)
        elif name in ("ul", "ol"):
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                bullet = f"{i}. " if name == "ol" else "- "
                lines.append(bullet + _inline_text(li))
        elif name == "blockquote":
            for line in el.get_text("\n").strip().splitlines():
                lines.append("> " + line.strip())
        elif name in ("pre",):
            code = el.get_text()
            lines.append(f"\n```\n{code.strip()}\n```")
        elif name == "figure":
            img = el.find("img")
            if img and img_count < IMG_MAX_PER_ARTICLE:
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    local = await _download_image(src, base_url)
                    img_count += 1
                    if local:
                        lines.append(f"\n\n![]({local})\n\n")
            cap = el.find("figcaption")
            if cap:
                lines.append(f"*{cap.get_text(strip=True)}*")
        elif name == "img":
            if img_count < IMG_MAX_PER_ARTICLE:
                src = el.get("src") or el.get("data-src") or ""
                if src:
                    local = await _download_image(src, base_url)
                    img_count += 1
                    if local:
                        lines.append(f"\n\n![]({local})\n\n")
        elif name in ("div", "section", "article"):
            # 递归处理块级容器
            sub = await html_to_markdown(el.decode_contents(), base_url)
            if sub.strip():
                lines.append(sub)
        else:
            txt = _inline_text(el)
            if txt:
                lines.append(txt)

    md = "\n\n".join(l.strip() for l in lines if l.strip())
    # 清理多余空行
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


async def _fetch_fulltext(url: str) -> str:
    """抓原文页正文 HTML（含图片）。优先 BeautifulSoup 定位 article/main，失败回退 trafilatura。"""
    import asyncio

    from app.core.net_safety import is_safe_url

    ok, _reason = is_safe_url(url)
    if not ok:
        logger.warning("fulltext fetch blocked (ssrf): %s", url)
        return ""

    def _extract() -> str:
        try:
            import trafilatura
            from bs4 import BeautifulSoup

            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return ""
            soup = BeautifulSoup(downloaded, "html.parser")
            body = soup.find("article") or soup.find("main")
            if body:
                return body.decode_contents()
            # 回退 trafilatura 纯文本提取
            return trafilatura.extract(downloaded, output_format="html") or ""
        except Exception as e:
            logger.warning("fulltext extract %s failed: %s", url, e)
            return ""

    return await asyncio.to_thread(_extract)


async def fetch_news_source(db: AsyncSession, source: AiNewsSource) -> list[dict]:
    """抓取单个资讯源，返回 [{title, url, content_md}]。优先 RSS 全文；RSS 只有摘要时自动抓原文页全文。"""
    items: list[dict] = []
    if source.type == "rsshub":
        # RSSHub 路由：url 字段存路由路径（如 /bing/daily），拼 RSSHub 基础地址
        rsshub_base = getattr(settings, "rsshub_base_url", "http://rsshub:1200")
        feed_url = rsshub_base.rstrip("/") + source.url
        from app.core.net_safety import is_safe_url

        ok, _r = is_safe_url(feed_url)
        if not ok:
            logger.warning("rsshub source blocked (ssrf): %s", feed_url)
            return []
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            raw_html = ""
            if entry.get("content"):
                raw_html = entry["content"][0].get("value", "")
            if not raw_html:
                raw_html = entry.get("summary") or entry.get("description") or ""
            if len(re.sub(r"<[^>]+>", "", raw_html)) < 500 and link:
                full = await _fetch_fulltext(link)
                if len(re.sub(r"<[^>]+>", "", full)) > len(re.sub(r"<[^>]+>", "", raw_html)):
                    raw_html = full
            items.append({"title": title, "url": link, "html": raw_html})
    elif source.type == "rss":
        from app.core.net_safety import is_safe_url

        ok, _r = is_safe_url(source.url)
        if not ok:
            logger.warning("rss source blocked (ssrf): %s", source.url)
            return []
        feed = feedparser.parse(source.url)
        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            # 优先全文 content:encoded，其次 summary
            raw_html = ""
            if entry.get("content"):
                raw_html = entry["content"][0].get("value", "")
            if not raw_html:
                raw_html = entry.get("summary") or entry.get("description") or ""
            # RSS 只给短摘要时，自动抓原文页全文
            if len(re.sub(r"<[^>]+>", "", raw_html)) < 500 and link:
                full = await _fetch_fulltext(link)
                if len(re.sub(r"<[^>]+>", "", full)) > len(re.sub(r"<[^>]+>", "", raw_html)):
                    raw_html = full
            items.append({"title": title, "url": link, "html": raw_html})
    elif source.type == "api":
        # 自定义 JSON 接口：支持字段映射（config），默认 {"data":[{"title","url","content"}]}
        cfg = source.config or {}
        items_path = cfg.get("items_path", "data")
        title_path = cfg.get("title_path", "title")
        url_path = cfg.get("url_path", "url")
        url_template = cfg.get("url_template", "")
        summary_path = cfg.get("summary_path", "summary")
        detail_url_template = cfg.get("detail_url_template", "")
        detail_content_path = cfg.get("detail_content_path", "")
        from app.core.net_safety import is_safe_url

        ok, _r = is_safe_url(source.url)
        if not ok:
            logger.warning("api source blocked (ssrf): %s", source.url)
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(source.url, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
            # 按 items_path 取列表
            rows = data
            if items_path and isinstance(rows, dict):
                for k in items_path.split("."):
                    rows = rows.get(k, {}) if isinstance(rows, dict) else []
            if not isinstance(rows, list):
                rows = []

            def _pick(obj, path):
                cur = obj
                for k in path.split("."):
                    if isinstance(cur, dict):
                        cur = cur.get(k)
                    else:
                        return None
                return cur

            def _fill_template(tmpl, row):
                # 支持 {a.b.c} 嵌套路径
                def _sub(m):
                    v = _pick(row, m.group(1))
                    return "" if v is None else str(v)
                return re.sub(r"\{([^}]+)\}", _sub, tmpl)

            for row in rows[:10]:
                title = str(_pick(row, title_path) or "").strip()
                url = _pick(row, url_path) or ""
                if url_template and not url:
                    url = _fill_template(url_template, row)
                if not url.startswith("http") and url:
                    # 相对 ID → 拼原文 URL（用 url_template 优先，否则拼完整）
                    if url_template:
                        url = _fill_template(url_template, row)
                summary = _pick(row, summary_path) or ""
                # 如果配了详情 API，再抓全文
                full_html = str(summary)
                if detail_url_template and detail_content_path:
                    try:
                        detail_url = _fill_template(detail_url_template, row)
                        ok2, _r2 = is_safe_url(detail_url)
                        if not ok2:
                            continue
                        async with httpx.AsyncClient(timeout=15) as client:
                            dresp = await client.get(detail_url, headers={"User-Agent": "Mozilla/5.0"})
                            ddata = dresp.json()
                        dc = _pick(ddata, detail_content_path)
                        if dc and len(str(dc)) > len(full_html):
                            full_html = str(dc)
                    except Exception as de:
                        logger.warning("detail fetch failed: %s", de)
                items.append({"title": title, "url": str(url), "html": full_html})
        except Exception as e:
            logger.warning("news api fetch failed %s: %s", source.url, e)

    elif source.type == "html_list":
        # 传统 HTML 列表页：配 CSS 选择器抓文章链接，正文自动抓详情页
        cfg = source.config or {}
        link_selector = cfg.get("link_selector", "a")
        title_attr = cfg.get("title_attr", "")  # 可选，从 a 标签的哪个属性取标题
        from app.core.net_safety import is_safe_url

        ok, _r = is_safe_url(source.url)
        if not ok:
            logger.warning("html_list source blocked (ssrf): %s", source.url)
            return []
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(source.url, headers={"User-Agent": "Mozilla/5.0"})
                html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            seen = set()
            for a in soup.select(link_selector):
                href = a.get("href", "")
                if not href or href.startswith("javascript") or href.startswith("#"):
                    continue
                # 只要看起来像文章链接（含 .html 或数字 ID）
                if not re.search(r"\.html|\d{6,}", href):
                    continue
                abs_url = urljoin(source.url, href)
                if abs_url in seen:
                    continue
                seen.add(abs_url)
                title = ""
                if title_attr:
                    title = a.get(title_attr, "") or ""
                if not title:
                    title = a.get_text(strip=True)
                # 标题太短或像导航文字则跳过
                if len(title) < 6 or len(title) > 200:
                    continue
                items.append({"title": title, "url": abs_url, "html": ""})
                if len(items) >= 10:
                    break
        except Exception as e:
            logger.warning("html_list fetch failed %s: %s", source.url, e)

    # HTML → Markdown（图片本地化）
    result: list[dict] = []
    for i in items:
        if not i.get("title"):
            continue
        # api 类型拿到的摘要太短时，自动抓原文页全文
        if i.get("url") and len(re.sub(r"<[^>]+>", "", i.get("html", ""))) < 500:
            full = await _fetch_fulltext(i["url"])
            if len(re.sub(r"<[^>]+>", "", full)) > len(re.sub(r"<[^>]+>", "", i.get("html", ""))):
                i["html"] = full
        try:
            md = await html_to_markdown(i.get("html", ""), i.get("url") or source.url)
        except Exception as e:
            logger.warning("html->md failed for %s: %s", i["url"], e)
            md = re.sub(r"<[^>]+>", "", i.get("html", ""))
        result.append({"title": i["title"], "url": i["url"], "content_md": md})
    return result


async def digest_and_publish(db: AsyncSession, source: AiNewsSource) -> int:
    """抓取 → 全文转 MD（图片本地化）→ AI 导读 → 发布资讯帖（运维 Agent 账号）。返回发布条数。"""
    items = await fetch_news_source(db, source)
    if not items:
        source.last_fetched_at = datetime.now(timezone.utc)
        await db.commit()
        return 0

    # 目标栏目兜底：未配置时自动落到「AI 资讯」栏目（slug=ai-news）
    category_id = source.target_category_id
    if not category_id:
        from app.models import Category
        cat = await db.scalar(select(Category).where(Category.slug == "ai-news"))
        if cat is None:
            raise RuntimeError("未配置资讯栏目（AI 资讯），请在资讯源中指定目标栏目")
        category_id = cat.id

    cfg = await get_default_llm_config(db)
    ops = await db.scalar(select(User).where(User.email == "ops-agent@community.local"))
    author_id = ops.id if ops else 0

    published = 0
    for item in items[:5]:  # 每次最多发布 5 条，避免刷屏
        exists = await db.scalar(
            select(Post).where(Post.title == item["title"][:250], Post.deleted_at.is_(None))
        )
        if exists:
            continue

        # AI 导读（可选，失败则不带导读）
        lead = ""
        try:
            lead = await chat_completion(cfg, LEAD_PROMPT, item["content_md"][:4000] or item["title"], max_tokens=200)
            lead = lead.strip()
        except Exception as e:
            logger.warning("lead digest failed: %s", e)

        body_parts = []
        if lead:
            body_parts.append(f"> 📰 **导读**：{lead}\n")
        if item["content_md"]:
            body_parts.append(item["content_md"])
        body_parts.append(f"\n---\n> 原文链接：[{item['title']}]({item['url']})")
        body = "\n\n".join(body_parts)

        db.add(
            Post(
                category_id=category_id,
                author_id=author_id,
                title=item["title"][:280],
                body_md=body,
                post_type="news",
                status="published",
                tags=["AI 资讯"],
            )
        )
        published += 1
    source.last_fetched_at = datetime.now(timezone.utc)
    await db.commit()
    return published


async def run_daily_news(db: AsyncSession) -> dict:
    """扫描所有启用的资讯源并发布。"""
    sources = list(
        await db.scalars(
            select(AiNewsSource).where(AiNewsSource.enabled.is_(True), AiNewsSource.deleted_at.is_(None))
        )
    )
    total = 0
    for src in sources:
        try:
            total += await digest_and_publish(db, src)
        except Exception as e:
            logger.exception("news source %s failed: %s", src.name, e)
    return {"sources": len(sources), "published": total}
