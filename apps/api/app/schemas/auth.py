"""Pydantic schemas：认证与用户。"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------- 认证 ----------
class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshIn(BaseModel):
    refresh_token: str


# ---------- 用户 ----------
class UserOut(BaseModel):
    id: int
    email: str
    name: str
    avatar_url: str | None
    account_type: str
    role: str
    status: str
    org_id: str | None
    department: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserAdminUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    status: str | None = None
    department: str | None = None
    org_id: str | None = None


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    department: str | None = Field(default=None, max_length=100)
    org_id: str | None = Field(default=None, max_length=100)
    # 员工扩展信息（SSO 抽取后可自行修改）
    employee_no: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    org_path: str | None = Field(default=None, max_length=500)
    mobile: str | None = Field(default=None, max_length=50)
    gender: str | None = Field(default=None, max_length=20)
    birth_date: str | None = Field(default=None, max_length=20)
    join_date: str | None = Field(default=None, max_length=20)
    manager: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    employee_type: str | None = Field(default=None, max_length=50)
    job_level: str | None = Field(default=None, max_length=50)
    cost_center: str | None = Field(default=None, max_length=100)
    # 自定义字段值（key=字段定义 field_key，仅启用的自定义字段会被写入）
    extras: dict | None = None


class EmployeeFieldDefIn(BaseModel):
    """新增自定义员工字段。"""
    field_name: str = Field(min_length=1, max_length=100)
    input_type: str = "text"  # text / date / number
    hint: str | None = Field(default=None, max_length=200)


class EmployeeFieldDefPatch(BaseModel):
    field_name: str | None = Field(default=None, min_length=1, max_length=100)
    input_type: str | None = None
    enabled: bool | None = None
    user_editable: bool | None = None
    hint: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None


class EmployeeFieldDefOut(BaseModel):
    """员工字段定义（后台字段配置 + 个人中心动态渲染共用）。"""
    id: int
    model_config = {"from_attributes": True}
    field_key: str
    field_name: str
    target: str  # user / employee / custom
    input_type: str
    builtin: bool
    enabled: bool
    user_editable: bool
    claim_key: str | None
    hint: str | None
    sort_order: int


class EmployeeOut(BaseModel):
    """员工扩展信息（个人中心展示/编辑）。"""

    sso_sub: str | None = None
    employee_no: str | None = None
    position: str | None = None
    org_path: str | None = None
    mobile: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    join_date: str | None = None
    manager: str | None = None
    location: str | None = None
    employee_type: str | None = None
    job_level: str | None = None
    cost_center: str | None = None
    extras: dict | None = None
    raw_claims: dict | None = None
    source: str = "manual"


class SsoStatusOut(BaseModel):
    """前台登录页：是否启用企业统一身份登录（不回传任何敏感配置）。"""

    enabled: bool = False
    label: str = "企业统一身份登录"


class PublicUserOut(BaseModel):
    """公开用户主页（含统计；is_following 需登录态）。"""

    id: int
    name: str
    avatar_url: str | None
    account_type: str
    role: str
    department: str | None
    org_id: str | None
    position: str | None = None  # 员工扩展：职位
    created_at: datetime
    post_count: int = 0
    reply_count: int = 0
    like_received: int = 0
    follower_count: int = 0
    following_count: int = 0
    is_following: bool = False
    is_self: bool = False


class UserBriefOut(BaseModel):
    """用户摘要（关注/粉丝列表项）。"""

    id: int
    name: str
    avatar_url: str | None
    account_type: str
    department: str | None
    created_at: datetime


# ---------- 邀请码 ----------
class InviteCreate(BaseModel):
    email: str | None = None
    note: str | None = None


class InviteOut(BaseModel):
    id: int
    code: str
    email: str | None
    used_by: int | None
    used_at: datetime | None
    expires_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
