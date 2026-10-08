"""Configurable OAuth2 authorization-code client; upstream responses are untrusted."""
import hashlib
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.schemas.sso_options import OAuthOptions


def options(cfg):
    return OAuthOptions.model_validate(getattr(cfg, "oauth_options", None) or {})


def is_safe_sso_url(url):
    from app.services.sso_service import is_safe_sso_url as check
    return check(url)


def checked_url(url):
    parsed = urlsplit(url or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("SSO 接口必须为不含凭据和 fragment 的 HTTPS 地址")
    ok, _ = is_safe_sso_url(url)
    if not ok:
        raise ValueError("SSO 接口被出站安全策略拦截；内网地址需配置 SSO_ALLOWED_HOSTS")
    return url


def with_query(url, params):
    parts = urlsplit(url)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    # Generated security parameters always win; never send duplicate state/code.
    pairs = [(key,value) for key,value in existing if key not in params]
    return urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(pairs+list(params.items())),""))


def renamed(values, names):
    return {names.get(key,key):value for key,value in values.items()}


def authorize_url(cfg, endpoints, state, verifier):
    from app.services.sso_service import _b64url, redirect_uri
    opt=options(cfg)
    params={"client_id":cfg.client_id,"redirect_uri":redirect_uri(),"response_type":"code","state":state}
    if cfg.scopes:
        params["scope"]=cfg.scopes
    if opt.pkce:
        params.update(code_challenge=_b64url(hashlib.sha256(verifier.encode("ascii")).digest()),code_challenge_method="S256")
    return with_query(checked_url(endpoints["authorization_endpoint"]),renamed(params,opt.authorize_params))


async def request_json(url, method, mode, values, *, auth=None):
    checked_url(url)
    # httpx logs entire request URLs at INFO; Query mode can carry IAM secrets.
    for name in ("httpx","httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    kwargs={"auth":auth}
    if mode=="query":
        url=with_query(url,values)
    elif mode=="bearer":
        kwargs["headers"]={"Authorization":"Bearer "+values["access_token"]}
    else:
        kwargs["data" if mode=="form" else "json"]=values
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            resp=await client.request(method,url,**kwargs)
        if not 200<=resp.status_code<300:
            raise ValueError("身份服务请求失败，请检查接口配置")
        data=resp.json()
        if not isinstance(data,dict) or data.get("error") or data.get("errcode") not in (None,0,"0"):
            raise ValueError("身份服务返回异常或拒绝授权")
        return data
    except (httpx.HTTPError,ValueError,TypeError):
        raise ValueError("身份服务返回异常，请联系管理员检查接口配置") from None


async def exchange(cfg, code, verifier):
    from app.services.sso_service import client_secret_of, redirect_uri
    opt=options(cfg)
    values={"client_id":cfg.client_id,"client_secret":client_secret_of(cfg),"code":code,
            "grant_type":"authorization_code","redirect_uri":redirect_uri()}
    auth=None
    if opt.token_auth=="basic":
        auth=httpx.BasicAuth(values.pop("client_id"),values.pop("client_secret"))
    if opt.pkce:
        values["code_verifier"]=verifier
    data=await request_json(cfg.token_endpoint,opt.token_method,opt.token_mode,renamed(values,opt.token_params),auth=auth)
    if not isinstance(data.get("access_token"),str) or not data["access_token"].strip():
        raise ValueError("身份服务未返回有效 access_token")
    return data


def field(data,path):
    for part in path.split(".") if path else []:
        if not isinstance(data,dict):
            return None
        data=data.get(part)
    return data


def userinfo_object(cfg,data):
    path=options(cfg).userinfo_path
    result=field(data,path) if path else data
    if not isinstance(result,dict) or not result:
        raise ValueError("用户信息为空或字段路径无效")
    return result


async def userinfo(cfg, access_token):
    opt=options(cfg)
    if not isinstance(access_token,str) or not access_token.strip():
        raise ValueError("缺少 access_token")
    values={"access_token" if opt.userinfo_mode=="bearer" else opt.access_token_param:access_token}
    data=await request_json(cfg.userinfo_endpoint,opt.userinfo_method,opt.userinfo_mode,values)
    return userinfo_object(cfg,data)


def normalize(cfg,claims):
    opt=options(cfg)
    sub=field(claims,cfg.claim_sub or "sub")
    if opt.subject_mode=="single_array":
        if not isinstance(sub,list) or len(sub)!=1:
            raise ValueError("账号标识必须包含且仅包含一个值，请联系管理员")
        sub=sub[0]
    if not isinstance(sub,str) or not sub.strip() or sub!=sub.strip() or len(sub)>255:
        raise ValueError("缺少有效的唯一账号标识，请联系管理员")
    def text(path):
        value=field(claims,path) if path else None
        return value.strip() if isinstance(value,str) else ""
    # Only explicitly mapped claims cross into provisioning/optional AI extraction.
    # Do not archive opaque tokens, OTP keys or the complete upstream response.
    return {"sub":sub,"name":text(cfg.claim_name),"email":text(cfg.claim_email),
            "preferred_username":text(opt.claim_username),"mobile":text(opt.claim_mobile)}
