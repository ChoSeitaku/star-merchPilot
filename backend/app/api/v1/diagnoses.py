"""商品诊断路由：生成、编辑保存、列表。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import ProductDiagnosis
from ...providers import get_ai_provider
from ...schemas import DiagnosisGenerate, DiagnosisUpdate
from ...serializers import diagnosis_out
from ...services import context_service
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}/diagnoses", tags=["商品诊断"])


@router.get("", summary="诊断列表")
def list_diagnoses(
    product_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(ProductDiagnosis)
            .where(ProductDiagnosis.product_id == product_id)
            .order_by(ProductDiagnosis.id.desc())
            .limit(limit)
        )
    )
    return {"total": len(rows), "items": [diagnosis_out(d) for d in rows]}


@router.get("/latest", summary="最近一次诊断")
def latest_diagnosis(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    row = db.scalar(
        select(ProductDiagnosis)
        .where(ProductDiagnosis.product_id == product_id)
        .order_by(ProductDiagnosis.id.desc())
        .limit(1)
    )
    return {"item": diagnosis_out(row) if row else None}


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="生成商品诊断",
    dependencies=[Depends(require_editor)],
)
def generate_diagnosis(
    product_id: int, payload: DiagnosisGenerate, db: Session = Depends(get_db)
) -> dict:
    """生成结构化商品诊断。

    输出包含：商品定位、价格带分析、目标人群洞察、用户痛点、
    卖点分析、风险点、优化建议（规格 1.5.9）。
    """
    product = get_product_or_404(db, product_id)

    ai_input = context_service.diagnosis_input(
        db, product, include_review_actions=payload.include_review_actions
    )
    output = get_ai_provider().generate_diagnosis(ai_input)

    diagnosis = ProductDiagnosis(
        product_id=product_id,
        source_type=payload.source_type or "ai_mock",
        summary_text=output.get("summary_text", ""),
        positioning=output.get("positioning", ""),
        price_band=output.get("price_band", ""),
        audience_insights=output.get("audience_insights", ""),
        pain_points=output.get("pain_points", ""),
        selling_point_analysis=output.get("selling_point_analysis", ""),
        risks=output.get("risks", ""),
        recommendations=output.get("recommendations", ""),
        raw_output={
            "generated_at": utcnow().isoformat(),
            "provider": get_ai_provider().name,
            "input_summary": {
                "sku_count": len(ai_input.get("skus", [])),
                "competitor_count": len(ai_input.get("competitors", [])),
                "performance_count": len(ai_input.get("performance", [])),
                "prior_actions": ai_input.get("prior_actions", []),
                "include_review_actions": payload.include_review_actions,
            },
            "remark": payload.remark,
        },
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return {
        **diagnosis_out(diagnosis),
        "closed_loop_note": (
            "已将上一轮复盘结论作为输入" if ai_input.get("prior_actions") else "暂无历史复盘结论，本次为首次诊断"
        ),
        "editable_hint": "所有字段均可通过 PATCH 接口人工编辑后保存",
    }


@router.patch(
    "/{diagnosis_id}",
    summary="编辑保存商品诊断",
    dependencies=[Depends(require_editor)],
)
def update_diagnosis(
    product_id: int,
    diagnosis_id: int,
    payload: DiagnosisUpdate,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    diagnosis = db.get(ProductDiagnosis, diagnosis_id)
    if diagnosis is None or diagnosis.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="诊断记录不存在")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in data.items():
        setattr(diagnosis, field, value)

    raw = dict(diagnosis.raw_output or {})
    raw["edited_at"] = utcnow().isoformat()
    raw["edited_fields"] = sorted(data.keys())
    raw["source_type"] = "manual_edit"
    diagnosis.raw_output = raw
    diagnosis.source_type = "manual_edit" if diagnosis.source_type == "ai_mock" else diagnosis.source_type

    db.commit()
    db.refresh(diagnosis)
    return diagnosis_out(diagnosis)
