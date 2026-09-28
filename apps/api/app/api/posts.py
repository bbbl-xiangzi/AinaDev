"""帖子 API：发帖、Feed、详情、搜索、互动。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, get_optional_user
from app.core.ratelimit import check_rate, client_ip
from app.models import Category, CategoryHumanAdmin, Post, Reply, Subscription, User
from app.schemas import PostIn, PostListOut, PostOut, ReplyIn, ReplyOut, SearchQuery
from app.services.audit_service import audit
from app.services.notify_service import notify

router = APIRouter(prefix="/api", tags=["posts"])

FEED_SORTS = {"latest", "hot", "unanswered", "following"}


async def _post_to_out(db: AsyncSession, p: Post, user: User | None) -> PostOut:
    author = await db.get(User, p.author_id)
    cat = await db.get(Category, p.category_id)
    is_liked = False
    is_sub = False
    if user:
        from app.models import AuditLog

        is_liked = await db.scalar(
            select(AuditLog.id).where(
                AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
                AuditLog.action == "like_post", AuditLog.target_id == p.id,
            )
        ) is not None
        is_sub = await db.scalar(
            select(Subscription.id).where(
                Subscription.user_id == user.id, Subscription.category_id == p.category_id, Subscription.tag.is_(None)
            )
        ) is not None
    author_type = "ai_agent" if author and author.account_type in ("agent", "system") else "human"
    return PostOut(
        id=p.id, category_id=p.category_id, category_name=cat.name if cat else None,
        author_id=p.author_id, author_name=author.name if author else None,
        author_avatar=author.avatar_url if author else None, author_type=author_type,
        title=p.title, body_md=p.body_md, post_type=p.post_type, status=p.status,
        pinned=p.pinned, featured=p.featured, locked=p.locked, is_solved=p.is_solved,
        tags=p.tags, attachments=p.attachments or [], view_count=p.view_count, like_count=p.like_count, reply_count=p.reply_count,
        ai_handled=p.ai_handled, human_needed=p.human_needed, review_reason=p.review_reason,
        created_at=p.created_at, updated_at=p.updated_at,
        is_liked=is_liked, is_subscribed=is_sub,
    )


async def _reply_to_out(db: AsyncSession, r: Reply, user: User | None) -> ReplyOut:
    author = await db.get(User, r.author_id)
    is_liked = False
    if user:
        from app.models import AuditLog

        is_liked = await db.scalar(
            select(AuditLog.id).where(
                AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
                AuditLog.action == "like_reply", AuditLog.target_id == r.id,
            )
        ) is not None
    return ReplyOut(
        id=r.id, post_id=r.post_id, parent_reply_id=r.parent_reply_id,
        author_id=r.author_id, author_name=author.name if author else None,
        author_avatar=author.avatar_url if author else None, author_type=r.author_type,
        body_md=r.body_md, status=r.status, citations=r.citations,
        attachments=r.attachments or [], review_reason=r.review_reason,
        like_count=r.like_count, created_at=r.created_at, is_liked=is_liked,
    )


@router.post("/posts", response_model=PostOut)
async def create_post(body: PostIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # 发帖频率限制（防刷 LLM 算力：发帖即触发 AI 审核+AI 回复）
    await check_rate(f"rl:post:user:{user.id}", 6, 60, "发帖过于频繁，请稍后再试")
    cat = await db.get(Category, body.category_id)
    if not cat or cat.deleted_at is not None:
        raise HTTPException(status_code=404, detail="栏目不存在")

    # 发帖权限三态：public=所有成员；staff_only=仅超管/栏目管理员；closed=任何人都不能发
    perm = getattr(cat, "post_permission", "public") or "public"
    if perm == "closed":
        raise HTTPException(status_code=403, detail="该栏目已关闭发帖")
    if perm == "staff_only" and user.role != "super_admin":
        from app.models import CategoryHumanAdmin
        is_cat_admin = await db.scalar(
            select(CategoryHumanAdmin.id).where(
                CategoryHumanAdmin.category_id == cat.id,
                CategoryHumanAdmin.user_id == user.id,
            )
        )
        if is_cat_admin is None:
            raise HTTPException(status_code=403, detail="该栏目仅管理员可发帖")

    # 发帖进入「审核中」状态：不直接发布，异步 AI 审核通过后才公开
    post = Post(
        category_id=body.category_id, author_id=user.id,
        title=body.title.strip(), body_md=body.body_md,
        post_type=body.post_type, status="pending_review", tags=body.tags[:5],
        attachments=[a.model_dump() for a in (body.attachments or [])][:20],
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    # 异步 AI 审核（worker 执行；审核通过后再触发 AI 回复流水线，两次调用分开）
    from app.tasks.worker import enqueue
    from app.services.ticket_service import grant as grant_ticket

    try:
        await grant_ticket(db, user.id, "post_create", "post", post.id)
    except Exception:
        pass
    try:
        await enqueue("review_post_task", post.id)
    except Exception:
        # Redis 不可用时同步执行（降级不阻塞发帖）
        from app.tasks.review_tasks import review_post

        await review_post(db, post.id)
    return await _post_to_out(db, post, user)


@router.get("/posts", response_model=PostListOut)
async def list_posts(
    sort: str = Query("latest", pattern="^(latest|hot|unanswered|following)$"),
    category_id: int | None = None,
    tag: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Post).where(Post.status == "published", Post.deleted_at.is_(None))
    if category_id:
        stmt = stmt.where(Post.category_id == category_id)
    if tag:
        stmt = stmt.where(Post.tags.any(tag))

    if sort == "hot":
        stmt = stmt.order_by(Post.reply_count.desc(), Post.view_count.desc(), Post.created_at.desc())
    elif sort == "unanswered":
        stmt = stmt.where(Post.reply_count == 0).order_by(Post.created_at.desc())
    elif sort == "following":
        if not user:
            raise HTTPException(status_code=401, detail="请先登录")
        sub_cats = select(Subscription.category_id).where(Subscription.user_id == user.id, Subscription.tag.is_(None))
        stmt = stmt.where(Post.category_id.in_(sub_cats)).order_by(Post.created_at.desc())
    else:
        stmt = stmt.order_by(Post.pinned.desc(), Post.created_at.desc())

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    items = [await _post_to_out(db, p, user) for p in rows]
    return PostListOut(total=total or 0, items=items)


@router.get("/posts/{post_id}", response_model=PostOut)
async def get_post(
    post_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post or post.deleted_at is not None or post.status not in ("published", "hidden", "pending_review", "rejected"):
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.status in ("hidden", "pending_review", "rejected") and (not user or user.id != post.author_id):
        from app.models import CategoryHumanAdmin

        is_admin = await db.scalar(
            select(CategoryHumanAdmin.id).where(
                CategoryHumanAdmin.category_id == post.category_id, CategoryHumanAdmin.user_id == user.id
            )
        ) if user else None
        is_super = user.role == "super_admin" if user else False
        if not is_admin and not is_super:
            raise HTTPException(status_code=404, detail="帖子不存在")
    post.view_count += 1
    await db.commit()
    await db.refresh(post)  # commit 后重新加载所有列，避免懒加载触发 MissingGreenlet
    # 每日阅读奖励（每日 1 次，已登录用户）
    if user:
        from app.services.ticket_service import grant as grant_ticket
        try:
            await grant_ticket(db, user.id, "daily_read", "post", post_id)
            await db.commit()
        except Exception:
            pass
    return await _post_to_out(db, user=user, p=post)


@router.get("/posts/{post_id}/replies", response_model=list[ReplyOut])
async def list_replies(
    post_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        return []
    # 可见性：published 所有人可见；pending_review（审核中）额外仅楼主本人或管理员可见
    stmt = select(Reply).where(Reply.post_id == post_id, Reply.deleted_at.is_(None))
    if user and (
        user.id == post.author_id
        or user.role == "super_admin"
        or await db.scalar(
            select(CategoryHumanAdmin.id).where(
                CategoryHumanAdmin.category_id == post.category_id,
                CategoryHumanAdmin.user_id == user.id,
            )
        )
        is not None
    ):
        stmt = stmt.where(Reply.status.in_(["published", "pending_review"]))
    else:
        stmt = stmt.where(Reply.status == "published")
    rows = list(await db.scalars(stmt.order_by(Reply.created_at.asc())))
    return [await _reply_to_out(db, r, user) for r in rows]


@router.post("/posts/{post_id}/replies", response_model=ReplyOut)
async def create_reply(
    post_id: int, body: ReplyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await check_rate(f"rl:reply:user:{user.id}", 12, 60, "回复过于频繁，请稍后再试")
    post = await db.get(Post, post_id)
    if not post or post.status != "published" or post.deleted_at is not None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.locked:
        raise HTTPException(status_code=403, detail="帖子已锁定，禁止回复")
    if body.parent_reply_id:
        parent = await db.get(Reply, body.parent_reply_id)
        if not parent or parent.post_id != post_id:
            raise HTTPException(status_code=400, detail="父回复不存在")

    reply = Reply(
        post_id=post_id, parent_reply_id=body.parent_reply_id,
        author_id=user.id, author_type="user", body_md=body.body_md,
        status="published",
        attachments=[a.model_dump() for a in (body.attachments or [])][:20],
    )
    db.add(reply)
    post.reply_count += 1
    await db.commit()
    await db.refresh(reply)

    # 回帖触发合规审查（worker 异步）；注意 reply 类型需传 reply.id（流水线按 reply.id 取目标）
    from app.tasks.worker import enqueue

    try:
        await enqueue("run_pipeline_task", reply.id, "reply")
    except Exception:
        from app.agent.runner import trigger_pipeline

        await trigger_pipeline(db, reply.id, "reply")

    # 通知楼主
    if post.author_id != user.id:
        await notify(db, post.author_id, "reply", f"{user.name} 回复了你的帖子", reply.body_md[:200], f"/post/{post_id}")

    # 奖励：回帖
    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "reply_create", "reply", reply.id)
    except Exception:
        pass
    return await _reply_to_out(db, reply, user)


@router.post("/posts/{post_id}/like")
async def like_post(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import AuditLog

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    existing = await db.scalar(
        select(AuditLog.id).where(
            AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
            AuditLog.action == "like_post", AuditLog.target_id == post_id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="已点赞")
    db.add(AuditLog(actor_type="user", actor_id=user.id, action="like_post", target_type="post", target_id=post_id))
    post.like_count += 1
    await db.commit()

    # 奖励：点赞人 + 被点赞作者
    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "like_given", "post", post_id)
        if post.author_id != user.id:
            await grant_ticket(db, post.author_id, "like_received", "post", post_id)
    except Exception:
        pass
    return {"like_count": post.like_count}


@router.post("/posts/{post_id}/unlike")
async def unlike_post(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import AuditLog

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    log = await db.scalar(
        select(AuditLog).where(
            AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
            AuditLog.action == "like_post", AuditLog.target_id == post_id,
        )
    )
    if log:
        await db.delete(log)
        post.like_count = max(0, post.like_count - 1)
        await db.commit()
    return {"like_count": post.like_count}


@router.post("/replies/{reply_id}/like")
async def like_reply(reply_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import AuditLog

    reply = await db.get(Reply, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="回复不存在")
    existing = await db.scalar(
        select(AuditLog.id).where(
            AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
            AuditLog.action == "like_reply", AuditLog.target_id == reply_id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="已点赞")
    db.add(AuditLog(actor_type="user", actor_id=user.id, action="like_reply", target_type="reply", target_id=reply_id))
    reply.like_count += 1
    await db.commit()

    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "like_given", "reply", reply_id)
        if reply.author_id != user.id:
            await grant_ticket(db, reply.author_id, "like_received", "reply", reply_id)
    except Exception:
        pass
    return {"like_count": reply.like_count}


@router.post("/posts/{post_id}/subscribe")
async def subscribe_category(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    existing = await db.scalar(
        select(Subscription.id).where(
            Subscription.user_id == user.id, Subscription.category_id == post.category_id, Subscription.tag.is_(None)
        )
    )
    if not existing:
        db.add(Subscription(user_id=user.id, category_id=post.category_id))
        await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/unsubscribe")
async def unsubscribe_category(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id, Subscription.category_id == post.category_id, Subscription.tag.is_(None)
        )
    )
    if sub:
        await db.delete(sub)
        await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/report")
async def report_post(post_id: int, reason: str = Query(min_length=1), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import Report

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    db.add(Report(reporter_id=user.id, target_type="post", target_id=post_id, reason=reason))
    await db.commit()
    return {"ok": True}


@router.post("/replies/{reply_id}/report")
async def report_reply(reply_id: int, reason: str = Query(min_length=1), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import Report

    reply = await db.get(Reply, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="回复不存在")
    db.add(Report(reporter_id=user.id, target_type="reply", target_id=reply_id, reason=reason))
    await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/solved")
async def mark_solved(post_id: int, solved: bool = Query(True), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="只有楼主可以标记已解决")
    post.is_solved = solved
    await db.commit()
    return {"is_solved": post.is_solved}


@router.get("/search")
async def search(
    q: str = Query(min_length=1),
    category_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """搜索：jieba 中文分词 + 多词模糊匹配（默认，跨环境一致）；
    zhparser 全文检索仅在配置 fulltext_mode=zhparser 且数据库已装扩展时启用。"""
    from sqlalchemy import text as sa_text

    from app.config import settings

    if request:
        await check_rate(f"rl:search:ip:{client_ip(request)}", 30, 60, "搜索过于频繁，请稍后再试")

    stmt = select(Post).where(Post.status == "published", Post.deleted_at.is_(None))

    use_zhparser = False
    if settings.fulltext_mode == "zhparser":
        try:
            has_zh = await db.scalar(sa_text("SELECT 1 FROM pg_extension WHERE extname = 'zhparser'"))
            use_zhparser = bool(has_zh)
        except Exception:
            use_zhparser = False

    if use_zhparser:
        stmt = stmt.where(
            sa_text("posts.title @@ plainto_tsquery('zh', :q) OR posts.body_md @@ plainto_tsquery('zh', :q)").bindparams(q=q)
        )
    else:
        # jieba 分词：query -> 词列表，所有词（AND）命中标题或正文
        import jieba

        tokens = [t.strip() for t in jieba.lcut(q) if t.strip()]
        if not tokens:
            tokens = [q]
        conds = [or_(Post.title.ilike(f"%{t}%"), Post.body_md.ilike(f"%{t}%")) for t in tokens]
        stmt = stmt.where(and_(*conds))

    if category_id:
        stmt = stmt.where(Post.category_id == category_id)
    stmt = stmt.order_by(Post.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    items = [await _post_to_out(db, p, None) for p in rows]
    return PostListOut(total=total or 0, items=items)
