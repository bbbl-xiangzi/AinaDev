"""管理后台：用户管理、邀请码、员工扩展信息、员工字段定义配置。"""
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import EmployeeFieldDef, EmployeeProfile, Invitation, User
from app.schemas import (
    EmployeeFieldDefIn, EmployeeFieldDefOut, EmployeeFieldDefPatch,
    InviteCreate, InviteOut, PublicUserOut, UserAdminUpdate, UserOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_to_out(u: User, ep: EmployeeProfile | None) -> dict[str, Any]:
    d = UserOut.model_validate(u).model_dump()
    d["employee"] = {"position": ep.position if ep else None}
    return d


@router.get("/users")
async def list_users(
    q: str = "", page: int = 1, page_size: int = 20,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((User.name.ilike(like)) | (User.email.ilike(like)))
    total = await db.scalar(select(func_count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size)))
    items: list[dict[str, Any]] = []
    for u in rows:
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == u.id))
        items.append(_user_to_out(u, ep))
    return {"total": total or 0, "items": items}


def func_count():
    from sqlalchemy import func

    return func.count()


@router.put("/users/{user_id}")
async def update_user(
    user_id: int, body: UserAdminUpdate,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if u.id == admin.id and body.role and body.role != "super_admin":
        raise HTTPException(status_code=400, detail="不能取消自己的管理员角色")
    if body.name is not None:
        u.name = body.name.strip()[:50] or u.name
    if body.role is not None and body.role in {"member", "super_admin"}:
        u.role = body.role
    if body.status is not None and body.status in {"active", "disabled"}:
        u.status = body.status
    await db.commit()
    return UserOut.model_validate(u)


# ---------- 邀请码 ----------
@router.post("/invitations", response_model=InviteOut)
async def create_invitation(
    body: InviteCreate,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    import secrets
    from datetime import timedelta

    code = secrets.token_urlsafe(10)
    inv = Invitation(
        code=code,
        email=(body.email or "").strip().lower() or None,
        note=body.note,
        expires_at=_utcnow() + timedelta(days=7),
        status="active",
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


@router.get("/invitations")
async def list_invitations(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone

    rows = list(await db.scalars(select(Invitation).order_by(Invitation.created_at.desc()).limit(100)))
    now = datetime.now(timezone.utc)
    return [
        {
            "id": i.id, "code": i.code, "email": i.email, "used_by": i.used_by, "used_at": i.used_at,
            "expires_at": i.expires_at, "status": ("expired" if i.expires_at < now else i.status), "created_at": i.created_at,
        }
        for i in rows
    ]


@router.delete("/invitations/{inv_id}")
async def revoke_invitation(inv_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    inv = await db.get(Invitation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    inv.status = "revoked"
    await db.commit()
    return {"ok": True}


# ---------- 员工扩展信息（管理员维护，按字段定义动态读写） ----------
@router.get("/users/{user_id}/employee")
async def get_user_employee(user_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
    if not ep:
        return {}
    return {
        "sso_sub": ep.sso_sub, "employee_no": ep.employee_no, "position": ep.position, "org_path": ep.org_path,
        "mobile": ep.mobile, "gender": ep.gender, "birth_date": ep.birth_date, "join_date": ep.join_date,
        "manager": ep.manager, "location": ep.location, "employee_type": ep.employee_type,
        "job_level": ep.job_level, "cost_center": ep.cost_center, "extras": ep.extras,
        "raw_claims": ep.raw_claims, "source": ep.source,
    }


@router.put("/users/{user_id}/employee")
async def update_user_employee(
    user_id: int, body: dict[str, Any] = Body(default={}),
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    """管理员维护员工扩展信息（动态字段：user 列 / employee 列 / extras 自定义字段）。"""
    from app.services.employee_fields import apply_field_values, list_field_defs

    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
    if ep is None:
        ep = EmployeeProfile(user_id=user_id)
        db.add(ep)
    defs = await list_field_defs(db, enabled_only=True)
    changed = apply_field_values(u, ep, defs, body)
    ep.source = "admin"
    await db.commit()
    from app.models import AuditLog

    db.add(AuditLog(actor_type="user", actor_id=admin.id, action="employee_update", target_type="user", target_id=user_id, detail={"changed": list(changed.keys())}))
    await db.commit()
    return {"ok": True, "changed": list(changed.keys())}


# ---------- 员工字段定义（可配置元数据） ----------
@router.get("/employee-fields", response_model=list[EmployeeFieldDefOut])
async def list_employee_fields(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from app.services.employee_fields import ensure_seed_fields, list_field_defs

    await ensure_seed_fields(db)
    defs = await list_field_defs(db, enabled_only=False)
    return [EmployeeFieldDefOut.model_validate(d) for d in defs]


@router.post("/employee-fields", response_model=EmployeeFieldDefOut)
async def create_employee_field(
    body: EmployeeFieldDefIn,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    from app.services.employee_fields import ensure_seed_fields

    await ensure_seed_fields(db)
    max_id = await db.scalar(select(EmployeeFieldDef.id).order_by(EmployeeFieldDef.id.desc()).limit(1))
    idx = (max_id or 0) + 1
    d = EmployeeFieldDef(
        field_key=f"custom_{idx}",
        field_name=body.field_name.strip(),
        target="custom",
        input_type=body.input_type or "text",
        builtin=False,
        enabled=True,
        user_editable=True,
        hint=body.hint,
        sort_order=999 + idx,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return EmployeeFieldDefOut.model_validate(d)


@router.put("/employee-fields/{field_id}", response_model=EmployeeFieldDefOut)
async def update_employee_field(
    field_id: int, body: EmployeeFieldDefPatch,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    d = await db.get(EmployeeFieldDef, field_id)
    if not d:
        raise HTTPException(status_code=404, detail="字段不存在")
    if body.field_name is not None:
        d.field_name = body.field_name.strip()
    if body.input_type is not None:
        d.input_type = body.input_type
    if body.enabled is not None:
        d.enabled = body.enabled
    if body.user_editable is not None:
        d.user_editable = body.user_editable
    if body.hint is not None:
        d.hint = body.hint.strip() or None
    if body.sort_order is not None:
        d.sort_order = body.sort_order
    await db.commit()
    await db.refresh(d)
    return EmployeeFieldDefOut.model_validate(d)


@router.delete("/employee-fields/{field_id}")
async def delete_employee_field(field_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    d = await db.get(EmployeeFieldDef, field_id)
    if not d:
        raise HTTPException(status_code=404, detail="字段不存在")
    if d.builtin:
        raise HTTPException(status_code=400, detail="内置字段不可删除，可停用")
    await db.delete(d)
    await db.commit()
    return {"ok": True}


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
