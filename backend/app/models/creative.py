"""creative_plans 表：主图方案与视频脚本统一存放，靠 plan_type 区分。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class CreativePlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "creative_plans"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False, default="main_image")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 结构化内容：主图方案为 3 个方向数组；视频脚本为 3 条脚本数组
    content_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    rationale_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
