"""后台任务工作进程。

在 FastAPI lifespan 中启动一个 asyncio 循环：

1. 每 ``poll_interval_sec`` 轮询一次待执行任务（可通过设置页热调整）
2. 顺带扫描并标记超时任务
3. 抢到任务后交给线程池执行（模拟耗时用 ``asyncio.sleep`` 实现，避免阻塞事件循环）

所有数据库访问都通过 ``asyncio.to_thread`` 进入线程，使用短生命周期会话，
因此不会与请求线程争抢连接，也不会长时间占用 SQLite 写锁。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from ..database import session_scope, utcnow
from ..services import job_service
from ..services.settings_service import queue_config
from . import executor

logger = logging.getLogger("merchpilot.worker")


class WorkerManager:
    def __init__(self) -> None:
        self.worker_id = f"worker-{os.getpid()}"
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._inflight: set[int] = set()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._loop_count = 0
        self._last_tick_at: Optional[str] = None
        self._last_error: str = ""

    # ------------------------------------------------------------- 生命周期
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="generation-worker")
        logger.info("生成任务工作进程已启动：%s", self.worker_id)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        logger.info("生成任务工作进程已停止：%s", self.worker_id)

    # ---------------------------------------------------------------- 主循环
    async def _loop(self) -> None:
        # 上一轮结束后等待的标记，避免任务一多就空转
        while self._running:
            try:
                interval, concurrency, timeout_sec, simulate_seconds, max_attempts = (
                    await asyncio.to_thread(self._read_config)
                )
                self._semaphore = asyncio.Semaphore(concurrency)

                await asyncio.to_thread(self._sweep, timeout_sec)
                await self._dispatch(concurrency, simulate_seconds, max_attempts)
                self._loop_count += 1
                self._last_tick_at = utcnow().isoformat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001  工作进程不能因单次异常退出
                self._last_error = str(exc)
                logger.exception("工作进程轮询异常：%s", exc)
                interval = 3

            await asyncio.sleep(interval)

    @staticmethod
    def _read_config() -> tuple[int, int, int, int, int]:
        db = session_scope()
        try:
            cfg = queue_config(db)
            return (
                cfg["poll_interval_sec"],
                cfg["concurrency"],
                cfg["job_timeout_sec"],
                cfg["simulate_seconds"],
                cfg["max_attempts"],
            )
        finally:
            db.close()

    @staticmethod
    def _sweep(timeout_sec: int) -> list[int]:
        db = session_scope()
        try:
            return job_service.sweep_timeouts(db, timeout_sec)
        finally:
            db.close()

    async def _dispatch(self, concurrency: int, simulate_seconds: int, max_attempts: int) -> None:
        """在并发额度内尽可能多地抢占并派发任务。"""
        while len(self._inflight) < concurrency:
            job_id = await asyncio.to_thread(self._claim, max_attempts)
            if job_id is None:
                break
            self._inflight.add(job_id)
            asyncio.create_task(self._run_one(job_id, simulate_seconds))

    def _claim(self, max_attempts: int) -> Optional[int]:
        db = session_scope()
        try:
            job = job_service.claim_next_job(db, self.worker_id)
            # 首次执行的任务沿用当前队列配置的最大尝试次数
            if job is not None and job.attempts == 0 and job.max_attempts != max_attempts:
                job.max_attempts = max_attempts
                db.commit()
            return job.id if job else None
        finally:
            db.close()

    async def _run_one(self, job_id: int, simulate_seconds: int) -> None:
        try:
            # 模拟生成耗时，不阻塞事件循环，也不占用数据库连接
            await asyncio.sleep(simulate_seconds)
            await asyncio.to_thread(executor.execute_job, job_id, simulate_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            logger.exception("任务 %s 执行异常：%s", job_id, exc)
            await asyncio.to_thread(self._mark_failed, job_id, str(exc))
        finally:
            self._inflight.discard(job_id)

    @staticmethod
    def _mark_failed(job_id: int, error: str) -> None:
        db = session_scope()
        try:
            from ..models import GenerationJob

            job = db.get(GenerationJob, job_id)
            if job is not None and job.job_status not in job_service.TERMINAL_STATUSES:
                job_service.fail_job(db, job, f"执行器异常：{error}")
        finally:
            db.close()

    # ------------------------------------------------------------------ 状态
    def status(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "running": self._running,
            "inflight_jobs": sorted(self._inflight),
            "loop_count": self._loop_count,
            "last_tick_at": self._last_tick_at,
            "last_error": self._last_error,
        }


worker_manager = WorkerManager()
