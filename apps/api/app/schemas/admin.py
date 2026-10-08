"""Pydantic schemas：管理侧（模型配置/知识库/资讯源/审核/审计）。"""
from datetime import datetime

from pydantic import BaseModel
from typing import Literal
from app.schemas.sso_options import OAuthOptions


# ---------- 模型配置 ----------
class ModelConfigIn(BaseModel):
    name: str
    provider: str = "openai_compatible"
    base_url: str
    api_key: str | None = None  # 回填时若为空则保持原值
    chat_model: str
    embedding_model: str | None = None
    embedding_dim: int = 2048
    context_length: int = 128000
    max_tokens: int = 2048
    is_default: bool = False
    enabled: bool = True


class ModelConfigOut(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str
    chat_model: str
    embedding_model: str | None
    embedding_dim: int
    context_length: int
    max_tokens: int
    is_default: bool
    enabled: bool
    created_at: datetime
    has_api_key: bool = False  # 是否已配置 Key（不回传明文）

    model_config = {"from_attributes": True}


# ---------- 知识库 ----------
class RagDocumentOut(BaseModel):
    id: int
    category_id: int
    filename: str
    file_type: str
    status: str
    chunk_count: int
    enabled: bool
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RagChunkOut(BaseModel):
    id: int
    chunk_index: int
    title: str | None
    content: str
    meta_data: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 资讯源 ----------
class NewsSourceIn(BaseModel):
    name: str
    type: str = "rss"  # rss / rsshub / api / manual
    url: str
    target_category_id: int | None = None
    enabled: bool = True
    fetch_cron: str | None = None
    config: dict | None = None


class NewsSourceOut(BaseModel):
    id: int
    name: str
    type: str
    url: str
    target_category_id: int | None
    enabled: bool
    fetch_cron: str | None
    config: dict | None = None
    last_fetched_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 审核 ----------
class ReviewItemOut(BaseModel):
    kind: str  # post_mid / reply_low_conf / report
    id: int
    title: str | None = None
    body: str | None = None
    author_name: str | None = None
    created_at: datetime | None = None
    reason: str | None = None
    score: float | None = None
    target_id: int | None = None
    target_type: str | None = None


class ReviewAction(BaseModel):
    action: str  # approve / hide / delete / warn / dismiss
    resolution: str | None = None


# ---------- 审计 ----------
class AuditLogOut(BaseModel):
    id: int
    actor_type: str
    actor_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    detail: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRunOut(BaseModel):
    id: int
    trace_id: str
    trigger_type: str
    post_id: int | None
    category_id: int | None
    ai_admin_id: int | None
    node: str
    decision: str | None
    score: float | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 站点配置 ----------
class SiteConfigIn(BaseModel):
    site_name: str | None = None
    site_description: str | None = None
    mcp_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    invite_expire_days: int | None = None
    upload_allowed_types: str | None = None   # 逗号分隔，如 "png,jpg,pdf"
    upload_max_size_mb: int | None = None     # 单文件大小上限 MB
    review_prompt: str | None = None          # AI 内容审核提示词（后台可编辑）
    logo_url: str | None = None               # 站点 LOGO 图片 URL


class StatsOut(BaseModel):
    user_count: int
    post_count: int
    reply_count: int
    today_posts: int
    pending_reviews: int
    open_reports: int
    ai_replies: int
    doc_count: int


# ---------- SSO（企业统一身份登录） ----------
class SsoConfigIn(BaseModel):
    protocol: Literal["oidc", "oauth2"] | None = None
    oauth_options: OAuthOptions | None = None
    enabled: bool = False
    label: str | None = None
    issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None  # 回填时为空则保持原值
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_uri: str | None = None
    userinfo_endpoint: str | None = None
    scopes: str | None = None
    bind_rule: str | None = None
    auto_provision: bool = True
    extract_employee: bool = True
    claim_sub: str | None = None
    claim_email: str | None = None
    claim_name: str | None = None


class SsoConfigOut(BaseModel):
    oauth_options: OAuthOptions
    id: int
    enabled: bool
    label: str
    protocol: str
    issuer: str | None
    client_id: str
    has_client_secret: bool  # 是否已配置（不回传明文）
    authorization_endpoint: str | None
    token_endpoint: str | None
    jwks_uri: str | None
    userinfo_endpoint: str | None
    scopes: str
    bind_rule: str
    auto_provision: bool
    extract_employee: bool
    claim_sub: str
    claim_email: str
    claim_name: str
    redirect_uri: str  # 回调地址（由 PUBLIC_BASE_URL 自动生成，客户 IDP 需配置）
    updated_at: datetime

    model_config = {"from_attributes": True}


class SsoTestOut(BaseModel):
    ok: bool
    message: str
    details: dict | None = None
