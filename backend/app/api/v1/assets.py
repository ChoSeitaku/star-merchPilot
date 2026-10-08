"""素材库路由：列表、同步、审核字段更新。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import CreativePlan, GeneratedAsset, GenerationJob
from ...schemas import AssetReviewUpdate
from ...serializers import asset_out
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}/assets", tags=["素材库"])


def _plan_titles(db: Session, plan_ids: list[int]) -> dict[int, str]:
    if not plan_ids:
        return {}
    rows = db.execute(
        select(CreativePlan.id, CreativePlan.title).where(CreativePlan.id.in_(plan_ids))
    ).all()
    return {pid: title for pid, title in rows}


@router.get("", summary="素材列表（素材库）")
def list_assets(
    product_id: int,
    db: Session = Depends(get_db),
    asset_type: str = Query(default="", description="image / video"),
    review_status: str = Query(default="", description="pending / approved / rejected"),
    plan_id: Optional[int] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    get_product_or_404(db, product_id)
    stmt = select(GeneratedAsset).where(GeneratedAsset.product_id == product_id)
    if asset_type:
        stmt = stmt.where(GeneratedAsset.asset_type == asset_type)
    if review_status:
        stmt = stmt.where(GeneratedAsset.review_status == review_status)
    if plan_id is not None:
        stmt = stmt.where(GeneratedAsset.creative_plan_id == plan_id)

    rows = list(db.scalars(stmt.order_by(GeneratedAsset.id.desc()).limit(limit)))
    titles = _plan_titles(db, [a.creative_plan_id for a in rows if a.creative_plan_id])

    summary = db.execute(
        select(GeneratedAsset.review_status, func.count(GeneratedAsset.id))
        .where(GeneratedAsset.product_id == product_id)
        .group_by(GeneratedAsset.review_status)
    ).all()

    return {
        "total": len(rows),
        "items": [
            asset_out(a, plan_title=titles.get(a.creative_plan_id or 0, "")) for a in rows
        ],
        "review_summary": {status_name: count for status_name, count in summary},
    }


@router.get("/{asset_id}", summary="素材详情")
def get_asset(product_id: int, asset_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    asset = db.get(GeneratedAsset, asset_id)
    if asset is None or asset.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    titles = _plan_titles(db, [asset.creative_plan_id] if asset.creative_plan_id else [])
    return asset_out(asset, plan_title=titles.get(asset.creative_plan_id or 0, ""))


@router.post(
    "/sync",
    summary="同步素材（把已完成任务产出的素材同步入库）",
    dependencies=[Depends(require_editor)],
)
def sync_assets(product_id: int, db: Session = Depends(get_db)) -> dict:
    """同步已完成任务的结果。

     正常链路中素材在任务成功时即已落库，本接口用于：
    - 修正历史数据（任务成功但素材缺失）
    - 演示「素材同步」这一操作节点
    """
    product = get_product_or_404(db, product_id)

    succeeded_jobs = list(
        db.scalars(
            select(GenerationJob).where(
                GenerationJob.product_id == product_id,
                GenerationJob.job_status == "succeeded",
            )
        )
    )

    created: list[GeneratedAsset] = []
    for job in succeeded_jobs:
        asset_ids = (job.result_json or {}).get("asset_ids") or []
        existing = set(
            db.scalars(
                select(GeneratedAsset.id).where(GeneratedAsset.id.in_(asset_ids or [0]))
            )
        )
        missing = [aid for aid in asset_ids if aid not in existing]
        if missing:
            from ...worker import executor

            try:
                assets, summary = (
                    executor._build_image_assets(db, job, 0)
                    if job.job_kind == "image"
                    else executor._build_video_assets(db, job, 0)
                )
                created.extend(assets)
                job.result_json = {
                    **(job.result_json or {}),
                    "asset_ids": [a.id for a in assets if a.id],
                    "resynced_at": "sync",
                    "summary": summary,
                }
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"同步任务 {job.id} 的素材失败：{exc}",
                ) from exc

    db.commit()

    all_assets = list(
        db.scalars(
            select(GeneratedAsset)
            .where(GeneratedAsset.product_id == product_id)
            .order_by(GeneratedAsset.id.desc())
        )
    )
    titles = _plan_titles(db, [a.creative_plan_id for a in all_assets if a.creative_plan_id])
    return {
        "product_id": product_id,
        "product_name": product.name,
        "scanned_jobs": len(succeeded_jobs),
        "created_count": len(created),
        "total_assets": len(all_assets),
        "message": (
            f"同步完成，新增 {len(created)} 个素材" if created else "素材已是最新，无需新增"
        ),
        "items": [asset_out(a, plan_title=titles.get(a.creative_plan_id or 0, "")) for a in all_assets],
    }


@router.patch("/review", summary="批量更新素材审核字段", dependencies=[Depends(require_editor)])
def update_assets_review(
    product_id: int, payload: AssetReviewUpdate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
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

    titles = _plan_titles(db, [a.creative_plan_id for a in assets if a.creative_plan_id])
    return {
        "message": f"已更新 {len(assets)} 个素材",
        "items": [asset_out(a, plan_title=titles.get(a.creative_plan_id or 0, "")) for a in assets],
    }


@router.patch("/{asset_id}", summary="更新单个素材审核字段", dependencies=[Depends(require_editor)])
def update_asset(
    product_id: int, asset_id: int, payload: AssetReviewUpdate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
    asset = db.get(GeneratedAsset, asset_id)
    if asset is None or asset.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    data.pop("asset_ids", None)
    for field, value in data.items():
        setattr(asset, field, value)
    db.commit()

    titles = _plan_titles(db, [asset.creative_plan_id] if asset.creative_plan_id else [])
    return asset_out(asset, plan_title=titles.get(asset.creative_plan_id or 0, ""))
