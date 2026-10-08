"""请求/响应模型统一出口。"""

from .auth import LoginRequest, UserCreate, UserUpdate
from .common import ApiModel, ErrorRow, ImportPreview, ImportResult, MessageOut, PageResult
from .competitor import (
    CompetitorCreate,
    CompetitorUpdate,
    LinkParseTaskCreate,
    MonitorCreate,
)
from .creative import (
    AssetReviewUpdate,
    CreativePlanUpdate,
    DiagnosisGenerate,
    DiagnosisUpdate,
    ImageGenerateRequest,
    JobFailRequest,
    JobQuery,
    VideoGenerateRequest,
)
from .product import (
    InventoryAdjust,
    PlatformMappingCreate,
    ProductCreate,
    ProductUpdate,
    SkuCreate,
    SkuUpdate,
)
from .promotion import (
    AdConfirmationUpdate,
    AdExperimentGenerate,
    AdExperimentUpdate,
    AdRecommendationGenerate,
    PerformanceRecordCreate,
    PromotionLinkCreate,
    PromotionLinkUpdate,
    ReviewReportGenerate,
)
from .store import (
    AuthorizationCallbackPlaceholder,
    AuthorizationStartRequest,
    PlatformAccountCreate,
    StoreCreate,
    StoreUpdate,
)

__all__ = [
    "ApiModel",
    "PageResult",
    "MessageOut",
    "ErrorRow",
    "ImportPreview",
    "ImportResult",
    # auth
    "LoginRequest",
    "UserCreate",
    "UserUpdate",
    # store
    "StoreCreate",
    "StoreUpdate",
    "PlatformAccountCreate",
    "AuthorizationStartRequest",
    "AuthorizationCallbackPlaceholder",
    # product
    "ProductCreate",
    "ProductUpdate",
    "PlatformMappingCreate",
    "SkuCreate",
    "SkuUpdate",
    "InventoryAdjust",
    # competitor
    "CompetitorCreate",
    "CompetitorUpdate",
    "LinkParseTaskCreate",
    "MonitorCreate",
    # creative
    "DiagnosisGenerate",
    "DiagnosisUpdate",
    "CreativePlanUpdate",
    "ImageGenerateRequest",
    "VideoGenerateRequest",
    "AssetReviewUpdate",
    "JobQuery",
    "JobFailRequest",
    # promotion / ad / performance
    "PromotionLinkCreate",
    "PromotionLinkUpdate",
    "AdRecommendationGenerate",
    "AdConfirmationUpdate",
    "AdExperimentGenerate",
    "AdExperimentUpdate",
    "PerformanceRecordCreate",
    "ReviewReportGenerate",
]
