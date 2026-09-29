"""SSO（企业统一身份登录）与员工扩展信息模型。

设计：社区 = SP（服务提供方），企业客户应用中台 = IDP（身份提供方）。
采用标准 OIDC 授权码 + PKCE 流程；单租户（一套部署只对接一家企业客户，为每家客户独立部署）。
首登自动开通社区账号（免注册），员工扩展信息由 SSO 带过来的 claims 确定性映射 +
LLM 按事实抽取（杜绝猜测），原始 claims 全量存档可追溯。
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SsoConfig(Base):
    """企业统一身份登录（OIDC）配置。仅启用一条作为当前生效配置。"""

    __tablename__ = "sso_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # 登录页按钮文案，如「企业统一身份登录」
    label: Mapped[str] = mapped_column(String(100), default="企业统一身份登录", server_default="企业统一身份登录")
    # 协议：固定 oidc（授权码 + PKCE + RS256）
    protocol: Mapped[str] = mapped_column(String(20), default="oidc", server_default="oidc")
    # IDP 信息（二选一：填 issuer 自动发现端点；或显式填端点覆盖）
    issuer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_id: Mapped[str] = mapped_column(String(500), default="", server_default="")
    client_secret_encrypted: Mapped[str] = mapped_column(Text, default="", server_default="")  # AES 加密，永不回传明文
    authorization_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    jwks_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    userinfo_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scopes: Mapped[str] = mapped_column(String(200), default="openid profile email", server_default="openid profile email")
    # 绑定规则：email=按邮箱匹配已有账号；sub=按 IDP 唯一标识（存 employee_profiles.sso_sub）匹配
    bind_rule: Mapped[str] = mapped_column(String(20), default="email", server_default="email")
    # 首登自动开通社区账号（免注册）
    auto_provision: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 员工扩展信息：LLM 按事实抽取（有就有、没有留空，杜绝猜测）
    extract_employee: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # claim 字段名映射（不同 IDP claim 命名可能不同，可后台调整）
    claim_sub: Mapped[str] = mapped_column(String(100), default="sub", server_default="sub")
    claim_email: Mapped[str] = mapped_column(String(100), default="email", server_default="email")
    claim_name: Mapped[str] = mapped_column(String(100), default="name", server_default="name")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmployeeFieldDef(Base):
    """员工扩展字段定义（元数据，可配置）。

    字段集合由管理员维护：内置字段（builtin=True）只可停用/改名，不可删除；
    自定义字段（target=custom）由管理员按客户需求新增，值存 EmployeeProfile.extras。
    SSO 登录的 AI 抽取只按 enabled 的字段清单抽取，不会因 claims 而新增字段。
    """

    __tablename__ = "employee_field_defs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 字段标识（内置固定：department/org_id/employee_no/...；自定义自动生成 custom_xx）
    field_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    field_name: Mapped[str] = mapped_column(String(100))  # 中文名，如「成本中心」
    # 值存储目标：user=users 表列（department/org_id）；employee=employee_profiles 固定列；custom=extras(JSONB)
    target: Mapped[str] = mapped_column(String(20), default="employee", server_default="employee")
    input_type: Mapped[str] = mapped_column(String(20), default="text", server_default="text")  # text / date / number
    builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    user_editable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")  # 是否允许用户本人编辑
    # 确定性 claim 映射（逗号分隔候选，按顺序取首个非空）；为空则交给 LLM 按中文名抽取
    claim_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hint: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 占位提示
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmployeeProfile(Base):
    """员工扩展信息：users 的一对一扩展表。

    SSO 首登时由 claims 确定性映射 + LLM 抽取填充；用户可在「我的 - 编辑资料」自行修改。
    raw_claims 全量存档原始 claims，保证可追溯；sso_sub 用于 sub 绑定规则。
    extras 存储管理员新增的自定义字段值。
    """

    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    sso_sub: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)  # IDP 用户唯一标识
    employee_no: Mapped[str | None] = mapped_column(String(100), nullable=True)   # 工号
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)       # 职位
    org_path: Mapped[str | None] = mapped_column(String(500), nullable=True)       # 组织架构路径
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)          # 手机号
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)          # 性别
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)      # 出生日期
    join_date: Mapped[str | None] = mapped_column(String(20), nullable=True)       # 入职日期
    manager: Mapped[str | None] = mapped_column(String(100), nullable=True)        # 直属上级
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)       # 办公地点
    employee_type: Mapped[str | None] = mapped_column(String(50), nullable=True)   # 员工类型
    job_level: Mapped[str | None] = mapped_column(String(50), nullable=True)       # 职级
    cost_center: Mapped[str | None] = mapped_column(String(100), nullable=True)    # 成本中心
    extras: Mapped[dict | None] = mapped_column(JSON, nullable=True)               # 其他自定义字段
    raw_claims: Mapped[dict | None] = mapped_column(JSON, nullable=True)            # 原始 claims 存档（可追溯）
    source: Mapped[str] = mapped_column(String(20), default="sso", server_default="sso")  # sso / manual / admin
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
