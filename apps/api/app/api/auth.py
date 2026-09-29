"""认证 API。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import check_rate, client_ip
from app.core.security import decode_token, hash_password, verify_password
from app.models import User
from app.schemas import ChangePasswordIn, LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import AuthError, issue_tokens, login, register

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register_user(body: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    await check_rate(f"rl:register:ip:{ip}", 5, 3600, "注册过于频繁，请稍后再试")
    await check_rate(f"rl:register:acct:{body.email.lower()}", 2, 3600, "该邮箱注册过于频繁，请稍后再试")
    try:
        user = await register(db, body.email, body.name, body.password, body.invite_code)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "register", note="新用户注册奖励")
        await db.commit()
    except Exception:
        pass
    tokens = issue_tokens(user)
    return {**tokens, "user": UserOut.model_validate(user)}


@router.post("/login", response_model=TokenOut)
async def login_user(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    await check_rate(f"rl:login:ip:{ip}", 15, 60, "登录尝试过于频繁，请稍后再试")
    await check_rate(f"rl:login:acct:{body.email.lower()}", 5, 60, "该账号登录尝试过于频繁，请稍后再试")
    try:
        user = await login(db, body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from app.services.ticket_service import grant as grant_ticket
    try:
        await grant_ticket(db, user.id, "daily_login", note="每日首次登录")
        await db.commit()
    except Exception:
        pass
    tokens = issue_tokens(user)
    return {**tokens, "user": UserOut.model_validate(user)}


@router.post("/refresh", response_model=TokenOut)
async def refresh_token(body: RefreshIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    await check_rate(f"rl:refresh:ip:{ip}", 60, 60, "操作过于频繁，请稍后再试")
    payload = decode_token(body.refresh_token, "refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="刷新令牌无效")
    user = await db.get(User, int(payload["sub"]))
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="账号不可用")
    tokens = issue_tokens(user)
    return {**tokens, "user": UserOut.model_validate(user)}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # SSO 自动开通的账号无本地密码（password_hash 为空）：设置密码时无需验证旧密码
    if user.password_hash and not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
