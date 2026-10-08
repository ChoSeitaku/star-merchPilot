"""stores / platform_accounts 表。

合规：platform_accounts 只保存安全元数据与授权状态，
不保存明文密码、明文 token、明文 cookie。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin


class Store(IdMixin, TimestampMixin, Base):
    __tablename__ = "stores"

    store_name: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    external_store_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    owner_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")

    accounts: Mapped[list["PlatformAccount"]] = relationship(
        back_populates="store", cascade="all, delete-orphan", lazy="selectin"
    )


class PlatformAccount(IdMixin, TimestampMixin, Base):
    """平台账号占位：仅保存授权状态与安全元数据。"""

    __tablename__ = "platform_accounts"

    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    account_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    auth_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unauthorized")
    # 仅存放安全元数据：授权范围、占位授权链接、过期时间等，绝不含密钥明文
    auth_meta_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")

    store: Mapped[Store] = relationship(back_populates="accounts")
