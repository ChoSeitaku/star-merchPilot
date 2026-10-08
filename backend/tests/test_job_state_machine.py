"""生成任务状态机测试（规格 1.5.5 / 1.5.9）。

覆盖：入队 → 抢占 → 成功 / 失败重试退避 / 达到上限失败 / 取消 / 超时。
直接驱动 ``services.job_service``，不依赖后台工作进程，因此结果确定。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database import utcnow
from app.models import GeneratedAsset, GenerationJob, GenerationJobEvent
from app.services import job_service


@pytest.fixture()
def product_id(sample_product) -> int:
    """任务必须挂在真实商品下（generation_jobs.product_id 有外键约束）。"""
    return sample_product["id"]


def _enqueue(db, product_id: int, **kwargs) -> GenerationJob:
    return job_service.enqueue_job(
        db,
        product_id=product_id,
        creative_plan_id=None,
        job_kind=kwargs.pop("job_kind", "image"),
        params=kwargs.pop("params", {"direction_indexes": [0]}),
        **kwargs,
    )


def _events(db, job_id: int) -> list[str]:
    rows = db.scalars(
        select(GenerationJobEvent)
        .where(GenerationJobEvent.job_id == job_id)
        .order_by(GenerationJobEvent.id.asc())
    )
    return [e.event_type for e in rows]


# ------------------------------------------------------------------ 入队
def test_enqueue_sets_pending_and_logs_event(db, product_id):
    job = _enqueue(db, product_id)
    assert job.job_status == "pending"
    assert job.attempts == 0
    assert job.next_run_at is not None
    assert _events(db, job.id) == [job_service.EVENT_ENQUEUED]


# ------------------------------------------------------------------ 抢占
def test_claim_marks_running_and_is_exclusive(db, product_id):
    job = _enqueue(db, product_id)

    claimed = job_service.claim_next_job(db, "worker-a")
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.job_status == "running"
    assert claimed.locked_by == "worker-a"
    assert claimed.locked_at is not None

    # 已被抢走，第二个消费者抢不到同一个任务
    assert job_service.claim_next_job(db, "worker-b") is None

    assert job_service.EVENT_RUNNING in _events(db, job.id)


def test_claim_skips_jobs_not_yet_due(db, product_id):
    job = _enqueue(db, product_id)
    job.next_run_at = utcnow() + timedelta(hours=1)
    db.commit()

    assert job_service.claim_next_job(db, "worker-a") is None


def test_claim_returns_none_when_no_pending_jobs(db, product_id):
    assert job_service.claim_next_job(db, "worker-a") is None


# ------------------------------------------------------------------ 成功
def test_complete_job_creates_assets_and_event(db, product_id):
    job = _enqueue(db, product_id)
    job_service.claim_next_job(db, "worker-a")

    assets = [
        GeneratedAsset(
            product_id=job.product_id,
            creative_plan_id=None,
            asset_type="image",
            asset_url="/static/assets/job_1/a.svg",
            file_path="a.svg",
            width=800,
            height=800,
            review_status="pending",
            version_no=1,
        )
    ]
    job_service.complete_job(db, job, assets, "生成完成")

    assert job.job_status == "succeeded"
    assert job.finished_at is not None
    assert job.locked_at is None
    assert job.result_json["asset_count"] == 1
    assert job_service.EVENT_SUCCEEDED in _events(db, job.id)


# ------------------------------------------------------------------ 失败与重试
def test_fail_below_max_attempts_returns_to_pending_with_backoff(db, product_id):
    job = _enqueue(db, product_id, max_attempts=3)
    job_service.claim_next_job(db, "worker-a")
    before = utcnow()

    job_service.fail_job(db, job, "模拟失败")

    assert job.job_status == "pending"
    assert job.attempts == 1
    assert job.error_message == "模拟失败"
    # 第 1 次失败退避 2^1 * 5 = 10 秒
    assert job.next_run_at > before + timedelta(seconds=8)
    assert job_service.EVENT_RETRY in _events(db, job.id)


def test_fail_at_max_attempts_becomes_terminal(db, product_id):
    job = _enqueue(db, product_id, max_attempts=2)

    job_service.claim_next_job(db, "worker-a")
    job_service.fail_job(db, job, "第一次失败")
    assert job.job_status == "pending"

    job.next_run_at = utcnow()
    db.commit()
    job_service.claim_next_job(db, "worker-a")
    job_service.fail_job(db, job, "第二次失败")

    assert job.job_status == "failed"
    assert job.attempts == 2
    assert job.finished_at is not None
    types = _events(db, job.id)
    assert job_service.EVENT_RETRY in types
    assert job_service.EVENT_FAILED in types


def test_backoff_grows_exponentially(db, product_id):
    job = _enqueue(db, product_id, max_attempts=5)

    delays = []
    for _ in range(3):
        job.next_run_at = utcnow()
        db.commit()
        job_service.claim_next_job(db, "worker-a")
        before = utcnow()
        job_service.fail_job(db, job, "失败")
        delays.append((job.next_run_at - before).total_seconds())

    assert delays[0] < delays[1] < delays[2], f"退避应递增，实际 {delays}"


# ------------------------------------------------------------------ 取消
def test_cancel_pending_job(db, product_id):
    job = _enqueue(db, product_id)
    job_service.cancel_job(db, job)

    assert job.job_status == "cancelled"
    assert job.finished_at is not None
    assert job_service.EVENT_CANCELLED in _events(db, job.id)
    # 已取消的任务不会被再次抢占
    assert job_service.claim_next_job(db, "worker-a") is None


def test_cancel_running_job(db, product_id):
    job = _enqueue(db, product_id)
    job_service.claim_next_job(db, "worker-a")
    job_service.cancel_job(db, job)
    assert job.job_status == "cancelled"


@pytest.mark.parametrize("terminal", ["succeeded", "failed", "cancelled", "timeout"])
def test_cannot_cancel_terminal_job(db, terminal, product_id):
    job = _enqueue(db, product_id)
    job.job_status = terminal
    db.commit()

    with pytest.raises(ValueError):
        job_service.cancel_job(db, job)


# ------------------------------------------------------------------ 重试
@pytest.mark.parametrize("status", ["failed", "timeout", "cancelled"])
def test_retry_resets_job(db, status, product_id):
    job = _enqueue(db, product_id)
    job.job_status = status
    job.attempts = 3
    job.error_message = "旧错误"
    db.commit()

    job_service.retry_job(db, job)

    assert job.job_status == "pending"
    assert job.attempts == 0
    assert job.error_message == ""
    assert job.started_at is None
    assert job.finished_at is None
    assert job_service.EVENT_ENQUEUED in _events(db, job.id)


def test_cannot_retry_pending_job(db, product_id):
    job = _enqueue(db, product_id)
    with pytest.raises(ValueError):
        job_service.retry_job(db, job)


# ------------------------------------------------------------------ 超时
def test_sweep_marks_aged_running_jobs_as_timeout(db, product_id):
    job = _enqueue(db, product_id)
    job_service.claim_next_job(db, "worker-a")

    # 人工把锁定时间回拨到超时阈值之外
    job.locked_at = utcnow() - timedelta(seconds=600)
    db.commit()

    marked = job_service.sweep_timeouts(db, timeout_sec=120)

    assert marked == [job.id]
    db.refresh(job)
    assert job.job_status == "timeout"
    assert job.finished_at is not None
    assert "超时" in job.error_message
    assert job_service.EVENT_TIMEOUT in _events(db, job.id)


def test_sweep_ignores_fresh_running_jobs(db, product_id):
    job = _enqueue(db, product_id)
    job_service.claim_next_job(db, "worker-a")

    assert job_service.sweep_timeouts(db, timeout_sec=120) == []
    db.refresh(job)
    assert job.job_status == "running"


def test_sweep_ignores_non_running_jobs(db, product_id):
    job = _enqueue(db, product_id)
    job.locked_at = utcnow() - timedelta(seconds=9999)
    db.commit()

    assert job_service.sweep_timeouts(db, timeout_sec=10) == []


# ------------------------------------------------------------------ 事件完整性
def test_full_lifecycle_event_sequence(db, product_id):
    """一次完整生命周期应覆盖 入队 → 运行中 → 重试 → 成功 四个节点。"""
    job = _enqueue(db, product_id, max_attempts=3)

    job_service.claim_next_job(db, "worker-a")
    job_service.fail_job(db, job, "首次失败")

    job.next_run_at = utcnow()
    db.commit()
    job_service.claim_next_job(db, "worker-a")
    job_service.complete_job(db, job, [], "第二次成功")

    types = _events(db, job.id)
    assert types == [
        job_service.EVENT_ENQUEUED,
        job_service.EVENT_RUNNING,
        job_service.EVENT_RETRY,
        job_service.EVENT_RUNNING,
        job_service.EVENT_SUCCEEDED,
    ]


def test_event_count_map(db, product_id):
    a = _enqueue(db, product_id)
    b = _enqueue(db, product_id)
    job_service.claim_next_job(db, "worker-a")

    counts = job_service.event_count_map(db, [a.id, b.id])
    assert counts[a.id] == 2  # 入队 + 运行中
    assert counts[b.id] == 1
    assert job_service.event_count_map(db, []) == {}
