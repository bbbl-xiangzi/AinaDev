import unittest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.sdk_pages import router
from app.core.db import get_db
from app.core.deps import get_current_user


class FakeDB:
    def __init__(self): self.row = None
    async def get(self, *args): return self.row
    def add(self, row): self.row = row
    async def commit(self): pass


class SdkPagesTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(router)
        self.app = app; self.db = FakeDB()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.page = dict(slug="assistant", title="Assistant", enabled=True, provider="hiagent",
                         base_url="https://agent.example", sdk_url="https://agent.example/sdk.js", app_key="public-app-id")

    def user(self, role):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=role)

    def test_authorization(self):
        for path in ("/api/sdk-pages", "/api/sdk-pages/assistant", "/api/admin/sdk-pages"):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.user("user")
        self.assertEqual(self.client.get("/api/admin/sdk-pages").status_code, 403)
        self.assertEqual(self.client.put("/api/admin/sdk-pages", json={"pages": []}).status_code, 403)

    def test_lifecycle_and_navigation(self):
        self.user("super_admin")
        self.assertEqual(self.client.get("/api/admin/sdk-pages").json(), {"pages": []})
        self.assertEqual(self.client.put("/api/admin/sdk-pages", json={"pages": [self.page]}).status_code, 200)
        self.user("user")
        self.assertEqual(self.client.get("/api/sdk-pages").json(), [{"slug": "assistant", "title": "Assistant"}])
        self.assertEqual(self.client.get("/api/sdk-pages/assistant").json(), self.page)
        self.user("super_admin")
        self.page["enabled"] = False
        self.client.put("/api/admin/sdk-pages", json={"pages": [self.page]})
        self.assertEqual(self.client.get("/api/sdk-pages").json(), [])
        self.assertEqual(self.client.get("/api/sdk-pages/assistant").status_code, 404)
        self.client.put("/api/admin/sdk-pages", json={"pages": []})
        self.assertEqual(self.client.get("/api/admin/sdk-pages").json(), {"pages": []})

    def test_invalid_configuration_is_not_saved(self):
        self.user("super_admin")
        for field, value in [("slug", "../admin"), ("title", " "), ("app_key", " "),
                             ("sdk_url", "javascript:alert(1)"), ("sdk_url", "https://a:pass@agent.example/a.js"),
                             ("base_url", "https://agent.example/path"), ("base_url", "https://agent.example:bad"),
                             ("provider", "unknown")]:
            with self.subTest(field=field, value=value):
                self.assertEqual(self.client.put("/api/admin/sdk-pages", json={"pages": [{**self.page, field: value}]}).status_code, 422)
        self.assertEqual(self.client.put("/api/admin/sdk-pages", json={"pages": [self.page, self.page]}).status_code, 422)
        self.assertIsNone(self.db.row)
