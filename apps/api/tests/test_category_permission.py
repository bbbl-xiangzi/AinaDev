import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from app.api.categories import _can_post
class Permissions(unittest.IsolatedAsyncioTestCase):
 async def test_permissions_match_post_endpoint(self):
  cat=NS(id=1,post_permission='staff_only',deleted_at=None)
  db=NS(scalar=AsyncMock(return_value=42))
  self.assertTrue(await _can_post(db,cat,NS(id=7,role='user')))
  db.scalar.return_value=None
  self.assertFalse(await _can_post(db,cat,NS(id=7,role='user')))
  self.assertTrue(await _can_post(db,cat,NS(id=7,role='super_admin')))
  cat.post_permission='closed'
  self.assertFalse(await _can_post(db,cat,NS(id=7,role='super_admin')))
  cat.post_permission='public'
  self.assertTrue(await _can_post(db,cat,NS(id=7,role='user')))
  self.assertFalse(await _can_post(db,cat,None))

 async def test_category_output_uses_mapped_fields_and_capability(self):
  from app.models import Category
  from app.api.categories import _to_out
  cat=Category(id=1,slug='support',name='Support',sort_order=0,allow_post=True,post_permission='public',auto_reply_enabled=True,reply_threshold=0.7,notify_human_on_no_evidence=True,relevance_check_enabled=False,reply_to_author_questions=False)
  db=NS(scalar=AsyncMock(return_value=None))
  result=await _to_out(db,cat,NS(id=7,role='user'))
  self.assertTrue(result.can_post)
  self.assertIsNone(result.external_agent_id)
