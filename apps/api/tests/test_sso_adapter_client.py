import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt

from app.config import settings
from app.services import sso_service


class AdapterClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.secret = "only-for-test-secret-with-at-least-32-characters"
        self.cfg = SimpleNamespace(issuer="https://adapter.example", client_id="community")
        self.enterContext(patch.object(sso_service, "client_secret_of", return_value=self.secret))

    def token(self, **changes):
        claims = dict(iss="https://adapter.example", aud="community", sub="employee-1",
                      iat=int(time.time()), exp=int(time.time()) + 300, nonce="nonce")
        claims.update(changes)
        return jwt.encode(claims, self.secret, algorithm="HS256")

    async def test_correct_issuer_and_audience_pass(self):
        claims = await sso_service.verify_id_token(self.cfg, self.token(), "nonce")
        self.assertEqual(claims["sub"], "employee-1")

    async def test_token_from_wrong_issuer_or_for_other_client_is_rejected(self):
        for changes in ({"iss": "https://other.example"}, {"aud": "another-client"}, {"nonce": "wrong"}):
            with self.subTest(changes=changes), self.assertRaises((jwt.PyJWTError, ValueError)):
                await sso_service.verify_id_token(self.cfg, self.token(**changes), "nonce")

    async def test_missing_identity_or_expiry_is_rejected(self):
        claims = jwt.decode(self.token(), options={"verify_signature": False})
        for key in ("sub", "exp", "iss", "aud", "iat"):
            broken = {k: v for k, v in claims.items() if k != key}
            with self.subTest(key=key), self.assertRaises((jwt.PyJWTError, ValueError)):
                await sso_service.verify_id_token(self.cfg, jwt.encode(broken, self.secret, algorithm="HS256"), "nonce")

    def test_private_sso_allowlist_is_exact_and_does_not_change_global_policy(self):
        with patch.object(settings, "sso_allowed_hosts", "adapter.internal"), patch.object(sso_service, "is_safe_url", return_value=(False, "private")):
            self.assertTrue(sso_service.is_safe_sso_url("https://adapter.internal/jwks")[0])
            for url in ("https://evil-adapter.internal/jwks", "https://adapter.internal.evil/jwks",
                        "http://adapter.internal/jwks", "https://user:pass@adapter.internal/jwks"):
                self.assertFalse(sso_service.is_safe_sso_url(url)[0])

    async def test_complete_explicit_endpoints_do_not_require_discovery(self):
        cfg = SimpleNamespace(issuer="https://adapter.example", authorization_endpoint="https://adapter.example/authorize",
                              token_endpoint="https://adapter.example/token", jwks_uri="https://adapter.example/jwks",
                              userinfo_endpoint="https://adapter.example/userinfo")
        with patch.object(sso_service, "is_safe_sso_url", return_value=(True, "")), patch.object(sso_service.httpx, "AsyncClient", side_effect=AssertionError("Unexpected discovery request")):
            endpoints = await sso_service.resolve_endpoints(cfg)
        self.assertEqual(endpoints["token_endpoint"], "https://adapter.example/token")


if __name__ == "__main__":
    unittest.main()
