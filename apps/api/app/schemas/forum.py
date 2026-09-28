"""Pydantic schemas：栏目 / 帖子 / 回复。"""
from datetime import datetime

from pydantic import BaseModel, Field


# ---------- 栏目 ----------
class CategoryIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{2,64}$")
    name: str
    description: str | None = None
    icon: str | None = None
    sort_order: int = 0
    allow_post: bool = True
    post_permission: str = "public"  # public | staff_only | closed
    auto_reply_enabled: bool = True
    reply_threshold: float = 0.7
    notify_human_on_no_evidence: bool = True
    external_agent_id: int | None = None
    relevance_check_enabled: bool = False
    reply_to_author_questions: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    sort_order: int | None = None
    allow_post: bool | None = None
    post_permission: str | None = None
    auto_reply_enabled: bool | None = None
    reply_threshold: float | None = None
    notify_human_on_no_evidence: bool | None = None
    external_agent_id: int | None = None
    relevance_check_enabled: bool | None = None
    reply_to_author_questions: bool | None = None


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    icon: str | None
    sort_order: int
    allow_post: bool
    post_permission: str = "public"
    auto_reply_enabled: bool
    reply_threshold: float
    notify_human_on_no_evidence: bool
    external_agent_id: int | None = None
    relevance_check_enabled: bool = False
    reply_to_author_questions: bool = False
    external_agent_name: str | None = None
    post_count: int = 0
    is_subscribed: bool = False
    ai_admin: "AiAdminBrief | None" = None

    model_config = {"from_attributes": True}


class AiAdminBrief(BaseModel):
    id: int
    persona_name: str
    persona_avatar: str | None
    active: bool

    model_config = {"from_attributes": True}


class HumanAdminOut(BaseModel):
    user_id: int
    name: str
    email: str

    model_config = {"from_attributes": True}


class AiAdminIn(BaseModel):
    persona_name: str
    persona_avatar: str | None = None
    system_prompt: str | None = None
    style_prompt: str | None = None
    model_config_id: int | None = None
    auto_reply_enabled: bool = True
    reply_threshold: float | None = None
    self_review_threshold: float = 0.6
    active: bool = True


class AiAdminOut(BaseModel):
    id: int
    category_id: int
    user_id: int
    persona_name: str
    persona_avatar: str | None
    system_prompt: str | None
    style_prompt: str | None
    model_config_id: int | None
    auto_reply_enabled: bool
    reply_threshold: float | None
    self_review_threshold: float
    active: bool

    model_config = {"from_attributes": True}


# ---------- 外部 Agent 回帖源 ----------
class ExternalAgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    protocol: str = "openai_compatible"  # openai_compatible / dify_chatflow / dify_workflow / custom_http
    api_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = None  # 回填为空则保持原值
    model: str | None = None
    headers_json: dict | None = None
    request_template: str | None = None
    response_path: str | None = None
    timeout_seconds: int = 60
    enabled: bool = True


class ExternalAgentOut(BaseModel):
    id: int
    name: str
    protocol: str
    api_url: str
    model: str | None
    headers_json: dict | None
    request_template: str | None
    response_path: str | None
    timeout_seconds: int
    enabled: bool
    has_api_key: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 附件 ----------
class AttachmentItem(BaseModel):
    name: str
    url: str
    size: int = 0
    type: str = "file"  # image / document / archive / other


# ---------- 帖子 ----------
class PostIn(BaseModel):
    category_id: int
    title: str = Field(min_length=1, max_length=300)
    body_md: str = Field(min_length=1)
    post_type: str = "discussion"
    tags: list[str] = []
    at_ai: bool = False  # @ 栏目 AI 管理员
    attachments: list[AttachmentItem] = []


class PostOut(BaseModel):
    id: int
    category_id: int
    category_name: str | None = None
    author_id: int
    author_name: str | None = None
    author_avatar: str | None = None
    author_type: str = "human"
    title: str
    body_md: str
    post_type: str
    status: str
    pinned: bool
    featured: bool
    locked: bool
    is_solved: bool
    tags: list[str]
    attachments: list[AttachmentItem] = []
    view_count: int
    like_count: int
    reply_count: int
    ai_handled: bool
    human_needed: bool
    review_reason: str | None = None  # 审核不通过原因（仅作者/管理员可见）
    created_at: datetime
    updated_at: datetime
    is_liked: bool = False
    is_subscribed: bool = False

    model_config = {"from_attributes": True}


class PostListOut(BaseModel):
    total: int
    items: list[PostOut]


class PostModerate(BaseModel):
    """管理操作：置顶/加精/锁定/移动/软删/恢复/合并/编辑。"""

    action: str  # pin / unpin / feature / unfeature / lock / unlock / move / delete / restore / edit / merge
    category_id: int | None = None
    title: str | None = None
    body_md: str | None = None
    merge_into_post_id: int | None = None


class ReplyIn(BaseModel):
    post_id: int
    parent_reply_id: int | None = None
    body_md: str = Field(min_length=1)
    at_ai: bool = False
    attachments: list[AttachmentItem] = []


class ReplyOut(BaseModel):
    id: int
    post_id: int
    parent_reply_id: int | None
    author_id: int
    author_name: str | None = None
    author_avatar: str | None = None
    author_type: str
    body_md: str
    status: str
    citations: list | None
    attachments: list[AttachmentItem] = []
    review_reason: str | None = None  # 审核不通过原因
    like_count: int
    created_at: datetime
    is_liked: bool = False

    model_config = {"from_attributes": True}


class SearchQuery(BaseModel):
    q: str = Field(min_length=1, max_length=200)
    category_id: int | None = None
    page: int = 1
    page_size: int = 20
