"""ORM → 对外 JSON 的序列化助手。

统一在这里处理日期格式化、计算字段（如毛利率、可用库存）与展示名，
避免各路由重复拼装响应结构。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from .models import (
    AdExperiment,
    AdRecommendation,
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    CreativePlan,
    GeneratedAsset,
    GenerationJob,
    GenerationJobEvent,
    InventoryItem,
    InventoryMovement,
    PlatformAccount,
    PlatformProductMapping,
    PLATFORM_LABELS,
    Product,
    ProductDiagnosis,
    ProductSku,
    PromotionLink,
    PublicLinkParseTask,
    PerformanceRecord,
    ReviewReport,
    Store,
    SystemSetting,
    User,
)


def dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def d(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def platform_label(code: str) -> str:
    return PLATFORM_LABELS.get(code, code or "其他")


def _margin_rate(price: float, cost: float) -> float:
    if not price:
        return 0.0
    return round((price - cost) / price * 100, 2)


# --------------------------------------------------------------------- 用户
def user_out(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name or u.username,
        "role": u.role,
        "status": u.status,
        "last_login_at": dt(u.last_login_at),
        "created_at": dt(u.created_at),
        "updated_at": dt(u.updated_at),
    }


# --------------------------------------------------------------------- 店铺
def platform_account_out(a: PlatformAccount) -> dict[str, Any]:
    meta = a.auth_meta_json or {}
    return {
        "id": a.id,
        "store_id": a.store_id,
        "platform": a.platform,
        "platform_label": platform_label(a.platform),
        "account_name": a.account_name,
        "auth_status": a.auth_status,
        "auth_meta_json": meta,
        "remark": a.remark,
        # 合规提示：仅保存安全元数据
        "credential_policy": "仅保存授权状态与安全元数据，不保存明文密码 / 令牌 / Cookie",
        "created_at": dt(a.created_at),
        "updated_at": dt(a.updated_at),
    }


def store_out(s: Store, *, product_count: int = 0, low_stock_count: int = 0) -> dict[str, Any]:
    return {
        "id": s.id,
        "store_name": s.store_name,
        "platform": s.platform,
        "platform_label": platform_label(s.platform),
        "external_store_id": s.external_store_id,
        "owner_name": s.owner_name,
        "remark": s.remark,
        "product_count": product_count,
        "low_stock_count": low_stock_count,
        "account_count": len(s.accounts) if s.accounts is not None else 0,
        "created_at": dt(s.created_at),
        "updated_at": dt(s.updated_at),
    }


# --------------------------------------------------------------------- 商品
def product_out(
    p: Product,
    *,
    store_name: str = "",
    sku_count: int = 0,
    last_diagnosis_at: Optional[datetime] = None,
    last_review_at: Optional[datetime] = None,
) -> dict[str, Any]:
    return {
        "id": p.id,
        "store_id": p.store_id,
        "store_name": store_name or (p.store.store_name if p.store else ""),
        "name": p.name,
        "platform": p.platform,
        "platform_label": platform_label(p.platform),
        "category": p.category,
        "price": p.price,
        "cost": p.cost,
        "margin_rate": _margin_rate(p.price, p.cost),
        "target_audience": p.target_audience,
        "selling_points": p.selling_points,
        "product_url": p.product_url,
        "images_json": p.images_json or [],
        "status": p.status,
        "sku_count": sku_count,
        "last_diagnosis_at": dt(last_diagnosis_at),
        "last_review_at": dt(last_review_at),
        "created_at": dt(p.created_at),
        "updated_at": dt(p.updated_at),
    }


def mapping_out(m: PlatformProductMapping) -> dict[str, Any]:
    return {
        "id": m.id,
        "product_id": m.product_id,
        "platform": m.platform,
        "platform_label": platform_label(m.platform),
        "platform_product_id": m.platform_product_id,
        "platform_sku_id": m.platform_sku_id,
        "mapping_status": m.mapping_status,
        "raw_payload_json": m.raw_payload_json,
        "created_at": dt(m.created_at),
    }


def sku_out(s: ProductSku) -> dict[str, Any]:
    inv = s.inventory
    return {
        "id": s.id,
        "product_id": s.product_id,
        "sku_code": s.sku_code,
        "sku_name": s.sku_name,
        "spec_json": s.spec_json or {},
        "price": s.price,
        "cost": s.cost,
        "margin_rate": _margin_rate(s.price, s.cost),
        "status": s.status,
        "platform_sku_id": s.platform_sku_id,
        "stock_qty": inv.stock_qty if inv else 0,
        "locked_qty": inv.locked_qty if inv else 0,
        "available_qty": (inv.stock_qty - inv.locked_qty) if inv else 0,
        "warning_threshold": inv.warning_threshold if inv else 0,
        "location_text": inv.location_text if inv else "",
        "is_low_stock": bool(inv and inv.stock_qty <= inv.warning_threshold),
        "created_at": dt(s.created_at),
        "updated_at": dt(s.updated_at),
    }


def inventory_out(inv: InventoryItem) -> dict[str, Any]:
    sku = inv.sku
    return {
        "id": inv.id,
        "sku_id": inv.sku_id,
        "sku_code": sku.sku_code if sku else "",
        "sku_name": sku.sku_name if sku else "",
        "product_id": sku.product_id if sku else None,
        "stock_qty": inv.stock_qty,
        "locked_qty": inv.locked_qty,
        "available_qty": inv.available_qty,
        "warning_threshold": inv.warning_threshold,
        "location_text": inv.location_text,
        "is_low_stock": inv.stock_qty <= inv.warning_threshold,
        "updated_at": dt(inv.updated_at),
    }


def movement_out(m: InventoryMovement, *, sku_code: str = "", sku_name: str = "") -> dict[str, Any]:
    return {
        "id": m.id,
        "sku_id": m.sku_id,
        "sku_code": sku_code,
        "sku_name": sku_name,
        "movement_type": m.movement_type,
        "change_qty": m.change_qty,
        "before_qty": m.before_qty,
        "after_qty": m.after_qty,
        "reason_text": m.reason_text,
        "reference_type": m.reference_type,
        "reference_id": m.reference_id,
        "created_at": dt(m.created_at),
    }


# --------------------------------------------------------------------- 竞品
def competitor_out(c: Competitor, *, monitor: Optional[CompetitorMonitor] = None) -> dict[str, Any]:
    return {
        "id": c.id,
        "product_id": c.product_id,
        "name": c.name,
        "platform": c.platform,
        "platform_label": platform_label(c.platform),
        "url": c.url,
        "price": c.price,
        "sales_hint": c.sales_hint,
        "title": c.title,
        "main_image": c.main_image,
        "selling_points": c.selling_points,
        "review_keywords": c.review_keywords,
        "has_monitor": monitor is not None,
        "monitor_id": monitor.id if monitor else None,
        "monitor_status": monitor.monitor_status if monitor else "",
        "created_at": dt(c.created_at),
        "updated_at": dt(c.updated_at),
    }


def monitor_out(m: CompetitorMonitor) -> dict[str, Any]:
    c = m.competitor
    return {
        "id": m.id,
        "competitor_id": m.competitor_id,
        "competitor_name": c.name if c else "",
        "monitor_status": m.monitor_status,
        "interval_minutes": m.interval_minutes,
        "next_run_at": dt(m.next_run_at),
        "created_at": dt(m.created_at),
    }


def monitor_snapshot_out(s: CompetitorMonitorSnapshot) -> dict[str, Any]:
    return {
        "id": s.id,
        "monitor_id": s.monitor_id,
        "price": s.price,
        "sales_hint": s.sales_hint,
        "selling_points": s.selling_points,
        "raw_payload_json": s.raw_payload_json,
        "created_at": dt(s.created_at),
    }


def link_parse_task_out(t: PublicLinkParseTask) -> dict[str, Any]:
    return {
        "id": t.id,
        "product_id": t.product_id,
        "source_url": t.source_url,
        "task_status": t.task_status,
        "attempts": t.attempts,
        "result_json": t.result_json,
        "error_message": t.error_message,
        "created_at": dt(t.created_at),
        "updated_at": dt(t.updated_at),
    }


# --------------------------------------------------------------------- 诊断
def diagnosis_out(x: ProductDiagnosis) -> dict[str, Any]:
    return {
        "id": x.id,
        "product_id": x.product_id,
        "source_type": x.source_type,
        "summary_text": x.summary_text,
        "positioning": x.positioning,
        "price_band": x.price_band,
        "audience_insights": x.audience_insights,
        "pain_points": x.pain_points,
        "selling_point_analysis": x.selling_point_analysis,
        "risks": x.risks,
        "recommendations": x.recommendations,
        "raw_output": x.raw_output,
        "created_at": dt(x.created_at),
        "updated_at": dt(x.updated_at),
    }


# --------------------------------------------------------------------- 方案
def creative_plan_out(
    p: CreativePlan, *, asset_count: int = 0, job_count: int = 0
) -> dict[str, Any]:
    return {
        "id": p.id,
        "product_id": p.product_id,
        "plan_type": p.plan_type,
        "title": p.title,
        "content_json": p.content_json or {},
        "rationale_text": p.rationale_text,
        "status": p.status,
        "asset_count": asset_count,
        "job_count": job_count,
        "created_at": dt(p.created_at),
        "updated_at": dt(p.updated_at),
    }


# --------------------------------------------------------------------- 任务
def job_out(j: GenerationJob, *, event_count: int = 0) -> dict[str, Any]:
    return {
        "id": j.id,
        "product_id": j.product_id,
        "creative_plan_id": j.creative_plan_id,
        "job_kind": j.job_kind,
        "job_status": j.job_status,
        "attempts": j.attempts,
        "max_attempts": j.max_attempts,
        "locked_at": dt(j.locked_at),
        "locked_by": j.locked_by,
        "next_run_at": dt(j.next_run_at),
        "params_json": j.params_json or {},
        "result_json": j.result_json or {},
        "error_message": j.error_message,
        "started_at": dt(j.started_at),
        "finished_at": dt(j.finished_at),
        "created_at": dt(j.created_at),
        "event_count": event_count,
    }


def job_event_out(e: GenerationJobEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "job_id": e.job_id,
        "event_type": e.event_type,
        "event_message": e.event_message,
        "created_at": dt(e.created_at),
    }


# --------------------------------------------------------------------- 素材
def asset_out(a: GeneratedAsset, *, plan_title: str = "") -> dict[str, Any]:
    return {
        "id": a.id,
        "product_id": a.product_id,
        "creative_plan_id": a.creative_plan_id,
        "plan_title": plan_title,
        "asset_type": a.asset_type,
        "asset_url": a.asset_url,
        "model_name": a.model_name,
        "width": a.width,
        "height": a.height,
        "duration_sec": a.duration_sec,
        "review_status": a.review_status,
        "version_no": a.version_no,
        "usage_scene": a.usage_scene,
        "score": a.score,
        "tags_json": a.tags_json or [],
        "remark": a.remark,
        "created_at": dt(a.created_at),
    }


# --------------------------------------------------------------------- 链接
def promotion_link_out(link: PromotionLink, *, product_name: str = "") -> dict[str, Any]:
    return {
        "id": link.id,
        "product_id": link.product_id,
        "product_name": product_name,
        "link_name": link.link_name,
        "target_url": link.target_url,
        "tracking_code": link.tracking_code,
        "track_url": f"/api/v1/r/{link.tracking_code}",
        "utm_json": link.utm_json or {},
        "status": link.status,
        "click_count": link.click_count,
        "scene_text": link.scene_text,
        "created_at": dt(link.created_at),
    }


# --------------------------------------------------------------------- 投放
def ad_recommendation_out(r: AdRecommendation) -> dict[str, Any]:
    return {
        "id": r.id,
        "product_id": r.product_id,
        "summary_text": r.summary_text,
        "objective_text": r.objective_text,
        "audience_segments_json": r.audience_segments_json or [],
        "budget_plan_json": r.budget_plan_json or {},
        "creative_tests_json": r.creative_tests_json or [],
        "bid_strategy_json": r.bid_strategy_json or {},
        "risk_controls_json": r.risk_controls_json or [],
        "next_steps_json": r.next_steps_json or [],
        "confirm_status": r.confirm_status,
        "confirmed_by": r.confirmed_by,
        "confirmed_at": dt(r.confirmed_at),
        "confirm_remark": r.confirm_remark,
        "created_at": dt(r.created_at),
    }


def ad_experiment_out(e: AdExperiment) -> dict[str, Any]:
    return {
        "id": e.id,
        "product_id": e.product_id,
        "related_asset_id": e.related_asset_id,
        "related_link_id": e.related_link_id,
        "experiment_name": e.experiment_name,
        "target_text": e.target_text,
        "audience_text": e.audience_text,
        "budget_amount": e.budget_amount,
        "success_metric_text": e.success_metric_text,
        "hypothesis_text": e.hypothesis_text,
        "experiment_status": e.experiment_status,
        "created_at": dt(e.created_at),
        "updated_at": dt(e.updated_at),
    }


# ------------------------------------------------------------------ 经营数据
def performance_out(r: PerformanceRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "product_id": r.product_id,
        "creative_plan_id": r.creative_plan_id,
        "generated_asset_id": r.generated_asset_id,
        "promotion_link_id": r.promotion_link_id,
        "experiment_id": r.experiment_id,
        "period_start": d(r.period_start),
        "period_end": d(r.period_end),
        "impressions": r.impressions,
        "clicks": r.clicks,
        "ctr": r.ctr,
        "conversions": r.conversions,
        "conversion_rate": r.conversion_rate,
        "spend": r.spend,
        "revenue": r.revenue,
        "roi": r.roi,
        "notes": r.notes,
        "created_at": dt(r.created_at),
    }


def review_report_out(r: ReviewReport) -> dict[str, Any]:
    return {
        "id": r.id,
        "product_id": r.product_id,
        "period_start": d(r.period_start),
        "period_end": d(r.period_end),
        "summary_text": r.summary_text,
        "insights_json": r.insights_json or [],
        "next_actions_json": r.next_actions_json or [],
        "created_at": dt(r.created_at),
    }


# --------------------------------------------------------------------- 设置
def setting_out(s: SystemSetting) -> dict[str, Any]:
    return {
        "id": s.id,
        "key": s.key,
        "value": s.value,
        "value_type": s.value_type,
        "category": s.category,
        "description": s.description,
        "editable": bool(s.editable),
        "updated_at": dt(s.updated_at),
    }
