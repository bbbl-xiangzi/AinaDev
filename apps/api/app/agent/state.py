"""发帖事件流水线状态定义（LangGraph TypedDict）。"""

from typing import TypedDict


class PipelineState(TypedDict):
    # 输入
    post_id: int
    content_type: str  # post / reply
    category_id: int
    author_id: int
    author_name: str | None = None
    title: str
    body: str
    trace_id: str
    # 合规
    compliance_result: dict  # {pass, reason, severity}
    guardrail_done: bool = False  # 评论合规已在 trigger 层执行
    # 路由
    should_reply: bool
    ai_admin_id: int | None
    ai_admin_name: str | None
    # 检索与判定
    chunks: list
    top1_score: float
    # 生成
    generation: str
    self_score: float
    citations: list
    # 决策
    decision: str  # hidden / review / ended / no_evidence / no_answer / pending_review / published
    human_needed: bool
