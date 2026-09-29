"""SSO（企业统一身份登录）与员工扩展信息模型。"""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SsoConfig(Base):
    """企业统一身份登录配置（单租户：一套部署只对接一家企业客户 IDP）。"""

    __tablename__ = "sso_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str] = mapped_column(String(100), default="企业统一身份登录")
    protocol: Mapped[str] = mapped_column(String(20), default="oidc")
    issuer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_id: Mapped[str] = mapped_column(String(500), default="")
    client_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # AES 加密
    authorization_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    jwks_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    userinfo_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scopes: Mapped[str] = mapped_column(String(500), default="openid profile email")
    bind_rule: Mapped[str] = mapped_column(String(20), default="email")  # email | sub
    auto_provision: Mapped[bool] = mapped_column(Boolean, default=True)  # 首登自动开通账号
    extract_employee: Mapped[bool] = mapped_column(Boolean, default=True)  # 员工信息 AI 抽取
    claim_sub: Mapped[str] = mapped_column(String(50), default="sub")
    claim_email: Mapped[str] = mapped_column(String(50), default="email")
    claim_name: Mapped[str] = mapped_column(String(50), default="name")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmployeeProfile(Base):
    """员工扩展信息：SSO 同步 / LLM 抽取 / 用户自行编辑。

    确定性强映射优先，映射不到才 LLM 按事实抽取（杜绝猜测）；raw_claims 全量存档可追溯。
    """

    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    sso_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    org_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    join_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extras: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 其它未映射字段
    raw_claims: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # SSO 原始 claims 全量存档
    source: Mapped[str] = mapped_column(String(20), default="manual")  # sso | llm | manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", name="uq_employee_user"),)
