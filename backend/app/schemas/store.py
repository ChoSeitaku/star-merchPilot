"""店铺与平台账号请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .common import ApiModel
from ..models import PLATFORMS


def _check_platform(v: str) -> str:
    if v not in PLATFORMS:
        raise ValueError(f"平台必须是 {PLATFORMS} 之一")
    return v


class StoreCreate(ApiModel):
    store_name: str = Field(..., min_length=1, max_length=128)
    platform: str = Field(default="other")
    external_store_id: str = Field(default="", max_length=128)
    owner_name: str = Field(default="", max_length=64)
    remark: str = ""

    @field_validator("platform")
    @classmethod
    def _p(cls, v: str) -> str:
        return _check_platform(v)


class StoreUpdate(ApiModel):
    store_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    platform: Optional[str] = None
    external_store_id: Optional[str] = Field(default=None, max_length=128)
    owner_name: Optional[str] = Field(default=None, max_length=64)
    remark: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def _p(cls, v: Optional[str]) -> Optional[str]:
        return v if v is None else _check_platform(v)


class PlatformAccountCreate(ApiModel):
    """创建平台账号占位。注意：不接受任何明文密码/token/cookie 字段。"""

    platform: str = Field(default="other")
    account_name: str = Field(default="", max_length=128)
    remark: str = ""

    @field_validator("platform")
    @classmethod
    def _p(cls, v: str) -> str:
        return _check_platform(v)


class AuthorizationStartRequest(ApiModel):
    redirect_uri: str = Field(default="", description="授权回调地址（占位用）")
    scope: str = Field(default="item_read,order_read", description="申请授权的数据范围")


class AuthorizationCallbackPlaceholder(ApiModel):
    """保存授权元数据（仅安全元数据，不含任何密钥明文）。"""

    auth_code_masked: str = Field(default="", description="授权码掩码，如 abcd****wxyz")
    granted_scope: str = Field(default="", description="实际授予的范围")
    authorized_account_name: str = Field(default="", description="授权账号展示名")
    expires_at: Optional[str] = Field(default=None, description="授权过期时间（ISO 字符串）")
    extra_meta: dict[str, Any] = Field(default_factory=dict, description="其他安全元数据")
