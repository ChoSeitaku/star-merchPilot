"""生成任务状态机。

事件节点与规格 1.5.9 一致：入队 → 运行中 → 成功 / 失败 / 重试 / 取消 / 超时。

SQLite 并发策略：
- 只有一个工作进程（``queue_concurrency`` 默认 1）在写库
- 抢占用单条原子 ``UPDATE ... WHERE job_status='pending'`` + rowcount 判定，
  不依赖跨事务长锁
- 模拟耗时期间**不持有**数据库连接
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import GenerationJob, GenerationJobEvent, GeneratedAsset

# 事件类型
EVENT_ENQUEUED = "enqueued"
EVENT_RUNNING = "running"
EVENT_SUCCEEDED = "succeeded"
EVENT_FAILED = "failed"
EVENT_RETRY = "retry"
EVENT_CANCELLED = "cancelled"
EVENT_TIMEOUT = "timeout"

TERMINAL_STATUSES = ("succeeded", "failed", "cancelled", "timeout")


# --------------------------------------------------------------------- 事件
def add_event(db: Session, job_id: int, event_type: str, message: str) -> GenerationJobEvent:
    event = GenerationJobEvent(job_id=job_id, event_type=event_type, event_message=message)
    db.add(event)
    return event


def event_count_map(db: Session, job_ids: list[int]) -> dict[int, int]:
    if not job_ids:
        return {}
    rows = db.execute(
        select(GenerationJobEvent.job_id, func.count(GenerationJobEvent.id))
        .where(GenerationJobEvent.job_id.in_(job_ids))
        .group_by(GenerationJobEvent.job_id)
    ).all()
    return {job_id: count for job_id, count in rows}


# --------------------------------------------------------------------- 入队
def enqueue_job(
    db: Session,
    *,
    product_id: int,
    creative_plan_id: Optional[int],
    job_kind: str,
    params: dict[str, Any],
    max_attempts: int = 3,
) -> GenerationJob:
    now = utcnow()
    job = GenerationJob(
        product_id=product_id,
        creative_plan_id=creative_plan_id,
        job_kind=job_kind,
        job_status="pending",
        attempts=0,
        max_attempts=max_attempts,
        next_run_at=now,
        params_json=params,
    )
    db.add(job)
    db.flush()
    add_event(
        db,
        job.id,
        EVENT_ENQUEUED,
        f"任务已入队：{_kind_label(job_kind)}生成，最多尝试 {max_attempts} 次",
    )
    db.commit()
    db.refresh(job)
    return job


def _kind_label(kind: str) -> str:
    return {"image": "图片", "video": "视频"}.get(kind, kind)


# ------------------------------------------------------------------- 重试/取消
def retry_job(db: Session, job: GenerationJob) -> GenerationJob:
    if job.job_status not in ("failed", "timeout", "cancelled"):
        raise ValueError(f"任务当前状态为 {job.job_status}，只有失败/超时/已取消的任务可以重试")
    job.job_status = "pending"
    job.attempts = 0
    job.error_message = ""
    job.locked_at = None
    job.locked_by = ""
    job.next_run_at = utcnow()
    job.started_at = None
    job.finished_at = None
    add_event(db, job.id, EVENT_ENQUEUED, "人工触发重试，任务重新入队")
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job: GenerationJob) -> GenerationJob:
    if job.job_status in TERMINAL_STATUSES:
        raise ValueError(f"任务已处于终态（{job.job_status}），无法取消")
    job.job_status = "cancelled"
    job.finished_at = utcnow()
    job.locked_at = None
    job.locked_by = ""
    add_event(db, job.id, EVENT_CANCELLED, "任务已被人工取消")
    db.commit()
    db.refresh(job)
    return job


# --------------------------------------------------------------------- 抢占
def claim_next_job(db: Session, worker_id: str) -> Optional[GenerationJob]:
    """原子抢占一个到期任务。

    通过 ``UPDATE ... WHERE job_status='pending' AND next_run_at <= now`` 的
    rowcount 判断是否抢到，抢到后再回读该行，避免多个消费者重复执行。
    """
    now = utcnow()
    candidate_id = db.scalar(
        select(GenerationJob.id)
        .where(
            GenerationJob.job_status == "pending",
            (GenerationJob.next_run_at.is_(None)) | (GenerationJob.next_run_at <= now),
        )
        .order_by(GenerationJob.next_run_at.asc(), GenerationJob.id.asc())
        .limit(1)
    )
    if candidate_id is None:
        return None

    result = db.execute(
        update(GenerationJob)
        .where(
            GenerationJob.id == candidate_id,
            GenerationJob.job_status == "pending",
            (GenerationJob.next_run_at.is_(None)) | (GenerationJob.next_run_at <= now),
        )
        .values(
            job_status="running",
            locked_at=now,
            locked_by=worker_id,
            started_at=now,
        )
    )
    db.commit()
    if result.rowcount != 1:
        return None

    job = db.get(GenerationJob, candidate_id)
    if job is None:
        return None
    add_event(
        db,
        job.id,
        EVENT_RUNNING,
        f"任务开始执行（第 {job.attempts + 1} 次尝试，执行者 {worker_id}）",
    )
    db.commit()
    db.refresh(job)
    return job


# --------------------------------------------------------------- 超时扫描
def sweep_timeouts(db: Session, timeout_sec: int) -> list[int]:
    """把执行超时的 running 任务标记为 timeout。返回被标记的任务 ID。"""
    deadline = utcnow() - timedelta(seconds=timeout_sec)
    jobs = list(
        db.scalars(
            select(GenerationJob).where(
                GenerationJob.job_status == "running",
                GenerationJob.locked_at.is_not(None),
                GenerationJob.locked_at < deadline,
            )
        )
    )
    for job in jobs:
        job.job_status = "timeout"
        job.finished_at = utcnow()
        job.error_message = f"任务执行超过 {timeout_sec} 秒未完成，已判定为超时"
        job.locked_at = None
        job.locked_by = ""
        add_event(db, job.id, EVENT_TIMEOUT, job.error_message)
    if jobs:
        db.commit()
    return [j.id for j in jobs]


# --------------------------------------------------------------- 成功/失败
def complete_job(
    db: Session, job: GenerationJob, assets: list[GeneratedAsset], summary: str
) -> None:
    for asset in assets:
        db.add(asset)
    job.job_status = "succeeded"
    job.error_message = ""
    job.finished_at = utcnow()
    job.locked_at = None
    job.locked_by = ""
    job.result_json = {
        "asset_count": len(assets),
        "asset_ids": [a.id for a in assets if a.id],
        "summary": summary,
    }
    add_event(db, job.id, EVENT_SUCCEEDED, summary)
    db.commit()


def fail_job(db: Session, job: GenerationJob, error: str) -> None:
    """失败处理：未达最大尝试次数则回到 pending 并计算退避时间，否则终态失败。"""
    job.attempts += 1
    job.locked_at = None
    job.locked_by = ""

    if job.attempts < job.max_attempts:
        backoff = 2 ** job.attempts * 5
        job.job_status = "pending"
        job.next_run_at = utcnow() + timedelta(seconds=backoff)
        job.error_message = error
        add_event(
            db,
            job.id,
            EVENT_RETRY,
            f"第 {job.attempts} 次尝试失败：{error}；将在 {backoff} 秒后自动重试",
        )
    else:
        job.job_status = "failed"
        job.finished_at = utcnow()
        job.error_message = error
        add_event(
            db,
            job.id,
            EVENT_FAILED,
            f"任务失败（已尝试 {job.attempts}/{job.max_attempts} 次）：{error}",
        )
    db.commit()
