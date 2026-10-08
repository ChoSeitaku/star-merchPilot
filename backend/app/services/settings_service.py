"""system_settings 读写与类型转换。

任务队列参数（轮询间隔、超时阈值、最大尝试次数、并发数、模拟耗时）
存放在这里，工作进程每轮读取一次，因此设置页修改后无需重启即可生效。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SystemSetting

# 队列参数默认值（表里缺失时兜底）
QUEUE_DEFAULTS: dict[str, Any] = {
    "queue_poll_interval_sec": 2,
    "queue_job_timeout_sec": 120,
    "queue_max_attempts": 3,
    "queue_concurrency": 1,
    "queue_simulate_seconds": 4,
}

_CACHE: dict[str, Any] = {}
_CACHE_LOADED = False


def _coerce(value: str, value_type: str) -> Any:
    try:
        if value_type == "int":
            return int(value)
        if value_type == "float":
            return float(value)
        if value_type == "bool":
            return value.strip().lower() in ("1", "true", "yes", "on")
    except (TypeError, ValueError):
        return None
    return value


def get_raw(db: Session, key: str, default: Any = None) -> Any:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if row is None:
        return default
    parsed = _coerce(row.value, row.value_type)
    return default if parsed is None else parsed


def get_many(db: Session, keys: list[str]) -> dict[str, Any]:
    rows = {s.key: s for s in db.scalars(select(SystemSetting).where(SystemSetting.key.in_(keys)))}
    out: dict[str, Any] = {}
    for key in keys:
        row = rows.get(key)
        out[key] = _coerce(row.value, row.value_type) if row else None
    return out


def queue_config(db: Session) -> dict[str, Any]:
    """读取任务队列配置，缺失项用默认值补齐并做安全钳制。"""
    values = {**QUEUE_DEFAULTS, **{k: v for k, v in get_many(db, list(QUEUE_DEFAULTS)).items() if v is not None}}
    return {
        "poll_interval_sec": max(1, int(values["queue_poll_interval_sec"])),
        "job_timeout_sec": max(10, int(values["queue_job_timeout_sec"])),
        "max_attempts": max(1, min(10, int(values["queue_max_attempts"]))),
        "concurrency": max(1, min(8, int(values["queue_concurrency"]))),
        "simulate_seconds": max(1, min(60, int(values["queue_simulate_seconds"]))),
    }


def set_value(db: Session, key: str, value: Any) -> SystemSetting:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if row is None:
        row = SystemSetting(key=key, value=str(value), value_type="string", category="custom")
        db.add(row)
    elif row.editable:
        row.value = str(value)
    return row
