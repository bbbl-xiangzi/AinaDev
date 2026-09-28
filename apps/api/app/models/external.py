"""外部 Agent 回帖源（Dify / HiAgent / OpenAI 兼容 / 自定义 HTTP）。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ExternalAgent(Base):
    """栏目可绑定的第三方 Agent，用于替代内置 AI 管理员自动回帖。"""

    __tablename__ = "external_agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # openai_compatible / dify_chatflow / dify_workflow / custom_http
    protocol: Mapped[str] = mapped_column(String(32), default="openai_compatible", server_default="openai_compatible")
    api_url: Mapped[str] = mapped_column(String(500))          # 完整 endpoint（含版本前缀）
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # AES 加密
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)  # openai_compatible 用
    headers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 附加请求头
    request_template: Mapped[str | None] = mapped_column(Text, nullable=True)  # custom_http 请求体模板
    response_path: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 从响应提取回复文本，如 data.outputs.text
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
