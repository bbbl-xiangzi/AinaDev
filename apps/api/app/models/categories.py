"""栏目与管理员模型。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)  # emoji
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    allow_post: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 发帖权限：public=所有成员可发 / staff_only=仅管理员或栏目管理员 / closed=仅系统/Agent
    post_permission: Mapped[str] = mapped_column(String(20), default="public", server_default="public")
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    reply_threshold: Mapped[float] = mapped_column(Float, default=0.7, server_default="0.7")
    notify_human_on_no_evidence: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    external_agent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_check_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reply_to_author_questions: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CategoryHumanAdmin(Base):
    __tablename__ = "category_human_admins"
    __table_args__ = (UniqueConstraint("category_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CategoryAiAdmin(Base):
    """栏目 AI 管理员：绑定一个 agent 类型账号 + 独立模型与 RAG 挂载。"""

    __tablename__ = "category_ai_admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 对应用户账号（agent 类型，不可登录）
    persona_name: Mapped[str] = mapped_column(String(100))
    persona_avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("model_configs.id"), nullable=True)  # 空=系统默认
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    reply_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)  # 空=用栏目阈值
    self_review_threshold: Mapped[float] = mapped_column(Float, default=0.6, server_default="0.6")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
