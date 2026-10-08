"""performance_records / review_reports 表：经营数据与复盘报告。"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin


class PerformanceRecord(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "performance_records"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    creative_plan_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("creative_plans.id", ondelete="SET NULL"), nullable=True
    )
    generated_asset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("generated_assets.id", ondelete="SET NULL"), nullable=True
    )
    promotion_link_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("promotion_links.id", ondelete="SET NULL"), nullable=True
    )
    experiment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ad_experiments.id", ondelete="SET NULL"), nullable=True
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    roi: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ReviewReport(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "review_reports"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    insights_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    next_actions_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
