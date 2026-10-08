"""经营数据路由：录入、批量导入、列表。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import PerformanceRecord
from ...schemas import PerformanceRecordCreate
from ...serializers import performance_out
from ...services import import_service
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}/performance-records", tags=["经营数据"])


def _parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} 格式应为 YYYY-MM-DD，收到：{value}",
        ) from exc


def compute_metrics(
    *, impressions: int, clicks: int, conversions: int, spend: float, revenue: float
) -> dict[str, float]:
    """按行业惯用口径计算派生指标（未显式提供时使用）。"""
    ctr = round(clicks / impressions * 100, 4) if impressions else 0.0
    cvr = round(conversions / clicks * 100, 4) if clicks else 0.0
    roi = round(revenue / spend, 4) if spend else 0.0
    return {"ctr": ctr, "conversion_rate": cvr, "roi": roi}


@router.get("", summary="经营数据列表")
def list_records(
    product_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(PerformanceRecord)
            .where(PerformanceRecord.product_id == product_id)
            .order_by(PerformanceRecord.period_end.desc().nullslast(), PerformanceRecord.id.desc())
            .limit(limit)
        )
    )
    total_spend = sum(r.spend for r in rows)
    total_revenue = sum(r.revenue for r in rows)
    total_impressions = sum(r.impressions for r in rows)
    total_clicks = sum(r.clicks for r in rows)
    total_conversions = sum(r.conversions for r in rows)
    return {
        "total": len(rows),
        "items": [performance_out(r) for r in rows],
        "aggregate": {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "conversions": total_conversions,
            "spend": round(total_spend, 2),
            "revenue": round(total_revenue, 2),
            "ctr": round(total_clicks / total_impressions * 100, 4) if total_impressions else 0.0,
            "conversion_rate": round(total_conversions / total_clicks * 100, 4) if total_clicks else 0.0,
            "roi": round(total_revenue / total_spend, 4) if total_spend else 0.0,
        },
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="录入经营数据",
    dependencies=[Depends(require_editor)],
)
def create_record(
    product_id: int, payload: PerformanceRecordCreate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)

    period_start = _parse_date(payload.period_start, "period_start")
    period_end = _parse_date(payload.period_end, "period_end")
    if period_start and period_end and period_end < period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="周期结束日期不能早于开始日期"
        )

    derived = compute_metrics(
        impressions=payload.impressions,
        clicks=payload.clicks,
        conversions=payload.conversions,
        spend=payload.spend,
        revenue=payload.revenue,
    )

    record = PerformanceRecord(
        product_id=product_id,
        creative_plan_id=payload.creative_plan_id,
        generated_asset_id=payload.generated_asset_id,
        promotion_link_id=payload.promotion_link_id,
        experiment_id=payload.experiment_id,
        period_start=period_start,
        period_end=period_end,
        impressions=payload.impressions,
        clicks=payload.clicks,
        ctr=payload.ctr if payload.ctr is not None else derived["ctr"],
        conversions=payload.conversions,
        conversion_rate=(
            payload.conversion_rate if payload.conversion_rate is not None else derived["conversion_rate"]
        ),
        spend=payload.spend,
        revenue=payload.revenue,
        roi=payload.roi if payload.roi is not None else derived["roi"],
        notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return performance_out(record)


@router.post(
    "/import",
    summary="批量导入经营数据（支持部分成功）",
    dependencies=[Depends(require_editor)],
)
async def import_records(
    product_id: int,
    db: Session = Depends(get_db),
    file: Optional[UploadFile] = File(
        default=None, description="经营数据 xlsx（预览阶段必传，确认阶段可省略）"
    ),
    preview_only: bool = Query(default=True, description="true=仅预览校验，false=确认导入"),
    import_id: str = Query(default="", description="确认导入时传入预览阶段返回的 import_id"),
) -> dict:
    """两段式导入：先预览（preview_only=true），确认后再提交（preview_only=false）。

    确认阶段不再重复上传文件，服务端会从暂存目录读取预览时保存的那一份。
    """
    get_product_or_404(db, product_id)
    if preview_only and file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="预览需要上传文件")
    return await import_service.handle_import(
        db,
        import_type="performance",
        file=file,  # type: ignore[arg-type]
        preview_only=preview_only,
        import_id=import_id,
        product_id=product_id,
    )
