"""外部 Agent 回帖调用服务：支持多协议，统一返回结构化结果。

协议：
- openai_compatible : POST {url}，body {"model","messages"}，Bearer key
- dify_chatflow     : POST {url}/chat-messages，body {"inputs","query","user","response_mode":"blocking"}，Bearer key
- dify_workflow     : POST {url}/workflows/run，body {"inputs","response_mode":"blocking","user"}，Bearer key
- custom_http       : POST {url}，body 按 request_template 渲染（{title}/{body}/{author_name}/{category_name}），
                      响应按 response_path（点分路径，如 data.outputs.text / choices.0.message.content）提取
"""
import json
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import aes_decrypt
from app.models import ExternalAgent

logger = logging.getLogger(__name__)


def _extract_by_path(data: Any, path: str) -> str | None:
    """按点分路径提取，如 data.outputs.text / choices.0.message.content。"""
    if not path:
        return None
    cur = data
    for seg in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError, TypeError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            return None
    if isinstance(cur, str):
        return cur
    if cur is not None:
        return json.dumps(cur, ensure_ascii=False)
    return None


def _render_template(template: str, ctx: dict) -> dict:
    """渲染 custom_http 请求体模板（JSON，支持 {title} 等变量替换）。"""
    if not template or not template.strip():
        return {}
    try:
        text = template
        for k, v in ctx.items():
            text = text.replace("{" + k + "}", str(v or ""))
        return json.loads(text)
    except Exception:
        return {}


async def call_external_agent(db: AsyncSession, agent: ExternalAgent, ctx: dict) -> dict:
    """调用外部 Agent。ctx: {title, body, author_name, category_name}

    返回 {"ok": True, "text": 回复文本, "raw": 原始响应}
     或 {"ok": False, "error_code": str, "error_msg": str, "raw": 原始响应}
    """
    if not agent.enabled:
        return {"ok": False, "error_code": "DISABLED", "error_msg": "外部 Agent 已被停用", "raw": ""}

    api_key = ""
    if agent.api_key_encrypted:
        try:
            api_key = aes_decrypt(agent.api_key_encrypted)
        except Exception:
            return {"ok": False, "error_code": "KEY_DECRYPT", "error_msg": "API Key 解密失败", "raw": ""}

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if agent.headers_json:
        headers.update({str(k): str(v) for k, v in agent.headers_json.items()})

    timeout = httpx.Timeout(agent.timeout_seconds or 60, connect=15)
    proto = agent.protocol or "openai_compatible"
    url = agent.api_url.rstrip("/")

    payload: dict = {}
    response_path = agent.response_path

    try:
        if proto == "openai_compatible":
            payload = {
                "model": agent.model or "",
                "messages": [
                    {"role": "system", "content": "你是一个开发者社区的 AI 助手，请针对用户帖子给出专业、有帮助的回复。"},
                    {"role": "user", "content": f"栏目：{ctx.get('category_name', '')}\n标题：{ctx.get('title', '')}\n内容：{ctx.get('body', '')}"},
                ],
            }
            response_path = response_path or "choices.0.message.content"

        elif proto == "dify_chatflow":
            payload = {
                "inputs": {},
                "query": f"栏目：{ctx.get('category_name', '')}\n标题：{ctx.get('title', '')}\n内容：{ctx.get('body', '')}",
                "user": "community-bot",
                "response_mode": "blocking",
            }
            response_path = response_path or "answer"

        elif proto == "dify_workflow":
            payload = {
                "inputs": {
                    "title": ctx.get("title", ""),
                    "body": ctx.get("body", ""),
                    "author_name": ctx.get("author_name", ""),
                    "category_name": ctx.get("category_name", ""),
                },
                "response_mode": "blocking",
                "user": "community-bot",
            }
            response_path = response_path or "data.outputs.text"

        elif proto == "custom_http":
            payload = _render_template(agent.request_template or "", ctx)
            if not payload:
                return {"ok": False, "error_code": "BAD_TEMPLATE", "error_msg": "请求体模板为空或非法 JSON", "raw": ""}

        else:
            return {"ok": False, "error_code": "BAD_PROTOCOL", "error_msg": f"不支持的协议：{proto}", "raw": ""}

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            raw = resp.text

        if resp.status_code >= 400:
            return {
                "ok": False, "error_code": f"HTTP_{resp.status_code}",
                "error_msg": f"外部 Agent 返回 HTTP {resp.status_code}：{raw[:300]}",
                "raw": raw[:2000],
            }

        try:
            data = resp.json()
        except Exception:
            return {"ok": False, "error_code": "BAD_JSON", "error_msg": "外部 Agent 响应不是合法 JSON", "raw": raw[:2000]}

        text = _extract_by_path(data, response_path) if response_path else None
        if not text or not text.strip():
            return {
                "ok": False, "error_code": "EMPTY_TEXT",
                "error_msg": f"未能从响应中提取回复文本（path={response_path}）",
                "raw": raw[:2000],
            }
        return {"ok": True, "text": text.strip(), "raw": raw[:2000]}

    except httpx.TimeoutException:
        return {"ok": False, "error_code": "TIMEOUT", "error_msg": f"外部 Agent 请求超时（>{agent.timeout_seconds}s）", "raw": ""}
    except Exception as e:  # noqa: BLE001
        logger.exception("external agent call failed")
        return {"ok": False, "error_code": type(e).__name__, "error_msg": str(e)[:300], "raw": ""}
