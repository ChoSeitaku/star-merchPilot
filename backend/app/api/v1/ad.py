"""投放建议与投放实验路由。

合规（规格 1.5.5 / 1.5.12）：
- 系统只生成**建议**与**实验计划**；
- 不自动创建平台广告计划、不自动扣费、不直接修改预算；
- 建议必须由具备权限的人员人工确认或驳回（单独权限校验）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import AdExperiment, AdRecommendation, GeneratedAsset, PromotionLink
from ...providers import get_ai_provider
from ...schemas import (
    AdConfirmationUpdate,
    AdExperimentGenerate,
    AdExperimentUpdate,
    AdRecommendationGenerate,
)
from ...serializers import ad_experiment_out, ad_recommendation_out
from ...services import context_service
from ..deps import require_ad_confirm, require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}", tags=["投放管理"])

COMPLIANCE_NOTE = (
    "本模块只生成投放建议与实验计划，不自动创建广告计划、不自动扣费、不直接修改预算；"
    "所有投放动作需由具备权限的人员确认后在平台侧手动执行。"
)

# 实验状态流转白名单：只允许向前推进或取消，避免出现非法回退
_ALLOWED_TRANSITIONS = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"running", "cancelled"},
    "running": {"finished", "cancelled"},
    "finished": set(),
    "cancelled": set(),
}


# ---------------------------------------------------------------- 投放建议
@router.get("/ad-recommendations", summary="投放建议列表")
def list_recommendations(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(AdRecommendation)
            .where(AdRecommendation.product_id == product_id)
            .order_by(AdRecommendation.id.desc())
        )
    )
    return {
        "total": len(rows),
        "items": [ad_recommendation_out(r) for r in rows],
        "compliance_note": COMPLIANCE_NOTE,
    }


@router.post(
    "/ad-recommendations/generate",
    status_code=status.HTTP_201_CREATED,
    summary="生成投放建议",
    dependencies=[Depends(require_editor)],
)
def generate_recommendation(
    product_id: int, payload: AdRecommendationGenerate, db: Session = Depends(get_db)
) -> dict:
    product = get_product_or_404(db, product_id)
    ai_input = context_service.ad_input(db, product)
    output = get_ai_provider().generate_ad_recommendation(ai_input)

    budget_plan = output.get("budget_plan") or {}
    if payload.daily_budget is not None:
        budget_plan = {**budget_plan, "daily_budget": payload.daily_budget}

    rec = AdRecommendation(
        product_id=product_id,
        summary_text=output.get("summary_text", ""),
        objective_text=output.get("objective_text", "") or f"本轮目标：{payload.objective}",
        audience_segments_json=output.get("audience_segments"),
        budget_plan_json=budget_plan,
        creative_tests_json=output.get("creative_tests"),
        bid_strategy_json=output.get("bid_strategy"),
        risk_controls_json=output.get("risk_controls"),
        next_steps_json=output.get("next_steps"),
        confirm_status="pending",
        confirm_remark="",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {
        **ad_recommendation_out(rec),
        "compliance_note": COMPLIANCE_NOTE,
        "hint": "建议处于待确认状态，需由管理员或运营人员人工确认后才可用于执行",
    }


@router.patch(
    "/ad-recommendations/{recommendation_id}/confirmation",
    summary="人工确认或驳回投放建议（单独权限校验）",
)
def confirm_recommendation(
    product_id: int,
    recommendation_id: int,
    payload: AdConfirmationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_ad_confirm),
) -> dict:
    get_product_or_404(db, product_id)
    rec = db.get(AdRecommendation, recommendation_id)
    if rec is None or rec.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="投放建议不存在")
    if rec.confirm_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该建议已处于「{rec.confirm_status}」状态，不能重复确认",
        )

    rec.confirm_status = payload.confirm_status
    rec.confirmed_by = current_user.id
    rec.confirmed_at = utcnow()
    rec.confirm_remark = payload.confirm_remark
    db.commit()
    db.refresh(rec)

    action = "确认" if payload.confirm_status == "confirmed" else "驳回"
    return {
        **ad_recommendation_out(rec),
        "message": f"投放建议已{action}（操作人：{current_user.display_name or current_user.username}）",
        "compliance_note": COMPLIANCE_NOTE,
    }


# ---------------------------------------------------------------- 投放实验
@router.get("/ad-experiments", summary="投放实验列表")
def list_experiments(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(AdExperiment)
            .where(AdExperiment.product_id == product_id)
            .order_by(AdExperiment.id.desc())
        )
    )
    return {
        "total": len(rows),
        "items": [ad_experiment_out(e) for e in rows],
        "allowed_transitions": {k: sorted(v) for k, v in _ALLOWED_TRANSITIONS.items()},
        "compliance_note": COMPLIANCE_NOTE,
    }


@router.post(
    "/ad-experiments/generate",
    status_code=status.HTTP_201_CREATED,
    summary="生成投放实验计划",
    dependencies=[Depends(require_editor)],
)
def generate_experiment(
    product_id: int, payload: AdExperimentGenerate, db: Session = Depends(get_db)
) -> dict:
    product = get_product_or_404(db, product_id)

    rec = db.scalar(
        select(AdRecommendation)
        .where(AdRecommendation.product_id == product_id)
        .order_by(AdRecommendation.id.desc())
        .limit(1)
    )
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先生成投放建议，再基于建议创建实验计划",
        )

    # 关联素材与链接：优先取已通过审核的素材
    asset_id = payload.related_asset_id
    if asset_id is None:
        asset_id = db.scalar(
            select(GeneratedAsset.id)
            .where(
                GeneratedAsset.product_id == product_id,
                GeneratedAsset.review_status == "approved",
            )
            .order_by(GeneratedAsset.id.desc())
            .limit(1)
        )
    if asset_id is not None:
        asset = db.get(GeneratedAsset, asset_id)
        if asset is None or asset.product_id != product_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关联素材不存在")

    link_id = payload.related_link_id
    if link_id is not None:
        link = db.get(PromotionLink, link_id)
        if link is None or link.product_id != product_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关联推广链接不存在")

    budget_plan = rec.budget_plan_json or {}
    budget = payload.budget_amount
    if budget is None:
        budget = float(budget_plan.get("daily_budget") or 100.0)

    tests = rec.creative_tests_json or []
    hypothesis = (
        tests[0].get("hypothesis")
        if tests and isinstance(tests[0], dict)
        else "主图方向 A 的点击率高于当前在线素材"
    )
    segments = rec.audience_segments_json or []
    audience_text = (
        segments[0].get("segment_name", "") if segments and isinstance(segments[0], dict) else "高意向搜索人群"
    )

    experiment = AdExperiment(
        product_id=product_id,
        related_asset_id=asset_id,
        related_link_id=link_id,
        experiment_name=payload.experiment_name or f"{product.name} 素材测试实验",
        target_text=rec.objective_text or "验证素材点击效率，控制 CPA",
        audience_text=audience_text,
        budget_amount=budget,
        success_metric_text="点击率 ≥ 2.5% 且 ROI ≥ 1.5",
        hypothesis_text=hypothesis,
        experiment_status="draft",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return {
        **ad_experiment_out(experiment),
        "based_on_recommendation_id": rec.id,
        "compliance_note": COMPLIANCE_NOTE,
        "hint": "实验计划为草稿状态，确认后才会进入执行跟踪；系统不会自动执行投放",
    }


@router.patch(
    "/ad-experiments/{experiment_id}",
    summary="更新实验状态（单独权限校验）",
    dependencies=[Depends(require_ad_confirm)],
)
def update_experiment(
    product_id: int,
    experiment_id: int,
    payload: AdExperimentUpdate,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    experiment = db.get(AdExperiment, experiment_id)
    if experiment is None or experiment.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="投放实验不存在")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    new_status = data.get("experiment_status")
    if new_status is not None and new_status != experiment.experiment_status:
        allowed = _ALLOWED_TRANSITIONS.get(experiment.experiment_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"不允许从「{experiment.experiment_status}」变更为「{new_status}」；"
                    f"当前状态允许变更为：{sorted(allowed) or '无（终态）'}"
                ),
            )

    for field, value in data.items():
        setattr(experiment, field, value)
    db.commit()
    db.refresh(experiment)
    return {
        **ad_experiment_out(experiment),
        "compliance_note": COMPLIANCE_NOTE,
        "hint": "状态变更仅用于记录管理意图，系统不会触发任何平台侧投放动作",
    }
