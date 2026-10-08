"""把数据库中的真实业务数据整理成内容生成所需的输入。

这些 payload 会同时用于：
1. 传给 ``AiProvider`` 生成结构化内容；
2. 写入 ``raw_output`` / ``result_json`` 作为生成依据留痕。

所有函数只做读取与序列化，不修改数据。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Competitor,
    CreativePlan,
    GeneratedAsset,
    InventoryItem,
    Product,
    ProductDiagnosis,
    ProductSku,
    PromotionLink,
    PerformanceRecord,
    ReviewReport,
)


def product_payload(db: Session, product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "platform": product.platform,
        "category": product.category,
        "price": product.price,
        "cost": product.cost,
        "target_audience": product.target_audience,
        "selling_points": product.selling_points,
        "product_url": product.product_url,
        "status": product.status,
    }


def sku_payload(db: Session, product_id: int) -> list[dict[str, Any]]:
    skus = list(
        db.scalars(select(ProductSku).where(ProductSku.product_id == product_id).order_by(ProductSku.id))
    )
    out = []
    for s in skus:
        inv = s.inventory
        out.append(
            {
                "id": s.id,
                "sku_code": s.sku_code,
                "sku_name": s.sku_name,
                "price": s.price,
                "cost": s.cost,
                "status": s.status,
                "spec": s.spec_json or {},
                "stock_qty": inv.stock_qty if inv else 0,
                "warning_threshold": inv.warning_threshold if inv else 0,
            }
        )
    return out


def competitor_payload(db: Session, product_id: int) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(select(Competitor).where(Competitor.product_id == product_id).order_by(Competitor.id))
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "platform": c.platform,
            "url": c.url,
            "price": c.price,
            "sales_hint": c.sales_hint,
            "title": c.title,
            "selling_points": c.selling_points,
            "review_keywords": c.review_keywords,
        }
        for c in rows
    ]


def performance_payload(db: Session, product_id: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(PerformanceRecord)
            .where(PerformanceRecord.product_id == product_id)
            .order_by(PerformanceRecord.period_end.desc().nullslast(), PerformanceRecord.id.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": r.id,
            "period_start": r.period_start.isoformat() if r.period_start else "",
            "period_end": r.period_end.isoformat() if r.period_end else "",
            "impressions": r.impressions,
            "clicks": r.clicks,
            "ctr": r.ctr,
            "conversions": r.conversions,
            "conversion_rate": r.conversion_rate,
            "spend": r.spend,
            "revenue": r.revenue,
            "roi": r.roi,
            "notes": r.notes,
        }
        for r in rows
    ]


def latest_diagnosis(db: Session, product_id: int) -> Optional[ProductDiagnosis]:
    return db.scalar(
        select(ProductDiagnosis)
        .where(ProductDiagnosis.product_id == product_id)
        .order_by(ProductDiagnosis.id.desc())
        .limit(1)
    )


def latest_review_actions(db: Session, product_id: int) -> list[str]:
    """取最近一份复盘报告的「下一步动作」，作为下一轮诊断的输入，形成闭环。"""
    report = db.scalar(
        select(ReviewReport)
        .where(ReviewReport.product_id == product_id)
        .order_by(ReviewReport.id.desc())
        .limit(1)
    )
    if report is None or not report.next_actions_json:
        return []
    actions = []
    for item in report.next_actions_json:
        if isinstance(item, dict):
            title = item.get("action_title") or item.get("title") or ""
            detail = item.get("action_detail") or item.get("detail") or ""
            actions.append(f"{title}：{detail}".strip("："))
        else:
            actions.append(str(item))
    return [a for a in actions if a]


def low_stock_count(db: Session, product_id: int) -> int:
    """统计该商品低于预警阈值的 SKU 数量。"""
    return (
        db.scalar(
            select(func.count(InventoryItem.id))
            .join(ProductSku, ProductSku.id == InventoryItem.sku_id)
            .where(
                ProductSku.product_id == product_id,
                InventoryItem.stock_qty <= InventoryItem.warning_threshold,
            )
        )
        or 0
    )


def asset_payload(db: Session, product_id: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(GeneratedAsset)
            .where(GeneratedAsset.product_id == product_id)
            .order_by(GeneratedAsset.id.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": a.id,
            "asset_type": a.asset_type,
            "asset_url": a.asset_url,
            "usage_scene": a.usage_scene,
            "review_status": a.review_status,
            "score": a.score,
            "tags": a.tags_json or [],
        }
        for a in rows
    ]


def link_payload(db: Session, product_id: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(PromotionLink)
            .where(PromotionLink.product_id == product_id)
            .order_by(PromotionLink.id.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": link.id,
            "link_name": link.link_name,
            "scene_text": link.scene_text,
            "tracking_code": link.tracking_code,
            "click_count": link.click_count,
        }
        for link in rows
    ]


def plan_payload(db: Session, product_id: int) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(select(CreativePlan).where(CreativePlan.product_id == product_id).order_by(CreativePlan.id))
    )
    return [
        {
            "id": p.id,
            "plan_type": p.plan_type,
            "title": p.title,
            "status": p.status,
        }
        for p in rows
    ]


def diagnosis_input(db: Session, product: Product, include_review_actions: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "product": product_payload(db, product),
        "skus": sku_payload(db, product.id),
        "competitors": competitor_payload(db, product.id),
        "performance": performance_payload(db, product.id),
        "low_stock_count": low_stock_count(db, product.id),
        "prior_actions": latest_review_actions(db, product.id) if include_review_actions else [],
        "live_plans": plan_payload(db, product.id),
    }
    previous = latest_diagnosis(db, product.id)
    payload["previous_diagnosis"] = (
        {"id": previous.id, "summary_text": previous.summary_text} if previous else None
    )
    return payload


def creative_input(db: Session, product: Product) -> dict[str, Any]:
    return {
        "product": product_payload(db, product),
        "skus": sku_payload(db, product.id),
        "competitors": competitor_payload(db, product.id),
        "performance": performance_payload(db, product.id),
        "diagnosis": (
            {
                "positioning": d.positioning,
                "pain_points": d.pain_points,
                "selling_point_analysis": d.selling_point_analysis,
                "recommendations": d.recommendations,
            }
            if (d := latest_diagnosis(db, product.id))
            else None
        ),
    }


def ad_input(db: Session, product: Product) -> dict[str, Any]:
    return {
        "product": product_payload(db, product),
        "competitors": competitor_payload(db, product.id),
        "performance": performance_payload(db, product.id),
        "assets": asset_payload(db, product.id),
        "links": link_payload(db, product.id),
        "diagnosis": (
            {"summary_text": d.summary_text, "recommendations": d.recommendations}
            if (d := latest_diagnosis(db, product.id))
            else None
        ),
    }


def review_input(
    db: Session,
    product: Product,
    *,
    period_start: Optional[str],
    period_end: Optional[str],
    records: list[PerformanceRecord],
) -> dict[str, Any]:
    return {
        "product": product_payload(db, product),
        "period_start": period_start or "",
        "period_end": period_end or "",
        "performance": [
            {
                "id": r.id,
                "period_start": r.period_start.isoformat() if r.period_start else "",
                "period_end": r.period_end.isoformat() if r.period_end else "",
                "impressions": r.impressions,
                "clicks": r.clicks,
                "ctr": r.ctr,
                "conversions": r.conversions,
                "conversion_rate": r.conversion_rate,
                "spend": r.spend,
                "revenue": r.revenue,
                "roi": r.roi,
                "notes": r.notes,
            }
            for r in records
        ],
        "diagnosis": (
            {"positioning": d.positioning, "recommendations": d.recommendations}
            if (d := latest_diagnosis(db, product.id))
            else None
        ),
        "plans": plan_payload(db, product.id),
    }
