"""Agent 流水线运行入口：供 API / worker / MCP 触发。

支持三种自动回复来源：
- 内置 AI 管理员（RAG + LLM，栏目未绑定外部源时）
- 外部 Agent 回帖源（栏目绑定 external_agent_id 时：Dify / HiAgent / OpenAI 兼容 / 自定义 HTTP）
- 楼主追问评论自动回复（栏目 reply_to_author_questions 开启时，用内置 LLM 判断是否提问）
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import AgentRun, Category, CategoryAiAdmin, CategoryHumanAdmin, ExternalAgent, Post, Reply, User
from app.services.audit_service import audit
from app.services.compliance_service import compliance_check, is_question_check, relevance_check
from app.services.external_agent_service import call_external_agent
from app.services.notify_service import notify

logger = logging.getLogger(__name__)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


async def _first_category_admin(db: AsyncSession, category_id: int) -> User | None:
    """栏目第一个人类管理员（没有则通知超管 1 号）。"""
    uid = await db.scalar(
        select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == category_id).limit(1)
    )
    if uid:
        return await db.get(User, uid)
    admin = await db.scalar(select(User).where(User.role == "super_admin").order_by(User.id.asc()).limit(1))
    return admin


async def _external_reply_flow(state: PipelineState, db: AsyncSession, agent: ExternalAgent) -> None:
    """外部 Agent 回帖闭环：调用 → 生成待审回复 → 审核（违规+相关性）→ 通过发布 / 不通过隐藏+通知管理员。

    外部调用失败时**不回退内置 AI 管理员**，通知管理员人工回复（含失败码/原因）。
    """
    post = await db.get(Post, state["post_id"])
    category = await db.get(Category, state["category_id"])
    if not post or not category:
        return

    ctx = {
        "title": state.get("title", ""),
        "body": state.get("body", ""),
        "author_name": state.get("author_name", ""),
        "category_name": category.name,
    }
    result = await call_external_agent(db, agent, ctx)

    if not result.get("ok"):
        # 外部调用失败：不回退内置 AI；通知管理员人工回复，给出失败码/原因
        error_code = result.get("error_code", "UNKNOWN")
        error_msg = result.get("error_msg", "未知错误")
        post.human_needed = True
        await db.commit()
        admin = await _first_category_admin(db, category.id)
        if admin:
            await notify(
                db, admin.id, "external_agent_fail",
                f"外部回帖源「{agent.name}」调用失败，需人工回复",
                f"帖子《{post.title[:60]}》\n失败码：{error_code}\n原因：{error_msg}\n\n"
                f"请到帖子页面人工回复，并在后台检查外部 Agent 配置（协议/URL/Key/响应路径）。",
                f"/post/{post.id}",
            )
        await audit(
            db, "ai_agent", None, "external_agent_fail", "post", post.id,
            {"agent_id": agent.id, "error_code": error_code, "error_msg": error_msg},
        )
        db.add(
            AgentRun(
                trace_id=state["trace_id"], trigger_type="judge", post_id=post.id,
                category_id=category.id, node="external", decision="failed",
                detail={"error_code": error_code, "error_msg": error_msg},
            )
        )
        await db.commit()
        return

    text = result.get("text", "").strip()
    if not text:
        return

    # 生成待审回复（pending_review，仅楼主/管理员可见）
    agent_user = await db.scalar(select(User).where(User.email == "external-agent@community.local"))
    author_id = agent_user.id if agent_user else 0
    reply = Reply(
        post_id=post.id, author_id=author_id, author_type="ai_admin",
        ai_admin_id=None, body_md=text, status="pending_review",
    )
    db.add(reply)
    await db.flush()

    # 审核外部回复内容（违规 + 栏目相关性）
    content = f"{post.title}\n{text}"[:8000]
    comp = await compliance_check(db, content, post.id, state["trace_id"])
    passed = bool(comp.get("pass", False)) and comp.get("severity", "mid") == "low"
    reason = str(comp.get("reason", ""))[:200]

    if passed and category.relevance_check_enabled:
        rel = await relevance_check(db, category.name, category.description, content, post.id, state["trace_id"])
        if not rel.get("pass", False):
            passed = False
            reason = f"与栏目「{category.name}」主题不相关：{rel.get('reason', '')}"

    if passed:
        reply.status = "published"
        reply.review_reason = None
        post.ai_handled = True
        post.reply_count += 1
        await db.commit()
        await audit(db, "ai_agent", None, "external_reply_published", "post", post.id, {"reply_id": reply.id})
        return

    # 审核不通过：进审核队列（pending_review，不公开，仅楼主/管理员可见）+ 通知管理员人工处理
    reply.status = "pending_review"
    reply.review_reason = reason or "外部回复未通过 AI 审核"
    post.human_needed = True
    await db.commit()
    admin = await _first_category_admin(db, category.id)
    if admin:
        await notify(
            db, admin.id, "review_status",
            f"外部回帖源「{agent.name}」的回复未通过审核，待人工处理",
            f"帖子《{post.title[:60]}》\n原因：{reason}\n\n后台审核队列可「通过并发布」或「删除」。",
            f"/admin?tab=reviews",
        )
    await audit(db, "ai_agent", None, "external_reply_rejected", "post", post.id, {"reply_id": reply.id, "reason": reason})


async def trigger_pipeline(db: AsyncSession, post_id: int, content_type: str = "post") -> str:
    """触发发帖/回帖事件的 AI 流水线。返回 trace_id。"""
    trace_id = new_trace_id()
    author_name = ""
    if content_type == "post":
        post = await db.get(Post, post_id)
        if not post:
            return trace_id
        category_id, author_id, title, body = post.category_id, post.author_id, post.title, post.body_md
        author = await db.get(User, post.author_id)
        author_name = author.name if author else ""
    else:
        reply = await db.get(Reply, post_id)
        if not reply:
            return trace_id
        parent = await db.get(Post, reply.post_id)
        if not parent:
            return trace_id
        category_id, author_id, title, body = parent.category_id, reply.author_id, parent.title, reply.body_md
        author = await db.get(User, reply.author_id)
        author_name = author.name if author else ""

    category = await db.get(Category, category_id)
    cat_name = category.name if category else ""

    state: PipelineState = {
        "post_id": post_id,
        "content_type": content_type,
        "category_id": category_id,
        "author_id": author_id,
        "author_name": author_name,
        "title": title,
        "body": body,
        "trace_id": trace_id,
        "compliance_result": {},
        "guardrail_done": False,
        "should_reply": False,
        "ai_admin_id": None,
        "ai_admin_name": None,
        "chunks": [],
        "top1_score": 0.0,
        "generation": "",
        "self_score": 0.0,
        "citations": [],
        "decision": "",
        "human_needed": False,
        "reply_threshold": category.reply_threshold if category else 0.7,
        "self_review_threshold": 0.6,
    }

    if content_type == "post":
        # 发帖：栏目绑定外部源 → 走外部回帖闭环；否则走内置 AI 管理员
        external_agent = None
        if category and category.external_agent_id:
            external_agent = await db.get(ExternalAgent, category.external_agent_id)
            if external_agent and external_agent.deleted_at is not None:
                external_agent = None
        if external_agent and external_agent.enabled:
            await _external_reply_flow(state, db, external_agent)
            return trace_id
        # 内置 AI 管理员（未绑定外部源 或 外部源被停用）
        state["should_reply"] = bool(category and category.auto_reply_enabled)
        await _run_pipeline(state, db)
        return trace_id

    # 回帖（评论）：
    #  1) 评论内容合规审查（原有逻辑，先发布后事后审查）
    #  2) 若评论者是楼主 且 栏目开启「楼主评论自动回复」→ 判断是否提问，是提问才回复
    reply = await db.get(Reply, post_id)
    post = await db.get(Post, reply.post_id) if reply else None
    # 评论流水线中 post_id 语义统一为「帖子 id」；reply 目标由 reply.id 承担
    if reply:
        state["post_id"] = reply.post_id
    is_author_comment = bool(reply and post and reply.author_id == post.author_id)
    should_reply_comment = bool(
        is_author_comment and category and category.reply_to_author_questions and category.auto_reply_enabled
    )

    from app.agent.nodes import guardrail_node

    state = await guardrail_node(state, db)
    if state.get("decision") in ("hidden", "review"):
        return trace_id
    state["guardrail_done"] = True

    if not should_reply_comment:
        return trace_id

    # 内置 LLM 判断楼主评论是否提问（闲聊不回复）
    q = await is_question_check(db, reply.body_md, post.id, trace_id)
    if not q.get("is_question", False):
        return trace_id

    # 是提问 → 走外部回帖源（若绑定）或内置 AI 管理员
    external_agent = None
    if category and category.external_agent_id:
        external_agent = await db.get(ExternalAgent, category.external_agent_id)
        if external_agent and external_agent.deleted_at is not None:
            external_agent = None
    if external_agent and external_agent.enabled:
        # 重写 state 为「针对楼主追问回复」
        state["title"] = post.title if post else title
        state["body"] = reply.body_md
        await _external_reply_flow(state, db, external_agent)
        return trace_id

    state["should_reply"] = True
    await _run_pipeline(state, db)
    return trace_id


async def _run_pipeline(state: PipelineState, db: AsyncSession) -> None:
    """执行流水线。LangGraph 图节点均为 async 函数且接收 db。
    注：这里直接顺序执行各节点（等价于图拓扑），并使用 checkpointer 语义写入 agent_runs；
    生产环境下可替换为 LangGraph 原生 compile + AsyncPostgresSaver 以支持断点续跑。
    """
    from app.agent.nodes import generate_node, guardrail_node, judge_node, postprocess_node, retrieve_node, route_node

    try:
        # 发帖事件在发布前已由 review_post 完成 AI 合规审核（两次 AI 调用分开），此处跳过 guardrail 避免重复审核
        if state.get("content_type") != "post" and not state.get("guardrail_done"):
            state = await guardrail_node(state, db)
            if state.get("decision") in ("hidden", "review"):
                return
        state = await route_node(state, db)
        if not state.get("should_reply"):
            return
        state = await retrieve_node(state, db)
        state = await judge_node(state, db)
        if state.get("decision") == "no_evidence":
            return
        state = await generate_node(state, db)
        state = await postprocess_node(state, db)
        # ⑦ 异步后处理（打标签 / 重复帖检测 / 推送通知）
        from app.services.postprocess_service import async_postprocess

        await async_postprocess(db, state)
    except Exception as e:  # ⑧ 异常分支：记录并告警（重试由任务队列层负责）
        logger.exception("pipeline failed: %s", e)

        db.add(
            AgentRun(
                trace_id=state.get("trace_id", ""), trigger_type="compliance",
                post_id=state.get("post_id"), category_id=state.get("category_id"),
                node="pipeline", decision="error", detail={"error": str(e)},
            )
        )
        await db.commit()
