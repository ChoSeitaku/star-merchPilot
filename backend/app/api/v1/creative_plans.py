"""主图方案、视频脚本与图片 / 视频生成任务路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import CreativePlan, GeneratedAsset, GenerationJob
from ...providers import get_ai_provider
from ...schemas import (
    AssetReviewUpdate,
    CreativePlanUpdate,
    ImageGenerateRequest,
    VideoGenerateRequest,
)
from ...serializers import asset_out, creative_plan_out, job_out
from ...services import context_service, job_service
from ...services.settings_service import get_raw
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}/creative-plans", tags=["内容方案"])

PLAN_TYPE_LABEL = {"main_image": "主图方案", "video_script": "视频脚本"}


def _get_plan_or_404(db: Session, product_id: int, plan_id: int) -> CreativePlan:
    plan = db.get(CreativePlan, plan_id)
    if plan is None or plan.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    return plan


def _plan_metrics(db: Session, plan_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    if not plan_ids:
        return {}, {}
    asset_counts = dict(
        db.execute(
            select(GeneratedAsset.creative_plan_id, func.count(GeneratedAsset.id))
            .where(GeneratedAsset.creative_plan_id.in_(plan_ids))
            .group_by(GeneratedAsset.creative_plan_id)
        ).all()
    )
    job_counts = dict(
        db.execute(
            select(GenerationJob.creative_plan_id, func.count(GenerationJob.id))
            .where(GenerationJob.creative_plan_id.in_(plan_ids))
            .group_by(GenerationJob.creative_plan_id)
        ).all()
    )
    return asset_counts, job_counts


# -------------------------------------------------------------------- 列表
@router.get("", summary="方案列表（可按类型过滤）")
def list_plans(
    product_id: int,
    db: Session = Depends(get_db),
    plan_type: str = Query(default="", description="main_image / video_script"),
) -> dict:
    get_product_or_404(db, product_id)
    stmt = select(CreativePlan).where(CreativePlan.product_id == product_id)
    if plan_type:
        stmt = stmt.where(CreativePlan.plan_type == plan_type)
    rows = list(db.scalars(stmt.order_by(CreativePlan.id.desc())))
    asset_counts, job_counts = _plan_metrics(db, [p.id for p in rows])
    return {
        "total": len(rows),
        "items": [
            creative_plan_out(
                p,
                asset_count=asset_counts.get(p.id, 0),
                job_count=job_counts.get(p.id, 0),
            )
            for p in rows
        ],
    }


@router.get("/{creative_plan_id}", summary="方案详情")
def get_plan(product_id: int, creative_plan_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    plan = _get_plan_or_404(db, product_id, creative_plan_id)
    asset_counts, job_counts = _plan_metrics(db, [plan.id])
    return creative_plan_out(
        plan, asset_count=asset_counts.get(plan.id, 0), job_count=job_counts.get(plan.id, 0)
    )


# ---------------------------------------------------------------- 生成主图方案
@router.post(
    "/main-images/generate",
    status_code=status.HTTP_201_CREATED,
    summary="生成主图方案（至少 3 个方向）",
    dependencies=[Depends(require_editor)],
)
def generate_main_image_plan(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = get_product_or_404(db, product_id)
    ai_input = context_service.creative_input(db, product)
    output = get_ai_provider().generate_main_image_plans(ai_input)

    directions = output.get("directions") or []
    if len(directions) < 3:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="生成结果不足 3 个方向，请重试"
        )

    plan = CreativePlan(
        product_id=product_id,
        plan_type="main_image",
        title=output.get("title") or f"{product.name} 主图方案",
        content_json={
            "directions": directions,
            "generated_at": utcnow().isoformat(),
            "provider": get_ai_provider().name,
            "input_summary": {
                "competitor_count": len(ai_input.get("competitors", [])),
                "has_diagnosis": bool(ai_input.get("diagnosis")),
            },
        },
        rationale_text=output.get("rationale_text", ""),
        status="draft",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {
        **creative_plan_out(plan),
        "direction_count": len(directions),
        "editable_hint": "方案内容可编辑后保存；提交图片生成任务前请先选定方向",
    }


# ---------------------------------------------------------------- 生成视频脚本
@router.post(
    "/video-scripts/generate",
    status_code=status.HTTP_201_CREATED,
    summary="生成视频脚本（至少 3 条）",
    dependencies=[Depends(require_editor)],
)
def generate_video_script_plan(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = get_product_or_404(db, product_id)
    ai_input = context_service.creative_input(db, product)
    output = get_ai_provider().generate_video_scripts(ai_input)

    scripts = output.get("scripts") or []
    if len(scripts) < 3:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="生成结果不足 3 条脚本，请重试"
        )

    plan = CreativePlan(
        product_id=product_id,
        plan_type="video_script",
        title=output.get("title") or f"{product.name} 视频脚本",
        content_json={
            "scripts": scripts,
            "generated_at": utcnow().isoformat(),
            "provider": get_ai_provider().name,
            "input_summary": {"has_diagnosis": bool(ai_input.get("diagnosis"))},
        },
        rationale_text=output.get("rationale_text", ""),
        status="draft",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {
        **creative_plan_out(plan),
        "script_count": len(scripts),
        "editable_hint": "脚本内容可编辑后保存；提交视频生成任务前请先选定脚本",
    }


# -------------------------------------------------------------------- 编辑
@router.patch(
    "/{creative_plan_id}",
    summary="编辑方案（内容 / 状态切换）",
    dependencies=[Depends(require_editor)],
)
def update_plan(
    product_id: int,
    creative_plan_id: int,
    payload: CreativePlanUpdate,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    plan = _get_plan_or_404(db, product_id, creative_plan_id)

    data = payload.model_dump(exclude_unset=True, exclude_none=True)

    # 同一商品同一类型只允许一个 selected，避免生成任务选错方向
    new_status = data.get("status")
    if new_status == "selected":
        siblings = db.scalars(
            select(CreativePlan).where(
                CreativePlan.product_id == product_id,
                CreativePlan.plan_type == plan.plan_type,
                CreativePlan.id != plan.id,
                CreativePlan.status == "selected",
            )
        )
        for sibling in siblings:
            sibling.status = "archived"

    for field, value in data.items():
        setattr(plan, field, value)

    content = dict(plan.content_json or {})
    content["edited_at"] = utcnow().isoformat()
    plan.content_json = content

    db.commit()
    db.refresh(plan)
    asset_counts, job_counts = _plan_metrics(db, [plan.id])
    return creative_plan_out(
        plan, asset_count=asset_counts.get(plan.id, 0), job_count=job_counts.get(plan.id, 0)
    )


@router.delete(
    "/{creative_plan_id}",
    summary="删除方案（级联删除其素材与任务）",
    dependencies=[Depends(require_editor)],
)
def delete_plan(product_id: int, creative_plan_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    plan = _get_plan_or_404(db, product_id, creative_plan_id)
    db.delete(plan)
    db.commit()
    return {"message": "方案已删除", "creative_plan_id": creative_plan_id}


# ------------------------------------------------------- 提交图片生成任务
@router.post(
    "/{creative_plan_id}/images/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建图片生成任务（异步）",
    dependencies=[Depends(require_editor)],
)
def generate_images(
    product_id: int,
    creative_plan_id: int,
    payload: ImageGenerateRequest,
    db: Session = Depends(get_db),
) -> dict:
    """提交图片生成任务后立即返回，不阻塞请求；进度请在任务页查看。"""
    get_product_or_404(db, product_id)
    plan = _get_plan_or_404(db, product_id, creative_plan_id)
    if plan.plan_type != "main_image":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该方案不是主图方案，无法生成图片"
        )

    directions = (plan.content_json or {}).get("directions") or []
    if not directions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="方案没有可用的方向内容")

    indexes = payload.direction_indexes or list(range(len(directions)))
    invalid = [i for i in indexes if i < 0 or i >= len(directions)]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"方向下标越界：{invalid}（共 {len(directions)} 个方向）",
        )

    max_attempts = int(get_raw(db, "queue_max_attempts", 3) or 3)
    job = job_service.enqueue_job(
        db,
        product_id=product_id,
        creative_plan_id=plan.id,
        job_kind="image",
        params={
            "direction_indexes": indexes,
            "count_per_direction": payload.count_per_direction,
            "usage_scene": payload.usage_scene,
        },
        max_attempts=max_attempts,
    )
    return {
        **job_out(job, event_count=1),
        "message": "图片生成任务已入队，任务页会自动刷新状态",
    }


# ------------------------------------------------------- 提交视频生成任务
@router.post(
    "/{creative_plan_id}/videos/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建视频生成任务（异步）",
    dependencies=[Depends(require_editor)],
)
def generate_videos(
    product_id: int,
    creative_plan_id: int,
    payload: VideoGenerateRequest,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    plan = _get_plan_or_404(db, product_id, creative_plan_id)
    if plan.plan_type != "video_script":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该方案不是视频脚本，无法生成视频"
        )

    scripts = (plan.content_json or {}).get("scripts") or []
    if not scripts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="方案没有可用的脚本内容")

    indexes = payload.script_indexes or list(range(len(scripts)))
    invalid = [i for i in indexes if i < 0 or i >= len(scripts)]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"脚本下标越界：{invalid}（共 {len(scripts)} 条脚本）",
        )

    max_attempts = int(get_raw(db, "queue_max_attempts", 3) or 3)
    job = job_service.enqueue_job(
        db,
        product_id=product_id,
        creative_plan_id=plan.id,
        job_kind="video",
        params={
            "script_indexes": indexes,
            "duration_sec": payload.duration_sec,
            "usage_scene": payload.usage_scene,
        },
        max_attempts=max_attempts,
    )
    return {
        **job_out(job, event_count=1),
        "message": "视频生成任务已入队，任务页会自动刷新状态",
    }


# ------------------------------------------------------- 素材审核字段更新
@router.patch(
    "/{creative_plan_id}/assets",
    summary="更新素材审核字段（状态 / 版本 / 场景 / 评分 / 标签 / 备注）",
    dependencies=[Depends(require_editor)],
)
def update_plan_assets(
    product_id: int,
    creative_plan_id: int,
    payload: AssetReviewUpdate,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    plan = _get_plan_or_404(db, product_id, creative_plan_id)

    assets = list(
        db.scalars(
            select(GeneratedAsset).where(
                GeneratedAsset.id.in_(payload.asset_ids),
                GeneratedAsset.product_id == product_id,
            )
        )
    )
    if not assets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到可更新的素材")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    data.pop("asset_ids", None)
    for asset in assets:
        for field, value in data.items():
            setattr(asset, field, value)

    db.commit()
    return {
        "message": f"已更新 {len(assets)} 个素材",
        "items": [asset_out(a, plan_title=plan.title) for a in assets],
    }
