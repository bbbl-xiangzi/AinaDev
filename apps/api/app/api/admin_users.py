"""管理：用户 + 邀请码 + 员工扩展信息。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import EmployeeProfile, Invitation, User
from app.schemas import EmployeeOut, InviteCreate, InviteOut, ProfileUpdateIn, UserAdminUpdate, UserOut
from app.services.audit_service import audit
from app.services.auth_service import create_invite

router = APIRouter(prefix="/api/admin", tags=["admin-users"])


@router.get("/users", response_model=dict)
async def list_users(
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.deleted_at.is_(None), User.account_type == "human")
    if q:
        stmt = stmt.where(or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    stmt = stmt.order_by(User.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    # 批量附加员工扩展摘要（工号 / 职位），供后台列表展示
    emp_map: dict[int, dict] = {}
    if rows:
        emp_stmt = select(EmployeeProfile.user_id, EmployeeProfile.employee_no, EmployeeProfile.position).where(
            EmployeeProfile.user_id.in_([u.id for u in rows])
        )
        for r in await db.execute(emp_stmt):
            emp_map[r.user_id] = {"employee_no": r.employee_no, "position": r.position}
    items = []
    for u in rows:
        d = UserOut.model_validate(u).model_dump()
        d["employee"] = emp_map.get(u.id, {})
        items.append(d)
    return {"total": total or 0, "items": items}


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserAdminUpdate, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and body.status == "disabled":
        raise HTTPException(status_code=400, detail="不能禁用自己")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    await db.commit()
    await audit(db, "user", admin.id, "user_update", "user", user_id, body.model_dump(exclude_unset=True))
    return UserOut.model_validate(user)


@router.get("/users/{user_id}/employee", response_model=EmployeeOut)
async def get_user_employee(user_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """查看某用户的员工扩展信息（含 SSO 来源与原始 claims 可追溯）。"""
    ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
    if not ep:
        return EmployeeOut()
    return EmployeeOut(
        sso_sub=ep.sso_sub, employee_no=ep.employee_no, position=ep.position, org_path=ep.org_path,
        mobile=ep.mobile, gender=ep.gender, birth_date=ep.birth_date, join_date=ep.join_date,
        manager=ep.manager, location=ep.location, employee_type=ep.employee_type,
        job_level=ep.job_level, cost_center=ep.cost_center, extras=ep.extras,
        raw_claims=ep.raw_claims, source=ep.source,
    )


@router.put("/users/{user_id}/employee", response_model=dict)
async def update_user_employee(user_id: int, body: ProfileUpdateIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """管理员维护某用户的部门/组织与员工扩展信息（SSO 抽取后可人工修正）。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.department is not None:
        user.department = body.department.strip() or None
    if body.org_id is not None:
        user.org_id = body.org_id.strip() or None
    employee_fields = {
        "employee_no": body.employee_no, "position": body.position, "org_path": body.org_path,
        "mobile": body.mobile, "gender": body.gender, "birth_date": body.birth_date,
        "join_date": body.join_date, "manager": body.manager, "location": body.location,
        "employee_type": body.employee_type, "job_level": body.job_level, "cost_center": body.cost_center,
    }
    changed = {}
    if any(v is not None for v in employee_fields.values()):
        ep = await db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
        if ep is None:
            ep = EmployeeProfile(user_id=user_id)
            db.add(ep)
        for field, val in employee_fields.items():
            if val is not None:
                v = val.strip() or None
                if getattr(ep, field) != v:
                    setattr(ep, field, v)
                    changed[field] = v
        if ep.source != "admin":
            ep.source = "admin"
        changed["source"] = "admin"
    await db.commit()
    await audit(db, "user", admin.id, "employee_update", "user", user_id, changed)
    return {"ok": True, "changed": changed}