"""基于 Redis 的轻量限流：防暴力破解 / 防刷 LLM 算力。

- Redis 不可用时 fail-open（记日志，不阻断业务），避免把 Redis 故障放大为全站不可用。
- key 统一前缀 rl:<scope>:<维度>，INCR + EXPIRE 实现固定窗口计数。
"""
import logging
from typing import Optional

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)
_client: Optional[object] = None


def _get_client():
    global _client
    if _client is None:
        import redis.asyncio as aioredis

        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def check_rate(key: str, limit: int, window: int, detail: str = "操作过于频繁，请稍后再试") -> None:
    """计数 +1；超过 limit 抛 429。window 秒内最多 limit 次。"""
    try:
        r = _get_client()
        n = await r.incr(key)
        if n == 1:
            await r.expire(key, window)
        if n > limit:
            raise HTTPException(status_code=429, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rate limit unavailable (fail-open) %s: %s", key, e)


def client_ip(request) -> str:
    """取客户端 IP（考虑 X-Forwarded-For，nginx 反代场景）。"""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
