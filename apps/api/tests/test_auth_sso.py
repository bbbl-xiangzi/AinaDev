"""SSO regression tests. Run: python -m unittest discover -s tests -v."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException

from app.api import auth_sso
from app.core.security import decode_token
from app.services import employee_fields, sso_service
from app.tasks import worker


class RedisDouble:
    """In-memory boundary for Redis state and queued JSON-compatible arguments."""

    def __init__(self):
        self.values = {}
        self.jobs = []
        self.fail_enqueue = False
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def setex(self, key, ttl, value):
        self.values[key] = value.encode()

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        self.values.pop(key, None)

    async def enqueue_job(self, name, *args):
        if self.fail_enqueue:
            raise ConnectionError("queue unavailable")
        self.jobs.append((name, json.loads(json.dumps(args))))

    async def close(self):
        self.closed = True


class SsoCallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.redis = RedisDouble()
        self.db = object()
        self.cfg = SimpleNamespace(extract_employee=True, client_id="test-client", scopes="openid")
        self.fields = [SimpleNamespace(enabled=True, field_key="department", claim_key="department")]
        self.claims = {"sub": "employee-42", "name": "Test", "department": "Engineering"}
        self.enterContext(patch("redis.asyncio.from_url", return_value=self.redis))
        self.enterContext(patch.object(worker, "create_pool", AsyncMock(return_value=self.redis)))
        self.enterContext(patch.object(sso_service, "get_active_config", AsyncMock(return_value=self.cfg)))
        self.enterContext(patch.object(sso_service, "resolve_endpoints", AsyncMock(return_value={
            "authorization_endpoint": "https://idp.example/authorize",
        })))
        self.enterContext(patch.object(sso_service, "exchange_token", AsyncMock(return_value={
            "id_token": "test-id-token", "access_token": "test-access-token",
        })))
        self.enterContext(patch.object(sso_service, "verify_id_token", AsyncMock(return_value=self.claims)))
        self.enterContext(patch.object(sso_service, "fetch_userinfo", AsyncMock(return_value={})))
        self.enterContext(patch.object(employee_fields, "list_field_defs", AsyncMock(return_value=self.fields)))
        self.enterContext(patch.object(sso_service, "provision_or_bind", AsyncMock(return_value=SimpleNamespace(id=42))))
        self.enterContext(patch.object(auth_sso.settings, "jwt_secret", "test-only-signing-key-32-bytes-long"))
        self.enterContext(patch.object(auth_sso.settings, "public_base_url", "https://community.example"))

    async def login_and_callback(self):
        login = await auth_sso.sso_login(db=self.db, login_attempt="browser-attempt-12345")
        self.assertEqual(login.status_code, 302)
        params = parse_qs(urlsplit(login.headers["location"]).query)
        state = params["state"][0]
        response = await auth_sso.sso_callback(code="test-code", state=state, db=self.db)
        self.assertEqual(response.status_code, 302)
        tokens = parse_qs(urlsplit(response.headers["location"]).fragment)
        self.assertEqual(tokens["attempt"], ["browser-attempt-12345"])
        self.assertEqual(decode_token(tokens["token"][0])["sub"], "42")
        self.assertEqual(decode_token(tokens["refresh"][0], "refresh")["sub"], "42")
        self.assertNotIn("test-id-token", response.headers["location"])
        self.assertNotIn(f"sso:auth:state:{state}", self.redis.values)
        return state

    async def test_login_enqueues_registered_employee_task_with_serializable_arguments(self):
        await self.login_and_callback()
        self.assertEqual(self.redis.jobs, [("extract_employee_task", [42, self.claims])])
        self.assertIn(self.redis.jobs[0][0], {fn.__name__ for fn in worker.FUNCTIONS})
        self.assertTrue(self.redis.closed)

    async def test_queue_failure_does_not_prevent_login(self):
        self.redis.fail_enqueue = True
        with self.assertLogs(auth_sso.__name__, level="WARNING") as logs:
            await self.login_and_callback()
        self.assertNotIn("employee-42", " ".join(logs.output))
        self.assertNotIn("test-access-token", " ".join(logs.output))

    async def test_disabled_extraction_does_not_enqueue(self):
        self.cfg.extract_employee = False
        await self.login_and_callback()
        self.assertEqual(self.redis.jobs, [])

    async def test_no_enabled_fields_does_not_enqueue(self):
        self.fields.clear()
        await self.login_and_callback()
        self.assertEqual(self.redis.jobs, [])

    async def test_consumed_state_cannot_be_replayed(self):
        state = await self.login_and_callback()
        with self.assertRaises(HTTPException) as caught:
            await auth_sso.sso_callback(code="test-code", state=state, db=self.db)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(len(self.redis.jobs), 1)

    async def test_invalid_state_is_rejected_without_enqueue(self):
        with self.assertRaises(HTTPException) as caught:
            await auth_sso.sso_callback(code="test-code", state="unknown", db=self.db)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.redis.jobs, [])

    async def test_failed_identity_verification_is_not_treated_as_optional(self):
        self.redis.values["sso:auth:state:valid-state"] = b"verifier|nonce|browser-attempt-12345"
        with patch.object(sso_service, "verify_id_token", AsyncMock(side_effect=ValueError("invalid signature"))):
            with self.assertRaises(HTTPException) as caught:
                await auth_sso.sso_callback(code="test-code", state="valid-state", db=self.db)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.redis.jobs, [])


if __name__ == "__main__":
    unittest.main()
