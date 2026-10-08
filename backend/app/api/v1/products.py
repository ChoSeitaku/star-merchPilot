"""商品、平台映射、SKU 与库存路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import (
    GeneratedAsset,
    InventoryItem,
    InventoryMovement,
    PlatformProductMapping,
    Product,
    ProductDiagnosis,
    ProductSku,
    ReviewReport,
    Store,
)
from ...schemas import (
    InventoryAdjust,
    PlatformMappingCreate,
    ProductCreate,
    ProductUpdate,
    SkuCreate,
    SkuUpdate,
)
from ...serializers import (
    inventory_out,
    mapping_out,
    movement_out,
    product_out,
    sku_out,
)
from ..deps import require_editor

router = APIRouter(prefix="/products", tags=["商品管理"])


# ------------------------------------------------------------------ 公共工具
def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product


def _enrich(db: Session, products: list[Product]) -> list[dict]:
    """批量补齐商品列表所需的统计字段，避免 N+1 查询。"""
    ids = [p.id for p in products]
    if not ids:
        return []

    store_names = dict(db.execute(select(Store.id, Store.store_name)).all())
    sku_counts = dict(
        db.execute(
            select(ProductSku.product_id, func.count(ProductSku.id))
            .where(ProductSku.product_id.in_(ids))
            .group_by(ProductSku.product_id)
        ).all()
    )
    last_diag = dict(
        db.execute(
            select(ProductDiagnosis.product_id, func.max(ProductDiagnosis.created_at))
            .where(ProductDiagnosis.product_id.in_(ids))
            .group_by(ProductDiagnosis.product_id)
        ).all()
    )
    last_review = dict(
        db.execute(
            select(ReviewReport.product_id, func.max(ReviewReport.created_at))
            .where(ReviewReport.product_id.in_(ids))
            .group_by(ReviewReport.product_id)
        ).all()
    )
    return [
        product_out(
            p,
            store_name=store_names.get(p.store_id, ""),
            sku_count=sku_counts.get(p.id, 0),
            last_diagnosis_at=last_diag.get(p.id),
            last_review_at=last_review.get(p.id),
        )
        for p in products
    ]


def _product_detail(db: Session, product: Product) -> dict:
    data = _enrich(db, [product])[0]
    data["skus"] = [sku_out(s) for s in product.skus]
    data["mappings"] = [
        mapping_out(m)
        for m in db.scalars(
            select(PlatformProductMapping)
            .where(PlatformProductMapping.product_id == product.id)
            .order_by(PlatformProductMapping.id.desc())
        )
    ]
    return data


# -------------------------------------------------------------------- 商品
@router.get("", summary="商品列表（商品池）")
def list_products(
    db: Session = Depends(get_db),
    store_id: Optional[int] = Query(default=None),
    platform: str = Query(default=""),
    status_filter: str = Query(default="", alias="status", description="draft / active / inactive"),
    category: str = Query(default=""),
    keyword: str = Query(default="", description="按商品名或类目模糊搜索"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    conditions = []
    if store_id is not None:
        conditions.append(Product.store_id == store_id)
    if platform:
        conditions.append(Product.platform == platform)
    if status_filter:
        conditions.append(Product.status == status_filter)
    if category:
        conditions.append(Product.category == category)
    if keyword:
        like = f"%{keyword}%"
        conditions.append(or_(Product.name.like(like), Product.category.like(like)))

    stmt = select(Product)
    if conditions:
        stmt = stmt.where(*conditions)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(Product.id.desc()).offset(offset).limit(limit)))
    return {"total": total, "items": _enrich(db, rows)}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="创建商品",
    dependencies=[Depends(require_editor)],
)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> dict:
    store = db.get(Store, payload.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属店铺不存在")

    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_detail(db, product)


@router.get("/{product_id}", summary="商品详情")
def get_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    return _product_detail(db, get_product_or_404(db, product_id))


@router.patch(
    "/{product_id}", summary="更新商品", dependencies=[Depends(require_editor)]
)
def update_product(
    product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)
) -> dict:
    product = get_product_or_404(db, product_id)
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "store_id" in data and db.get(Store, data["store_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属店铺不存在")
    for field, value in data.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return _product_detail(db, product)


@router.delete(
    "/{product_id}",
    summary="删除商品（级联删除其下全部运营数据）",
    dependencies=[Depends(require_editor)],
)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = get_product_or_404(db, product_id)
    db.delete(product)
    db.commit()
    return {"message": f"商品「{product.name}」及其关联数据已删除", "product_id": product_id}


# ---------------------------------------------------------------- 平台映射
@router.get("/{product_id}/platform-mappings", summary="商品平台映射列表")
def list_mappings(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(PlatformProductMapping)
            .where(PlatformProductMapping.product_id == product_id)
            .order_by(PlatformProductMapping.id.desc())
        )
    )
    return {"total": len(rows), "items": [mapping_out(m) for m in rows]}


@router.post(
    "/{product_id}/platform-mappings",
    status_code=status.HTTP_201_CREATED,
    summary="创建 / 更新商品平台映射",
    dependencies=[Depends(require_editor)],
)
def create_mapping(
    product_id: int, payload: PlatformMappingCreate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
    mapping = PlatformProductMapping(product_id=product_id, **payload.model_dump())
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping_out(mapping)


# ---------------------------------------------------------------------- SKU
@router.get("/{product_id}/skus", summary="SKU 列表（含库存）")
def list_skus(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = get_product_or_404(db, product_id)
    return {"total": len(product.skus), "items": [sku_out(s) for s in product.skus]}


@router.post(
    "/{product_id}/skus",
    status_code=status.HTTP_201_CREATED,
    summary="新增 SKU（同时建立库存记录并写入期初流水）",
    dependencies=[Depends(require_editor)],
)
def create_sku(product_id: int, payload: SkuCreate, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)

    duplicated = db.scalar(
        select(ProductSku.id).where(
            ProductSku.product_id == product_id, ProductSku.sku_code == payload.sku_code
        )
    )
    if duplicated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"SKU 编码 {payload.sku_code} 已存在"
        )

    sku = ProductSku(
        product_id=product_id,
        sku_code=payload.sku_code,
        sku_name=payload.sku_name or payload.sku_code,
        spec_json=payload.spec_json or {},
        price=payload.price,
        cost=payload.cost,
        status=payload.status,
        platform_sku_id=payload.platform_sku_id,
    )
    db.add(sku)
    db.flush()

    db.add(
        InventoryItem(
            sku_id=sku.id,
            stock_qty=payload.stock_qty,
            locked_qty=0,
            warning_threshold=payload.warning_threshold,
            location_text=payload.location_text,
        )
    )
    if payload.stock_qty:
        db.add(
            InventoryMovement(
                sku_id=sku.id,
                movement_type="init",
                change_qty=payload.stock_qty,
                before_qty=0,
                after_qty=payload.stock_qty,
                reason_text="新建 SKU 期初库存",
                reference_type="sku_create",
                reference_id=sku.id,
            )
        )

    db.commit()
    db.refresh(sku)
    return sku_out(sku)


@router.patch(
    "/{product_id}/skus/{sku_id}",
    summary="更新 SKU（含启停用）",
    dependencies=[Depends(require_editor)],
)
def update_sku(
    product_id: int, sku_id: int, payload: SkuUpdate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
    sku = db.get(ProductSku, sku_id)
    if sku is None or sku.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU 不存在")
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(sku, field, value)
    db.commit()
    db.refresh(sku)
    return sku_out(sku)


@router.get("/{product_id}/skus/{sku_id}/movements", summary="单个 SKU 的库存流水")
def sku_movements(
    product_id: int,
    sku_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    get_product_or_404(db, product_id)
    sku = db.get(ProductSku, sku_id)
    if sku is None or sku.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU 不存在")
    rows = list(
        db.scalars(
            select(InventoryMovement)
            .where(InventoryMovement.sku_id == sku_id)
            .order_by(InventoryMovement.id.desc())
            .limit(limit)
        )
    )
    return {
        "total": len(rows),
        "items": [movement_out(m, sku_code=sku.sku_code, sku_name=sku.sku_name) for m in rows],
    }


# -------------------------------------------------------------------- 库存
@router.get("/{product_id}/inventory", summary="商品库存概览")
def product_inventory(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = get_product_or_404(db, product_id)
    items = [s.inventory for s in product.skus if s.inventory is not None]
    return {
        "product_id": product_id,
        "sku_count": len(product.skus),
        "total_stock": sum(i.stock_qty for i in items),
        "total_locked": sum(i.locked_qty for i in items),
        "total_available": sum(i.available_qty for i in items),
        "low_stock_count": sum(1 for i in items if i.stock_qty <= i.warning_threshold),
        "items": [inventory_out(i) for i in items],
    }


@router.post(
    "/{product_id}/skus/{sku_id}/inventory/adjust",
    summary="库存调整（自动写入库存流水）",
    dependencies=[Depends(require_editor)],
)
def adjust_inventory(
    product_id: int,
    sku_id: int,
    payload: InventoryAdjust,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    sku = db.get(ProductSku, sku_id)
    if sku is None or sku.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU 不存在")

    inv = sku.inventory
    if inv is None:
        inv = InventoryItem(sku_id=sku.id, stock_qty=0, locked_qty=0, warning_threshold=10)
        db.add(inv)
        db.flush()

    before = inv.stock_qty
    after = before + payload.change_qty
    if after < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"库存不足：当前 {before}，本次变动 {payload.change_qty}",
        )

    inv.stock_qty = after
    inv.updated_at = utcnow()
    if payload.warning_threshold is not None:
        inv.warning_threshold = payload.warning_threshold
    if payload.location_text is not None:
        inv.location_text = payload.location_text

    db.add(
        InventoryMovement(
            sku_id=sku.id,
            movement_type=payload.movement_type,
            change_qty=payload.change_qty,
            before_qty=before,
            after_qty=after,
            reason_text=payload.reason_text or "手工库存调整",
            reference_type="manual",
            reference_id=None,
        )
    )
    db.commit()
    db.refresh(inv)
    return {
        **inventory_out(inv),
        "message": f"库存已从 {before} 调整为 {after}，流水已记录",
    }


@router.get("/{product_id}/inventory/movements", summary="商品全部库存流水")
def product_movements(
    product_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    product = get_product_or_404(db, product_id)
    sku_map = {s.id: s for s in product.skus}
    rows = list(
        db.scalars(
            select(InventoryMovement)
            .where(InventoryMovement.sku_id.in_(list(sku_map.keys()) or [0]))
            .order_by(InventoryMovement.id.desc())
            .limit(limit)
        )
    )
    return {
        "total": len(rows),
        "items": [
            movement_out(
                m,
                sku_code=sku_map[m.sku_id].sku_code if m.sku_id in sku_map else "",
                sku_name=sku_map[m.sku_id].sku_name if m.sku_id in sku_map else "",
            )
            for m in rows
        ],
    }


# ---------------------------------------------------------------- 工作台统计
@router.get("/{product_id}/timeline", summary="商品运营时间线（闭环进度）")
def product_timeline(product_id: int, db: Session = Depends(get_db)) -> dict:
    """返回该商品在闭环各环节的完成情况，用于详情页展示闭环进度。"""
    product = get_product_or_404(db, product_id)
    from ...models import (
        AdExperiment,
        AdRecommendation,
        Competitor,
        CreativePlan,
        PromotionLink,
    )

    def _count(model, *conditions) -> int:
        return db.scalar(select(func.count(model.id)).where(*conditions)) or 0

    diag_count = _count(ProductDiagnosis, ProductDiagnosis.product_id == product_id)
    image_plans = _count(
        CreativePlan,
        CreativePlan.product_id == product_id,
        CreativePlan.plan_type == "main_image",
    )
    video_plans = _count(
        CreativePlan,
        CreativePlan.product_id == product_id,
        CreativePlan.plan_type == "video_script",
    )
    asset_count = _count(GeneratedAsset, GeneratedAsset.product_id == product_id)
    approved_assets = _count(
        GeneratedAsset,
        GeneratedAsset.product_id == product_id,
        GeneratedAsset.review_status == "approved",
    )
    ad_count = _count(AdRecommendation, AdRecommendation.product_id == product_id)
    confirmed_ads = _count(
        AdRecommendation,
        AdRecommendation.product_id == product_id,
        AdRecommendation.confirm_status == "confirmed",
    )
    experiment_count = _count(AdExperiment, AdExperiment.product_id == product_id)
    report_count = _count(ReviewReport, ReviewReport.product_id == product_id)

    from ...models import PerformanceRecord

    perf_count = _count(PerformanceRecord, PerformanceRecord.product_id == product_id)
    link_count = _count(PromotionLink, PromotionLink.product_id == product_id)
    competitor_count = _count(Competitor, Competitor.product_id == product_id)

    steps = [
        {"key": "product", "label": "录入商品", "done": True, "detail": f"{len(product.skus)} 个 SKU"},
        {"key": "competitor", "label": "补充竞品", "done": competitor_count > 0, "detail": f"{competitor_count} 个竞品"},
        {"key": "diagnosis", "label": "生成诊断", "done": diag_count > 0, "detail": f"{diag_count} 份诊断"},
        {"key": "main_image", "label": "生成主图方案", "done": image_plans > 0, "detail": f"{image_plans} 个方案"},
        {"key": "video", "label": "生成视频脚本", "done": video_plans > 0, "detail": f"{video_plans} 个脚本"},
        {"key": "asset", "label": "生成素材", "done": asset_count > 0, "detail": f"{asset_count} 个素材"},
        {"key": "review_asset", "label": "人工审核素材", "done": approved_assets > 0, "detail": f"{approved_assets} 个已通过"},
        {"key": "ad", "label": "生成投放建议", "done": ad_count > 0, "detail": f"{ad_count} 条建议"},
        {"key": "ad_confirm", "label": "人工确认投放", "done": confirmed_ads > 0, "detail": f"{confirmed_ads} 条已确认"},
        {"key": "experiment", "label": "投放实验计划", "done": experiment_count > 0, "detail": f"{experiment_count} 个实验"},
        {"key": "link", "label": "推广链接", "done": link_count > 0, "detail": f"{link_count} 条链接"},
        {"key": "performance", "label": "回填经营数据", "done": perf_count > 0, "detail": f"{perf_count} 条数据"},
        {"key": "report", "label": "生成复盘报告", "done": report_count > 0, "detail": f"{report_count} 份报告"},
    ]
    completed = sum(1 for s in steps if s["done"])
    return {
        "product_id": product_id,
        "completed_steps": completed,
        "total_steps": len(steps),
        "progress_percent": round(completed / len(steps) * 100, 1),
        "steps": steps,
        "next_step": next((s for s in steps if not s["done"]), None),
    }
