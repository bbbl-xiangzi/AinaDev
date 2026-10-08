import json
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import httpx

from app.models import SsoConfig
from app.services import sso_service


class OAuthTests(unittest.IsolatedAsyncioTestCase):
    def cfg(self, **options):
        return SsoConfig(protocol="oauth2", client_id="test-client", scopes="", issuer=None,
            authorization_endpoint="https://iam.example/oauth/authorize",
            token_endpoint="https://iam.example/oauth/token",
            userinfo_endpoint="https://iam.example/oauth/userinfo?client_id=test-client",
            claim_sub="subject_ids", claim_name="displayName", claim_email="mail",
            oauth_options={"subject_mode": "single_array", **options})

    async def test_oauth_does_not_require_oidc_discovery_or_jwks(self):
        cfg = self.cfg()
        endpoints = await sso_service.resolve_endpoints(cfg)
        url = sso_service.authorize_url_of(cfg, endpoints, "state", "verifier", "nonce")
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["state"], ["state"])
        self.assertNotIn("nonce", params)
        self.assertNotIn("scope", params)
        self.assertNotIn("code_challenge", params)

    async def test_token_post_query_and_userinfo_get_query(self):
        cfg = self.cfg(token_mode="query", userinfo_mode="query")
        requests = []
        def handle(req):
            requests.append(req)
            return httpx.Response(200, json={"access_token":"upstream"} if "/token" in req.url.path
                                  else {"subject_ids":["person-1"], "displayName":"张三"})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.object(sso_service, "client_secret_of", return_value="test-secret"), \
             patch("app.services.oauth2_service.is_safe_sso_url", return_value=(True,"")), \
             patch("app.services.oauth2_service.httpx.AsyncClient", return_value=client):
            token = await sso_service.exchange_token(cfg,"code","verifier")
        self.assertEqual(requests[0].method,"POST")
        self.assertEqual(requests[0].url.params["client_secret"],"test-secret")
        self.assertNotIn("code_verifier", requests[0].url.params)
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch("app.services.oauth2_service.is_safe_sso_url", return_value=(True,"")), \
             patch("app.services.oauth2_service.httpx.AsyncClient", return_value=client):
            claims = await sso_service.fetch_userinfo(cfg,token["access_token"])
        self.assertEqual(requests[1].url.params["access_token"],"upstream")
        self.assertEqual(requests[1].url.params["client_id"],"test-client")
        normalized = sso_service.normalize_claims(cfg,claims)
        self.assertEqual(normalized["sub"],"person-1")
        self.assertEqual(normalized["name"],"张三")

    async def test_strict_array_and_configured_fields_take_precedence(self):
        cfg = self.cfg()
        for value in ([],["a","b"],[""],[" "],"a",None,[42]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sso_service.normalize_claims(cfg,{"subject_ids":value,"sub":"must-not-fallback"})
        result = sso_service.normalize_claims(cfg,{"subject_ids":["a"],"sub":"wrong","mail":"x@example.com","email":"wrong@example.com"})
        self.assertEqual(result["sub"],"a")
        self.assertEqual(result["email"],"x@example.com")

    async def test_custom_parameter_names_and_existing_query(self):
        cfg=self.cfg(authorize_params={"client_id":"app_id"})
        cfg.authorization_endpoint += "?tenant=one"
        endpoints=await sso_service.resolve_endpoints(cfg)
        params=parse_qs(urlsplit(sso_service.authorize_url_of(cfg,endpoints,"state","verifier","nonce")).query)
        self.assertEqual(params["tenant"],["one"])
        self.assertEqual(params["app_id"],["test-client"])
        self.assertNotIn("client_id",params)

    async def test_business_error_and_redirect_are_rejected_without_secrets(self):
        for response in (httpx.Response(200,json={"errcode":1,"message":"secret"}),
                         httpx.Response(302,headers={"location":"https://evil.example"}),
                         httpx.Response(200,json=["secret"])):
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:response))
            with patch.object(sso_service,"client_secret_of",return_value="test-secret"), \
                 patch("app.services.oauth2_service.is_safe_sso_url",return_value=(True,"")), \
                 patch("app.services.oauth2_service.httpx.AsyncClient",return_value=client), \
                 self.assertRaises(ValueError) as caught:
                await sso_service.exchange_token(self.cfg(),"code","verifier")
            self.assertNotIn("secret",str(caught.exception))

    async def test_invalid_parameter_collisions_rejected(self):
        from app.schemas.sso_options import OAuthOptions
        for opts in ({"authorize_params":{"client_id":"state"}},
                     {"token_params":{"grant_type":"code"}},
                     {"token_mode":"invalid"}, {"subject_mode":"guess"}):
            with self.subTest(opts=opts),self.assertRaises(ValueError):
                OAuthOptions(**opts)

    async def test_json_basic_and_custom_token_parameters(self):
        captured=[]
        def handle(req):
            captured.append(req)
            return httpx.Response(200,json={"access_token":"upstream"})
        cfg=self.cfg(token_method="PUT",token_mode="json",token_auth="basic",token_params={"code":"ticket"},pkce=True)
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.object(sso_service,"client_secret_of",return_value="test-secret"), \
             patch("app.services.oauth2_service.is_safe_sso_url",return_value=(True,"")), \
             patch("app.services.oauth2_service.httpx.AsyncClient",return_value=client):
            await sso_service.exchange_token(cfg,"abc","verifier")
        self.assertEqual(captured[0].method,"PUT")
        body=json.loads(captured[0].content)
        self.assertEqual(body["ticket"],"abc")
        self.assertEqual(body["code_verifier"],"verifier")
        self.assertNotIn("client_secret",body)
        self.assertTrue(captured[0].headers["authorization"].startswith("Basic "))

    async def test_nested_token_userinfo_and_sensitive_field_filter(self):
        from app.services.oauth2_service import userinfo_object
        cfg=self.cfg(subject_mode="string",userinfo_source="token",userinfo_path="data.user")
        cfg.claim_sub="uid"
        data=userinfo_object(cfg,{"access_token":"secret","data":{"user":{"uid":"stable","otpKey":"private","displayName":"Name"}}})
        normalized=sso_service.normalize_claims(cfg,data)
        self.assertEqual(normalized["sub"],"stable")
        self.assertNotIn("otpKey",normalized)
        self.assertNotIn("access_token",normalized)

    async def test_oidc_mapping_preserves_employee_fields(self):
        cfg=SimpleNamespace(protocol="oidc",claim_sub="uid",claim_name="displayName",claim_email="mail")
        mapped=sso_service.normalize_claims(cfg,{"sub":"original","uid":"stable","displayName":"Name","mail":"a@example.com","department":"IT"})
        self.assertEqual(mapped["sub"],"stable")
        self.assertEqual(mapped["name"],"Name")
        self.assertEqual(mapped["email"],"a@example.com")
        self.assertEqual(mapped["department"],"IT")
