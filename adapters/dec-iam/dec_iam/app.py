import base64
import hashlib
import json
import logging
import re
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import jwt
import redis.asyncio as aioredis
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .config import Settings
from .iam import IamClient, IamError
from .store import Store

logger = logging.getLogger(__name__)


def create_app(settings=None, *, store=None, iam_transport=None):
    cfg = settings or Settings()
    # httpx INFO logs include request query parameters containing IAM credentials.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    key = serialization.load_pem_private_key(cfg.signing_key_file.read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("Signing key must be RSA with at least 2048 bits")
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    kid = hashlib.sha256(json.dumps(jwk, sort_keys=True).encode()).hexdigest()[:24]
    jwk.update(kid=kid, use="sig", alg="RS256")
    owned_redis = None if store else aioredis.from_url(cfg.redis_url.get_secret_value())
    records = store or Store(owned_redis)
    iam = IamClient(cfg, iam_transport)

    @asynccontextmanager
    async def lifespan(app):
        try:
            await records.redis.ping()
            yield
        finally:
            if owned_redis is not None:
                await owned_redis.aclose()

    app = FastAPI(title="东方电气 IAM 适配服务", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def secure_responses(request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("Adapter request failed (%s)", type(exc).__name__)
            response = JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
        response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache",
                                 "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"})
        return response

    def error(name="invalid_request", status=400):
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return JSONResponse({"error": name}, status_code=status, headers=headers)

    @app.get("/health")
    async def health():
        await records.redis.ping()
        return {"status": "ok"}

    @app.get("/.well-known/openid-configuration")
    async def discovery():
        return {
            "issuer": cfg.issuer,
            "authorization_endpoint": cfg.issuer + "/authorize",
            "token_endpoint": cfg.issuer + "/token",
            "userinfo_endpoint": cfg.issuer + "/userinfo",
            "jwks_uri": cfg.issuer + "/jwks",
            "response_types_supported": ["code"], "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"], "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "code_challenge_methods_supported": ["S256"],
            "claims_supported": ["sub", "iss", "aud", "iat", "exp", "nonce", "name", "preferred_username", "employee_no", "org_path"],
        }

    @app.get("/jwks")
    async def jwks():
        return {"keys": [jwk]}

    @app.get("/authorize")
    async def authorize(request: Request):
        p = request.query_params
        if (len(p) != len(p.multi_items()) or p.get("client_id") != cfg.client_id
                or p.get("redirect_uri") != cfg.redirect_uri or p.get("response_type") != "code"
                or "openid" not in p.get("scope", "").split()
                or set(p.get("scope", "").split()) - {"openid", "profile", "email"}
                or p.get("code_challenge_method") != "S256"
                or not re.fullmatch(r"[A-Za-z0-9_-]{43}", p.get("code_challenge", ""))
                or not 1 <= len(p.get("state", "")) <= 512 or len(p.get("nonce", "")) > 512):
            return error()
        state = secrets.token_urlsafe(32)
        browser = secrets.token_urlsafe(32)
        await records.put("state", state, {"state": p["state"], "nonce": p.get("nonce", ""),
                          "scope": p["scope"], "challenge": p["code_challenge"], "browser": browser}, cfg.state_ttl)
        response = RedirectResponse(cfg.iam_base_url + "/idp/oauth2/authorize?" + urlencode({
            "client_id": cfg.iam_client_id, "redirect_uri": cfg.iam_callback_uri, "response_type": "code", "state": state,
        }), status_code=302)
        response.set_cookie("dec_auth_" + state[:16], browser, max_age=cfg.state_ttl,
                            path="/iam/callback", secure=not cfg.allow_http, httponly=True, samesite="lax")
        return response

    @app.get("/iam/callback")
    async def callback(request: Request):
        p = request.query_params
        state = p.get("state", "")
        if len(p) != len(p.multi_items()) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", state):
            return error()
        saved = await records.pop("state", state)
        if not saved or not secrets.compare_digest(saved["browser"], request.cookies.get("dec_auth_" + state[:16], "")):
            return error()
        result = {"state": saved["state"]}
        try:
            if p.get("error") or not 1 <= len(p.get("code", "")) <= 2048:
                raise IamError("IAM authorization failed")
            claims = await iam.authenticate(p["code"])
            code = secrets.token_urlsafe(32)
            await records.put("code", code, {"claims": claims, "nonce": saved["nonce"],
                              "scope": saved["scope"], "challenge": saved["challenge"]}, cfg.code_ttl)
            result["code"] = code
        except IamError:
            logger.warning("IAM login denied")
            result.update(error="access_denied", error_description="IAM authentication or application permission denied")
        response = RedirectResponse(cfg.redirect_uri + "?" + urlencode(result), status_code=302)
        response.delete_cookie("dec_auth_" + state[:16], path="/iam/callback", secure=not cfg.allow_http, httponly=True, samesite="lax")
        return response

    @app.post("/token")
    async def token(request: Request):
        if len(await request.body()) > 16384:
            return error()
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return error()
        p = await request.form()
        if len(p) != len(p.multi_items()):
            return error()
        if (p.get("client_id") != cfg.client_id
                or not secrets.compare_digest(str(p.get("client_secret", "")), cfg.client_secret.get_secret_value())):
            return error("invalid_client", 401)
        if p.get("grant_type") != "authorization_code":
            return error("unsupported_grant_type")
        if p.get("redirect_uri") != cfg.redirect_uri:
            return error("invalid_grant")
        verifier = str(p.get("code_verifier", ""))
        if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
            return error("invalid_grant")
        code = str(p.get("code", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", code):
            return error("invalid_grant")
        saved = await records.pop("code", code)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if not saved or not secrets.compare_digest(challenge, saved["challenge"]):
            return error("invalid_grant")
        claims = saved["claims"] if "profile" in saved["scope"].split() else {"sub": saved["claims"]["sub"]}
        now = int(time.time())
        payload = {**claims, "iss": cfg.issuer, "aud": cfg.client_id, "iat": now, "exp": now + cfg.token_ttl}
        if saved["nonce"]:
            payload["nonce"] = saved["nonce"]
        access = secrets.token_urlsafe(32)
        await records.put("access", access, claims, cfg.token_ttl)
        return {"access_token": access, "token_type": "Bearer", "expires_in": cfg.token_ttl,
                "scope": saved["scope"], "id_token": jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})}

    @app.get("/userinfo")
    async def userinfo(request: Request):
        parts = request.headers.get("authorization", "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not re.fullmatch(r"[A-Za-z0-9_-]{43}", parts[1]):
            return error("invalid_token", 401)
        claims = await records.get("access", parts[1])
        return claims if claims else error("invalid_token", 401)

    @app.get("/logout")
    async def logout():
        return RedirectResponse(cfg.iam_base_url + "/idp/profile/OAUTH2/Redirect/GLO?" + urlencode({
            "redirctToUrl": cfg.community_url + "/login", "redirectToLogin": "true", "entityId": cfg.iam_client_id,
        }), status_code=302)

    return app
