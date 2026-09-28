"""帖子发布审核任务：异步 AI 审核 → 通过后发布并触发 AI 回复流水线 / 不通过置 rejected。"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, CategoryHumanAdmin, Post, User
from app.services.audit_service import audit
from app.services.compliance_service import compliance_check, relevance_check
from app.services.notify_service import notify

logger = logging.getLogger(__name__)


async def review_post(db: AsyncSession, post_id: int) -> str:
    """审核帖子（发帖后异步执行，AI 审核与 AI 回复分两次调用）。

    - 通过（pass && severity=low && 相关性通过）→ status=published，触发 AI 回复流水线
    - 不通过 / AI 异常 / 输出非法 → status=rejected，通知管理员处理
    返回 "published" / "rejected" / "review"。
    """
    post = await db.get(Post, post_id)
    if not post or post.deleted_at is not None:
        return "gone"
    if post.status != "pending_review":
        return post.status

    trace_id = uuid.uuid4().hex[:16]
    content = f"{post.title}\n{post.body_md}"[:8000]
    result = await compliance_check(db, content, post.id, trace_id)

    passed = bool(result.get("pass", False))
    severity = result.get("severity", "mid")
    reason = str(result.get("reason", ""))[:300]

    # ① 主题相关性审核（栏目开启时）：不相关直接拒绝发布
    relevance_passed = True
    relevance_reason = ""
    category = await db.get(Category, post.category_id)
    if category and category.relevance_check_enabled:
        rel = await relevance_check(
            db, category.name, category.description, content, post.id, trace_id,
        )
        relevance_passed = bool(rel.get("pass", False))
        relevance_reason = str(rel.get("reason", ""))[:200]
        if not relevance_passed:
            reason = f"与栏目「{category.name}」主题不相关：{relevance_reason}"
            passed = False
            severity = "high" if severity == "low" else severity

    if passed and severity == "low":
        post.status = "published"
        post.human_needed = False
        post.review_reason = None
        await db.commit()
        await audit(db, "ai_agent", None, "post_approved", "post", post.id, {"reason": reason})

        # 第二次 AI 调用：AI 管理员自动回复（worker 异步执行）
        from app.tasks.worker import enqueue

        try:
            await enqueue("run_pipeline_task", post.id, "post")
        except Exception:
            from app.agent.runner import trigger_pipeline

            await trigger_pipeline(db, post.id, "post")
        return "published"

    # 不通过 / AI 异常 / 非法输出 → rejected（管理员可在后台处理：通过或删除）
    post.status = "rejected"
    post.human_needed = True
    post.review_reason = reason or "内容未通过 AI 审核"
    await db.commit()
    await audit(db, "ai_agent", None, "post_rejected", "post", post.id, {"reason": reason, "severity": severity})

    # 通知栏目人类管理员处理
    admin_ids = list(
        await db.scalars(select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == post.category_id))
    )
    if admin_ids:
        await notify(
            db, admin_ids[0], "review_status", "帖子未通过 AI 审核，待人工处理",
            f"《{post.title[:60]}》\n原因：{reason}",
            f"/admin?tab=reviews",
        )
    return "rejected"
