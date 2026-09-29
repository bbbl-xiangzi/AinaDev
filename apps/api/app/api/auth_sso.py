import html
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.ratelimit import check_rate, client_ip
from app.models import SsoConfig
from app.schemas import SsoStatusOut, UserOut
from app.services import sso_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/sso", tags=["auth-sso"])

STATE_PREFIX = sso_service.STATE_PREFIX
STATE_TTL = sso_service.STATE_TTL


def _redis():
    import redis.asyncio as aioredis

    return aioredis.from_url(settings.redis_url, decode_responses=True)


@router.get("/status", response_model=SsoStatusOut)
async def sso_status(db: AsyncSession = Depends(get_db)):
    cfg = await sso_service.get_active_config(db)
    if not cfg:
        return SsoStatusOut(enabled=False, label="企业统一身份登录")
    return SsoStatusOut(enabled=True, label=cfg.label or "企业统一身份登录")


@router.get("/login")
async def sso_login(request: Request, db: AsyncSession = Depends(get_db)):
    """发起 OIDC 授权：生成 state + PKCE，302 跳转企业 IDP 登录页。"""
    ip = client_ip(request)
    await check_rate(f"rl:sso:ip:{ip}", 20, 60, "操作过于频繁，请稍后再试")
    cfg = await sso_service.get_active_config(db)
    if not cfg:
        raise HTTPException(status_code=400, detail="未启用企业统一身份登录")
    if not cfg.client_id:
        raise HTTPException(status_code=400, detail="SSO 尚未配置 Client ID，请联系管理员")
    try:
        endpoints = await sso_service.resolve_endpoints(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SSO 配置不完整：{e}")
    state, verifier, nonce = sso_service._new_state_record()
    url = sso_service.authorize_url_of(cfg, endpoints, state, verifier, nonce)
    try:
        r = _redis()
        await r.setex(f"{STATE_PREFIX}{state}", STATE_TTL, json.dumps({"v": verifier, "n": nonce}))
    except Exception as e:
        logger.warning("SSO state 缓存失败：%s", e)
        raise HTTPException(status_code=503, detail="登录服务暂不可用，请稍后再试")
    return RedirectResponse(url, status_code=302)


@router.get("/callback")
async def sso_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """IDP 回调：换 token → 验签 → 开通/绑定账号 → 签发社区 JWT → HTML 写 token 回首页。"""
    ip = client_ip(request)
    await check_rate(f"rl:sso:cb:ip:{ip}", 30, 60, "操作过于频繁，请稍后再试")

    def error_page(message: str, status: int = 400) -> HTMLResponse:
        msg = html.escape(message)
        body = (
            "<!doctype html><html><head><meta charset='utf-8'><title>登录失败</title></head>"
            "<body style='font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;"
            "height:100vh;margin:0;background:#f6f8fa'>"
            "<div style='text-align:center;padding:28px;background:#fff;border:1px solid #d0d7de;"
            "border-radius:8px;max-width:420px'>"
            "<h2 style='margin:0 0 8px;font-size:18px;color:#cf222e'>SSO 登录失败</h2>"
            f"<p style='margin:0 0 16px;font-size:13px;color:#57606a'>{msg}</p>"
            "<a href='/login' style='display:inline-block;padding:8px 20px;background:#0969da;color:#fff;"
            "border-radius:6px;text-decoration:none;font-size:14px'>返回登录页</a>"
            "</div></body></html>"
        )
        return HTMLResponse(body, status_code=status)

    if error:
        return error_page(f"身份认证失败：{html.escape(error_description or error)}")
    if not code or not state:
        return error_page("缺少授权码或状态参数")

    try:
        r = _redis()
        record = await r.get(f"{STATE_PREFIX}{state}")
        await r.delete(f"{STATE_PREFIX}{state}")
        if not record:
            return error_page("登录状态已失效，请重新发起登录")
        rec = json.loads(record)
        verifier = rec.get("v", "")
        nonce = rec.get("n")
    except Exception as e:
        logger.warning("SSO state 读取失败：%s", e)
        return error_page("登录状态校验失败，请重新发起登录")

    try:
        cfg = await sso_service.get_active_config(db)
        if not cfg:
            return error_page("未启用企业统一身份登录")
        token_resp = await sso_service.exchange_token(cfg, code, verifier)
        id_token = token_resp.get("id_token")
        access_token = token_resp.get("access_token", "")
        if not id_token:
            return error_page("IDP 未返回 id_token（可能未开启 OIDC 或 scope 缺少 openid）")
        payload = await sso_service.verify_id_token(cfg, id_token, nonce)
        userinfo = await sso_service.fetch_userinfo(cfg, access_token)
        claims = {**payload, **userinfo}
        mapped = sso_service.map_claims(claims)
        user = await sso_service.provision_or_bind(db, cfg, claims, mapped)
    except ValueError as e:
        return error_page(str(e))
    except Exception as e:
        logger.exception("SSO 回调处理失败")
        return error_page("SSO 登录处理异常，请稍后再试或联系管理员")

    # 每日首次登录奖励
    try:
        from app.services.ticket_service import grant as grant_ticket

        await grant_ticket(db, user.id, "daily_login", note="SSO 每日首次登录")
        await db.commit()
    except Exception:
        pass

    # 员工扩展信息 LLM 抽取（异步，失败不影响登录）
    if cfg.extract_employee:
        try:
            from app.tasks.worker import enqueue

            await enqueue("extract_employee_task", user.id, claims)
        except Exception as e:
            logger.warning("入队员工信息抽取失败：%s", e)

    from app.services.auth_service import issue_tokens

    tokens = issue_tokens(user)
    user_data = json.dumps(UserOut.model_validate(user).model_dump(), ensure_ascii=False).replace("</", "<\\/")
    token_json = json.dumps(tokens, ensure_ascii=False).replace("</", "<\\/")
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>登录成功</title></head>"
        "<body style='font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;"
        "height:100vh;margin:0;background:#f6f8fa'>"
        "<div style='text-align:center;padding:28px;background:#fff;border:1px solid #d0d7de;border-radius:8px'>"
        "<p style='margin:0;font-size:14px;color:#24292f'>登录成功，正在进入社区…</p>"
        "</div>"
        "<script>"
        "try{"
        f"localStorage.setItem('community_token', {token_json}.access_token);"
        f"localStorage.setItem('community_user', JSON.stringify({user_data}));"
        "}catch(e){}"
        "location.href='/';".replace("'", "\'")
        "</script></body></html>"
    )
    return HTMLResponse(body)
