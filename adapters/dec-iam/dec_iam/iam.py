import ssl

import httpx

from .config import Settings


class IamError(Exception):
    """No upstream error text, URLs, tokens or personal data in exception messages."""


def map_identity(data: dict) -> dict:
    roles = data.get("spRoleList")
    if not isinstance(roles, list) or len(roles) != 1 or not isinstance(roles[0], str) or not roles[0].strip():
        raise IamError("IAM account must have exactly one application identity")
    if roles[0] != roles[0].strip() or len(roles[0]) > 255:
        raise IamError("Invalid application identity")
    claims = {"sub": roles[0]}
    for target, candidates in {
        "name": ("displayName", "fullName", "loginName"),
        "preferred_username": ("loginName",),
        "employee_no": ("employeeNumber", "loginName"),
        "org_path": ("orgNamePath",),
    }.items():
        for key in candidates:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                claims[target] = value.strip()[:500]
                break
    return claims


class IamClient:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.transport = transport

    async def authenticate(self, code: str) -> dict:
        cfg = self.settings
        verify = ssl.create_default_context(cafile=str(cfg.iam_ca_file)) if cfg.iam_ca_file else True
        try:
            async with httpx.AsyncClient(transport=self.transport, verify=verify, timeout=15, follow_redirects=False, trust_env=False) as client:
                parameters = dict(client_id=cfg.iam_client_id, client_secret=cfg.iam_client_secret.get_secret_value(),
                                  grant_type="authorization_code", code=code)
                kwargs = {"params" if cfg.iam_token_parameters == "query" else "data": parameters}
                token_response = await client.post(cfg.iam_base_url + "/idp/oauth2/getToken", **kwargs)
                token = self._object(token_response)
                access = token.get("access_token")
                if not isinstance(access, str) or not access:
                    raise IamError("IAM did not return an access token")
                user_response = await client.get(cfg.iam_base_url + "/idp/oauth2/getUserInfo",
                                                params={"access_token": access, "client_id": cfg.iam_client_id})
                user = self._object(user_response)
                if token.get("uid") and user.get("uid") and token["uid"] != user["uid"]:
                    raise IamError("IAM user identity mismatch")
                return map_identity(user)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise IamError("IAM request failed") from None

    @staticmethod
    def _object(response):
        if response.status_code != 200:
            raise IamError("IAM returned an unexpected HTTP status")
        data = response.json()
        if not isinstance(data, dict) or data.get("errcode") not in (None, 0, "0"):
            raise IamError("IAM rejected the request")
        return data
