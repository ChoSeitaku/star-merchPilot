"""竞品监控：到期快照生成。

与公开链接解析一致，快照数据为**确定性演示数值**，
真实接入时替换为开放接口 / 用户授权数据。
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import CompetitorMonitor, CompetitorMonitorSnapshot


def _digest(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)


def take_snapshot(db: Session, monitor: CompetitorMonitor, run_seq: int) -> CompetitorMonitorSnapshot:
    """为一次监控生成快照，并推进下次运行时间。"""
    competitor = monitor.competitor
    base_price = float(competitor.price or 0) or 99.0
    seed = f"{monitor.id}|{run_seq}"

    # 价格在 ±6% 内确定性波动，销量提示按序号递推，便于演示「监控到变化」
    delta_ratio = ((_digest(seed) % 1201) - 600) / 10000.0
    new_price = round(max(1.0, base_price * (1 + delta_ratio)), 2)

    base_sales = 200 + (_digest(f"{competitor.id}|sales") % 3000)
    sales_value = base_sales + run_seq * (17 + (_digest(seed) % 40))

    raw: dict[str, Any] = {
        "run_seq": run_seq,
        "price_delta_ratio": round(delta_ratio, 4),
        "price_before": base_price,
        "data_source": "演示用确定性快照（真实接入时替换为开放接口数据）",
        "captured_at": utcnow().isoformat(),
    }

    snapshot = CompetitorMonitorSnapshot(
        monitor_id=monitor.id,
        price=new_price,
        sales_hint=f"月销 {sales_value}+",
        selling_points=competitor.selling_points,
        raw_payload_json=raw,
    )
    db.add(snapshot)

    # 同步回写竞品当前价格，让诊断/投放建议读到最新数据
    competitor.price = new_price
    competitor.sales_hint = snapshot.sales_hint

    monitor.next_run_at = utcnow() + timedelta(minutes=monitor.interval_minutes)
    return snapshot


def run_due_monitors(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    """运行所有到期监控，返回本次产生的快照摘要。"""
    now = utcnow()
    due = list(
        db.scalars(
            select(CompetitorMonitor)
            .where(
                CompetitorMonitor.monitor_status == "active",
                (CompetitorMonitor.next_run_at.is_(None)) | (CompetitorMonitor.next_run_at <= now),
            )
            .order_by(CompetitorMonitor.next_run_at.asc().nullsfirst())
            .limit(limit)
        )
    )

    results: list[dict[str, Any]] = []
    for monitor in due:
        run_seq = _count_snapshots(db, monitor.id) + 1
        snapshot = take_snapshot(db, monitor, run_seq)
        db.flush()
        results.append(
            {
                "monitor_id": monitor.id,
                "competitor_id": monitor.competitor_id,
                "competitor_name": monitor.competitor.name if monitor.competitor else "",
                "snapshot_id": snapshot.id,
                "price": snapshot.price,
                "sales_hint": snapshot.sales_hint,
                "next_run_at": monitor.next_run_at.isoformat() if monitor.next_run_at else None,
            }
        )

    if results:
        db.commit()
    return results


def _count_snapshots(db: Session, monitor_id: int) -> int:
    from sqlalchemy import func

    return (
        db.scalar(
            select(func.count(CompetitorMonitorSnapshot.id)).where(
                CompetitorMonitorSnapshot.monitor_id == monitor_id
            )
        )
        or 0
    )
