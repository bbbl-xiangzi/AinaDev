"""管理：审核队列（合规中危帖 / 低置信 AI 回帖 / 用户举报）+ 帖子管理操作。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_super_admin
from app.models import CategoryHumanAdmin, Post, Reply, Report, User
from app.schemas import ReviewAction, ReviewItemOut
from app.services.audit_service import audit

router = APIRouter(prefix="/api/admin", tags=["admin-reviews"])


async def _can_manage(db: AsyncSession, user: User, category_id: int) -> bool:
    if user.role == "super_admin":
        return True
    return await db.scalar(
        select(CategoryHumanAdmin.id).where(
            CategoryHumanAdmin.category_id == category_id, CategoryHumanAdmin.user_id == user.id
        )
    ) is not None


@router.get("/reviews", response_model=list[ReviewItemOut])
async def review_queue(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items: list[ReviewItemOut] = []

    # 0) AI 审核不通过的帖子（rejected，待人工处理：通过或删除）
    rejected = list(await db.scalars(select(Post).where(Post.status == "rejected", Post.deleted_at.is_(None)).order_by(Post.created_at.asc())))
    for p in rejected:
        if not await _can_manage(db, user, p.category_id):
            continue
        author = await db.get(User, p.author_id)
        items.append(
            ReviewItemOut(
                kind="post_rejected", id=p.id, title=p.title, body=p.body_md[:500],
                author_name=author.name if author else None, created_at=p.created_at,
                reason="AI 审核不通过，待人工处理",
            )
        )

    # 1) 合规中危帖（pending_review）
    posts = list(await db.scalars(select(Post).where(Post.status == "pending_review", Post.deleted_at.is_(None)).order_by(Post.created_at.asc())))
    for p in posts:
        if not await _can_manage(db, user, p.category_id):
            continue
        author = await db.get(User, p.author_id)
        items.append(
            ReviewItemOut(
                kind="post_mid", id=p.id, title=p.title, body=p.body_md[:500],
                author_name=author.name if author else None, created_at=p.created_at,
                reason="合规中危，待人工审核",
            )
        )

    # 2) 待审 AI/外部回复（pending_review：内置 AI 低置信 / 外部 Agent 回复未通过审核）
    replies = list(
        await db.scalars(
            select(Reply).where(Reply.status == "pending_review", Reply.deleted_at.is_(None)).order_by(Reply.created_at.asc())
        )
    )
    for r in replies:
        post = await db.get(Post, r.post_id)
        if not post or not await _can_manage(db, user, post.category_id):
            continue
        author = await db.get(User, r.author_id)
        reason = r.review_reason or "AI 自检低置信，待人工放行"
        items.append(
            ReviewItemOut(
                kind="reply_low_conf", id=r.id, target_id=r.post_id, target_type="reply",
                title=f"AI 回复待审（帖子：{post.title[:60]}）", body=r.body_md[:500],
                author_name=author.name if author else None, created_at=r.created_at,
                reason=reason,
            )
        )

    # 3) 用户举报
    reports = list(await db.scalars(select(Report).where(Report.status == "open").order_by(Report.created_at.asc())))
    for rep in reports:
        if rep.target_type == "post":
            post = await db.get(Post, rep.target_id)
            if not post or not await _can_manage(db, user, post.category_id):
                continue
            items.append(
                ReviewItemOut(
                    kind="report", id=rep.id, target_id=rep.target_id, target_type="post",
                    title=f"举报帖子：{post.title[:60]}", body=rep.reason,
                    created_at=rep.created_at, reason=f"举报人 #{rep.reporter_id}",
                )
            )
        else:
            reply = await db.get(Reply, rep.target_id)
            if not reply:
                continue
            post = await db.get(Post, reply.post_id)
            if not post or not await _can_manage(db, user, post.category_id):
                continue
            items.append(
                ReviewItemOut(
                    kind="report", id=rep.id, target_id=rep.target_id, target_type="reply",
                    title=f"举报回复（帖子：{post.title[:50]}）", body=rep.reason,
                    created_at=rep.created_at, reason=f"举报人 #{rep.reporter_id}",
                )
            )
    return items


@router.post("/reviews/action")
async def review_action(
    kind: str, id: int, body: ReviewAction,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """kind: post_rejected / post_mid / reply_low_conf / report；action: approve/hide/delete/warn/dismiss。"""
    if kind == "post_rejected":
        # AI 审核不通过的帖子：人工通过（发布并触发 AI 回复）或删除
        post = await db.get(Post, id)
        if not post or not await _can_manage(db, user, post.category_id):
            raise HTTPException(status_code=403, detail="无权操作该栏目")
        if body.action == "approve":
            post.status = "published"
            post.human_needed = False
            await db.commit()
            # 人工放行后触发 AI 回复流水线（异步）
            from app.tasks.worker import enqueue

            try:
                await enqueue("run_pipeline_task", post.id, "post")
            except Exception:
                from app.agent.runner import trigger_pipeline

                await trigger_pipeline(db, post.id, "post")
        elif body.action in ("hide", "delete"):
            post.status = "hidden" if body.action == "hide" else "deleted"
            from datetime import datetime, timezone

            if body.action == "delete":
                post.deleted_at = datetime.now(timezone.utc)
            post.human_needed = True
            await db.commit()
        else:
            raise HTTPException(status_code=400, detail="无效操作")
        await audit(db, "user", user.id, f"review_rejected_{body.action}", "post", id)

    elif kind == "post_mid":
        post = await db.get(Post, id)
        if not post or not await _can_manage(db, user, post.category_id):
            raise HTTPException(status_code=403, detail="无权操作该栏目")
        if body.action == "approve":
            post.status = "published"
        elif body.action in ("hide", "delete"):
            post.status = "hidden" if body.action == "hide" else "deleted"
            post.human_needed = True
        elif body.action == "warn":
            post.status = "published"
        else:
            raise HTTPException(status_code=400, detail="无效操作")
        await db.commit()
        await audit(db, "user", user.id, f"review_post_{body.action}", "post", id)

    elif kind == "reply_low_conf":
        reply = await db.get(Reply, id)
        if not reply:
            raise HTTPException(status_code=404, detail="回复不存在")
        post = await db.get(Post, reply.post_id)
        if not post or not await _can_manage(db, user, post.category_id):
            raise HTTPException(status_code=403, detail="无权操作该栏目")
        if body.action == "approve":
            reply.status = "published"
            reply.review_reason = None
        elif body.action in ("hide", "delete"):
            reply.status = "hidden" if body.action == "hide" else "deleted"
            if body.action == "delete":
                from datetime import datetime, timezone

                reply.deleted_at = datetime.now(timezone.utc)
        else:
            raise HTTPException(status_code=400, detail="无效操作")
        await db.commit()
        await audit(db, "user", user.id, f"review_reply_{body.action}", "reply", id)

    elif kind == "report":
        rep = await db.get(Report, id)
        if not rep:
            raise HTTPException(status_code=404, detail="举报不存在")
        if rep.target_type == "post":
            target = await db.get(Post, rep.target_id)
        else:
            target = await db.get(Reply, rep.target_id)
            target = await db.get(Post, target.post_id) if target else None
        if not target or not await _can_manage(db, user, target.category_id):
            raise HTTPException(status_code=403, detail="无权操作该栏目")
        if body.action == "dismiss":
            rep.status = "dismissed"
        else:
            rep.status = "resolved"
            if body.action in ("hide", "delete"):
                if rep.target_type == "post":
                    t = await db.get(Post, rep.target_id)
                    if t:
                        t.status = "hidden" if body.action == "hide" else "deleted"
                else:
                    t = await db.get(Reply, rep.target_id)
                    if t:
                        t.status = "hidden" if body.action == "hide" else "deleted"
        rep.handler_id = user.id
        rep.resolved_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        rep.resolution = body.resolution or body.action
        await db.commit()
        await audit(db, "user", user.id, f"report_{body.action}", "report", id)

    else:
        raise HTTPException(status_code=400, detail="无效类型")
    return {"ok": True}


# ---------- 帖子管理操作 ----------
@router.post("/posts/{post_id}/moderate")
async def moderate_post(
    post_id: int, action: str,
    category_id: int | None = None,
    merge_into_post_id: int | None = None,
    title: str | None = None,
    body_md: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas import PostModerate

    req = PostModerate(action=action, category_id=category_id, merge_into_post_id=merge_into_post_id, title=title, body_md=body_md)
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if not await _can_manage(db, user, post.category_id):
        raise HTTPException(status_code=403, detail="无权操作该栏目")

    from datetime import datetime, timezone

    if req.action in ("pin", "unpin"):
        post.pinned = req.action == "pin"
    elif req.action in ("feature", "unfeature"):
        post.featured = req.action == "feature"
    elif req.action in ("lock", "unlock"):
        post.locked = req.action == "lock"
    elif req.action == "move":
        if not req.category_id:
            raise HTTPException(status_code=400, detail="缺少目标栏目")
        post.category_id = req.category_id
    elif req.action == "delete":
        post.status = "deleted"
        post.deleted_at = datetime.now(timezone.utc)
    elif req.action == "restore":
        post.status = "published"
        post.deleted_at = None
    elif req.action == "edit":
        if req.title:
            post.title = req.title
        if req.body_md:
            post.body_md = req.body_md
    elif req.action == "merge":
        if not req.merge_into_post_id:
            raise HTTPException(status_code=400, detail="缺少合并目标帖")
        # 把本帖回复迁移到目标帖
        await db.execute(
            __import__("sqlalchemy").update(Reply).where(Reply.post_id == post_id).values(post_id=req.merge_into_post_id)
        )
        target = await db.get(Post, req.merge_into_post_id)
        if target:
            target.reply_count += post.reply_count
        post.status = "deleted"
        post.deleted_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail="无效操作")
    await db.commit()
    await audit(db, "user", user.id, f"post_{req.action}", "post", post_id, {"detail": req.model_dump(exclude_none=True)})
    return {"ok": True}
