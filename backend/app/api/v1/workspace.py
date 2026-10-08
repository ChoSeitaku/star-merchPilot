"""工作区路由：模板下载、演示数据、定时任务入口、系统设置。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import SystemSetting
from ...serializers import setting_out
from ...services import demo_service, monitor_service, template_service
from ...worker import worker_manager
from ..deps import require_admin, require_editor

router = APIRouter(prefix="/workspace", tags=["工作区"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------------------------------------------------------- 模板下载
def _template_response(import_type: str) -> StreamingResponse:
    try:
        buffer, filename = template_service.build_template(import_type)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"模板不存在：{import_type}"
        ) from exc
    # 文件名含中文，使用 RFC 5987 编码，避免浏览器乱码
    from urllib.parse import quote

    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return StreamingResponse(
        buffer,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": disposition,
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/templates/products", summary="下载商品导入模板")
def template_products() -> StreamingResponse:
    return _template_response("products")


@router.get("/templates/sku-inventory", summary="下载 SKU 库存导入模板")
def template_sku_inventory() -> StreamingResponse:
    return _template_response("sku-inventory")


@router.get("/templates/performance-records", summary="下载经营数据导入模板")
def template_performance() -> StreamingResponse:
    return _template_response("performance-records")


@router.get("/templates/platform-mappings", summary="下载平台字段映射导入模板")
def template_platform_mappings() -> StreamingResponse:
    return _template_response("platform-mappings")


@router.get("/templates", summary="模板清单")
def list_templates() -> dict:
    return {
        "items": [
            {
                "import_type": key,
                "title": spec["title"],
                "filename": spec["filename"],
                "description": spec["description"],
                "endpoint": f"/api/v1/workspace/templates/{key}",
                "column_count": len(spec["columns"]),
            }
            for key, spec in template_service.TEMPLATES.items()
        ]
    }


# ---------------------------------------------------------------- 首页工作台
@router.get("/dashboard", summary="首页工作台概览（店铺卡片 / 低库存 / 商品池入口）")
def dashboard(
    db: Session = Depends(get_db),
    platform: str = Query(default="", description="按平台筛选店铺与商品"),
) -> dict:
    """工作台聚合数据：店铺卡片、平台分布、低库存提示、商品池统计、闭环进度。"""
    from sqlalchemy import func

    from ...models import (
        AdRecommendation,
        CreativePlan,
        GeneratedAsset,
        GenerationJob,
        InventoryItem,
        Product,
        ProductDiagnosis,
        ProductSku,
        ReviewReport,
        Store,
    )

    store_stmt = select(Store)
    if platform:
        store_stmt = store_stmt.where(Store.platform == platform)
    stores = list(db.scalars(store_stmt.order_by(Store.id.desc())))

    store_cards: list[dict] = []
    for store in stores:
        product_ids = list(
            db.scalars(select(Product.id).where(Product.store_id == store.id))
        )
        product_count = len(product_ids)
        low_stock = 0
        if product_ids:
            low_stock = (
                db.scalar(
                    select(func.count(InventoryItem.id))
                    .join(ProductSku, ProductSku.id == InventoryItem.sku_id)
                    .where(
                        ProductSku.product_id.in_(product_ids),
                        InventoryItem.stock_qty <= InventoryItem.warning_threshold,
                    )
                )
                or 0
            )
        store_cards.append(
            {
                "id": store.id,
                "store_name": store.store_name,
                "platform": store.platform,
                "owner_name": store.owner_name,
                "product_count": product_count,
                "low_stock_count": low_stock,
                "updated_at": store.updated_at.isoformat() if store.updated_at else None,
            }
        )

    # 平台分布（用于筛选器与卡片统计）
    platform_rows = db.execute(
        select(Store.platform, func.count(Store.id)).group_by(Store.platform)
    ).all()
    product_platform_rows = db.execute(
        select(Product.platform, func.count(Product.id)).group_by(Product.platform)
    ).all()

    # 低库存明细（前 10 条）
    low_stmt = (
        select(InventoryItem, ProductSku, Product)
        .join(ProductSku, ProductSku.id == InventoryItem.sku_id)
        .join(Product, Product.id == ProductSku.product_id)
        .where(InventoryItem.stock_qty <= InventoryItem.warning_threshold)
    )
    if platform:
        low_stmt = low_stmt.where(Product.platform == platform)
    low_rows = db.execute(low_stmt.order_by(InventoryItem.stock_qty.asc()).limit(10)).all()

    total_low_stock = db.scalar(
        select(func.count(InventoryItem.id)).where(
            InventoryItem.stock_qty <= InventoryItem.warning_threshold
        )
    ) or 0

    product_stmt = select(Product)
    if platform:
        product_stmt = product_stmt.where(Product.platform == platform)
    product_ids_all = list(db.scalars(product_stmt.with_only_columns(Product.id)))

    def _count_product_scoped(model, *conditions) -> int:
        """统计挂在商品下的记录数（model 必须带 product_id 列）。"""
        if not product_ids_all:
            return 0
        return (
            db.scalar(
                select(func.count(model.id)).where(
                    model.product_id.in_(product_ids_all), *conditions
                )
            )
            or 0
        )

    def _count_products(*conditions) -> int:
        if not product_ids_all:
            return 0
        return (
            db.scalar(
                select(func.count(Product.id)).where(Product.id.in_(product_ids_all), *conditions)
            )
            or 0
        )

    job_stats = {}
    if product_ids_all:
        job_rows = db.execute(
            select(GenerationJob.job_status, func.count(GenerationJob.id))
            .where(GenerationJob.product_id.in_(product_ids_all))
            .group_by(GenerationJob.job_status)
        ).all()
        job_stats = {status_name: count for status_name, count in job_rows}

    return {
        "stores": store_cards,
        "platform_filter": {
            "selected": platform,
            "store_platforms": [
                {"platform": p, "count": c} for p, c in sorted(platform_rows, key=lambda x: -x[1])
            ],
            "product_platforms": [
                {"platform": p, "count": c}
                for p, c in sorted(product_platform_rows, key=lambda x: -x[1])
            ],
        },
        "low_stock": {
            "total": total_low_stock,
            "items": [
                {
                    "sku_id": inv.sku_id,
                    "sku_code": sku.sku_code,
                    "sku_name": sku.sku_name,
                    "product_id": prod.id,
                    "product_name": prod.name,
                    "store_id": prod.store_id,
                    "stock_qty": inv.stock_qty,
                    "warning_threshold": inv.warning_threshold,
                }
                for inv, sku, prod in low_rows
            ],
        },
        "product_pool": {
            "total_products": len(product_ids_all),
            "active_products": _count_products(Product.status == "active"),
            "draft_products": _count_products(Product.status == "draft"),
            "inactive_products": _count_products(Product.status == "inactive"),
        },
        "loop_progress": {
            "diagnoses": _count_product_scoped(ProductDiagnosis),
            "main_image_plans": _count_product_scoped(
                CreativePlan, CreativePlan.plan_type == "main_image"
            ),
            "video_scripts": _count_product_scoped(
                CreativePlan, CreativePlan.plan_type == "video_script"
            ),
            "assets": _count_product_scoped(GeneratedAsset),
            "approved_assets": _count_product_scoped(
                GeneratedAsset, GeneratedAsset.review_status == "approved"
            ),
            "ad_recommendations": _count_product_scoped(AdRecommendation),
            "confirmed_ads": _count_product_scoped(
                AdRecommendation, AdRecommendation.confirm_status == "confirmed"
            ),
            "review_reports": _count_product_scoped(ReviewReport),
        },
        "jobs": {
            "by_status": job_stats,
            "running": len(worker_manager.status()["inflight_jobs"]),
            "worker": worker_manager.status(),
        },
    }


# ---------------------------------------------------------------- 演示数据
@router.post(
    "/demo-data",
    summary="创建演示数据（一次性铺满完整闭环）",
    dependencies=[Depends(require_admin)],
)
def create_demo_data(
    db: Session = Depends(get_db),
    force: bool = Query(default=False, description="已存在演示数据时是否强制再建一套"),
) -> dict:
    return demo_service.create_demo_data(db, force=force)


# ------------------------------------------------------------ 竞品监控调度
@router.post(
    "/competitor-monitors/run-due",
    summary="运行到期的竞品监控（定时任务入口）",
    dependencies=[Depends(require_editor)],
)
def run_due_monitors(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    results = monitor_service.run_due_monitors(db, limit=limit)
    return {
        "total": len(results),
        "items": results,
        "message": f"本次运行了 {len(results)} 个到期监控" if results else "当前没有到期的监控任务",
    }


# ---------------------------------------------------------------- 系统设置
@router.get("/settings", summary="系统设置列表（模型 / 队列 / 系统参数）")
def list_settings(
    db: Session = Depends(get_db),
    category: str = Query(default="", description="model / queue / system / compliance"),
) -> dict:
    stmt = select(SystemSetting)
    if category:
        stmt = stmt.where(SystemSetting.category == category)
    rows = list(db.scalars(stmt.order_by(SystemSetting.category, SystemSetting.id)))

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.category, []).append(setting_out(row))

    from ...providers import active_provider_name, available_providers
    from ...services.settings_service import queue_config

    return {
        "total": len(rows),
        "categories": grouped,
        "runtime": {
            "active_provider": active_provider_name(),
            "available_providers": available_providers(),
            "queue": queue_config(db),
            "worker": worker_manager.status(),
        },
    }


@router.patch(
    "/settings", summary="更新系统设置（仅管理员）", dependencies=[Depends(require_admin)]
)
def update_settings(payload: dict, db: Session = Depends(get_db)) -> dict:
    """批量更新可编辑的配置项。

    只读项（如合规声明）不允许修改，避免误改造成演示结果与说明不一致。
    """
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请以 {\"items\": [{\"key\": \"...\", \"value\": \"...\"}]} 的形式提交",
        )

    updated: list[str] = []
    rejected: list[str] = []
    for item in items:
        key = (item or {}).get("key")
        if not key:
            continue
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if row is None:
            rejected.append(f"{key}（不存在）")
            continue
        if not row.editable:
            rejected.append(f"{key}（只读项）")
            continue
        row.value = str(item.get("value", ""))
        updated.append(key)

    db.commit()
    return {
        "updated": updated,
        "rejected": rejected,
        "message": f"已更新 {len(updated)} 项配置"
        + (f"，拒绝 {len(rejected)} 项：{'、'.join(rejected)}" if rejected else ""),
    }
