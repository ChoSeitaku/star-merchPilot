"""product_diagnoses 表。AI 诊断结果结构化保存，且允许人工编辑。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class ProductDiagnosis(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_diagnoses"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ai_mock")
    # 列表页摘要（附加列，便于工作台展示）
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    positioning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_band: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience_insights: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pain_points: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selling_point_analysis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risks: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommendations: Mapped[str] = mapped_column(Text, nullable=False, default="")

    raw_output: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
