import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from test_login_branding import LoginBrandingTests
from app.api import auth_sso


class AutoSsoConfigTests(LoginBrandingTests):
    def test_auto_sso_default_and_roundtrip(self):
        from app.core.deps import get_current_user
        self.assertIs(self.client.get('/api/admin/site-config-public').json().get('auto_sso_login'), False)
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='super_admin')
        for enabled in (True, False):
            self.assertEqual(self.client.put('/api/admin/site-config', json={'auto_sso_login': enabled}).status_code, 200)
            self.assertIs(self.client.get('/api/admin/site-config-public').json()['auto_sso_login'], enabled)


class AutoSsoFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_browser_callback_returns_login_without_details(self):
        with patch.object(auth_sso, 'sso_callback', AsyncMock(side_effect=HTTPException(400, 'secret details'))):
            response = await auth_sso.sso_callback_browser(code='code', state='state', db=object())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['location'], '/login?sso_error=1')
        self.assertEqual(response.headers['cache-control'], 'no-store')

    async def test_failed_browser_start_returns_login(self):
        with patch.object(auth_sso, 'sso_login', AsyncMock(side_effect=RuntimeError('unavailable'))):
            response = await auth_sso.sso_login_browser(login_attempt='browser-attempt-12345', db=object())
        self.assertEqual(response.headers['location'], '/login?sso_error=1')

    async def test_successful_callback_response_preserved(self):
        expected = object()
        with patch.object(auth_sso, 'sso_callback', AsyncMock(return_value=expected)):
            self.assertIs(await auth_sso.sso_callback_browser(code='code', state='state', db=object()), expected)
