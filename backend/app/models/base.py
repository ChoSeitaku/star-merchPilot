"""模型公共基类与常量。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, utcnow


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


__all__ = ["Base", "IdMixin", "CreatedAtMixin", "TimestampMixin"]


# ---------------------------------------------------------------------------
# 状态枚举（与规格 1.5.5 一致，以字符串存库，便于演示时直接读表）
# ---------------------------------------------------------------------------

# 商品状态
PRODUCT_STATUSES = ("draft", "active", "inactive")
# 素材方案状态
CREATIVE_PLAN_STATUSES = ("draft", "selected", "archived")
# 方案类型
CREATIVE_PLAN_TYPES = ("main_image", "video_script")
# 生成任务状态
JOB_STATUSES = ("pending", "running", "succeeded", "failed", "cancelled", "timeout")
JOB_KINDS = ("image", "video")
# 投放建议确认状态
AD_CONFIRM_STATUSES = ("pending", "confirmed", "rejected")
# 投放实验状态
AD_EXPERIMENT_STATUSES = ("draft", "confirmed", "running", "finished", "cancelled")
# 素材审核状态
ASSET_REVIEW_STATUSES = ("pending", "approved", "rejected")
# 用户角色与状态
USER_ROLES = ("admin", "operator", "viewer")
USER_STATUSES = ("active", "disabled")
# 平台（演示用，第一版以货架电商为主）
PLATFORMS = ("taobao", "tmall", "jd", "pdd", "douyin", "xiaohongshu", "other")
# 店铺/商品所属平台展示名
PLATFORM_LABELS = {
    "taobao": "淘宝",
    "tmall": "天猫",
    "jd": "京东",
    "pdd": "拼多多",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "other": "其他",
}
