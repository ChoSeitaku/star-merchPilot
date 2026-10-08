"""competitors / competitor_monitors / snapshots / public_link_parse_tasks 表。

合规：公开链接解析只做有限的公开信息提取（域名识别 + 用户提供的公开字段），
不实现任何绕过登录、验证码或平台风控的抓取逻辑。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class Competitor(IdMixin, TimestampMixin, Base):
    __tablename__ = "competitors"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sales_hint: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    main_image: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    selling_points: Mapped[str] = mapped_column(Text, nullable=False, default="")
    review_keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")


class CompetitorMonitor(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "competitor_monitors"

    competitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("competitors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    monitor_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    competitor: Mapped[Competitor] = relationship(lazy="joined")


class CompetitorMonitorSnapshot(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "competitor_monitor_snapshots"

    monitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("competitor_monitors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sales_hint: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    selling_points: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class PublicLinkParseTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "public_link_parse_tasks"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    task_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
