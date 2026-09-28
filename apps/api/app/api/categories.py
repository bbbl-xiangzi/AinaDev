"""栏目 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, get_optional_user
from app.models import Category, CategoryAiAdmin, Post, Subscription, User
from app.schemas import CategoryOut, AiAdminBrief

router = APIRouter(prefix="/api/categories", tags=["categories"])


async def _to_out(db: AsyncSession, cat: Category, user: User | None) -> CategoryOut:
    post_count = await db.scalar(
        select(func.count(Post.id)).where(Post.category_id == cat.id, Post.status == "published", Post.deleted_at.is_(None))
    )
    is_sub = False
    if user:
        is_sub = await db.scalar(
            select(Subscription.id).where(
                Subscription.user_id == user.id, Subscription.category_id == cat.id, Subscription.tag.is_(None)
            )
        ) is not None
    ai_admin = await db.scalar(
        select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == cat.id, CategoryAiAdmin.active.is_(True))
    )
    # 外部 Agent 名称（绑定外部回帖源时前端展示）
    external_agent_name = None
    if cat.external_agent_id:
        from app.models import ExternalAgent

        ext = await db.get(ExternalAgent, cat.external_agent_id)
        if ext and ext.deleted_at is None:
            external_agent_name = ext.name
    return CategoryOut(
        **{k: getattr(cat, k) for k in ("id", "slug", "name", "description", "icon", "sort_order", "allow_post", "post_permission", "auto_reply_enabled", "reply_threshold", "notify_human_on_no_evidence", "external_agent_id", "relevance_check_enabled", "reply_to_author_questions")},
        post_count=post_count or 0,
        is_subscribed=is_sub,
        external_agent_name=external_agent_name,
        ai_admin=AiAdminBrief(id=ai_admin.id, persona_name=ai_admin.persona_name, persona_avatar=ai_admin.persona_avatar, active=ai_admin.active) if ai_admin else None,
    )


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    cats = list(await db.scalars(select(Category).where(Category.deleted_at.is_(None)).order_by(Category.sort_order, Category.id)))
    return [await _to_out(db, c, user) for c in cats]


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    cat = await db.get(Category, category_id)
    if not cat or cat.deleted_at is not None:
        raise HTTPException(status_code=404, detail="栏目不存在")
    return await _to_out(db, cat, user)
