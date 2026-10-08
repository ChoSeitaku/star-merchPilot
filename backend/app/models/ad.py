"""ad_recommendations / ad_experiments 表。

合规：系统只生成投放建议与实验计划，由有权限的人员人工确认；
不自动创建平台广告计划、不自动扣费、不直接执行预算变更。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class AdRecommendation(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "ad_recommendations"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    objective_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience_segments_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    budget_plan_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    creative_tests_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    bid_strategy_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_controls_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    next_steps_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)

    confirm_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confirm_remark: Mapped[str] = mapped_column(Text, nullable=False, default="")


class AdExperiment(IdMixin, TimestampMixin, Base):
    __tablename__ = "ad_experiments"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    related_asset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("generated_assets.id", ondelete="SET NULL"), nullable=True
    )
    related_link_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("promotion_links.id", ondelete="SET NULL"), nullable=True
    )
    experiment_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    budget_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    success_metric_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hypothesis_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    experiment_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
