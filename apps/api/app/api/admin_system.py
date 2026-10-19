"""管理：统计、审计、Agent 执行记录、站点配置。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import AgentRun, AuditLog, Post, RagDocument, Reply, Report, User
from app.schemas import AgentRunOut, AuditLogOut, SiteConfigIn, StatsOut

router = APIRouter(prefix="/api/admin", tags=["admin-system"])


@router.get("/stats", response_model=StatsOut)
async def stats(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc) - timedelta(days=1)
    return StatsOut(
        user_count=await db.scalar(select(func.count(User.id)).where(User.account_type == "human", User.deleted_at.is_(None))) or 0,
        post_count=await db.scalar(select(func.count(Post.id)).where(Post.deleted_at.is_(None))) or 0,
        reply_count=await db.scalar(select(func.count(Reply.id)).where(Reply.deleted_at.is_(None))) or 0,
        today_posts=await db.scalar(select(func.count(Post.id)).where(Post.created_at >= today, Post.deleted_at.is_(None))) or 0,
        pending_reviews=await db.scalar(select(func.count(Post.id)).where(Post.status.in_(["pending_review", "rejected"]), Post.deleted_at.is_(None))) or 0,
        open_reports=await db.scalar(select(func.count(Report.id)).where(Report.status == "open")) or 0,
        ai_replies=await db.scalar(select(func.count(Reply.id)).where(Reply.author_type == "ai_admin", Reply.deleted_at.is_(None))) or 0,
        doc_count=await db.scalar(select(func.count(RagDocument.id)).where(RagDocument.deleted_at.is_(None))) or 0,
    )


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def audit_logs(
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return [AuditLogOut.model_validate(r) for r in rows]


@router.get("/agent-runs", response_model=dict)
async def agent_runs(
    trace_id: str | None = None,
    post_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc())
    if trace_id:
        stmt = stmt.where(AgentRun.trace_id == trace_id)
    if post_id:
        stmt = stmt.where(AgentRun.post_id == post_id)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return {"total": total or 0, "items": [AgentRunOut.model_validate(r) for r in rows]}


@router.get("/agent-runs/{run_id}")
async def agent_run_detail(run_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    run = await db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {
        "id": run.id, "trace_id": run.trace_id, "trigger_type": run.trigger_type,
        "post_id": run.post_id, "category_id": run.category_id, "node": run.node,
        "prompt": run.prompt, "response": run.response,
        "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
        "latency_ms": run.latency_ms, "decision": run.decision, "score": run.score,
        "detail": run.detail, "created_at": run.created_at,
    }


@router.get("/site-config")
async def get_site_config(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from app.config import settings
    from app.models import SiteConfig

    rows = list(await db.scalars(select(SiteConfig)))
    data = {r.key: r.value for r in rows}
    # 合并默认值（未在库中设置的项）
    defaults = {
        "site_name": settings.site_name, "site_description": settings.site_description,
        "mcp_api_key": settings.mcp_api_key,
        "upload_allowed_types": "png,jpg,jpeg,gif,webp,pdf,doc,docx,xls,xlsx,txt,md,csv,zip",
        "upload_max_size_mb": "10",
        "review_prompt": "",
    }
    for k, v in defaults.items():
        data.setdefault(k, str(v))
    # 审核提示词：未配置时返回默认预设，便于后台编辑
    if not data.get("review_prompt"):
        from app.services.compliance_service import DEFAULT_REVIEW_PROMPT

        data["review_prompt"] = DEFAULT_REVIEW_PROMPT
    return data


@router.get("/site-config-public")
async def site_config_public(db: AsyncSession = Depends(get_db)):
    """公开接口：前端顶栏和 HTML title 用，不需要登录。"""
    from app.config import settings
    from app.models import SiteConfig
    rows = list(await db.scalars(select(SiteConfig)))
    data = {r.key: r.value for r in rows}
    return {
        "site_name": data.get("site_name") or settings.site_name,
        "site_description": data.get("site_description") or settings.site_description,
        "logo_url": data.get("logo_url") or "",
    }


@router.put("/site-config")
async def update_site_config(body: SiteConfigIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from app.config import settings
    from app.models import SiteConfig

    mapping = {
        "site_name": settings.site_name, "site_description": settings.site_description,
        "mcp_api_key": settings.mcp_api_key, "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port, "smtp_user": settings.smtp_user,
        "smtp_password": settings.smtp_password, "smtp_from": settings.smtp_from,
        "invite_expire_days": settings.invite_expire_days,
        "upload_allowed_types": "png,jpg,jpeg,gif,webp,pdf,doc,docx,xls,xlsx,txt,md,csv,zip",
        "upload_max_size_mb": "10",
        "review_prompt": "",
    }
    data = body.model_dump(exclude_unset=True)
    for key, default in mapping.items():
        if key in data and data[key] is not None:
            existing = await db.get(SiteConfig, key)
            if existing:
                existing.value = str(data[key])
            else:
                db.add(SiteConfig(key=key, value=str(data[key])))
    await db.commit()
    return {"ok": True}
