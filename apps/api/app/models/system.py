"""系统级模型：模型配置、资讯源、站点配置。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50), default="openai_compatible", server_default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(500))
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="", server_default="")  # AES 加密，永不回传明文
    chat_model: Mapped[str] = mapped_column(String(200))
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding_dim: Mapped[int] = mapped_column(Integer, default=2048, server_default="2048")
    context_length: Mapped[int] = mapped_column(Integer, default=128000, server_default="128000")
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, server_default="2048")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiNewsSource(Base):
    __tablename__ = "ai_news_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="rss")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    url: Mapped[str] = mapped_column(String(1000))
    target_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fetch_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SiteConfig(Base):
    """站点级 key-value 配置（站点名、MCP 开关等，均可后台修改）。"""

    __tablename__ = "site_configs"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
