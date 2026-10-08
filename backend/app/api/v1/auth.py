"""认证路由：登录与当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import User
from ...schemas import LoginRequest
from ...security import create_access_token, verify_password
from ...serializers import user_out
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", summary="用户登录并返回访问令牌")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == payload.username))
    # 用户不存在与密码错误返回同一提示，避免暴露账号是否存在
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被停用，请联系管理员"
        )

    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, extra={"username": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": 480,
        "user": user_out(user),
    }


@router.get("/me", summary="查询当前登录用户")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return user_out(current_user)
