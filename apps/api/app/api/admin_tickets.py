"""管理：Ticket 奖励配置。"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import TicketConfig, User, UserTicket

router = APIRouter(prefix="/api/admin/tickets", tags=["admin-tickets"])


class TicketConfigUpdate(BaseModel):
    reward: float | None = None
    enabled: bool | None = None
    daily_cap: int | None = None


@router.get("/configs")
async def list_configs(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(TicketConfig).order_by(TicketConfig.action_key)))
    return [
        {
            "action_key": r.action_key,
            "action_name": r.action_name,
            "reward": float(r.reward),
            "enabled": r.enabled,
            "daily_cap": r.daily_cap,
            "description": r.description,
        }
        for r in rows
    ]


@router.put("/configs/{action_key}")
async def update_config(
    action_key: str,
    body: TicketConfigUpdate,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    cfg = await db.get(TicketConfig, action_key)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置项不存在")
    if body.reward is not None:
        cfg.reward = Decimal(str(round(body.reward, 1)))
    if body.enabled is not None:
        cfg.enabled = body.enabled
    if body.daily_cap is not None:
        cfg.daily_cap = max(0, body.daily_cap)
    await db.commit()
    return {"ok": True}


@router.get("/users")
async def list_user_balances(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(UserTicket).order_by(UserTicket.balance.desc()).limit(100)))
    out = []
    for w in rows:
        u = await db.get(User, w.user_id)
        out.append({
            "user_id": w.user_id, "name": u.name if u else "?",
            "balance": float(w.balance), "total_earned": float(w.total_earned),
        })
    return out
