"""复盘报告路由：生成与查看。

闭环要点：报告的 ``next_actions_json`` 会在下一次生成诊断时作为输入，
从而「从复盘结果回到诊断环节」，形成下一轮优化闭环。
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ProductDiagnosis, ReviewReport
from ...providers import get_ai_provider
from ...schemas import ReviewReportGenerate
from ...serializers import review_report_out
from ...services import context_service
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}/review-reports", tags=["复盘报告"])


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


@router.get("", summary="复盘报告列表")
def list_reports(
    product_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(ReviewReport)
            .where(ReviewReport.product_id == product_id)
            .order_by(ReviewReport.id.desc())
            .limit(limit)
        )
    )
    return {"total": len(rows), "items": [review_report_out(r) for r in rows]}


@router.get("/latest", summary="最近一次复盘报告")
def latest_report(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    row = db.scalar(
        select(ReviewReport)
        .where(ReviewReport.product_id == product_id)
        .order_by(ReviewReport.id.desc())
        .limit(1)
    )
    return {"item": review_report_out(row) if row else None}


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="生成复盘报告",
    dependencies=[Depends(require_editor)],
)
def generate_report(
    product_id: int, payload: ReviewReportGenerate, db: Session = Depends(get_db)
) -> dict:
    """生成复盘报告。

    输出包含：周期摘要、核心洞察、问题判断、下一步动作（规格 1.5.9）。
    报告的下一步动作会在下一轮诊断生成时自动作为输入，形成优化闭环。
    """
    product = get_product_or_404(db, product_id)

    period_start = _parse_date(payload.period_start, "period_start")
    period_end = _parse_date(payload.period_end, "period_end")
    if period_start and period_end and period_end < period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="周期结束日期不能早于开始日期"
        )

    # 取周期内的经营数据（未指定周期则取最近全部）
    from ...models import PerformanceRecord

    stmt = select(PerformanceRecord).where(PerformanceRecord.product_id == product_id)
    if period_start:
        stmt = stmt.where(
            (PerformanceRecord.period_start.is_(None)) | (PerformanceRecord.period_start >= period_start)
        )
    if period_end:
        stmt = stmt.where(
            (PerformanceRecord.period_end.is_(None)) | (PerformanceRecord.period_end <= period_end)
        )
    records = list(
        db.scalars(stmt.order_by(PerformanceRecord.period_end.desc().nullslast()).limit(60))
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该周期内没有经营数据，请先录入或导入经营数据后再生成复盘报告",
        )

    ai_input = context_service.review_input(
        db,
        product,
        period_start=period_start.isoformat() if period_start else None,
        period_end=period_end.isoformat() if period_end else None,
        records=records,
    )
    output = get_ai_provider().generate_review_report(ai_input)

    report = ReviewReport(
        product_id=product_id,
        period_start=period_start,
        period_end=period_end,
        summary_text=output.get("summary_text", ""),
        insights_json=output.get("insights") or [],
        next_actions_json=output.get("next_actions") or [],
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        **review_report_out(report),
        "based_on_record_count": len(records),
        "closed_loop_note": (
            "报告中的「下一步动作」会在下一次生成商品诊断时自动作为输入，"
            "点击诊断页的「生成诊断」即可开启下一轮优化"
        ),
        "last_diagnosis_at": _last_diagnosis_at(db, product_id),
    }


@router.patch(
    "/{report_id}", summary="编辑复盘报告", dependencies=[Depends(require_editor)]
)
def update_report(
    product_id: int,
    report_id: int,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """人工编辑复盘结论后保存。"""
    get_product_or_404(db, product_id)
    report = db.get(ReviewReport, report_id)
    if report is None or report.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="复盘报告不存在")

    if payload.get("summary_text") is not None:
        report.summary_text = str(payload["summary_text"])
    if payload.get("insights_json") is not None:
        report.insights_json = payload["insights_json"]
    if payload.get("next_actions_json") is not None:
        report.next_actions_json = payload["next_actions_json"]

    db.commit()
    db.refresh(report)
    return review_report_out(report)


def _last_diagnosis_at(db: Session, product_id: int) -> str | None:
    row = db.scalar(
        select(ProductDiagnosis)
        .where(ProductDiagnosis.product_id == product_id)
        .order_by(ProductDiagnosis.id.desc())
        .limit(1)
    )
    return row.created_at.isoformat() if row and row.created_at else None
