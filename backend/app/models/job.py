"""generation_jobs / generation_job_events 表：图片与视频异步生成任务。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin


class GenerationJob(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "generation_jobs"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    creative_plan_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("creative_plans.id", ondelete="SET NULL"), index=True, nullable=True
    )
    job_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="image")
    job_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    # 入队参数：方案方向、数量等
    params_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class GenerationJobEvent(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "generation_job_events"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    event_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
