"""帖子与回复模型。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

PostType = Enum("discussion", "question", "announcement", "news", name="post_type")
PostStatus = Enum("draft", "pending_review", "rejected", "published", "hidden", "deleted", name="post_status")
ReplyAuthorType = Enum("user", "ai_admin", "official", name="reply_author_type")
ReplyStatus = Enum("published", "pending_review", "hidden", "deleted", name="reply_status")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    body_md: Mapped[str] = mapped_column(Text)
    post_type: Mapped[str] = mapped_column(PostType, default="discussion", server_default="discussion")
    status: Mapped[str] = mapped_column(PostStatus, default="published", server_default="published")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_solved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list, server_default="{}")
    attachments: Mapped[list | None] = mapped_column(JSONB, default=list, server_default="[]")  # [{"name","url","size","type"}]
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    like_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reply_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_handled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    human_needed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    parent_reply_id: Mapped[int | None] = mapped_column(ForeignKey("replies.id"), nullable=True)  # 二级嵌套
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    author_type: Mapped[str] = mapped_column(ReplyAuthorType, default="user", server_default="user")
    ai_admin_id: Mapped[int | None] = mapped_column(ForeignKey("category_ai_admins.id"), nullable=True)
    body_md: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ReplyStatus, default="published", server_default="published")
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{"doc_id":1,"chunk":12,"title":"...","content":"..."}]
    attachments: Mapped[list | None] = mapped_column(JSONB, default=list, server_default="[]")  # [{"name","url","size","type"}]
    like_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
