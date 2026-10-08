"""竞品、公开链接解析任务、竞品监控请求体。"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from .common import ApiModel
from ..models import PLATFORMS


class CompetitorCreate(ApiModel):
    name: str = Field(default="", max_length=255)
    platform: str = Field(default="other")
    url: str = Field(default="", max_length=512)
    price: float = Field(default=0.0, ge=0)
    sales_hint: str = Field(default="", max_length=128, description="销量提示，如「月销 2000+」")
    title: str = Field(default="", max_length=512)
    main_image: str = Field(default="", max_length=512)
    selling_points: str = ""
    review_keywords: str = ""

    @field_validator("platform")
    @classmethod
    def _p(cls, v: str) -> str:
        if v not in PLATFORMS:
            raise ValueError(f"平台必须是 {PLATFORMS} 之一")
        return v


class CompetitorUpdate(ApiModel):
    name: Optional[str] = Field(default=None, max_length=255)
    platform: Optional[str] = None
    url: Optional[str] = Field(default=None, max_length=512)
    price: Optional[float] = Field(default=None, ge=0)
    sales_hint: Optional[str] = Field(default=None, max_length=128)
    title: Optional[str] = Field(default=None, max_length=512)
    main_image: Optional[str] = Field(default=None, max_length=512)
    selling_points: Optional[str] = None
    review_keywords: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def _p(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PLATFORMS:
            raise ValueError(f"平台必须是 {PLATFORMS} 之一")
        return v


class LinkParseTaskCreate(ApiModel):
    """创建公开链接解析任务。

    合规：仅对公开可访问的链接做有限信息提取，
    不绕过登录、验证码或平台风控。
    """

    urls: list[str] = Field(..., min_length=1, description="待解析的公开商品链接列表")
    auto_create_competitors: bool = Field(
        default=True, description="解析成功后是否自动创建竞品记录"
    )

    @field_validator("urls")
    @classmethod
    def _u(cls, v: list[str]) -> list[str]:
        cleaned = [u.strip() for u in v if u and u.strip()]
        if not cleaned:
            raise ValueError("至少需要一个有效链接")
        return cleaned


class MonitorCreate(ApiModel):
    interval_minutes: int = Field(default=60, ge=5, le=10080, description="监控间隔（分钟）")
