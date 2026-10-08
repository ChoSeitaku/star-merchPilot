"""生成任务路由：列表、事件时间线、重试、取消。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import GenerationJob, GenerationJobEvent
from ...schemas import JobFailRequest
from ...serializers import job_event_out, job_out
from ...services import job_service
from ...worker import worker_manager
from ..deps import require_admin, require_editor
from .products import get_product_or_404

router = APIRouter(tags=["生成任务"])


def _get_job_or_404(db: Session, job_id: int) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


# -------------------------------------------------------------------- 列表
@router.get("/generation-jobs", summary="生成任务列表（全局）")
def list_all_jobs(
    db: Session = Depends(get_db),
    product_id: Optional[int] = Query(default=None),
    job_kind: str = Query(default="", description="image / video"),
    job_status: str = Query(default="", description="pending/running/succeeded/failed/cancelled/timeout"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    stmt = select(GenerationJob)
    if product_id is not None:
        stmt = stmt.where(GenerationJob.product_id == product_id)
    if job_kind:
        stmt = stmt.where(GenerationJob.job_kind == job_kind)
    if job_status:
        stmt = stmt.where(GenerationJob.job_status == job_status)
    rows = list(db.scalars(stmt.order_by(GenerationJob.id.desc()).limit(limit)))
    counts = job_service.event_count_map(db, [j.id for j in rows])
    return {
        "total": len(rows),
        "items": [job_out(j, event_count=counts.get(j.id, 0)) for j in rows],
        "worker": worker_manager.status(),
    }


@router.get("/products/{product_id}/generation-jobs", summary="商品生成任务列表")
def list_product_jobs(
    product_id: int,
    db: Session = Depends(get_db),
    job_kind: str = Query(default=""),
    job_status: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    get_product_or_404(db, product_id)
    stmt = select(GenerationJob).where(GenerationJob.product_id == product_id)
    if job_kind:
        stmt = stmt.where(GenerationJob.job_kind == job_kind)
    if job_status:
        stmt = stmt.where(GenerationJob.job_status == job_status)
    rows = list(db.scalars(stmt.order_by(GenerationJob.id.desc()).limit(limit)))
    counts = job_service.event_count_map(db, [j.id for j in rows])
    return {
        "total": len(rows),
        "items": [job_out(j, event_count=counts.get(j.id, 0)) for j in rows],
        "worker": worker_manager.status(),
    }


@router.get("/products/{product_id}/generation-jobs/{job_id}", summary="任务详情")
def get_job(product_id: int, job_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    job = _get_job_or_404(db, job_id)
    if job.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该任务不属于此商品")
    counts = job_service.event_count_map(db, [job.id])
    return job_out(job, event_count=counts.get(job.id, 0))


@router.get("/products/{product_id}/generation-jobs/{job_id}/events", summary="任务事件时间线")
def job_events(product_id: int, job_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    job = _get_job_or_404(db, job_id)
    if job.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该任务不属于此商品")
    rows = list(
        db.scalars(
            select(GenerationJobEvent)
            .where(GenerationJobEvent.job_id == job_id)
            .order_by(GenerationJobEvent.id.asc())
        )
    )
    return {"job_id": job_id, "total": len(rows), "items": [job_event_out(e) for e in rows]}


# ---------------------------------------------------------------- 重试 / 取消
@router.post(
    "/products/{product_id}/generation-jobs/{job_id}/retry",
    summary="重试失败任务",
    dependencies=[Depends(require_editor)],
)
def retry_job(product_id: int, job_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    job = _get_job_or_404(db, job_id)
    if job.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该任务不属于此商品")
    try:
        job = job_service.retry_job(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    counts = job_service.event_count_map(db, [job.id])
    return {**job_out(job, event_count=counts.get(job.id, 0)), "message": "任务已重新入队"}


@router.post(
    "/products/{product_id}/generation-jobs/{job_id}/cancel",
    summary="取消任务",
    dependencies=[Depends(require_editor)],
)
def cancel_job(product_id: int, job_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    job = _get_job_or_404(db, job_id)
    if job.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该任务不属于此商品")
    try:
        job = job_service.cancel_job(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    counts = job_service.event_count_map(db, [job.id])
    return {**job_out(job, event_count=counts.get(job.id, 0)), "message": "任务已取消"}


# ---------------------------------------------------------------- 工作区维护
@router.post(
    "/workspace/generation-jobs/sweep-timeouts",
    summary="扫描超时任务",
    dependencies=[Depends(require_admin)],
)
def sweep_timeouts(db: Session = Depends(get_db)) -> dict:
    from ...services.settings_service import queue_config

    timeout_sec = queue_config(db)["job_timeout_sec"]
    ids = job_service.sweep_timeouts(db, timeout_sec)
    return {
        "timeout_threshold_sec": timeout_sec,
        "marked_count": len(ids),
        "marked_job_ids": ids,
        "message": f"已扫描并标记 {len(ids)} 个超时任务" if ids else "没有发现超时任务",
    }


@router.get("/workspace/worker-status", summary="查看后台工作进程状态")
def worker_status() -> dict:
    return worker_manager.status()


@router.post(
    "/products/{product_id}/generation-jobs/{job_id}/simulate-failure",
    summary="标记任务为「下次执行必失败」（演示失败与重试链路）",
    dependencies=[Depends(require_admin)],
)
def simulate_failure(
    product_id: int, job_id: int, payload: JobFailRequest, db: Session = Depends(get_db)
) -> dict:
    """演示用途：让任务在下次执行时按失败路径走一遍重试与终态。

    这不会绕过任何权限校验，只是给任务参数打上标记。
    """
    get_product_or_404(db, product_id)
    job = _get_job_or_404(db, job_id)
    if job.job_status not in ("pending",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="仅待执行的任务可以标记模拟失败，请先重试或新建任务",
        )
    params = dict(job.params_json or {})
    params["force_fail"] = True
    params["force_fail_reason"] = payload.reason
    job.params_json = params
    db.commit()
    db.refresh(job)
    counts = job_service.event_count_map(db, [job.id])
    return {
        **job_out(job, event_count=counts.get(job.id, 0)),
        "message": "已标记，任务下次执行将按失败路径处理",
    }
