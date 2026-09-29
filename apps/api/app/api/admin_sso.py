"""管理：SSO（企业统一身份登录）配置。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import SsoConfig, User
from app.schemas import SsoConfigIn, SsoConfigOut, SsoTestOut
from app.services import sso_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api/admin/sso", tags=["admin-sso"])


def _to_out(cfg: SsoConfig) -> SsoConfigOut:
    return SsoConfigOut(
        id=cfg.id, enabled=cfg.enabled, label=cfg.label, protocol=cfg.protocol,
        issuer=cfg.issuer, client_id=cfg.client_id or "",
        has_client_secret=bool(cfg.client_secret_encrypted),
        authorization_endpoint=cfg.authorization_endpoint, token_endpoint=cfg.token_endpoint,
        jwks_uri=cfg.jwks_uri, userinfo_endpoint=cfg.userinfo_endpoint,
        scopes=cfg.scopes or "openid profile email", bind_rule=cfg.bind_rule or "email",
        auto_provision=cfg.auto_provision, extract_employee=cfg.extract_employee,
        claim_sub=cfg.claim_sub or "sub", claim_email=cfg.claim_email or "email",
        claim_name=cfg.claim_name or "name", updated_at=cfg.updated_at,
        redirect_uri=sso_service.redirect_uri(),
    )


@router.get("/config", response_model=SsoConfigOut)
async def get_config(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    cfg = await sso_service.get_or_create_config(db)
    return _to_out(cfg)


@router.put("/config", response_model=SsoConfigOut)
async def update_config(
    body: SsoConfigIn,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    cfg = await sso_service.get_or_create_config(db)
    if body.label is not None and body.label.strip():
        cfg.label = body.label.strip()[:100]
    if body.issuer is not None:
        cfg.issuer = body.issuer.strip() or None
    if body.client_id is not None:
        cfg.client_id = body.client_id.strip()
    if body.client_secret is not None and body.client_secret.strip():
        cfg.client_secret_encrypted = sso_service.encrypt_secret(body.client_secret.strip())
    if body.authorization_endpoint is not None:
        cfg.authorization_endpoint = body.authorization_endpoint.strip() or None
    if body.token_endpoint is not None:
        cfg.token_endpoint = body.token_endpoint.strip() or None
    if body.jwks_uri is not None:
        cfg.jwks_uri = body.jwks_uri.strip() or None
    if body.userinfo_endpoint is not None:
        cfg.userinfo_endpoint = body.userinfo_endpoint.strip() or None
    if body.scopes is not None:
        cfg.scopes = body.scopes.strip() or "openid profile email"
    if body.bind_rule is not None:
        if body.bind_rule not in {"email", "sub"}:
            raise HTTPException(status_code=400, detail="绑定规则仅支持 email / sub")
        cfg.bind_rule = body.bind_rule
    if body.auto_provision is not None:
        cfg.auto_provision = body.auto_provision
    if body.extract_employee is not None:
        cfg.extract_employee = body.extract_employee
    if body.claim_sub is not None and body.claim_sub.strip():
        cfg.claim_sub = body.claim_sub.strip()
    if body.claim_email is not None and body.claim_email.strip():
        cfg.claim_email = body.claim_email.strip()
    if body.claim_name is not None and body.claim_name.strip():
        cfg.claim_name = body.claim_name.strip()
    cfg.enabled = body.enabled

    if cfg.enabled:
        if not cfg.client_id:
            raise HTTPException(status_code=400, detail="启用 SSO 前请先填写 Client ID")
        try:
            await sso_service.resolve_endpoints(cfg)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"启用 SSO 前请先通过「测试连接」：{e}")

    await db.commit()
    await db.refresh(cfg)
    await audit(db, "user", admin.id, "update_sso_config", "sso_configs", cfg.id,
                {"enabled": cfg.enabled, "issuer": cfg.issuer, "bind_rule": cfg.bind_rule})
    return _to_out(cfg)


@router.post("/config/test", response_model=SsoTestOut)
async def test_config(
    body: SsoConfigIn,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """用表单当前值（未保存）做连接测试，便于保存前验证。"""
    cfg = await sso_service.get_or_create_config(db)
    if body.client_id is not None:
        cfg.client_id = body.client_id.strip() or cfg.client_id
    if body.client_secret is not None and body.client_secret.strip():
        cfg.client_secret_encrypted = sso_service.encrypt_secret(body.client_secret.strip())
    if body.issuer is not None:
        cfg.issuer = body.issuer.strip() or cfg.issuer
    if body.authorization_endpoint is not None:
        cfg.authorization_endpoint = body.authorization_endpoint.strip() or cfg.authorization_endpoint
    if body.token_endpoint is not None:
        cfg.token_endpoint = body.token_endpoint.strip() or cfg.token_endpoint
    if body.jwks_uri is not None:
        cfg.jwks_uri = body.jwks_uri.strip() or cfg.jwks_uri
    if body.userinfo_endpoint is not None:
        cfg.userinfo_endpoint = body.userinfo_endpoint.strip() or cfg.userinfo_endpoint
    if not cfg.client_id:
        raise HTTPException(status_code=400, detail="请先填写 Client ID 再测试")
    try:
        result = await sso_service.test_connection(cfg)
    except Exception as e:
        return SsoTestOut(ok=False, message=f"测试失败：{e}", details=None)
    return SsoTestOut(ok=result["ok"], message=result["message"], details=result["details"])
