"""SSO 登录端点：企业统一身份登录（OIDC 授权码 + PKCE）。"""
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.security import create_access_token, create_refresh_token
from app.models import SsoConfig, User
from app.schemas import SsoStatusOut
from app.services import sso_service

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SsoStatusOut)
async def sso_status(db: AsyncSession = Depends(get_db)):
    cfg = await sso_service.get_active_config(db)
    if not cfg:
        return SsoStatusOut()
    return SsoStatusOut(enabled=True, label=cfg.label or "企业统一身份登录")


@router.get("/login")
async def sso_login(db: AsyncSession = Depends(get_db)):
    """登录入口：生成 state + PKCE，302 到企业应用中台授权页。"""
    cfg = await sso_service.get_active_config(db)
    if not cfg:
        raise HTTPException(status_code=400, detail="企业统一身份登录未启用")
    endpoints = await sso_service.resolve_endpoints(cfg)
    state, verifier, nonce = sso_service._new_state_record()
    async with aioredis.from_url(settings.redis_url) as redis:
        await redis.setex(
            f"{sso_service.STATE_PREFIX}{state}",
            sso_service.STATE_TTL,
            f"{verifier}|{nonce}",
        )
    url = sso_service.authorize_url_of(cfg, endpoints, state, verifier, nonce)
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback")
async def sso_callback(code: str = "", state: str = "", error: str = "", db: AsyncSession = Depends(get_db)):
    """IDP 回调：换 token → 验签 → 开通/绑定账号 → 签发社区 JWT。"""
    if error:
        raise HTTPException(status_code=400, detail=f"企业身份认证失败：{error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state")
    async with aioredis.from_url(settings.redis_url) as redis:
        rec = await redis.get(f"{sso_service.STATE_PREFIX}{state}")
        await redis.delete(f"{sso_service.STATE_PREFIX}{state}")
    if not rec:
        raise HTTPException(status_code=400, detail="state 无效或已过期（请重新发起登录）")
    verifier, nonce = rec.decode().split("|", 1)

    cfg = await sso_service.get_active_config(db)
    if not cfg:
        raise HTTPException(status_code=400, detail="企业统一身份登录已停用")

    try:
        token_resp = await sso_service.exchange_token(cfg, code, verifier)
        id_token = token_resp.get("id_token")
        if not id_token:
            raise ValueError("IDP 未返回 id_token")
        payload = await sso_service.verify_id_token(cfg, id_token, nonce)
        access_token = token_resp.get("access_token", "")
        userinfo = await sso_service.fetch_userinfo(cfg, access_token)
        claims = {**payload, **userinfo}
        # 按启用的员工字段定义做确定性映射（未配置映射的字段交给 LLM 抽取）
        from app.services.employee_fields import list_field_defs

        field_defs = await list_field_defs(db, enabled_only=True)
        mapped = sso_service.map_claims(claims, field_defs)
        user = await sso_service.provision_or_bind(db, cfg, claims, mapped, field_defs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"企业身份认证失败：{e}")

    # 异步 LLM 抽取员工扩展信息（不阻塞登录；失败静默，raw_claims 已存档）
    if cfg.extract_employee and field_defs:
        from app.tasks.worker import enqueue

        try:
            await enqueue("extract_employee_task", user.id, claims)
        except Exception as exc:
            # 抽取是可选任务；不把队列故障扩大为已认证用户的登录失败。
            logger.warning("SSO employee extraction enqueue failed (%s)", type(exc).__name__)

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    from urllib.parse import quote

    to = f"{settings.public_base_url.rstrip('/')}/login?sso_ok=1"
    return RedirectResponse(
        url=f"{to}#token={access}&refresh={quote(refresh)}&user_id={user.id}",
        status_code=302,
    )
