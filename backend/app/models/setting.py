"""system_settings 表：设置页使用的键值配置（模型配置 / 系统参数 / 任务队列配置）。"""

from __future__ import annotations



from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class SystemSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="string")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 是否允许在设置页修改
    editable: Mapped[int] = mapped_column(nullable=False, default=1)


__all__ = ["SystemSetting"]
