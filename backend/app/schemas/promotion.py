"""推广链接与投放相关请求体。

合规：投放相关接口只产出建议与实验计划，
不提供任何自动创建广告计划、自动扣费或直接改预算的能力。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .common import ApiModel
from ..models import AD_CONFIRM_STATUSES, AD_EXPERIMENT_STATUSES


class PromotionLinkCreate(ApiModel):
    link_name: str = Field(..., min_length=1, max_length=255)
    target_url: str = Field(..., min_length=1, max_length=512)
    scene_text: str = ""
    utm_json: Optional[dict[str, Any]] = None
    status: str = Field(default="active", description="active / inactive")


class PromotionLinkUpdate(ApiModel):
    link_name: Optional[str] = Field(default=None, max_length=255)
    target_url: Optional[str] = Field(default=None, max_length=512)
    scene_text: Optional[str] = None
    utm_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class AdRecommendationGenerate(ApiModel):
    objective: str = Field(default="转化", description="本轮投放目标")
    daily_budget: Optional[float] = Field(default=None, ge=0, description="期望日预算（留空由系统建议）")
    remark: str = ""


class AdConfirmationUpdate(ApiModel):
    """人工确认或驳回投放建议（需单独权限校验）。"""

    confirm_status: str = Field(..., description="confirmed / rejected")
    confirm_remark: str = ""

    @field_validator("confirm_status")
    @classmethod
    def _s(cls, v: str) -> str:
        if v not in ("confirmed", "rejected"):
            raise ValueError("确认状态只能是 confirmed 或 rejected")
        return v


class AdExperimentGenerate(ApiModel):
    related_asset_id: Optional[int] = None
    related_link_id: Optional[int] = None
    experiment_name: str = Field(default="", max_length=255)
    budget_amount: Optional[float] = Field(default=None, ge=0)
    remark: str = ""


class AdExperimentUpdate(ApiModel):
    """更新实验状态。

    合规：状态流转只记录管理意图，不触发任何平台侧投放动作。
    """

    experiment_status: Optional[str] = None
    experiment_name: Optional[str] = Field(default=None, max_length=255)
    target_text: Optional[str] = None
    audience_text: Optional[str] = None
    budget_amount: Optional[float] = Field(default=None, ge=0)
    success_metric_text: Optional[str] = None
    hypothesis_text: Optional[str] = None
    related_asset_id: Optional[int] = None
    related_link_id: Optional[int] = None

    @field_validator("experiment_status")
    @classmethod
    def _s(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in AD_EXPERIMENT_STATUSES:
            raise ValueError(f"实验状态必须是 {AD_EXPERIMENT_STATUSES} 之一")
        return v


class PerformanceRecordCreate(ApiModel):
    period_start: Optional[str] = Field(default=None, description="周期开始日期 YYYY-MM-DD")
    period_end: Optional[str] = Field(default=None, description="周期结束日期 YYYY-MM-DD")
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    spend: float = Field(default=0.0, ge=0)
    revenue: float = Field(default=0.0, ge=0)
    ctr: Optional[float] = Field(default=None, ge=0, description="留空则按 点击/曝光 自动计算")
    conversion_rate: Optional[float] = Field(default=None, ge=0, description="留空则按 成交/点击 自动计算")
    roi: Optional[float] = Field(default=None, ge=0, description="留空则按 成交金额/花费 自动计算")
    notes: str = ""
    creative_plan_id: Optional[int] = None
    generated_asset_id: Optional[int] = None
    promotion_link_id: Optional[int] = None
    experiment_id: Optional[int] = None


class ReviewReportGenerate(ApiModel):
    period_start: Optional[str] = Field(default=None, description="复盘周期开始 YYYY-MM-DD")
    period_end: Optional[str] = Field(default=None, description="复盘周期结束 YYYY-MM-DD")
    remark: str = ""


__all__ = [
    "PromotionLinkCreate",
    "PromotionLinkUpdate",
    "AdRecommendationGenerate",
    "AdConfirmationUpdate",
    "AdExperimentGenerate",
    "AdExperimentUpdate",
    "PerformanceRecordCreate",
    "ReviewReportGenerate",
    "AD_CONFIRM_STATUSES",
]
