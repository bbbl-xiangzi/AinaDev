"""Exercise edit authorization, review and optimistic writes against SQLite SQL."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, text

from app.api import post_edit
from app.models import AuditLog, Category, Post


class DatabaseBoundary:
    def __init__(self):
        self.engine = create_engine('sqlite://', isolation_level='AUTOCOMMIT')
        self.connection = self.engine.connect()
        self.connection.exec_driver_sql('''CREATE TABLE posts (
            id INTEGER PRIMARY KEY, title TEXT, body_md TEXT, status TEXT,
            author_id INTEGER, category_id INTEGER, locked BOOLEAN,
            deleted_at DATETIME, human_needed BOOLEAN, updated_at DATETIME,
            review_reason TEXT, view_count INTEGER, reply_count INTEGER
        )''')
        self.connection.exec_driver_sql("INSERT INTO posts VALUES (1,'Original','Old body','published',7,2,0,NULL,0,NULL,NULL,42,3)")
        self.category = SimpleNamespace(id=2, name='General', description='', deleted_at=None, relevance_check_enabled=False)
        self.audits = []

    def row(self):
        return dict(self.connection.execute(text('SELECT * FROM posts WHERE id=1')).mappings().one())

    async def get(self, model, key):
        if model is Post:
            if key != 1:
                return None
            return SimpleNamespace(**self.row(), attachments=[])
        if model is Category:
            return self.category
        raise AssertionError(model)

    async def execute(self, statement):
        return self.connection.execute(statement)

    def add(self, row):
        assert isinstance(row, AuditLog)
        self.audits.append(row)

    async def commit(self):
        self.connection.commit()

    async def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()
        self.engine.dispose()


class PostEditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = DatabaseBoundary()
        self.addCleanup(self.db.close)
        self.user = SimpleNamespace(id=7, role='member')
        self.review = self.enterContext(patch.object(post_edit, 'compliance_check', AsyncMock(return_value={'pass': True, 'severity': 'low'})))
        self.enterContext(patch.object(post_edit, 'relevance_check', AsyncMock(return_value={'pass': True})))
        self.enterContext(patch.object(post_edit, 'check_rate', AsyncMock()))

    async def payload(self, **changes):
        current = await post_edit.get_edit(1, user=self.user, db=self.db)
        values = dict(title='Updated', body_md='Updated body', revision=current['revision'])
        values.update(changes)
        return post_edit.PostEditIn(**values)

    async def rejected(self, code, operation):
        with self.assertRaises(HTTPException) as result:
            await operation
        self.assertEqual(result.exception.status_code, code)

    async def test_author_edit_changes_existing_post_and_preserves_counts(self):
        body = await self.payload()
        result = await post_edit.update_post(1, body, user=self.user, db=self.db)
        self.assertEqual(result, {'id': 1, 'status': 'published'})
        row = self.db.row()
        self.assertEqual((row['title'], row['body_md'], row['view_count'], row['reply_count']), ('Updated', 'Updated body', 42, 3))
        self.assertEqual(self.db.connection.execute(text('SELECT count(*) FROM posts')).scalar(), 1)
        self.assertEqual(len(self.db.audits), 1)
        self.assertEqual((self.db.audits[0].actor_id, self.db.audits[0].action), (7, 'edit_post'))

    async def test_title_correction_preserves_unresolved_human_intervention(self):
        self.db.connection.exec_driver_sql('UPDATE posts SET human_needed=1 WHERE id=1')
        body = await self.payload(body_md='Old body')
        await post_edit.update_post(1, body, user=self.user, db=self.db)
        self.assertEqual(self.db.row()['human_needed'], 1, 'editing does not resolve an unanswered support request')

    async def test_other_member_cannot_read_or_edit(self):
        body = await self.payload()
        other = SimpleNamespace(id=8, role='member')
        await self.rejected(403, post_edit.get_edit(1, user=other, db=self.db))
        await self.rejected(403, post_edit.update_post(1, body, user=other, db=self.db))
        self.assertEqual(self.db.row()['title'], 'Original')

    async def test_administrator_can_edit_another_authors_post(self):
        body = await self.payload()
        await post_edit.update_post(1, body, user=SimpleNamespace(id=8, role='super_admin'), db=self.db)
        self.assertEqual(self.db.row()['title'], 'Updated')

    async def test_missing_deleted_locked_and_pending_posts_are_rejected(self):
        await self.rejected(404, post_edit.get_edit(99, user=self.user, db=self.db))
        for column, value, code in [('deleted_at', '2026-11-10', 404), ('locked', 1, 409), ('status', 'pending_review', 409)]:
            self.db.connection.execute(text(f'UPDATE posts SET {column}=:value WHERE id=1'), {'value': value})
            await self.rejected(code, post_edit.get_edit(1, user=self.user, db=self.db))
            self.db.connection.exec_driver_sql("UPDATE posts SET deleted_at=NULL,locked=0,status='published' WHERE id=1")

    async def test_stale_revision_does_not_replace_newer_content(self):
        body = await self.payload(revision='0' * 64)
        await self.rejected(409, post_edit.update_post(1, body, user=self.user, db=self.db))
        self.assertEqual(self.db.row()['body_md'], 'Old body')
        self.assertEqual(self.db.audits, [])

    async def test_identical_content_does_not_trigger_review_or_write(self):
        body = await self.payload(title='Original', body_md='Old body')
        await post_edit.update_post(1, body, user=self.user, db=self.db)
        self.assertEqual(self.db.row()['updated_at'], None)
        self.assertEqual(self.db.audits, [])
        self.review.assert_not_awaited()

    async def test_rejected_review_keeps_published_content(self):
        body = await self.payload()
        self.review.return_value = {'pass': False, 'severity': 'high', 'reason': 'Rejected'}
        await self.rejected(422, post_edit.update_post(1, body, user=self.user, db=self.db))
        self.assertEqual(self.db.row()['title'], 'Original')
        self.assertEqual(self.db.audits, [])

    async def test_category_review_failure_keeps_original_content(self):
        body = await self.payload()
        self.db.category.relevance_check_enabled = True
        post_edit.relevance_check.return_value = {'pass': False, 'reason': 'Off topic'}
        await self.rejected(422, post_edit.update_post(1, body, user=self.user, db=self.db))
        self.assertEqual(self.db.row()['body_md'], 'Old body')

    async def test_concurrent_edit_during_review_is_not_overwritten(self):
        body = await self.payload()
        async def concurrent_edit(*args):
            self.db.connection.exec_driver_sql("UPDATE posts SET title='Concurrent edit' WHERE id=1")
            return {'pass': True, 'severity': 'low'}
        self.review.side_effect = concurrent_edit
        await self.rejected(409, post_edit.update_post(1, body, user=self.user, db=self.db))
        self.assertEqual(self.db.row()['title'], 'Concurrent edit')
        self.assertEqual(self.db.audits, [])
