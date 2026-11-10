"""Edit published posts without creating another post or rerunning reply jobs."""
import hashlib
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import check_rate
from app.models import Post, User, Category, AuditLog
from app.services.compliance_service import compliance_check, relevance_check

router = APIRouter()

class PostEditIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body_md: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("title", "body_md")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("标题和正文不能为空")
        return value

def revision(post):
    fields = [post.title, post.body_md, post.category_id, post.status, post.locked]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode()).hexdigest()

async def editable(db, post_id, user):
    post = await db.get(Post, post_id)
    if not post or post.deleted_at is not None:
        raise HTTPException(404, "帖子不存在")
    if post.author_id != user.id and user.role != "super_admin":
        raise HTTPException(403, "只能编辑自己的帖子")
    if post.locked or post.status not in ("published", "rejected"):
        raise HTTPException(409, "当前帖子状态不允许编辑")
    return post

@router.get("/posts/{post_id}/edit")
async def get_edit(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await editable(db, post_id, user)
    return {"id": post.id, "title": post.title, "body_md": post.body_md,
            "revision": revision(post), "attachments": post.attachments or []}

@router.put("/posts/{post_id}")
async def update_post(post_id: int, body: PostEditIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await editable(db, post_id, user)
    if body.revision != revision(post):
        raise HTTPException(409, "帖子已被修改，请刷新后重新编辑")
    title = body.title.strip()
    if title == post.title and body.body_md == post.body_md:
        return {"id": post.id, "status": post.status}
    await check_rate(f"rl:post_edit:user:{user.id}", 6, 60, "编辑过于频繁，请稍后再试")
    # Keep the previous version visible until the edited content passes review.
    old_title, old_body, old_status, category_id = post.title, post.body_md, post.status, post.category_id
    category = await db.get(Category, category_id)
    if not category or category.deleted_at is not None:
        raise HTTPException(404, "栏目不存在")
    trace_id = uuid.uuid4().hex[:16]
    content = f"{title}\n{body.body_md}"
    result = await compliance_check(db, content, post_id, trace_id)
    if result.get("pass") is not True or result.get("severity") != "low":
        raise HTTPException(422, "修改未通过审核：" + str(result.get("reason") or "请调整内容后重试"))
    if category.relevance_check_enabled:
        rel = await relevance_check(db, category.name, category.description, content, post_id, trace_id)
        if rel.get("pass") is not True:
            raise HTTPException(422, "修改未通过栏目审核：" + str(rel.get("reason") or "内容与栏目不相关"))
    changed = await db.execute(update(Post).where(
        Post.id == post_id, Post.title == old_title, Post.body_md == old_body,
        Post.status == old_status, Post.category_id == category_id,
        Post.locked.is_(False), Post.deleted_at.is_(None),
    ).values(title=title, body_md=body.body_md, status="published", review_reason=None,
             updated_at=func.now()).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "帖子已被修改，请刷新后重新编辑")
    db.add(AuditLog(actor_type="user", actor_id=user.id, action="edit_post", target_type="post", target_id=post_id,
                    detail={"previous_revision": body.revision}))
    await db.commit()
    return {"id": post_id, "status": "published"}
