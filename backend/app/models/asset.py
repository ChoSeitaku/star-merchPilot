"""generated_assets 表：生成的图片/视频素材及其审核字段。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin


class GeneratedAsset(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "generated_assets"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    creative_plan_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("creative_plans.id", ondelete="SET NULL"), index=True, nullable=True
    )
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False, default="image")
    asset_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # 附加列：内部磁盘相对路径，便于清理与同步
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, default="mock-generator")
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    usage_scene: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tags_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
