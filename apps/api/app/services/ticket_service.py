"""Ticket 奖励发放服务。"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TicketConfig, TicketTransaction, User, UserTicket

# 默认奖励方案（运营经验）：新建库时种子数据
DEFAULT_TICKET_RULES = [
    # (action_key, 名称, 奖励, 每日上限, 说明)
    ("register", "新用户注册", "5.0", 0, "完成注册一次性奖励"),
    ("daily_login", "每日首次登录", "0.5", 1, "每天首次访问社区"),
    ("post_create", "发表新帖", "2.0", 5, "每篇帖子，每日最多计 5 篇"),
    ("reply_create", "发表回复", "0.5", 20, "每条回复，每日最多计 20 条"),
    ("like_given", "点赞他人", "0.1", 10, "点赞别人内容，每日最多计 10 次"),
    ("like_received", "收到点赞", "0.3", 20, "自己帖子/回复被点赞"),
    ("post_solved", "帖子被标记已解决", "3.0", 0, "帖子被提问者标记为已解决"),
    ("post_featured", "帖子被加精/推荐", "5.0", 0, "管理员手动加精"),
    ("daily_read", "每日阅读", "0.1", 1, "每日首次阅读帖子（签到性质）"),
]


async def seed_default_tickets(db: AsyncSession) -> None:
    """首次启动时写入默认奖励配置（不覆盖已有）。"""
    for key, name, reward, cap, desc in DEFAULT_TICKET_RULES:
        existing = await db.get(TicketConfig, key)
        if existing:
            continue
        db.add(TicketConfig(
            action_key=key, action_name=name,
            reward=Decimal(reward), daily_cap=cap, description=desc,
        ))
    await db.commit()


async def get_or_create_wallet(db: AsyncSession, user_id: int) -> UserTicket:
    w = await db.get(UserTicket, user_id)
    if not w:
        w = UserTicket(user_id=user_id, balance=Decimal("0"), total_earned=Decimal("0"))
        db.add(w)
        await db.flush()
    return w


async def grant(
    db: AsyncSession,
    user_id: int,
    action_key: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    note: str | None = None,
) -> Decimal:
    """按 action 配置发放 ticket。已达每日上限则跳过。"""
    cfg = await db.get(TicketConfig, action_key)
    if not cfg or not cfg.enabled:
        return Decimal("0")
    if cfg.reward <= 0:
        return Decimal("0")

    # 每日上限检查
    if cfg.daily_cap and cfg.daily_cap > 0:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cnt = await db.scalar(
            select(func.count(TicketTransaction.id)).where(
                TicketTransaction.user_id == user_id,
                TicketTransaction.action_key == action_key,
                TicketTransaction.created_at >= today_start,
            )
        ) or 0
        if cnt >= cfg.daily_cap:
            return Decimal("0")

    wallet = await get_or_create_wallet(db, user_id)
    wallet.balance = (wallet.balance + cfg.reward).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if cfg.reward > 0:
        wallet.total_earned = (wallet.total_earned + cfg.reward).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    db.add(TicketTransaction(
        user_id=user_id, amount=cfg.reward, action_key=action_key,
        ref_type=ref_type, ref_id=ref_id, note=note or cfg.action_name,
    ))
    await db.commit()
    return cfg.reward
