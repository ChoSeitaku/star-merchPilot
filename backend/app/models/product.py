"""products / platform_product_mappings / product_skus / inventory_* 表。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import utcnow
from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .store import Store


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"

    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selling_points: Mapped[str] = mapped_column(Text, nullable=False, default="")
    product_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    images_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    store: Mapped["Store"] = relationship(lazy="joined")  # noqa: F821
    skus: Mapped[list["ProductSku"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


class PlatformProductMapping(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "platform_product_mappings"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    platform_sku_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unmapped")
    raw_payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class ProductSku(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_skus"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sku_code: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    sku_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    spec_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    platform_sku_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    product: Mapped[Product] = relationship(back_populates="skus")
    inventory: Mapped[Optional["InventoryItem"]] = relationship(
        back_populates="sku", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class InventoryItem(IdMixin, Base):
    __tablename__ = "inventory_items"

    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_skus.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    location_text: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    sku: Mapped[ProductSku] = relationship(back_populates="inventory")

    @property
    def available_qty(self) -> int:
        return self.stock_qty - self.locked_qty


class InventoryMovement(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "inventory_movements"

    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_skus.id", ondelete="CASCADE"), index=True, nullable=False
    )
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False, default="adjust")
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    before_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
