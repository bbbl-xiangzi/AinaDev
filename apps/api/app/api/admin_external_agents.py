"""管理：外部 Agent 回帖源（Dify / HiAgent / OpenAI 兼容 / 自定义 HTTP）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.core.security import aes_encrypt
from app.models import Category, ExternalAgent, User
from app.schemas import ExternalAgentIn, ExternalAgentOut
from app.services.audit_service import audit

router = APIRouter(prefix="/api/admin/external-agents", tags=["admin-external-agents"])


def _out(a: ExternalAgent) -> ExternalAgentOut:
    return ExternalAgentOut(
        id=a.id, name=a.name, protocol=a.protocol, api_url=a.api_url,
        model=a.model, headers_json=a.headers_json, request_template=a.request_template,
        response_path=a.response_path, timeout_seconds=a.timeout_seconds,
        enabled=a.enabled, has_api_key=bool(a.api_key_encrypted), created_at=a.created_at,
    )


@router.get("", response_model=list[ExternalAgentOut])
async def list_external_agents(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(ExternalAgent).where(ExternalAgent.deleted_at.is_(None)).order_by(ExternalAgent.id.desc())))
    return [_out(a) for a in rows]


@router.post("", response_model=ExternalAgentOut)
async def create_external_agent(body: ExternalAgentIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    data = body.model_dump(exclude={"api_key"})
    if body.api_key:
        data["api_key_encrypted"] = aes_encrypt(body.api_key)
    a = ExternalAgent(**data)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    await audit(db, "user", admin.id, "external_agent_create", "external_agent", a.id, {"name": a.name, "protocol": a.protocol})
    return _out(a)


@router.put("/{agent_id}", response_model=ExternalAgentOut)
async def update_external_agent(agent_id: int, body: ExternalAgentIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    a = await db.get(ExternalAgent, agent_id)
    if not a or a.deleted_at is not None:
        raise HTTPException(status_code=404, detail="外部 Agent 不存在")
    data = body.model_dump(exclude={"api_key"})
    if body.api_key:  # 回填新 Key 才更新，否则保留原值
        data["api_key_encrypted"] = aes_encrypt(body.api_key)
    for k, v in data.items():
        setattr(a, k, v)
    await db.commit()
    await audit(db, "user", admin.id, "external_agent_update", "external_agent", agent_id, {"name": a.name})
    return _out(a)


@router.delete("/{agent_id}")
async def delete_external_agent(agent_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    a = await db.get(ExternalAgent, agent_id)
    if not a:
        raise HTTPException(status_code=404, detail="外部 Agent 不存在")
    # 解除栏目绑定
    cats = list(await db.scalars(select(Category).where(Category.external_agent_id == agent_id)))
    for c in cats:
        c.external_agent_id = None
    from datetime import datetime, timezone

    a.deleted_at = datetime.now(timezone.utc)
    a.enabled = False
    await db.commit()
    await audit(db, "user", admin.id, "external_agent_delete", "external_agent", agent_id)
    return {"ok": True}
