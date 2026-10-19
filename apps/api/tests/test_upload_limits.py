import unittest
from types import SimpleNamespace
from pydantic import ValidationError
from app.schemas import SiteConfigIn
from app.api.uploads import _get_config

class LimitsTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounds_and_persisted_values(self):
        for value in (0, -1, 501):
            with self.assertRaises(ValidationError): SiteConfigIn(upload_max_size_mb=value)
        self.assertEqual(SiteConfigIn(upload_max_size_mb=500).upload_max_size_mb, 500)
        class DB:
            value = None
            async def scalars(self, query):
                return [] if self.value is None else [SimpleNamespace(key="upload_max_size_mb", value=self.value)]
        db=DB()
        for value, expected in [(None,100),("500",500),("9999",500),("-1",1),("invalid",100)]:
            db.value=value
            self.assertEqual((await _get_config(db))[1],expected)
