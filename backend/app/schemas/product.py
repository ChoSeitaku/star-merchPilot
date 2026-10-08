"""商品 / 平台映射 / SKU / 库存 请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .common import ApiModel
from ..models import PLATFORMS, PRODUCT_STATUSES


def _check_platform(v: str) -> str:
    if v not in PLATFORMS:
        raise ValueError(f"平台必须是 {PLATFORMS} 之一")
    return v


class ProductCreate(ApiModel):
    store_id: int = Field(..., description="所属店铺")
    name: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(default="other")
    category: str = Field(default="", max_length=128)
    price: float = Field(default=0.0, ge=0)
    cost: float = Field(default=0.0, ge=0)
    target_audience: str = ""
    selling_points: str = ""
    product_url: str = Field(default="", max_length=512)
    images_json: Optional[list[Any]] = None
    status: str = Field(default="draft")

    @field_validator("platform")
    @classmethod
    def _p(cls, v: str) -> str:
        return _check_platform(v)

    @field_validator("status")
    @classmethod
    def _s(cls, v: str) -> str:
        if v not in PRODUCT_STATUSES:
            raise ValueError(f"商品状态必须是 {PRODUCT_STATUSES} 之一")
        return v


class ProductUpdate(ApiModel):
    store_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    platform: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=128)
    price: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    target_audience: Optional[str] = None
    selling_points: Optional[str] = None
    product_url: Optional[str] = Field(default=None, max_length=512)
    images_json: Optional[list[Any]] = None
    status: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def _p(cls, v: Optional[str]) -> Optional[str]:
        return v if v is None else _check_platform(v)

    @field_validator("status")
    @classmethod
    def _s(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PRODUCT_STATUSES:
            raise ValueError(f"商品状态必须是 {PRODUCT_STATUSES} 之一")
        return v


class PlatformMappingCreate(ApiModel):
    platform: str = Field(default="other")
    platform_product_id: str = Field(default="", max_length=128)
    platform_sku_id: str = Field(default="", max_length=128)
    mapping_status: str = Field(default="mapped", description="mapped / unmapped / conflict")
    raw_payload_json: Optional[dict[str, Any]] = None

    @field_validator("platform")
    @classmethod
    def _p(cls, v: str) -> str:
        return _check_platform(v)


class SkuCreate(ApiModel):
    sku_code: str = Field(..., min_length=1, max_length=128)
    sku_name: str = Field(default="", max_length=255)
    spec_json: Optional[dict[str, Any]] = None
    price: float = Field(default=0.0, ge=0)
    cost: float = Field(default=0.0, ge=0)
    status: str = Field(default="active", description="active / inactive")
    platform_sku_id: str = Field(default="", max_length=128)
    stock_qty: int = Field(default=0, ge=0, description="初始库存")
    warning_threshold: int = Field(default=10, ge=0)
    location_text: str = Field(default="", max_length=128)


class SkuUpdate(ApiModel):
    sku_name: Optional[str] = Field(default=None, max_length=255)
    spec_json: Optional[dict[str, Any]] = None
    price: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None
    platform_sku_id: Optional[str] = Field(default=None, max_length=128)


class InventoryAdjust(ApiModel):
    """库存调整：正数入库、负数出库，自动写库存流水。"""

    change_qty: int = Field(..., description="变动数量，正数入库 / 负数出库")
    reason_text: str = Field(default="", description="变动原因")
    movement_type: str = Field(default="adjust", description="adjust / purchase / sale / return / lock")
    warning_threshold: Optional[int] = Field(default=None, ge=0)
    location_text: Optional[str] = Field(default=None, max_length=128)
