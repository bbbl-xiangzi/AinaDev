"""个人中心 + 通知 API。"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import EmployeeProfile, Notification, Post, Reply, Subscription, User
from app.schemas import EmployeeOut, PostListOut, PostOut, ProfileUpdateIn, ReplyOut, UserOut

router = APIRouter(prefix="/api/me", tags=["me"])


async def _post_out(db: AsyncSession, p: Post) -> PostOut:
    from app.api.posts import _post_to_out

    return await _post_to_out(db, p, None)


async def _reply_out(db: AsyncSession, r: Reply) -> ReplyOut:
    from app.api.posts import _reply_to_out

    return await _reply_to_out(db, r, None)


@router.get("/posts", response_model=PostListOut)
async def my_posts(
    page: int = 1, page_size: int = 20,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Post).where(Post.author_id == user.id, Post.deleted_at.is_(None)).order_by(Post.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return PostListOut(total=total or 0, items=[await _post_out(db, p) for p in rows])


@router.get("/replies", response_model=list[ReplyOut])
async def my_replies(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = list(
        await db.scalars(select(Reply).where(Reply.author_id == user.id, Reply.deleted_at.is_(None)).order_by(Reply.created_at.desc()).limit(100))
    )
    return [await _reply_out(db, r) for r in rows]


@router.get("/favorites")
async def my_favorites(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """收藏 = 订阅的栏目新帖（MVP 用 AuditLog 记录帖子点赞为收藏近似）。
    简化实现：返回我订阅栏目下的最新帖。"""
    from app.models import AuditLog, Category

    liked_ids = select(AuditLog.target_id).where(
        AuditLog.actor_type == "user", AuditLog.actor_id == user.id, AuditLog.action == "like_post"
    )
    rows = list(await db.scalars(select(Post).where(Post.id.in_(liked_ids), Post.deleted_at.is_(None)).order_by(Post.created_at.desc()).limit(50)))
    return [await _post_out(db, p) for p in rows]


@router.get("/subscriptions")
async def my_subscriptions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    subs = list(await db.scalars(select(Subscription).where(Subscription.user_id == user.id)))
    return [{"category_id": s.category_id, "tag": s.tag, "created_at": s.created_at} for s in subs]


@router.get("/notifications")
async def my_notifications(
    unread_only: bool = False, page: int = 1, page_size: int = 20,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    unread = await db.scalar(select(func.count()).where(Notification.user_id == user.id, Notification.is_read.is_(False)))
    return {
        "total": total or 0,
        "unread": unread or 0,
        "items": [
            {"id": n.id, "type": n.type, "title": n.title, "body": n.body, "link_url": n.link_url, "is_read": n.is_read, "created_at": n.created_at}
            for n in rows
        ],
    }


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    n = await db.get(Notification, notification_id)
    if n and n.user_id == user.id:
        n.is_read = True
        await db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
async def read_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import update

    await db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    await db.commit()
    return {"ok": True}


@router.get("/tickets")
async def my_tickets(
    page: int = 1, page_size: int = 30,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    from app.models import TicketTransaction, UserTicket
    from app.services.ticket_service import get_or_create_wallet

    wallet = await get_or_create_wallet(db, user.id)
    total = await db.scalar(
        select(func.count(TicketTransaction.id)).where(TicketTransaction.user_id == user.id)
    ) or 0
    rows = list(await db.scalars(
        select(TicketTransaction)
        .where(TicketTransaction.user_id == user.id)
        .order_by(TicketTransaction.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ))
    items = [
        {
            "id": r.id, "amount": float(r.amount), "action_key": r.action_key,
            "note": r.note, "ref_type": r.ref_type, "ref_id": r.ref_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return {
        "balance": float(wallet.balance),
        "total_earned": float(wallet.total_earned),
        "total": total, "items": items,
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in {"png", "jpg", "jpeg", "gif", "webp"}:
        raise HTTPException(status_code=400, detail="仅支持 png/jpg/jpeg/gif/webp 图片")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像不能超过 2MB")
    now = datetime.now(timezone.utc)
    rel_dir = Path(f"avatar/{now:%Y%m}")
    abs_dir = Path(settings.upload_dir).resolve() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}"
    (abs_dir / stored).write_bytes(content)
    user.avatar_url = f"/uploads/{rel_dir.as_posix()}/{stored}"
    await db.commit()
    return {"avatar_url": user.avatar_url}


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑个人资料：昵称 / 部门 / 所属组织 + 员工扩展信息。"""
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="昵称不能为空")
        user.name = body.name.strip()
    if body.department is not None:
        user.department = body.department.strip() or None
    if body.org_id is not None:
        user.org_id = body.org_id.strip() or None

    # 员工扩展信息（SSO 抽取后亦可自行修改）
    employee_fields = {
        "employee_no": body.employee_no, "position": body.position, "org_path": body.org_path,
        "mobile": body.mobile, "gender": body.gender, "birth_date": body.birth_date,
        "join_date": body.join_date, "manager": body.manager, "location": body.location,
        "employee_type": body.employee_type, "job_level": body.job_level, "cost_center": body.cost_center,
    }
    if any(v is not None for v in employee_fields.values()):
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user.id))
        if ep is None:
            ep = EmployeeProfile(user_id=user.id)
            db.add(ep)
        for field, val in employee_fields.items():
            if val is not None:
                setattr(ep, field, val.strip() or None)
        ep.source = ep.source or "manual"

    await db.commit()
    return UserOut.model_validate(user)


@router.get("/employee", response_model=EmployeeOut)
async def my_employee(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """员工扩展信息（SSO 来源或手动编辑，个人中心展示）。"""
    ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user.id))
    if not ep:
        return EmployeeOut()
    return EmployeeOut(
        sso_sub=ep.sso_sub, employee_no=ep.employee_no, position=ep.position, org_path=ep.org_path,
        mobile=ep.mobile, gender=ep.gender, birth_date=ep.birth_date, join_date=ep.join_date,
        manager=ep.manager, location=ep.location, employee_type=ep.employee_type,
        job_level=ep.job_level, cost_center=ep.cost_center, extras=ep.extras,
        raw_claims=ep.raw_claims, source=ep.source,
    )
