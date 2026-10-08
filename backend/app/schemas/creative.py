"""诊断、方案、任务、素材请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .common import ApiModel
from ..models import (
    ASSET_REVIEW_STATUSES,
    CREATIVE_PLAN_STATUSES,
    JOB_KINDS,
    JOB_STATUSES,
)


class DiagnosisGenerate(ApiModel):
    source_type: str = Field(default="ai_mock", description="生成来源标记")
    include_review_actions: bool = Field(
        default=True, description="是否把上一轮复盘结论作为输入（形成优化闭环）"
    )
    remark: str = Field(default="", description="本次生成的补充说明（仅记录）")


class DiagnosisUpdate(ApiModel):
    """诊断内容人工编辑保存。"""

    positioning: Optional[str] = None
    price_band: Optional[str] = None
    audience_insights: Optional[str] = None
    pain_points: Optional[str] = None
    selling_point_analysis: Optional[str] = None
    risks: Optional[str] = None
    recommendations: Optional[str] = None
    summary_text: Optional[str] = None


class CreativePlanUpdate(ApiModel):
    title: Optional[str] = Field(default=None, max_length=255)
    content_json: Optional[dict[str, Any]] = None
    rationale_text: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _s(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CREATIVE_PLAN_STATUSES:
            raise ValueError(f"方案状态必须是 {CREATIVE_PLAN_STATUSES} 之一")
        return v


class ImageGenerateRequest(ApiModel):
    """基于主图方案提交图片生成任务。"""

    direction_indexes: list[int] = Field(
        default_factory=list, description="要生成的方向下标（从 0 开始），留空表示全部方向"
    )
    count_per_direction: int = Field(default=1, ge=1, le=4, description="每个方向生成几张")
    usage_scene: str = Field(default="主图", max_length=64)


class VideoGenerateRequest(ApiModel):
    """基于视频脚本提交视频生成任务。"""

    script_indexes: list[int] = Field(
        default_factory=list, description="要生成的脚本下标（从 0 开始），留空表示全部脚本"
    )
    duration_sec: int = Field(default=15, ge=5, le=120, description="目标视频时长（秒）")
    usage_scene: str = Field(default="短视频", max_length=64)


class AssetReviewUpdate(ApiModel):
    """素材审核字段更新（可批量）。"""

    asset_ids: list[int] = Field(..., min_length=1, description="待更新素材 ID 列表")
    review_status: Optional[str] = None
    usage_scene: Optional[str] = Field(default=None, max_length=64)
    score: Optional[float] = Field(default=None, ge=0, le=5)
    tags_json: Optional[list[Any]] = None
    remark: Optional[str] = None
    version_no: Optional[int] = Field(default=None, ge=1)

    @field_validator("review_status")
    @classmethod
    def _s(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ASSET_REVIEW_STATUSES:
            raise ValueError(f"素材审核状态必须是 {ASSET_REVIEW_STATUSES} 之一")
        return v


class JobQuery(ApiModel):
    """任务列表过滤条件（作为查询参数使用）。"""

    product_id: Optional[int] = None
    job_kind: Optional[str] = None
    job_status: Optional[str] = None

    @field_validator("job_kind")
    @classmethod
    def _k(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in JOB_KINDS:
            raise ValueError(f"任务类型必须是 {JOB_KINDS} 之一")
        return v

    @field_validator("job_status")
    @classmethod
    def _s(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in JOB_STATUSES:
            raise ValueError(f"任务状态必须是 {JOB_STATUSES} 之一")
        return v


class JobFailRequest(ApiModel):
    """演示/测试用：强制下一次执行失败，用于展示失败与重试链路。"""

    reason: str = Field(default="模拟生成失败（演示用）")
