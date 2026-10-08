"""认证与用户相关请求体。"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from .common import ApiModel
from ..models import USER_ROLES, USER_STATUSES


class LoginRequest(ApiModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserCreate(ApiModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=64)
    role: str = Field(default="viewer", description="admin / operator / viewer")
    status: str = Field(default="active", description="active / disabled")

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        if v not in USER_ROLES:
            raise ValueError(f"角色必须是 {USER_ROLES} 之一")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in USER_STATUSES:
            raise ValueError(f"状态必须是 {USER_STATUSES} 之一")
        return v


class UserUpdate(ApiModel):
    display_name: Optional[str] = Field(default=None, max_length=64)
    role: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in USER_ROLES:
            raise ValueError(f"角色必须是 {USER_ROLES} 之一")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in USER_STATUSES:
            raise ValueError(f"状态必须是 {USER_STATUSES} 之一")
        return v
