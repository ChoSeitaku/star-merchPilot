"""FastAPI 依赖：当前用户识别与角色权限校验。

权限模型（规格 1.5.2）：
- admin    可管理用户、店铺、平台账号，编辑业务数据，确认投放，查看全部数据
- operator 可编辑商品/竞品/方案/素材/经营数据，可确认投放建议，但不能管理用户与店铺
- viewer   只读

实现要点：角色每次请求都从数据库现取，因此管理员在设置页调整角色后立即生效。
"""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False, description="Bearer 访问令牌")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="登录状态无效或已过期，请重新登录",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _UNAUTHORIZED
    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTHORIZED
    user = db.scalar(select(User).where(User.id == int(user_id)))
    if user is None:
        raise _UNAUTHORIZED
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被停用，请联系管理员"
        )
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    """生成角色校验依赖。写操作路由统一挂载。"""

    allowed = set(roles)

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"当前角色（{current_user.role}）无权执行该操作，需要 {'/'.join(sorted(allowed))} 权限",
            )
        return current_user

    return _checker


# 写操作通用：管理员与运营人员
require_editor = require_roles("admin", "operator")
# 仅管理员
require_admin = require_roles("admin")
# 投放确认需要单独的权限校验（规格 1.5.2 明确要求）
require_ad_confirm = require_roles("admin", "operator")
