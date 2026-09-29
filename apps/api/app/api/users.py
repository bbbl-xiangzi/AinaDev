"""用户公开主页与关注 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, get_optional_user
from app.models import Follow, Notification, Post, Reply, User
from app.schemas import PostListOut, PublicUserOut, UserBriefOut

router = APIRouter(prefix="/api/users", tags=["users"])


def _is_ai_account(u: User) -> bool:
    return u.account_type in ("agent", "system")


async def _stats(db: AsyncSession, uid: int) -> dict:
    post_count = await db.scalar(
        select(func.count(Post.id)).where(Post.author_id == uid, Post.deleted_at.is_(None), Post.status == "published")
    ) or 0
    reply_count = await db.scalar(
        select(func.count(Reply.id)).where(Reply.author_id == uid, Reply.deleted_at.is_(None), Reply.status == "published")
    ) or 0
    like_received = (
        await db.scalar(select(func.coalesce(func.sum(Post.like_count), 0)).where(Post.author_id == uid, Post.deleted_at.is_(None)))
        or 0
    ) + (
        await db.scalar(select(func.coalesce(func.sum(Reply.like_count), 0)).where(Reply.author_id == uid, Reply.deleted_at.is_(None)))
        or 0
    )
    follower_count = await db.scalar(select(func.count(Follow.id)).where(Follow.followee_id == uid)) or 0
    following_count = await db.scalar(select(func.count(Follow.id)).where(Follow.follower_id == uid)) or 0
    return {
        "post_count": int(post_count),
        "reply_count": int(reply_count),
        "like_received": int(like_received),
        "follower_count": int(follower_count),
        "following_count": int(following_count),
    }


async def _brief(u: User) -> UserBriefOut:
    return UserBriefOut(
        id=u.id, name=u.name, avatar_url=u.avatar_url,
        account_type=u.account_type, department=u.department, created_at=u.created_at,
    )


@router.get("/{user_id}", response_model=PublicUserOut)
async def public_user(
    user_id: int,
    viewer: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    stats = await _stats(db, user_id)
    is_following = False
    if viewer and viewer.id != user_id:
        is_following = (await db.scalar(
            select(func.count(Follow.id)).where(Follow.follower_id == viewer.id, Follow.followee_id == user_id)
        ) or 0) > 0
    return PublicUserOut(
        id=u.id, name=u.name, avatar_url=u.avatar_url,
        account_type=u.account_type, role=u.role,
        department=u.department, org_id=u.org_id, created_at=u.created_at,
        is_following=is_following, is_self=bool(viewer and viewer.id == user_id),
        **stats,
    )


@router.get("/{user_id}/posts", response_model=PostListOut)
async def user_posts(
    user_id: int,
    page: int = 1, page_size: int = 20,
    viewer: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    from app.api.posts import _post_to_out

    u = await db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    stmt = (
        select(Post)
        .where(Post.author_id == user_id, Post.deleted_at.is_(None), Post.status == "published")
        .order_by(Post.created_at.desc())
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return PostListOut(total=total, items=[await _post_to_out(db, p, viewer) for p in rows])


async def _ensure_followable(u: User | None, me: User):
    if not u or u.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if u.id == me.id:
        raise HTTPException(status_code=400, detail="不能关注自己")
    if _is_ai_account(u):
        raise HTTPException(status_code=400, detail="AI/官方账号不可关注")


@router.post("/{user_id}/follow")
async def follow(
    user_id: int,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    await _ensure_followable(target, me)
    exists = await db.scalar(
        select(func.count(Follow.id)).where(Follow.follower_id == me.id, Follow.followee_id == user_id)
    )
    if not exists:
        db.add(Follow(follower_id=me.id, followee_id=user_id))
        await db.flush()
        db.add(Notification(
            user_id=user_id, type="follow", title=f"{me.name} 关注了你",
            body=f"去 TA 的主页看看吧", link_url=f"/users/{me.id}",
        ))
        await db.commit()
    return {"ok": True}


@router.delete("/{user_id}/follow")
async def unfollow(
    user_id: int,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(Follow.__table__.delete().where(Follow.follower_id == me.id, Follow.followee_id == user_id))
    await db.commit()
    return {"ok": True}


@router.get("/{user_id}/followers", response_model=list[UserBriefOut])
async def followers(user_id: int, db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(User).join(Follow, Follow.follower_id == User.id)
        .where(Follow.followee_id == user_id, User.deleted_at.is_(None))
        .order_by(Follow.created_at.desc()).limit(100)
    ))
    return [await _brief(u) for u in rows]


@router.get("/{user_id}/followings", response_model=list[UserBriefOut])
async def followings(user_id: int, db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(User).join(Follow, Follow.followee_id == User.id)
        .where(Follow.follower_id == user_id, User.deleted_at.is_(None))
        .order_by(Follow.created_at.desc()).limit(100)
    ))
    return [await _brief(u) for u in rows]
