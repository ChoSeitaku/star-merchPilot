"""用户管理路由（仅管理员）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User
from ...schemas import UserCreate, UserUpdate
from ...security import hash_password
from ...serializers import user_out
from ..deps import require_admin

# 整个路由仅管理员可用（规格 1.5.2：用户管理必须单独权限校验）
router = APIRouter(
    prefix="/users", tags=["用户管理"], dependencies=[Depends(require_admin)]
)


@router.get("", summary="用户列表")
def list_users(
    db: Session = Depends(get_db),
    keyword: str = Query(default="", description="按用户名或展示名模糊搜索"),
    role: str = Query(default="", description="按角色过滤"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = select(User)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((User.username.like(like)) | (User.display_name.like(like)))
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.id.asc())

    rows = list(db.scalars(stmt))
    total = len(rows)
    return {
        "total": total,
        "items": [user_out(u) for u in rows[offset : offset + limit]],
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建用户")
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> dict:
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(
        username=payload.username,
        display_name=payload.display_name or payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        status=payload.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/{user_id}", summary="更新用户（角色 / 状态 / 展示名 / 重置密码）")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    # 保护措施：不允许管理员把自己降级或停用，避免把自己锁在系统外
    if user.id == current_user.id:
        if data.get("role") and data["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的管理员角色"
            )
        if data.get("status") == "disabled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用自己的账号"
            )

    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    for field, value in data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user_out(user)
