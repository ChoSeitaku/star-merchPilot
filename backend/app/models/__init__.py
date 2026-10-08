"""全部数据模型。导入本包即完成所有表的注册（create_all 依赖此副作用）。"""

from .ad import AdExperiment, AdRecommendation
from .asset import GeneratedAsset
from .base import (
    AD_CONFIRM_STATUSES,
    AD_EXPERIMENT_STATUSES,
    ASSET_REVIEW_STATUSES,
    CREATIVE_PLAN_STATUSES,
    CREATIVE_PLAN_TYPES,
    JOB_KINDS,
    JOB_STATUSES,
    PLATFORM_LABELS,
    PLATFORMS,
    PRODUCT_STATUSES,
    USER_ROLES,
    USER_STATUSES,
    Base,
)
from .competitor import (
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    PublicLinkParseTask,
)
from .creative import CreativePlan
from .diagnosis import ProductDiagnosis
from .job import GenerationJob, GenerationJobEvent
from .performance import PerformanceRecord, ReviewReport
from .product import (
    InventoryItem,
    InventoryMovement,
    PlatformProductMapping,
    Product,
    ProductSku,
)
from .promotion import PromotionLink, PromotionLinkClick
from .setting import SystemSetting
from .store import PlatformAccount, Store
from .user import User

__all__ = [
    "Base",
    "User",
    "Store",
    "PlatformAccount",
    "Product",
    "PlatformProductMapping",
    "ProductSku",
    "InventoryItem",
    "InventoryMovement",
    "Competitor",
    "CompetitorMonitor",
    "CompetitorMonitorSnapshot",
    "PublicLinkParseTask",
    "ProductDiagnosis",
    "CreativePlan",
    "GenerationJob",
    "GenerationJobEvent",
    "GeneratedAsset",
    "PromotionLink",
    "PromotionLinkClick",
    "AdRecommendation",
    "AdExperiment",
    "PerformanceRecord",
    "ReviewReport",
    "SystemSetting",
    # 枚举常量
    "PRODUCT_STATUSES",
    "CREATIVE_PLAN_STATUSES",
    "CREATIVE_PLAN_TYPES",
    "JOB_STATUSES",
    "JOB_KINDS",
    "AD_CONFIRM_STATUSES",
    "AD_EXPERIMENT_STATUSES",
    "ASSET_REVIEW_STATUSES",
    "USER_ROLES",
    "USER_STATUSES",
    "PLATFORMS",
    "PLATFORM_LABELS",
]
