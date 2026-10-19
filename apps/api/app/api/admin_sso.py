"""管理：SSO 配置；测试使用脱离 ORM 的副本，不修改运行中配置。"""
from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import SsoConfig, User
from app.schemas import SsoConfigIn, SsoConfigOut, SsoTestOut
from app.schemas.sso_options import OAuthOptions
from app.services import sso_service
from app.services.audit_service import audit
from app.services.oauth2_service import checked_url

router = APIRouter(prefix="/api/admin/sso", tags=["admin-sso"])


def _to_out(cfg):
    data={key:getattr(cfg,key) for key in SsoConfigOut.model_fields
          if key not in {"has_client_secret","redirect_uri","oauth_options"}}
    data.update(has_client_secret=bool(cfg.client_secret_encrypted),redirect_uri=sso_service.redirect_uri(),
                oauth_options=OAuthOptions.model_validate(cfg.oauth_options or {}))
    return SsoConfigOut(**data)


def candidate(current,body):
    cfg=SsoConfig(**{col.name:deepcopy(getattr(current,col.name)) for col in SsoConfig.__table__.columns})
    for key in body.model_fields_set:
        value=getattr(body,key)
        if key=="client_secret":
            if value and value.strip():
                cfg.client_secret_encrypted=sso_service.encrypt_secret(value.strip())
        elif key=="oauth_options":
            if value is not None:
                cfg.oauth_options=value.model_dump()
        elif value is not None:
            setattr(cfg,key,value.strip() if isinstance(value,str) else value)
    return cfg


async def validate_config(cfg, *, required=False):
    if cfg.bind_rule not in {"email","sub"}:
        raise ValueError("账号绑定规则无效")
    for path in (cfg.claim_sub,cfg.claim_email,cfg.claim_name):
        if path and (len(path)>100 or any(not part.replace('_','').replace('-','').isalnum() for part in path.split('.'))):
            raise ValueError("用户字段仅支持以点分隔的对象字段路径")
    opt=OAuthOptions.model_validate(cfg.oauth_options or {})
    if opt.logout_url:
        checked_url(opt.logout_url)
    fields=["authorization_endpoint","token_endpoint","userinfo_endpoint"]
    if cfg.protocol=="oidc":
        fields += ["jwks_uri","issuer"]
    for field in fields:
        if getattr(cfg,field,None):
            checked_url(getattr(cfg,field))
    if required:
        if not cfg.client_id or not cfg.claim_sub:
            raise ValueError("请填写 Client ID 和唯一账号标识字段")
        if cfg.protocol=="oidc" and not cfg.issuer:
            raise ValueError("OIDC 必须填写 Issuer 用于验证签发者")
        await sso_service.resolve_endpoints(cfg)


@router.get("/config", response_model=SsoConfigOut)
async def get_config(admin: User=Depends(require_super_admin),db:AsyncSession=Depends(get_db)):
    return _to_out(await sso_service.get_or_create_config(db))


@router.put("/config", response_model=SsoConfigOut)
async def update_config(body:SsoConfigIn,admin:User=Depends(require_super_admin),db:AsyncSession=Depends(get_db)):
    current=await sso_service.get_or_create_config(db)
    cfg=candidate(current,body)
    try:
        await validate_config(cfg,required=cfg.enabled)
    except ValueError as exc:
        raise HTTPException(400,detail=str(exc)) from None
    for col in SsoConfig.__table__.columns:
        if col.name not in {"id","created_at","updated_at"}:
            setattr(current,col.name,getattr(cfg,col.name))
    await db.commit()
    await db.refresh(current)
    await audit(db,"user",admin.id,"update_sso_config","sso_configs",current.id,
                {"enabled":current.enabled,"protocol":current.protocol,"bind_rule":current.bind_rule})
    return _to_out(current)


@router.post("/config/test", response_model=SsoTestOut)
async def test_config(body:SsoConfigIn,admin:User=Depends(require_super_admin),db:AsyncSession=Depends(get_db)):
    cfg=candidate(await sso_service.get_or_create_config(db),body)
    try:
        await validate_config(cfg,required=True)
        result=await sso_service.test_connection(cfg)
        return SsoTestOut(**result)
    except Exception:
        return SsoTestOut(ok=False,message="配置检查失败：请检查必填项、HTTPS 地址及内网 SSO 允许名单",details=None)
