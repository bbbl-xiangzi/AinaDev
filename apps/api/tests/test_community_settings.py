import unittest
from types import SimpleNamespace
from pydantic import ValidationError
from app.api.admin_system import update_site_config, site_config_public
from app.api.uploads import _get_config
from app.schemas import SiteConfigIn


class FakeDB:
    def __init__(self): self.rows = {}
    async def get(self, model, key): return self.rows.get(key)
    async def scalars(self, query): return list(self.rows.values())
    def add(self, row): self.rows[row.key] = row
    async def commit(self): pass


class CommunitySettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_logo_save_read_clear_and_public_whitelist(self):
        db = FakeDB()
        await update_site_config(SiteConfigIn(logo_url="/uploads/logo.png", mcp_api_key="private-test-value"), admin=None, db=db)
        public = await site_config_public(db=db)
        self.assertEqual(public["logo_url"], "/uploads/logo.png")
        self.assertEqual(set(public), {"site_name", "site_description", "logo_url"})
        await update_site_config(SiteConfigIn(logo_url=""), admin=None, db=db)
        self.assertEqual((await site_config_public(db=db))["logo_url"], "")

    async def test_upload_bounds_and_existing_default(self):
        for limit in (0, -1, 501):
            with self.assertRaises(ValidationError): SiteConfigIn(upload_max_size_mb=limit)
        self.assertEqual(SiteConfigIn(upload_max_size_mb=500).upload_max_size_mb, 500)
        db = FakeDB()
        self.assertEqual((await _get_config(db))[1], 10)
        for value, expected in [("500", 500), ("invalid", 10), ("999999", 500), ("-1", 1)]:
            db.rows["upload_max_size_mb"] = SimpleNamespace(key="upload_max_size_mb", value=value)
            self.assertEqual((await _get_config(db))[1], expected)
