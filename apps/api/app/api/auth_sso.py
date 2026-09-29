"""前台 SSO：状态 / 登录入口 / 回调（OIDC 授权码 + PKCE）。"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services import redis_service, sso_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth/sso", tags=["auth-sso"])

STATE_TTL = 600

_SUCCESS_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>登录成功</title></head>
<body style="font-family:sans-serif;background:#f6f8fa;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="background:#fff;border:1px solid #d0d7de;border-radius:12px;padding:32px 40px;text-align:center">
<h2 style="margin:0 0 8px;color:#1a7f37">✓ 登录成功</h2>
<p style="color:#57606a;font-size:14px">正在进入社区…</p>
</div>
<script>
(function(){
  try{
    localStorage.setItem('community_token', JSON.stringify({access_token:'%s', refresh_token:'%s', user:%s}));
    localStorage.setItem('community_user', JSON.stringify(%s));
    window.location.href='/';
  }catch(e){ document.body.innerHTML='<p style="color:#cf222e">本地存储写入失败，请重试</p>'; }
})();
</script>
</body></html>"""

_ERROR_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>登录失败</title></head>
<body style="font-family:sans-serif;background:#f6f8fa;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="background:#fff;border:1px solid #ffcecb;border-radius:12px;padding:32px 40px;text-align:center;max-width:520px">
<h2 style="margin:0 0 8px;color:#cf222e">✕ 企业统一登录失败</h2>
<p style="color:#57606a;font-size:14px">%s</p>
<p style="color:#8c959f;font-size:12px;margin-top:16px">可返回社区登录页使用账号密码登录，或联系管理员。</p>
</div>
</body></html>"""


def _err_page(msg: str) -> HTMLResponse:
    return HTMLResponse(_ERROR_HTML % msg.replace("<", "&lt;").replace(">", "&gt;"), status_code=200)


@router.get("/status")
async def sso_status(db: AsyncSession = Depends(get_db)):
    from app.schemas import SsoStatusOut

    cfg = await sso_service.get_or_create_config(db)
    return SsoStatusOut(enabled=bool(cfg.enabled), label=cfg.label or "企业统一身份登录")


@router.get("/login")
async def sso_login(request: Request, db: AsyncSession = Depends(get_db)):
    """跳转到企业 IDP 授权页（PKCE S256 + state + nonce）。"""
    ok, _ = await redis_service.check_rate_limit(request, "sso:login", 10, 60)
    if not ok:
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    cfg = await sso_service.get_or_create_config(db)
    if not cfg.enabled:
        raise HTTPException(status_code=400, detail="未启用企业统一身份登录")
    url, state, verifier = await sso_service.new_authorize_url(db, cfg)
    await redis_service.setex(f"sso:auth:state:{state}", STATE_TTL, verifier)
    return RedirectResponse(url)


@router.get("/callback")
async def sso_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    ok, _ = await redis_service.check_rate_limit(request, "sso:cb", 20, 60)
    if not ok:
        return _err_page("请求过于频繁，请稍后再试")
    if error:
        return _err_page(f"企业授权失败：{error} {error_description or ''}")
    if not code or not state:
        return _err_page("回调缺少必要参数（code/state）")
    verifier = await redis_service.get(f"sso:auth:state:{state}")
    if not verifier:
        return _err_page("state 无效或已过期，请重新发起登录")
    await redis_service.delete(f"sso:auth:state:{state}")
    cfg = await sso_service.get_or_create_config(db)
    if not cfg.enabled:
        return _err_page("企业统一身份登录未启用")
    try:
        token_resp = await sso_service.exchange_token(cfg, code, verifier)
        id_claims = await sso_service.verify_id_token(cfg, token_resp.get("id_token", ""), None)
        userinfo = await sso_service.fetch_userinfo(cfg, token_resp.get("access_token", ""))
        user = await sso_service.provision_or_bind(db, cfg, userinfo, id_claims)
    except HTTPException as e:
        return _err_page(str(e.detail))
    except Exception as e:  # noqa: BLE001
        logger.exception("sso callback error")
        return _err_page(f"登录处理异常：{type(e).__name__}")

    from app.api.auth import create_tokens
    from app.services.ticket_service import award_ticket

    tokens = await create_tokens(user)
    try:
        await award_ticket(db, user.id, "daily_login", note="企业统一登录每日奖励")
    except Exception:  # noqa: BLE001
        pass
    if cfg.extract_employee:
        try:
            from app.tasks.worker import enqueue

            await enqueue("extract_employee_task", user.id, {**id_claims, **userinfo})
        except Exception:  # noqa: BLE001
            logger.warning("extract_employee_task 入队失败")

    import json as _json

    user_json = _json.dumps({
        "id": user.id, "email": user.email, "name": user.name, "avatar_url": user.avatar_url,
        "account_type": user.account_type, "role": user.role, "status": user.status,
        "org_id": user.org_id, "department": user.department, "created_at": user.created_at.isoformat(),
    }, ensure_ascii=False)
    return HTMLResponse(_SUCCESS_HTML % (tokens["access_token"], tokens["refresh_token"], user_json, user_json))
