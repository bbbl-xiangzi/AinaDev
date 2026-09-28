"""认证与用户服务。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models import Invitation, User


class AuthError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def register(db: AsyncSession, email: str, name: str, password: str, invite_code: str) -> User:
    email = email.lower().strip()
    existing = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing:
        raise AuthError("该邮箱已注册")

    inv = await db.scalar(
        select(Invitation).where(
            Invitation.code == invite_code.strip(),
            Invitation.status == "valid",
            Invitation.expires_at > _utcnow(),
        )
    )
    if not inv:
        raise AuthError("邀请码无效或已过期")
    if inv.email and inv.email.lower() != email:
        raise AuthError("该邀请码绑定其他邮箱")

    user = User(
        email=email, name=name, password_hash=hash_password(password),
        account_type="human", role="member", status="active",
    )
    db.add(user)
    await db.flush()

    # 新用户注册奖励
    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "register")
    except Exception:
        pass

    inv.status = "used"
    inv.used_by = user.id
    inv.used_at = _utcnow()
    await db.commit()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(
        select(User).where(User.email == email.lower().strip(), User.deleted_at.is_(None))
    )
    if not user or user.account_type != "human" or not user.password_hash:
        raise AuthError("邮箱或密码错误")
    if user.status == "disabled":
        raise AuthError("账号已被禁用，请联系管理员")
    if not verify_password(password, user.password_hash):
        raise AuthError("邮箱或密码错误")
    user.last_active_at = _utcnow()
    await db.commit()

    # 每日首次登录奖励（每日 1 次）
    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "daily_login")
    except Exception:
        pass
    return user


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }


async def create_invite(db: AsyncSession, admin: User, email: str | None, note: str | None) -> Invitation:
    import secrets

    code = secrets.token_urlsafe(12)[:20]
    inv = Invitation(
        code=code,
        email=email.lower() if email else None,
        created_by=admin.id,
        expires_at=_utcnow() + timedelta(days=settings.invite_expire_days),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


async def create_system_accounts(db: AsyncSession) -> None:
    """初始化系统账号：超管（由环境变量/首次注册）、运维 Agent、官方公告账号。"""
    # 官方公告账号（system）
    if not await db.scalar(select(User).where(User.email == "official@community.local")):
        db.add(User(email="official@community.local", name="官方公告", account_type="system", role="member", status="active"))
    # 运维 Agent 账号（system）
    if not await db.scalar(select(User).where(User.email == "ops-agent@community.local")):
        db.add(User(email="ops-agent@community.local", name="运维助手", account_type="system", role="member", status="active"))
    # 外部回帖 Agent 账号（system，承载外部 Agent 回复）
    if not await db.scalar(select(User).where(User.email == "external-agent@community.local")):
        db.add(User(email="external-agent@community.local", name="外部智能体", account_type="system", role="member", status="active"))
    await db.commit()
