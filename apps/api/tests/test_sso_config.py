import unittest
from datetime import datetime,timezone
from unittest.mock import AsyncMock,patch

from app.api import admin_sso
from app.models import SsoConfig
from app.schemas.admin import SsoConfigIn
from app.schemas.sso_options import OAuthOptions
from app.services import sso_service


class ConfigurationTests(unittest.IsolatedAsyncioTestCase):
    def cfg(self):
        return SsoConfig(id=1,enabled=False,label="企业登录",protocol="oauth2",issuer="",client_id="client",client_secret_encrypted="ciphertext",
            authorization_endpoint="https://iam.example/authorize",token_endpoint="https://iam.example/token",userinfo_endpoint="https://iam.example/userinfo",
            scopes="",bind_rule="sub",auto_provision=True,extract_employee=False,claim_sub="uid",claim_name="name",claim_email="email",oauth_options={},updated_at=datetime.now(timezone.utc))

    async def test_test_config_never_mutates_current_orm_object(self):
        cfg=self.cfg()
        with patch.object(sso_service,"get_or_create_config",AsyncMock(return_value=cfg)), \
             patch.object(admin_sso,"validate_config",AsyncMock()), \
             patch.object(sso_service,"test_connection",AsyncMock(return_value={"ok":True,"message":"checked","details":None})) as test:
            result=await admin_sso.test_config(SsoConfigIn(client_id="draft",oauth_options=OAuthOptions(token_mode="query")),admin=None,db=None)
        self.assertTrue(result.ok)
        self.assertEqual(cfg.client_id,"client")
        self.assertEqual(cfg.oauth_options,{})
        self.assertEqual(test.await_args.args[0].client_id,"draft")

    def test_output_never_contains_secret_and_keeps_empty_scope(self):
        result=admin_sso._to_out(self.cfg()).model_dump()
        self.assertTrue(result["has_client_secret"])
        self.assertNotIn("ciphertext",str(result))
        self.assertEqual(result["scopes"],"")

    def test_blank_secret_keeps_value_and_blank_url_clears(self):
        current=self.cfg()
        draft=admin_sso.candidate(current,SsoConfigIn(client_secret="",issuer="",userinfo_endpoint="",scopes=""))
        self.assertEqual(draft.client_secret_encrypted,"ciphertext")
        self.assertEqual(draft.userinfo_endpoint,"")
        self.assertEqual(draft.scopes,"")

    async def test_private_host_requires_explicit_allowlist(self):
        cfg=self.cfg()
        cfg.token_endpoint="https://127.0.0.1/token"
        with patch.object(sso_service.settings,"sso_allowed_hosts",""):
            with self.assertRaises(ValueError):
                await admin_sso.validate_config(cfg,required=True)
