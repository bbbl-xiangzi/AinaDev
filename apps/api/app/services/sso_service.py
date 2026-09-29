"""SSO（企业统一身份登录）OIDC 服务。

标准 OIDC 授权码 + PKCE 流程（社区 = SP，企业客户应用中台 = IDP）：
  1) /api/auth/sso/login  → 生成 state + PKCE verifier，302 跳转 IDP 授权页
  2) IDP 回调 /api/auth/sso/callback?code=&state= → 用 verifier 换 token
  3) 验签 id_token（JWKS，支持 RS256/ES256/HS256）→ 取 userinfo → 合并 claims
  4) 自动开通/绑定社区账号（免注册）→ 员工扩展信息确定性映射 + LLM 按事实抽取（杜绝猜测）
  5) 签发社区 JWT

安全：state 防 CSRF、PKCE 防授权码拦截、JWKS 验签防伪造 token、
SSRF 防护（出站请求复用 net_safety 校验）、client_secret AES 加密存储。
"""
import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.net_safety import is_safe_url
from app.core.security import aes_decrypt, aes_encrypt
from app.models import EmployeeProfile, SsoConfig, User

logger = logging.getLogger(__name__)

# OIDC 端点发现（.well-known）
WELL_KNOWN = "/.well-known/openid-configuration"
STATE_TTL = 600  # state 缓存有效期（秒）
STATE_PREFIX = "sso:auth:state:"

# 确定性映射：目标字段 → 候选 claim 名（按优先级，取首个非空字符串）
CLAIM_MAP: dict[str, list[str]] = {
    "sso_sub": ["sub"],
    "email": ["email", "mail", "user_email", "upn"],
    "name": ["name", "preferred_username", "display_name", "nickname"],
    "department": ["department", "dept", "department_name", "division"],
    "position": ["position", "title", "job_title", "designation"],
    "employee_no": ["employee_no", "employeeNumber", "employee_id", "emp_no", "staff_no", "staff_id"],
    "org_path": ["org_path", "organization_path", "organizationPath", "organization", "ou"],
    "mobile": ["mobile", "phone", "phone_number", "mobile_number", "telephone"],
    "gender": ["gender", "sex"],
    "birth_date": ["birthdate", "birth_date", "date_of_birth", "dob"],
    "join_date": ["join_date", "hire_date", "employment_date", "onboard_date", "hireDate"],
    "manager": ["manager", "supervisor", "direct_manager", "directManager"],
    "location": ["location", "office_location", "work_location", "city"],
    "employee_type": ["employee_type", "employment_type", "employeeType"],
    "job_level": ["job_level", "jobLevel", "level", "job_grade", "grade"],
    "cost_center": ["cost_center", "costCenter"],
    "org": ["org", "company", "organization_name", "company_name"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def redirect_uri() -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/auth/sso/callback"


# ---------- 配置读写 ----------
async def get_active_config(db: AsyncSession) -> SsoConfig | None:
    return await db.scalar(
        select(SsoConfig).where(SsoConfig.enabled.is_(True)).order_by(SsoConfig.id.desc()).limit(1)
    )


async def get_or_create_config(db: AsyncSession) -> SsoConfig:
    cfg = await db.scalar(select(SsoConfig).order_by(SsoConfig.id.asc()).limit(1))
    if cfg:
        return cfg
    cfg = SsoConfig()
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


def client_secret_of(cfg: SsoConfig) -> str:
    return aes_decrypt(cfg.client_secret_encrypted)


async def resolve_endpoints(cfg: SsoConfig) -> dict[str, str]:
    """优先显式配置的端点；否则从 issuer 自动发现。返回 {authorization,token,jwks,userinfo}。"""
    endpoints: dict[str, str] = {
        "authorization_endpoint": (cfg.authorization_endpoint or "").strip(),
        "token_endpoint": (cfg.token_endpoint or "").strip(),
        "jwks_uri": (cfg.jwks_uri or "").strip(),
        "userinfo_endpoint": (cfg.userinfo_endpoint or "").strip(),
    }
    if cfg.issuer:
        issuer = cfg.issuer.strip().rstrip("/")
        if not issuer.startswith(("http://", "https://")):
            raise ValueError("Issuer URL 必须以 http(s):// 开头")
        ok, reason = is_safe_url(issuer)
        if not ok:
            raise ValueError(f"Issuer URL 不合法：{reason}")
        well_known = f"{issuer}{WELL_KNOWN}"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(well_known)
            resp.raise_for_status()
            meta = resp.json()
        for field, meta_key in [
            ("authorization_endpoint", "authorization_endpoint"),
            ("token_endpoint", "token_endpoint"),
            ("jwks_uri", "jwks_uri"),
            ("userinfo_endpoint", "userinfo_endpoint"),
        ]:
            if not endpoints[field]:
                endpoints[field] = str(meta.get(meta_key) or "").strip()
    missing = [k for k, v in endpoints.items() if not v]
    if missing:
        raise ValueError(f"缺少 OIDC 端点：{', '.join(missing)}（可填 Issuer 自动发现或显式填写）")
    return endpoints


async def test_connection(cfg: SsoConfig) -> dict[str, Any]:
    """后台「测试连接」：探测 discovery、端点可达、JWKS 可拉取。"""
    try:
        endpoints = await resolve_endpoints(cfg)
    except Exception as e:
        return {"ok": False, "message": f"发现端点失败：{e}"}
    checks: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for name, url in endpoints.items():
            try:
                ok, reason = is_safe_url(url)
                if not ok:
                    checks[name] = f"被 SSRF 防护拦截：{reason}"
                    continue
                resp = await client.get(url)
                checks[name] = f"HTTP {resp.status_code}" if resp.status_code < 400 else f"HTTP {resp.status_code}（异常）"
            except Exception as e:
                checks[name] = f"请求失败：{type(e).__name__}"
        # JWKS 内容可解析且含 keys
        jwks = await _fetch_jwks(client, endpoints["jwks_uri"])
        if jwks is None:
            checks["jwks_content"] = "无法拉取/解析 JWKS"
        else:
            keys = jwks.get("keys") or []
            algs = sorted({k.get("alg") for k in keys if k.get("alg")})
            checks["jwks_content"] = f"OK（{len(keys)} 个密钥，算法 {algs or '未知'}）"
    ok = all(v.startswith("HTTP 2") or v.startswith("OK") for v in checks.values())
    return {
        "ok": ok,
        "message": "连接正常，端点全部可达" if ok else "部分端点异常，请检查配置",
        "details": checks,
    }


async def _fetch_jwks(client: httpx.AsyncClient, jwks_uri: str) -> dict | None:
    ok, reason = is_safe_url(jwks_uri)
    if not ok:
        logger.warning("JWKS URL 被拦截：%s", reason)
        return None
    try:
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning("JWKS 拉取失败：%s", e)
        return None


# ---------- 授权流程 ----------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _new_state_record() -> tuple[str, str, str]:
    """返回 (state, verifier, nonce)。"""
    verifier = _b64url(secrets.token_bytes(48))
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(16)
    return state, verifier, nonce


def authorize_url_of(cfg: SsoConfig, endpoints: dict[str, str], state: str, verifier: str, nonce: str) -> str:
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri(),
        "scope": cfg.scopes or "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{endpoints['authorization_endpoint']}?{urlencode(params)}"


# ---------- 回调处理 ----------
async def exchange_token(cfg: SsoConfig, code: str, verifier: str) -> dict[str, Any]:
    """授权码换 token（client_secret + PKCE）。"""
    token_url = (cfg.token_endpoint or "").strip()
    if not token_url:
        endpoints = await resolve_endpoints(cfg)
        token_url = endpoints["token_endpoint"]
    ok, reason = is_safe_url(token_url)
    if not ok:
        raise ValueError(f"Token 端点被 SSRF 防护拦截：{reason}")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": cfg.client_id,
        "client_secret": client_secret_of(cfg),
        "code_verifier": verifier,
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.post(token_url, data=data)
        if resp.status_code >= 400:
            raise ValueError(f"换取令牌失败：HTTP {resp.status_code} {resp.text[:300]}")
        return resp.json()


async def fetch_userinfo(cfg: SsoConfig, access_token: str) -> dict[str, Any]:
    userinfo_url = (cfg.userinfo_endpoint or "").strip()
    if not userinfo_url:
        return {}
    ok, reason = is_safe_url(userinfo_url)
    if not ok:
        raise ValueError(f"UserInfo 端点被 SSRF 防护拦截：{reason}")
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code >= 400:
            logger.warning("userinfo 拉取失败：HTTP %s", resp.status_code)
            return {}
        return resp.json() if isinstance(resp.json(), dict) else {}


async def verify_id_token(cfg: SsoConfig, id_token: str, nonce: str | None) -> dict[str, Any]:
    """验签 id_token：JWKS（RS256/ES256）/ HS256，校验 iss/aud/exp/iat/nonce。"""
    unverified = jwt.decode(id_token, options={"verify_signature": False})
    headers = jwt.get_unverified_header(id_token)
    alg = headers.get("alg", "RS256")
    iss = unverified.get("iss", "")
    aud = unverified.get("aud")

    key: Any = None
    if alg in {"RS256", "ES256", "RS384", "ES384"}:
        jwks_uri = (cfg.jwks_uri or "").strip()
        if not jwks_uri:
            endpoints = await resolve_endpoints(cfg)
            jwks_uri = endpoints["jwks_uri"]
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            jwks = await _fetch_jwks(client, jwks_uri)
        if not jwks:
            raise ValueError("无法获取 IDP JWKS，验签失败")
        keys = jwks.get("keys") or []
        kid = headers.get("kid")
        chosen = next((k for k in keys if kid and k.get("kid") == kid), None)
        if chosen is None:
            chosen = next((k for k in keys if k.get("alg", alg) == alg), keys[0] if keys else None)
        if chosen is None:
            raise ValueError("JWKS 中没有可用密钥")
        if alg.startswith("RS"):
            key = jwt.algorithms.RSAAlgorithm.from_jwk(chosen)
        elif alg.startswith("ES"):
            key = jwt.algorithms.ECAlgorithm.from_jwk(chosen)
        else:
            raise ValueError(f"不支持的签名算法 {alg}")
        verify_algs = [alg]
    elif alg == "HS256":
        key = client_secret_of(cfg)
        verify_algs = ["HS256"]
    else:
        raise ValueError(f"不支持的签名算法 {alg}")

    options = {"verify_exp": True, "verify_iat": True, "verify_nbf": True}
    payload = jwt.decode(
        id_token,
        key=key,
        algorithms=verify_algs,
        audience=aud,
        issuer=iss,
        options=options,
    )
    if nonce and payload.get("nonce") != nonce:
        raise ValueError("nonce 校验失败（授权请求与回调不匹配）")
    return payload


def map_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """确定性映射：标准/常见 claim → 社区字段。只取原文有的，缺失留空。"""
    out: dict[str, Any] = {}
    for target, candidates in CLAIM_MAP.items():
        for c in candidates:
            val = claims.get(c)
            if isinstance(val, str) and val.strip():
                out[target] = val.strip()
                break
            if isinstance(val, (int, float)) and target in {"employee_no", "mobile"}:
                out[target] = str(val)
                break
    return out


# ---------- 账号开通 / 绑定 ----------
async def provision_or_bind(db: AsyncSession, cfg: SsoConfig, claims: dict[str, Any], mapped: dict[str, Any]) -> User:
    """按绑定规则找到或自动开通账号；写入 employee_profiles（raw_claims 全量存档）。"""
    sub = mapped.get("sso_sub") or claims.get(cfg.claim_sub or "sub")
    email = mapped.get("email") or claims.get(cfg.claim_email or "email")
    name = mapped.get("name") or claims.get(cfg.claim_name or "name") or "企业用户"
    email = (email or "").strip().lower()

    user: User | None = None
    if cfg.bind_rule == "sub" and sub:
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.sso_sub == str(sub)))
        if ep:
            user = await db.get(User, ep.user_id)
    if user is None and email:
        user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))

    if user is None:
        if not cfg.auto_provision:
            raise ValueError("社区未开通该账号且未开启自动开通，请联系管理员")
        # 无邮箱时用 sub 哈希生成占位邮箱保证唯一
        if not email:
            digest = hashlib.sha256(str(sub).encode()).hexdigest()[:12]
            email = f"sso-{digest}@sso.local"
        existing = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
        if existing:
            raise ValueError(f"邮箱 {email} 已注册但无法匹配 SSO 身份（绑定规则不匹配），请联系管理员处理")
        user = User(
            email=email,
            name=name[:100],
            account_type="human",
            role="member",
            status="active",
            password_hash=None,  # SSO 用户无本地密码
            department=(mapped.get("department") or None),
            org_id=(mapped.get("org") or None),
        )
        db.add(user)
        await db.flush()

    if user.deleted_at is not None:
        raise ValueError("账号已被删除，请联系管理员")
    if user.status == "disabled":
        raise ValueError("账号已被禁用，请联系管理员")
    if user.account_type != "human":
        raise ValueError("该身份与社区账号类型不匹配，请联系管理员")

    # 补充基本信息（SSO 优先，不覆盖用户已自行修改的非空值）
    if not user.name and name:
        user.name = name[:100]
    if not user.department and mapped.get("department"):
        user.department = mapped["department"][:100]
    if not user.org_id and mapped.get("org"):
        user.org_id = mapped["org"][:100]
    user.last_active_at = _utcnow()
    await db.flush()

    # 员工扩展信息 upsert
    ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user.id))
    if ep is None:
        ep = EmployeeProfile(user_id=user.id)
        db.add(ep)
    if sub:
        ep.sso_sub = str(sub)
    for field in [
        "employee_no", "position", "org_path", "mobile", "gender", "birth_date",
        "join_date", "manager", "location", "employee_type", "job_level", "cost_center",
    ]:
        val = mapped.get(field)
        if val and not getattr(ep, field):
            setattr(ep, field, str(val)[: (500 if field == "org_path" else 100)])
    ep.raw_claims = dict(claims)
    ep.source = "sso"
    await db.commit()
    await db.refresh(user)
    return user


async def extract_employee_with_llm(db: AsyncSession, user_id: int, claims: dict[str, Any]) -> None:
    """LLM 按事实抽取员工扩展信息（三约束：只依据原文、没有留空、杜绝猜测）。

    异步任务（worker）执行；失败静默（raw_claims 已存档，不影响登录）。
    """
    try:
        from app.services.model_service import get_default_llm_config
        from app.services.llm import chat_with_json

        cfg = await get_default_llm_config(db)
        prompt = (
            "你是企业身份数据抽取助手。下面 JSON 是从企业统一身份认证(SSO)返回的员工原始信息 claims，"
            "字段名可能各家不同。请严格依据原文，抽取以下字段：\n"
            "employee_no(工号)、position(职位)、org_path(组织架构路径)、mobile(手机号)、gender(性别)、"
            "birth_date(出生日期)、join_date(入职日期)、manager(直属上级)、location(办公地点)、"
            "employee_type(员工类型)、job_level(职级)、cost_center(成本中心)、department(部门)。\n"
            "硬性要求：\n"
            "1. 只从给定 JSON 中提取明确出现的信息，原文没有的字段一律输出 null；\n"
            "2. 严禁猜测、推断、拼接或编造任何值；\n"
            "3. 输出严格 JSON 对象：{\"employee_no\": ...|\"department\": ...}，只含上述字段，值为字符串或 null。\n"
            f"原始 claims JSON：\n{json.dumps(claims, ensure_ascii=False)}\n"
        )
        raw = await chat_with_json(cfg, prompt, "请按上述要求输出 JSON。")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
        if ep is None:
            return
        changed = False
        for field in [
            "employee_no", "position", "org_path", "mobile", "gender", "birth_date",
            "join_date", "manager", "location", "employee_type", "job_level", "cost_center", "department",
        ]:
            val = parsed.get(field)
            if isinstance(val, str) and val.strip() and not getattr(ep, field):
                setattr(ep, field, val.strip()[: (500 if field == "org_path" else 100)])
                changed = True
        if changed:
            await db.commit()
    except Exception as e:
        logger.warning("LLM 抽取员工信息失败（不影响登录）：%s", e)


def encrypt_secret(plain: str) -> str:
    return aes_encrypt(plain)
