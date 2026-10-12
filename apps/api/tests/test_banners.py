import unittest
from types import SimpleNamespace
from pydantic import ValidationError
from app.api.banners import Banner, BannerSettings, visible_banners

IMAGE='/uploads/202610/10/'+'a'*32+'.png'

class BannerTests(unittest.TestCase):
    def test_reject_external_or_non_image(self):
        for url in ('https://example.com/a.png','/uploads/../secret.png',IMAGE.replace('.png','.mp4')):
            with self.assertRaises(ValidationError): Banner(id='one',image_url=url,post_id=1)

    def test_duplicate_ids_rejected(self):
        item=dict(id='one',image_url=IMAGE,post_id=1)
        with self.assertRaises(ValidationError): BannerSettings(items=[item,item])

    def test_limits_and_invalid_post(self):
        with self.assertRaises(ValidationError): Banner(id='a',image_url=IMAGE,post_id=0)
        with self.assertRaises(ValidationError): BannerSettings(items=[dict(id=str(i),image_url=IMAGE,post_id=1) for i in range(21)])

    def test_visibility_and_pin_order(self):
        items=[Banner(id='normal',image_url=IMAGE,post_id=1),Banner(id='pin',image_url=IMAGE,post_id=2,pinned=True),Banner(id='off',image_url=IMAGE,post_id=1,enabled=False),Banner(id='hidden',image_url=IMAGE,post_id=3),Banner(id='deleted',image_url=IMAGE,post_id=4)]
        posts={n:SimpleNamespace(id=n,title=str(n),status='hidden' if n==3 else 'published',deleted_at=True if n==4 else None) for n in range(1,5)}
        self.assertEqual([b['id'] for b in visible_banners(items,posts)],['pin','normal'])

    def test_empty_or_missing_post_not_visible(self):
        self.assertEqual(visible_banners([],{}),[])
        self.assertEqual(visible_banners([Banner(id='one',image_url=IMAGE,post_id=42)],{}),[])

    def test_anonymous_cannot_manage_or_search(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.banners import router
        app=FastAPI();app.include_router(router)
        client=TestClient(app)
        self.assertIn(client.get('/api/admin/banners').status_code,(401,403))
        self.assertIn(client.get('/api/admin/banners/posts').status_code,(401,403))
        self.assertIn(client.put('/api/admin/banners',json={'items':[]}).status_code,(401,403))

    def test_regular_user_cannot_manage(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.banners import router
        from app.core.deps import get_current_user
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_current_user]=lambda: SimpleNamespace(role='user')
        client=TestClient(app)
        self.assertEqual(client.get('/api/admin/banners').status_code,403)
        self.assertEqual(client.put('/api/admin/banners',json={'items':[]}).status_code,403)
