import asyncio
import base64
import hashlib
import tempfile
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from dec_iam.app import create_app
from dec_iam.config import Settings
from dec_iam.store import Store


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        path = Path(self.temp.name) / "signing.pem"
        path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        self.cfg = Settings(
            _env_file=None, issuer="https://sso.example", community_url="https://community.example",
            iam_base_url="https://iam.example", iam_client_id="iam-app", iam_client_secret="upstream-secret",
            client_secret="downstream-secret-with-at-least-32-characters", signing_key_file=path,
        )
        self.redis = fakeredis.aioredis.FakeRedis()
        self.store = Store(self.redis)
        self.requests = []
        self.user = {"uid": "person-1", "spRoleList": ["app-account-42"], "displayName": "张三",
                     "loginName": "100390", "orgNamePath": "/集团/研发", "mail": None, "otpKey": "never-forward"}
        self.token_body = {"access_token": "iam-access-secret", "uid": "person-1", "expires_in": "1500"}
        self.iam_status = 200
        self.app = create_app(self.cfg, store=self.store, iam_transport=httpx.MockTransport(self.iam))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=self.cfg.issuer, follow_redirects=False)
        self.addAsyncCleanup(self.client.aclose)
        self.addAsyncCleanup(self.redis.aclose)
        self.verifier = "a" * 64
        self.challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()

    def iam(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/getToken"):
            return httpx.Response(self.iam_status, json=self.token_body)
        if request.url.path.endswith("/getUserInfo"):
            return httpx.Response(self.iam_status, json=self.user)
        raise AssertionError(f"Unexpected IAM path: {request.url.path}")

    async def authorize(self, **changes):
        params = dict(client_id=self.cfg.client_id, redirect_uri=self.cfg.redirect_uri, response_type="code",
                      scope="openid profile", state="community-state", nonce="community-nonce",
                      code_challenge=self.challenge, code_challenge_method="S256")
        params.update(changes)
        return await self.client.get("/authorize", params=params)

    async def callback(self):
        auth = await self.authorize()
        self.assertEqual(auth.status_code, 302, auth.text)
        params = parse_qs(urlsplit(auth.headers["location"]).query)
        self.assertEqual(params["client_id"], ["iam-app"])
        self.assertEqual(params["redirect_uri"], ["https://sso.example/iam/callback"])
        self.iam_state = params["state"][0]
        return await self.client.get("/iam/callback", params={"code": "iam-code", "state": self.iam_state})

    async def authorization_code(self):
        response = await self.callback()
        self.assertEqual(response.status_code, 302, response.text)
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["state"], ["community-state"])
        self.assertNotIn("error", query)
        return query["code"][0]

    async def exchange(self, code, **changes):
        data = dict(grant_type="authorization_code", code=code, client_id=self.cfg.client_id,
                    client_secret=self.cfg.client_secret.get_secret_value(), redirect_uri=self.cfg.redirect_uri,
                    code_verifier=self.verifier)
        data.update(changes)
        return await self.client.post("/token", data=data)

    async def test_complete_flow_uses_word_protocol_and_verifiable_oidc_tokens(self):
        response = await self.exchange(await self.authorization_code())
        self.assertEqual(response.status_code, 200, response.text)
        tokens = response.json()
        jwks = (await self.client.get("/jwks")).json()
        public_key = jwt.PyJWK.from_dict(jwks["keys"][0]).key
        claims = jwt.decode(tokens["id_token"], public_key, algorithms=["RS256"], audience="community", issuer=self.cfg.issuer)
        self.assertEqual(claims["sub"], "app-account-42")
        self.assertEqual(claims["nonce"], "community-nonce")
        self.assertEqual(claims["name"], "张三")
        self.assertNotIn("email", claims)
        self.assertNotIn("otpKey", claims)
        self.assertNotIn("role", claims)
        info = await self.client.get("/userinfo", headers={"Authorization": "Bearer " + tokens["access_token"]})
        self.assertEqual(info.json()["sub"], claims["sub"])
        self.assertEqual(self.requests[0].method, "POST")
        self.assertEqual(dict(self.requests[0].url.params), {"client_id": "iam-app", "client_secret": "upstream-secret", "grant_type": "authorization_code", "code": "iam-code"})
        self.assertEqual(dict(self.requests[1].url.params), {"access_token": "iam-access-secret", "client_id": "iam-app"})
        self.assertNotIn("iam-access-secret", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_discovery_and_health(self):
        meta = (await self.client.get("/.well-known/openid-configuration")).json()
        self.assertEqual(meta["issuer"], self.cfg.issuer)
        self.assertEqual(meta["token_endpoint"], self.cfg.issuer + "/token")
        self.assertEqual(meta["code_challenge_methods_supported"], ["S256"])
        self.assertEqual(meta["grant_types_supported"], ["authorization_code"])
        self.assertEqual((await self.client.get("/health")).status_code, 200)

    async def test_invalid_authorization_parameters_never_redirect(self):
        for changes in ({"client_id": "other"}, {"redirect_uri": "https://evil.example"},
                        {"redirect_uri": self.cfg.redirect_uri + "/extra"}, {"scope": "profile"},
                        {"code_challenge_method": "plain"}, {"code_challenge": "bad"}, {"response_type": "token"}):
            with self.subTest(changes=changes):
                response = await self.authorize(**changes)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("location", response.headers)
        self.assertEqual(self.requests, [])

    async def test_empty_multiple_and_malformed_roles_are_denied(self):
        for value in ([], ["one", "two"], [""], [12], "one", None):
            with self.subTest(value=value):
                self.user["spRoleList"] = value
                response = await self.callback()
                params = parse_qs(urlsplit(response.headers["location"]).query)
                self.assertEqual(params["error"], ["access_denied"])
                self.assertNotIn("code", params)

    async def test_missing_or_wrong_browser_cookie_is_rejected(self):
        response = await self.authorize()
        state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        self.client.cookies.clear()
        result = await self.client.get("/iam/callback", params={"code": "x", "state": state})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.requests, [])

    async def test_state_replay_is_rejected(self):
        await self.authorization_code()
        result = await self.client.get("/iam/callback", params={"code": "x", "state": self.iam_state})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(len(self.requests), 2)

    async def test_code_is_consumed_atomically(self):
        code = await self.authorization_code()
        responses = await asyncio.gather(self.exchange(code), self.exchange(code))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 400])

    async def test_token_rejects_wrong_verifier_redirect_client_and_grant(self):
        for changes, status in (({"code_verifier": "b" * 64}, 400), ({"redirect_uri": "https://evil.example"}, 400),
                                ({"client_secret": "wrong"}, 401), ({"client_id": "other"}, 401),
                                ({"grant_type": "password"}, 400)):
            with self.subTest(changes=changes):
                result = await self.exchange(await self.authorization_code(), **changes)
                self.assertEqual(result.status_code, status)
                self.assertNotIn("id_token", result.json())

    async def test_iam_business_error_is_not_success_and_does_not_leak_message(self):
        self.token_body = {"errcode": "1005", "msg": "private details and upstream-secret"}
        response = await self.callback()
        self.assertIn("error=access_denied", response.headers["location"])
        self.assertNotIn("private", response.text + str(response.headers))

    async def test_non_object_userinfo_is_rejected(self):
        self.user = []
        response = await self.callback()
        self.assertIn("error=access_denied", response.headers["location"])

    async def test_expired_state_code_and_access_token_are_rejected(self):
        auth = await self.authorize()
        state = parse_qs(urlsplit(auth.headers["location"]).query)["state"][0]
        await self.redis.flushall()
        self.assertEqual((await self.client.get("/iam/callback", params={"code": "x", "state": state})).status_code, 400)
        code = await self.authorization_code()
        await self.redis.flushall()
        self.assertEqual((await self.exchange(code)).status_code, 400)
        response = await self.exchange(await self.authorization_code())
        await self.redis.flushall()
        self.assertEqual((await self.client.get("/userinfo", headers={"Authorization": "Bearer " + response.json()["access_token"]})).status_code, 401)

    async def test_logout_uses_document_parameter_spelling_and_fixed_destination(self):
        result = await self.client.get("/logout", params={"redirect_uri": "https://evil.example"})
        location = urlsplit(result.headers["location"])
        self.assertEqual(location.path, "/idp/profile/OAUTH2/Redirect/GLO")
        self.assertEqual(parse_qs(location.query), {"redirctToUrl": ["https://community.example/login"], "redirectToLogin": ["true"], "entityId": ["iam-app"]})

    async def test_form_mode_has_no_client_secret_in_token_url(self):
        self.cfg.iam_token_parameters = "form"
        await self.authorization_code()
        request = self.requests[0]
        self.assertEqual(str(request.url), "https://iam.example/idp/oauth2/getToken")
        self.assertEqual(parse_qs(request.content.decode())["client_secret"], ["upstream-secret"])

    async def test_upstream_redirect_and_timeout_are_denied(self):
        self.iam_status = 302
        response = await self.callback()
        self.assertIn("error=access_denied", response.headers["location"])
        self.assertEqual(len(self.requests), 1)
        def timeout(request):
            raise httpx.ReadTimeout("sensitive query upstream-secret", request=request)
        other_app = create_app(self.cfg, store=self.store, iam_transport=httpx.MockTransport(timeout))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=other_app), base_url=self.cfg.issuer) as client:
            previous = self.client
            self.client = client
            try:
                with self.assertLogs("dec_iam.app", level="WARNING") as logs:
                    response = await self.callback()
                self.assertIn("error=access_denied", response.headers["location"])
                self.assertNotIn("upstream-secret", " ".join(logs.output))
            finally:
                self.client = previous

    async def test_transient_record_has_bounded_lifetime(self):
        response = await self.authorize()
        state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        ttl = await self.redis.ttl(self.store.key("state", state))
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 600)
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])

    async def test_real_community_oidc_client_accepts_adapter_discovery_and_signature(self):
        # Exercise both projects together, replacing only HTTP transport and IAM.
        api_path = str(Path(__file__).resolve().parents[3] / "apps/api")
        sys.path.insert(0, api_path)
        self.addCleanup(lambda: sys.path.remove(api_path))
        from app.services import sso_service
        token = (await self.exchange(await self.authorization_code())).json()["id_token"]
        cfg = SimpleNamespace(issuer=self.cfg.issuer, client_id="community", authorization_endpoint="",
                              token_endpoint="", userinfo_endpoint="", jwks_uri=self.cfg.issuer + "/jwks")
        real_client = httpx.AsyncClient
        def local_client(**kwargs):
            return real_client(transport=httpx.ASGITransport(app=self.app), **kwargs)
        with patch.object(sso_service.httpx, "AsyncClient", side_effect=local_client), patch.object(sso_service, "is_safe_sso_url", return_value=(True, "")):
            endpoints = await sso_service.resolve_endpoints(cfg)
            self.assertEqual(endpoints["token_endpoint"], "https://sso.example/token")
            claims = await sso_service.verify_id_token(cfg, token, "community-nonce")
            self.assertEqual(claims["sub"], "app-account-42")
            self.assertTrue((await sso_service.test_connection(cfg))["ok"])


if __name__ == "__main__":
    unittest.main()
