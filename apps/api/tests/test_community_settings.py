import unittest
from app.api.admin_system import update_site_config, site_config_public
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

