import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit
from starlette.requests import Request
from fastapi import HTTPException
from app.core.public_origin import public_origin
from app.api import auth_sso
from app.services import sso_service, oauth2_service
from test_auth_sso import SsoCallbackTests

def request(host, proto='https', extra=()):
    return Request({'type':'http','scheme':'http','server':('api',8000),
        'path':'/api/auth/sso/login','query_string':b'',
        'headers':[(b'host',host.encode()),(b'x-forwarded-proto',proto.encode()),*extra]})

class OriginTests(unittest.TestCase):
    def setUp(self):
        from app.config import settings
        self.enterContext(patch.object(settings, 'public_base_url', 'https://community.example'))
        self.enterContext(patch.object(settings, 'public_allowed_origins', 'https://community.example,http://192.0.2.75:8090,https://other.example:9443,http://[::1]:8091'))

    def test_untrusted_host_falls_back_to_configured_origin(self):
        self.assertEqual(public_origin(request('evil.example')), 'https://community.example')
        self.assertEqual(public_origin(request('community.example', 'http')), 'https://community.example')

    def test_arbitrary_domains_ips_and_ports(self):
        for host,proto in [('community.example','https'),('192.0.2.75:8090','http'),('other.example:9443','https'),('[::1]:8091','http')]:
            self.assertEqual(public_origin(request(host,proto)),f'{proto}://{host}')

    def test_forwarded_host_is_not_redirect_authority(self):
        self.assertEqual(public_origin(request('community.example',extra=[(b'x-forwarded-host',b'evil.example')])), 'https://community.example')

    def test_invalid_origins_rejected(self):
        for host,proto in [('evil.example@real.example','https'),('site/path','https'),('site:99999','https'),('site','https,http'),('site\\evil','https')]:
            with self.assertRaises(HTTPException):public_origin(request(host,proto))

class ProxyFlowTests(SsoCallbackTests):
    def setUp(self):
        super().setUp()
        from app.config import settings
        self.enterContext(patch.object(settings, 'public_allowed_origins', 'https://new.example:9443,http://192.0.2.75:8090,https://first.example,https://second.example'))

    async def test_same_origin_used_in_all_login_stages(self):
        for host,proto in [('new.example:9443','https'),('192.0.2.75:8090','http')]:
            req=request(host,proto);expected=f'{proto}://{host}/api/auth/sso/callback'
            login=await auth_sso.sso_login(request=req,db=self.db,login_attempt='browser-attempt-12345')
            params=parse_qs(urlsplit(login.headers['location']).query)
            self.assertEqual(params['redirect_uri'],[expected])
            result=await auth_sso.sso_callback(request=req,code='code',state=params['state'][0],db=self.db)
            self.assertTrue(result.headers['location'].startswith(f'{proto}://{host}/login?sso_ok=1#'))
            sso_service.exchange_token.assert_awaited_with(self.cfg,'code',unittest.mock.ANY,expected)

    async def test_different_callback_origin_is_rejected_before_exchange(self):
        login=await auth_sso.sso_login(request=request('first.example'),db=self.db,login_attempt='browser-attempt-12345')
        state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
        with self.assertRaises(HTTPException):
            await auth_sso.sso_callback(request=request('second.example'),code='code',state=state,db=self.db)
        sso_service.exchange_token.assert_not_awaited()

    async def test_oauth_authorize_and_exchange_keep_explicit_callback(self):
        self.cfg.protocol='oauth2';self.cfg.oauth_options={};self.cfg.token_endpoint='https://idp.example/token'
        callback='https://custom.example:8443/api/auth/sso/callback'
        with patch.object(oauth2_service,'checked_url',lambda u:u),patch.object(sso_service,'client_secret_of',return_value='test-secret'),patch.object(oauth2_service,'request_json',AsyncMock(return_value={'access_token':'opaque'})) as exchange:
            url=oauth2_service.authorize_url(self.cfg,{'authorization_endpoint':'https://idp.example/authorize'},'state','verifier',callback)
            self.assertEqual(parse_qs(urlsplit(url).query)['redirect_uri'],[callback])
            await oauth2_service.exchange(self.cfg,'code','verifier',callback)
            self.assertEqual(exchange.await_args.args[3]['redirect_uri'],callback)
