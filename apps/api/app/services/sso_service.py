"""SSO（OIDC 授权码 + PKCE）服务：社区为 SP、企业客户应用中台为 IDP。"""
import base64
import hashlib
import json
import logging
import os
import secrets
import time
from urllib.parse import urlencode, urlparse

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from jose import jwk, jwt
from jose.exceptions import JWTError, JWSError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import EmployeeProfile, SsoConfig, User
from app.services.ticket_service import award_ticket

logger = logging.getLogger(__name__)


# ---------- AES 加密（Client Secret 落库） ----------
def _aes_key() -> bytes:
    raw = settings.aes_key
    if len(raw) < 32:
        return hashlib.sha256(raw.encode()).digest()
    return raw.encode()[:32]


def encrypt_secret(secret: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_aes_key()).encrypt(nonce, secret.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt_secret(blob: str) -> str:
    data = base64.urlsafe_b64decode(blob.encode())
    nonce, ct = data[:12], data[12:]
    return AESGCM(_aes_key()).decrypt(nonce, ct, None).decode()


# ---------- 基础 ----------
def redirect_uri() -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/api/auth/sso/callback"


def is_safe_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("https", "http"):
        return False
    if not p.netloc:
        return False
    if p.hostname in ("localhost", "127.0.0.1", "::1"):
        return False
    if p.hostname and (p.hostname.endswith(".internal") or p.hostname.endswith(".local")):
        return False
    if p.hostname and p.hostname.split(".")[0] in ("169",):
        return False
    import ipaddress
    try:
        ip = ipaddress.ip_address(p.hostname)
    except ValueError:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return False
    return True


async def get_or_create_config(db: AsyncSession) -> SsoConfig:
    cfg = await db.scalar(select(SsoConfig).order_by(SsoConfig.id).limit(1))
    if not cfg:
        cfg = SsoConfig()
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


async def resolve_endpoints(cfg: SsoConfig) -> None:
    """优先显式端点；否则从 issuer 自动发现 .well-known/openid-configuration。"""
    if cfg.issuer:
        well_known = cfg.issuer.rstrip("/") + "/.well-known/openid-configuration"
        if not is_safe_url(well_known):
            raise HTTPException(status_code=400, detail="Issuer 地址不受信任，无法自动发现")
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(well_known)
            if r.status_code != 200:
                raise HTTPException(status_code=400, detail=f"OIDC 自动发现失败（{r.status_code}）")
            data = r.json()
        cfg.authorization_endpoint = data.get("authorization_endpoint") or cfg.authorization_endpoint
        cfg.token_endpoint = data.get("token_endpoint") or cfg.token_endpoint
        cfg.jwks_uri = data.get("jwks_uri") or cfg.jwks_uri
        cfg.userinfo_endpoint = data.get("userinfo_endpoint") or cfg.userinfo_endpoint
    for name, val in (("authorization_endpoint", cfg.authorization_endpoint),
                      ("token_endpoint", cfg.token_endpoint),
                      ("jwks_uri", cfg.jwks_uri),
                      ("userinfo_endpoint", cfg.userinfo_endpoint)):
        if not val or not is_safe_url(val):
            raise HTTPException(status_code=400, detail=f"{name} 缺失或不受信任")


async def test_connection(cfg: SsoConfig) -> dict:
    """探测端点 + JWKS 可解析性（不保存、不发起授权）。"""
    details: dict = {}
    if cfg.issuer:
        well_known = cfg.issuer.rstrip("/") + "/.well-known/openid-configuration"
        if not is_safe_url(well_known):
            raise HTTPException(status_code=400, detail="Issuer 地址不受信任")
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(well_known)
            if r.status_code != 200:
                raise HTTPException(status_code=400, detail=f"OIDC 自动发现失败（{r.status_code}）")
            data = r.json()
        details["discovery"] = {k: data.get(k) for k in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri", "userinfo_endpoint")}
        cfg.authorization_endpoint = data.get("authorization_endpoint") or cfg.authorization_endpoint
        cfg.token_endpoint = data.get("token_endpoint") or cfg.token_endpoint
        cfg.jwks_uri = data.get("jwks_uri") or cfg.jwks_uri
        cfg.userinfo_endpoint = data.get("userinfo_endpoint") or cfg.userinfo_endpoint
    if not cfg.authorization_endpoint or not cfg.token_endpoint:
        raise HTTPException(status_code=400, detail="缺少授权/令牌端点（请填写 Issuer 或显式端点）")
    for name, val in (("authorization_endpoint", cfg.authorization_endpoint), ("token_endpoint", cfg.token_endpoint),
                      ("jwks_uri", cfg.jwks_uri), ("userinfo_endpoint", cfg.userinfo_endpoint)):
        if val and is_safe_url(val):
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(val if name != "token_endpoint" else val)
            details[name] = r.status_code
        elif val:
            raise HTTPException(status_code=400, detail=f"{name} 不受信任")
    if cfg.jwks_uri:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(cfg.jwks_uri)
        try:
            jwk_set = r.json().get("keys", [])
            details["jwks_keys"] = len(jwk_set)
            if not jwk_set:
                raise HTTPException(status_code=400, detail="JWKS 未返回任何密钥")
        except ValueError:
            raise HTTPException(status_code=400, detail="JWKS 响应不是合法 JSON")
    if not cfg.client_id:
        raise HTTPException(status_code=400, detail="请先填写 Client ID")
    return {"ok": True, "message": "连接成功：端点可达、JWKS 可解析", "details": details}


# ---------- PKCE / 授权 ----------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sha256_b64url(s: str) -> str:
    return _b64url(hashlib.sha256(s.encode()).digest())


async def new_authorize_url(db: AsyncSession, cfg: SsoConfig) -> tuple[str, str, str]:
    """生成授权 URL，返回 (url, state, code_verifier)。state 与 verifier 由调用方落 Redis。"""
    await resolve_endpoints(cfg)
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri(),
        "scope": cfg.scopes or "openid profile email",
        "state": state,
        "code_challenge": _sha256_b64url(verifier),
        "code_challenge_method": "S256",
        "nonce": secrets.token_urlsafe(16),
    }
    url = cfg.authorization_endpoint + ("&" if "?" in cfg.authorization_endpoint else "?") + urlencode(params)
    return url, state, verifier


async def exchange_token(cfg: SsoConfig, code: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.post(
            cfg.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(),
                "client_id": cfg.client_id,
                "client_secret": decrypt_secret(cfg.client_secret_encrypted),
                "code_verifier": code_verifier,
            },
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"令牌交换失败（{r.status_code}）：{r.text[:200]}")
    return r.json()


async def fetch_userinfo(cfg: SsoConfig, access_token: str) -> dict:
    if not cfg.userinfo_endpoint:
        return {}
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(cfg.userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"})
    if r.status_code != 200:
        logger.warning("userinfo 获取失败 %s", r.status_code)
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


async def verify_id_token(cfg: SsoConfig, id_token: str, nonce: str | None) -> dict:
    """校验 ID Token：iss/aud/exp/iat/nonce；JWKS 或 HS256（仅当 issuer 与客户端自签）。"""
    unverified = jwt.get_unverified_claims(id_token)
    if nonce and unverified.get("nonce") != nonce:
        raise HTTPException(status_code=400, detail="nonce 校验失败")
    if cfg.issuer and unverified.get("iss") != cfg.issuer:
        raise HTTPException(status_code=400, detail="ID Token 签发方不匹配")
    if cfg.client_id and unverified.get("aud") != cfg.client_id and cfg.client_id not in (unverified.get("aud") or []):
        raise HTTPException(status_code=400, detail="ID Token 受众不匹配")
    exp = unverified.get("exp")
    if exp and exp < int(time.time()):
        raise HTTPException(status_code=400, detail="ID Token 已过期")
    header = jwt.get_unverified_header(id_token)
    alg = header.get("alg", "")
    try:
        if alg.startswith("HS"):
            secret = decrypt_secret(cfg.client_secret_encrypted)
            claims = jwt.decode(id_token, secret, algorithms=[alg], audience=cfg.client_id, issuer=cfg.issuer)
        else:
            keys = await _fetch_jwks(cfg)
            claims = jwt.decode(id_token, keys[0], algorithms=[alg], audience=cfg.client_id, issuer=cfg.issuer)
    except (JWTError, JWSError, KeyError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"ID Token 校验失败：{e}")
    return claims


async def _fetch_jwks(cfg: SsoConfig) -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(cfg.jwks_uri)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"JWKS 获取失败（{r.status_code}）")
    return [jwk.construct(k) for k in r.json().get("keys", [])]


# ---------- claims 映射（确定性优先） ----------
CLAIM_MAP = {
    "employee_no": ["employee_no", "employee_number", "staff_id", "staff_no", "work_no", "job_number"],
    "position": ["position", "title", "job_title", "role", "designation"],
    "org_path": ["org_path", "org", "organization", "department_path", "org_unit", "ou"],
    "mobile": ["mobile", "phone", "phone_number", "telephone", "mobile_phone"],
    "gender": ["gender", "sex"],
    "birth_date": ["birth_date", "birthday", "dob", "date_of_birth"],
    "join_date": ["join_date", "hire_date", "hireday", "onboard_date", "entry_date"],
    "manager": ["manager", "manager_name", "leader", "supervisor", "reports_to"],
    "location": ["location", "office", "workplace", "base", "city"],
    "employee_type": ["employee_type", "emp_type", "employment_type", "staff_type"],
    "job_level": ["job_level", "level", "grade", "rank", "job_grade"],
    "cost_center": ["cost_center", "costcentre", "cost_code"],
}


def _claim(claims: dict, keys: list[str]) -> str | None:
    for k in keys:
        v = claims.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()
    return None


def _extract_deterministic(claims: dict) -> dict:
    out = {}
    for field, keys in CLAIM_MAP.items():
        v = _claim(claims, keys)
        if v:
            out[field] = v
    return out


async def provision_or_bind(db: AsyncSession, cfg: SsoConfig, claims: dict, id_claims: dict) -> User:
    """绑定已有账号或自动开通新账号（免注册）。返回 User。"""
    sub = str(id_claims.get(cfg.claim_sub) or claims.get(cfg.claim_sub) or "")
    email = str(id_claims.get(cfg.claim_email) or claims.get(cfg.claim_email) or "").lower()
    name = str(id_claims.get(cfg.claim_name) or claims.get(cfg.claim_name) or "").strip()

    user: User | None = None
    if cfg.bind_rule == "email" and email:
        user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    elif cfg.bind_rule == "sub" and sub:
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.sso_sub == sub))
        if ep:
            user = await db.get(User, ep.user_id)
    if not user and cfg.auto_provision:
        if not email:
            email = f"sso-{hashlib.sha256(sub.encode()).hexdigest()[:12]}@sso.local"
        user = User(
            email=email,
            name=name or f"员工 {sub[:8]}",
            password_hash=None,  # SSO 账号无本地密码，可后续自行设置
            account_type="human",
            role="member",
            department=None,
            org_id=None,
            status="active",
        )
        db.add(user)
        await db.flush()
    if not user:
        raise HTTPException(status_code=403, detail="该企业账号未匹配到社区账号，且未开启自动开通")

    # 员工扩展信息 upsert（不覆盖用户已编辑的非空值）
    ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user.id))
    if not ep:
        ep = EmployeeProfile(user_id=user.id)
        db.add(ep)
    if sub:
        ep.sso_sub = sub
    mapped = _extract_deterministic({**id_claims, **claims})
    for field, val in mapped.items():
        if val and not getattr(ep, field):
            setattr(ep, field, val)
    ep.raw_claims = {**id_claims, **claims}
    ep.source = "sso"
    extras = {k: v for k, v in {**id_claims, **claims}.items() if not isinstance(v, (dict, list)) and k not in CLAIM_MAP and k not in ("aud", "exp", "iat", "iss", "sub", "nonce", "jti", "at_hash", "auth_time", "sid")}
    if extras:
        ep.extras = extras
    await db.commit()
    await db.refresh(user)
    return user


async def extract_employee_with_llm(db: AsyncSession, user_id: int, claims: dict) -> None:
    """LLM 按事实抽取员工扩展信息（JSON mode）：只从原文提取、没有留空、杜绝猜测。失败静默。"""
    from app.services.llm_service import call_llm_json

    try:
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
        if not ep:
            ep = EmployeeProfile(user_id=user_id)
            db.add(ep)
        prompt = (
            "你是企业员工信息抽取助手。请从下面的 SSO 用户信息原文中，提取以下字段："
            "employee_no, position, org_path, mobile, gender, birth_date, join_date, manager, location, employee_type, job_level, cost_center。\n"
            "规则：1) 只从原文提取，原文没有的字段输出 null；2) 绝不猜测、编造或推理（如根据名字猜性别）；3) 保留原文值不要翻译。\n"
            f"原文（JSON）：{json.dumps(claims, ensure_ascii=False, default=str)[:8000]}"
        )
        result = await call_llm_json(prompt)
        if not isinstance(result, dict):
            return
        mapped = _extract_deterministic(claims)
        for field, val in result.items():
            if field in CLAIM_MAP and isinstance(val, str) and val.strip() and not getattr(ep, field) and field not in mapped:
                setattr(ep, field, val.strip())
        ep.source = ep.source if ep.source == "sso" else "llm"
        if ep.source == "sso":
            ep.source = "sso"
        await db.commit()
    except Exception as e:  # noqa: BLE001 失败静默，不影响登录
        logger.warning("extract_employee_with_llm failed: %s", e)
        await db.rollback()
