"""promotion_links / promotion_link_clicks 表。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import utcnow
from .base import Base, CreatedAtMixin, IdMixin


class PromotionLink(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "promotion_links"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    link_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    tracking_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    utm_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scene_text: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PromotionLinkClick(IdMixin, Base):
    __tablename__ = "promotion_link_clicks"

    promotion_link_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("promotion_links.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(512), nullable=False, default="")
