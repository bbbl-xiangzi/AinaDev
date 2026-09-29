"""员工扩展字段定义服务：字段集合可配置，SSO 抽取与界面渲染均按启用的字段清单进行。

字段定义分三类目标：
  - target=user     → 写 users 表列（department / org_id）
  - target=employee → 写 employee_profiles 固定列（内置 12 个）
  - target=custom   → 写 employee_profiles.extras（JSONB，管理员按客户需求新增）
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployeeFieldDef, EmployeeProfile, User

# 内置字段（builtin=True，只可停用/改名/调序，不可删除；claim_key 为确定性 SSO 映射候选）
SEED_FIELDS: list[dict[str, Any]] = [
    # (field_key, field_name, target, claim_key, hint, sort_order)
    {"field_key": "department", "field_name": "部门", "target": "user",
     "claim_key": "department,dept,department_name,division", "sort_order": 1},
    {"field_key": "org_id", "field_name": "所属组织 / 单位", "target": "user",
     "claim_key": "org,company,organization_name,company_name,organization", "sort_order": 2},
    {"field_key": "employee_no", "field_name": "工号", "target": "employee",
     "claim_key": "employee_no,employeeNumber,employee_id,emp_no,staff_no,staff_id,employeeId", "sort_order": 3},
    {"field_key": "position", "field_name": "职位", "target": "employee",
     "claim_key": "position,title,job_title,designation", "sort_order": 4},
    {"field_key": "org_path", "field_name": "组织架构路径", "target": "employee",
     "claim_key": "org_path,organization_path,organizationPath,ou,department_path", "sort_order": 5},
    {"field_key": "mobile", "field_name": "手机号", "target": "employee",
     "claim_key": "mobile,phone,phone_number,mobile_number,telephone,mobilePhone", "sort_order": 6},
    {"field_key": "gender", "field_name": "性别", "target": "employee",
     "claim_key": "gender,sex", "sort_order": 7},
    {"field_key": "birth_date", "field_name": "出生日期", "target": "employee",
     "claim_key": "birthdate,birth_date,date_of_birth,dob", "sort_order": 8},
    {"field_key": "join_date", "field_name": "入职日期", "target": "employee",
     "claim_key": "join_date,hire_date,employment_date,onboard_date,hireDate", "sort_order": 9},
    {"field_key": "manager", "field_name": "直属上级", "target": "employee",
     "claim_key": "manager,supervisor,direct_manager,directManager,leader", "sort_order": 10},
    {"field_key": "location", "field_name": "办公地点", "target": "employee",
     "claim_key": "location,office_location,work_location,city", "sort_order": 11},
    {"field_key": "employee_type", "field_name": "员工类型", "target": "employee",
     "claim_key": "employee_type,employment_type,employeeType,staff_type", "sort_order": 12},
    {"field_key": "job_level", "field_name": "职级", "target": "employee",
     "claim_key": "job_level,jobLevel,level,job_grade,grade", "sort_order": 13},
    {"field_key": "cost_center", "field_name": "成本中心", "target": "employee",
     "claim_key": "cost_center,costCenter", "sort_order": 14},
]

# 内置固定列 → 长度上限
_COL_LIMIT: dict[str, int] = {"org_path": 500}


async def ensure_seed_fields(db: AsyncSession) -> None:
    """启动时补齐内置字段定义（已存在的不覆盖，保留管理员修改）。"""
    for seed in SEED_FIELDS:
        exists = await db.scalar(select(EmployeeFieldDef).where(EmployeeFieldDef.field_key == seed["field_key"]))
        if exists:
            continue
        db.add(EmployeeFieldDef(
            field_key=seed["field_key"],
            field_name=seed["field_name"],
            target=seed["target"],
            claim_key=seed["claim_key"],
            hint=seed.get("hint"),
            sort_order=seed["sort_order"],
            builtin=True,
            enabled=True,
            user_editable=True,
            input_type=seed.get("input_type", "text"),
        ))
    await db.commit()


async def list_field_defs(db: AsyncSession, enabled_only: bool = False) -> list[EmployeeFieldDef]:
    stmt = select(EmployeeFieldDef)
    if enabled_only:
        stmt = stmt.where(EmployeeFieldDef.enabled.is_(True))
    stmt = stmt.order_by(EmployeeFieldDef.sort_order.asc(), EmployeeFieldDef.id.asc())
    return list(await db.scalars(stmt))


async def defs_by_key(db: AsyncSession, enabled_only: bool = True) -> dict[str, EmployeeFieldDef]:
    return {d.field_key: d for d in await list_field_defs(db, enabled_only=enabled_only)}


def _val_of(d: EmployeeFieldDef, user: User | None, ep: EmployeeProfile | None, values: dict[str, Any]) -> Any:
    """从提交值中读取字段值（内置列 / 自定义 extras）。"""
    if d.target == "user":
        return values.get(d.field_key)
    if d.target == "custom":
        return (values.get("extras") or {}).get(d.field_key) if isinstance(values.get("extras"), dict) else None
    return values.get(d.field_key)


def apply_field_values(
    user: User, ep: EmployeeProfile | None, defs: list[EmployeeFieldDef], values: dict[str, Any]
) -> dict[str, Any]:
    """按字段定义白名单写入（user 列 / ep 列 / extras）。返回实际变更的字段。"""
    if ep is None:
        raise ValueError("员工档案不存在")
    changed: dict[str, Any] = {}
    extras = dict(ep.extras or {})
    for d in defs:
        raw = _val_of(d, user, ep, values)
        if raw is None:
            continue
        v = raw.strip() if isinstance(raw, str) else raw
        v = v or None
        if d.target == "user":
            if getattr(user, d.field_key) != v:
                setattr(user, d.field_key, v)
                changed[d.field_key] = v
        elif d.target == "custom":
            old = extras.get(d.field_key)
            if old != v:
                if v is None:
                    extras.pop(d.field_key, None)
                else:
                    extras[d.field_key] = v
                changed[d.field_key] = v
        else:
            limit = _COL_LIMIT.get(d.field_key, 100)
            if isinstance(v, str) and len(v) > limit:
                v = v[:limit]
            if getattr(ep, d.field_key) != v:
                setattr(ep, d.field_key, v)
                changed[d.field_key] = v
    if extras != (ep.extras or {}):
        ep.extras = extras or None
        changed["extras"] = True
    return changed


def field_value_map(user: User, ep: EmployeeProfile | None, defs: list[EmployeeFieldDef]) -> dict[str, Any]:
    """组装 {field_key: value}（含自定义字段），供前端渲染。"""
    out: dict[str, Any] = {}
    if ep is None:
        extras: dict[str, Any] = {}
    else:
        extras = ep.extras or {}
    for d in defs:
        if d.target == "user":
            out[d.field_key] = getattr(user, d.field_key) or None
        elif d.target == "custom":
            out[d.field_key] = extras.get(d.field_key)
        else:
            out[d.field_key] = getattr(ep, d.field_key) if ep else None
    return out
