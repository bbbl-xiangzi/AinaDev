"""Regression coverage for fields added by startup migrations.

Run against a disposable initialized PostgreSQL database with
RUN_DATABASE_TESTS=1. Every change is rolled back.
"""
import os
import unittest

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models import AiNewsSource, Category, Post, Reply


@unittest.skipUnless(os.environ.get("RUN_DATABASE_TESTS") == "1", "requires disposable PostgreSQL")
class ModelPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_migrated_fields_survive_database_reload(self):
        async with SessionLocal() as db:
            try:
                category = Category(slug="model-persistence-regression", name="Regression",
                                    external_agent_id=123, relevance_check_enabled=True,
                                    reply_to_author_questions=True)
                source = AiNewsSource(name="Regression", type="html_list", url="https://example.invalid",
                                      config={"selector": "article"})
                db.add_all([category, source])
                post = await db.scalar(select(Post).limit(1))
                reply = await db.scalar(select(Reply).limit(1))
                self.assertIsNotNone(post, "create a test post first")
                self.assertIsNotNone(reply, "create a test reply first")
                post.review_reason = "post review regression"
                reply.review_reason = "reply review regression"
                await db.flush()
                ids = category.id, source.id, post.id, reply.id
                db.expunge_all()
                category = await db.get(Category, ids[0])
                source = await db.get(AiNewsSource, ids[1])
                post = await db.get(Post, ids[2])
                reply = await db.get(Reply, ids[3])
                self.assertEqual(category.external_agent_id, 123)
                self.assertTrue(category.relevance_check_enabled)
                self.assertTrue(category.reply_to_author_questions)
                self.assertEqual(source.type, "html_list")
                self.assertEqual(source.config, {"selector": "article"})
                self.assertEqual(post.review_reason, "post review regression")
                self.assertEqual(reply.review_reason, "reply review regression")
            finally:
                await db.rollback()
        await engine.dispose()
