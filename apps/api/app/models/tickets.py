"""Ticket（星星⭐）奖励模型。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TicketConfig(Base):
    """每种用户行为对应的奖励配置（管理员可改）。"""
    __tablename__ = "ticket_configs"

    action_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_name: Mapped[str] = mapped_column(String(100))  # 中文展示名
    reward: Mapped[Decimal] = mapped_column(Numeric(10, 1), default=Decimal("0"))  # 0.x 一位小数
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    daily_cap: Mapped[int] = mapped_column(default=0, server_default="0")  # 每日上限次数，0=不限
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserTicket(Base):
    """用户 ticket 余额。"""
    __tablename__ = "user_tickets"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 1), default=Decimal("0"), server_default="0")
    total_earned: Mapped[Decimal] = mapped_column(Numeric(10, 1), default=Decimal("0"), server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TicketTransaction(Base):
    """ticket 流水。"""
    __tablename__ = "ticket_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 1))  # 正=收入，负=支出
    action_key: Mapped[str] = mapped_column(String(64), index=True)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # post/reply/...
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
