"""竞品、公开链接解析任务与竞品监控路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import (
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    PublicLinkParseTask,
)
from ...schemas import CompetitorCreate, CompetitorUpdate, LinkParseTaskCreate, MonitorCreate
from ...serializers import (
    competitor_out,
    link_parse_task_out,
    monitor_out,
    monitor_snapshot_out,
)
from ...services import monitor_service, parse_service
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}", tags=["竞品管理"])


def _monitor_map(db: Session, competitor_ids: list[int]) -> dict[int, CompetitorMonitor]:
    if not competitor_ids:
        return {}
    rows = list(
        db.scalars(
            select(CompetitorMonitor).where(CompetitorMonitor.competitor_id.in_(competitor_ids))
        )
    )
    return {m.competitor_id: m for m in rows}


# -------------------------------------------------------------------- 竞品
@router.get("/competitors", summary="竞品列表")
def list_competitors(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(Competitor).where(Competitor.product_id == product_id).order_by(Competitor.id.desc())
        )
    )
    monitors = _monitor_map(db, [c.id for c in rows])
    return {
        "total": len(rows),
        "items": [competitor_out(c, monitor=monitors.get(c.id)) for c in rows],
    }


@router.post(
    "/competitors",
    status_code=status.HTTP_201_CREATED,
    summary="录入竞品",
    dependencies=[Depends(require_editor)],
)
def create_competitor(
    product_id: int, payload: CompetitorCreate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
    # 未显式给出平台时，尝试从链接推断
    data = payload.model_dump()
    if data.get("url") and data.get("platform") in ("", "other"):
        data["platform"] = parse_service.detect_platform(data["url"])
    if not data.get("name") and data.get("title"):
        data["name"] = data["title"][:60]

    competitor = Competitor(product_id=product_id, **data)
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor_out(competitor)


@router.patch(
    "/competitors/{competitor_id}",
    summary="更新竞品",
    dependencies=[Depends(require_editor)],
)
def update_competitor(
    product_id: int,
    competitor_id: int,
    payload: CompetitorUpdate,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    competitor = db.get(Competitor, competitor_id)
    if competitor is None or competitor.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="竞品不存在")
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(competitor, field, value)
    db.commit()
    db.refresh(competitor)
    monitors = _monitor_map(db, [competitor.id])
    return competitor_out(competitor, monitor=monitors.get(competitor.id))


@router.delete(
    "/competitors/{competitor_id}",
    summary="删除竞品",
    dependencies=[Depends(require_editor)],
)
def delete_competitor(product_id: int, competitor_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    competitor = db.get(Competitor, competitor_id)
    if competitor is None or competitor.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="竞品不存在")
    db.delete(competitor)
    db.commit()
    return {"message": "竞品已删除", "competitor_id": competitor_id}


# ------------------------------------------------------- 公开链接解析任务
@router.get("/link-parse-tasks", summary="公开链接解析任务列表")
def list_parse_tasks(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(PublicLinkParseTask)
            .where(PublicLinkParseTask.product_id == product_id)
            .order_by(PublicLinkParseTask.id.desc())
        )
    )
    return {"total": len(rows), "items": [link_parse_task_out(t) for t in rows]}


@router.post(
    "/competitors/import-url-tasks",
    status_code=status.HTTP_201_CREATED,
    summary="创建公开链接解析任务",
    dependencies=[Depends(require_editor)],
)
def create_parse_tasks(
    product_id: int, payload: LinkParseTaskCreate, db: Session = Depends(get_db)
) -> dict:
    """批量创建链接解析任务。

    合规：仅对公开链接做有限信息提取，不抓取页面、不绕过任何访问控制。
    """
    get_product_or_404(db, product_id)
    created: list[PublicLinkParseTask] = []
    for url in payload.urls:
        task = PublicLinkParseTask(
            product_id=product_id,
            source_url=url[:512],
            task_status="pending",
            attempts=0,
            result_json={"auto_create_competitors": payload.auto_create_competitors},
        )
        db.add(task)
        created.append(task)
    db.commit()
    for t in created:
        db.refresh(t)
    return {
        "total": len(created),
        "items": [link_parse_task_out(t) for t in created],
        "hint": "任务已创建，调用 run 接口执行解析",
    }


@router.post(
    "/link-parse-tasks/{task_id}/run",
    summary="运行公开链接解析任务",
    dependencies=[Depends(require_editor)],
)
def run_parse_task(product_id: int, task_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    task = db.get(PublicLinkParseTask, task_id)
    if task is None or task.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="解析任务不存在")
    if task.task_status == "running":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务正在执行中")

    task.task_status = "running"
    task.attempts += 1
    db.commit()

    result = parse_service.parse_public_link(task.source_url)
    task.updated_at = utcnow()

    created_competitors: list[Competitor] = []
    if not result.get("ok"):
        task.task_status = "failed"
        task.error_message = result.get("error_message", "解析失败")
        db.commit()
        db.refresh(task)
        return {**link_parse_task_out(task), "created_competitors": []}

    extracted = result["extracted"]
    task.result_json = {
        **(task.result_json or {}),
        **result,
    }
    task.task_status = "succeeded"
    task.error_message = ""

    auto_create = bool((task.result_json or {}).get("auto_create_competitors", True))
    if auto_create:
        existing = db.scalar(
            select(Competitor.id).where(
                Competitor.product_id == product_id, Competitor.url == task.source_url
            )
        )
        if existing is None:
            competitor = Competitor(
                product_id=product_id,
                name=extracted.get("title", "")[:60],
                platform=result["platform"],
                url=task.source_url,
                price=float(extracted.get("price") or 0),
                sales_hint=extracted.get("sales_hint", ""),
                title=extracted.get("title", ""),
                main_image=extracted.get("main_image", ""),
                selling_points="",
                review_keywords="",
            )
            db.add(competitor)
            db.flush()
            created_competitors.append(competitor)

    db.commit()
    db.refresh(task)
    return {
        **link_parse_task_out(task),
        "created_competitors": [competitor_out(c) for c in created_competitors],
    }


# ---------------------------------------------------------------- 竞品监控
@router.get("/competitor-monitors", summary="竞品监控列表")
def list_monitors(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(CompetitorMonitor)
            .join(Competitor, Competitor.id == CompetitorMonitor.competitor_id)
            .where(Competitor.product_id == product_id)
            .order_by(CompetitorMonitor.id.desc())
        )
    )
    return {"total": len(rows), "items": [monitor_out(m) for m in rows]}


@router.post(
    "/competitors/{competitor_id}/monitor",
    status_code=status.HTTP_201_CREATED,
    summary="创建竞品监控",
    dependencies=[Depends(require_editor)],
)
def create_monitor(
    product_id: int, competitor_id: int, payload: MonitorCreate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
    competitor = db.get(Competitor, competitor_id)
    if competitor is None or competitor.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="竞品不存在")

    existing = db.scalar(
        select(CompetitorMonitor).where(CompetitorMonitor.competitor_id == competitor_id)
    )
    if existing is not None:
        existing.monitor_status = "active"
        existing.interval_minutes = payload.interval_minutes
        if existing.next_run_at is None:
            existing.next_run_at = utcnow()
        db.commit()
        db.refresh(existing)
        return monitor_out(existing)

    monitor = CompetitorMonitor(
        competitor_id=competitor_id,
        monitor_status="active",
        interval_minutes=payload.interval_minutes,
        next_run_at=utcnow(),
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor_out(monitor)


@router.patch(
    "/competitor-monitors/{monitor_id}",
    summary="更新竞品监控状态",
    dependencies=[Depends(require_editor)],
)
def update_monitor(
    product_id: int,
    monitor_id: int,
    db: Session = Depends(get_db),
    monitor_status: str = Query(default="active", description="active / paused"),
) -> dict:
    get_product_or_404(db, product_id)
    monitor = db.get(CompetitorMonitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    monitor.monitor_status = monitor_status
    db.commit()
    db.refresh(monitor)
    return monitor_out(monitor)


@router.get("/competitor-monitors/{monitor_id}/snapshots", summary="竞品监控快照")
def list_snapshots(
    product_id: int,
    monitor_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    get_product_or_404(db, product_id)
    monitor = db.get(CompetitorMonitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    rows = list(
        db.scalars(
            select(CompetitorMonitorSnapshot)
            .where(CompetitorMonitorSnapshot.monitor_id == monitor_id)
            .order_by(CompetitorMonitorSnapshot.id.desc())
            .limit(limit)
        )
    )
    return {
        "total": len(rows),
        "competitor_name": monitor.competitor.name if monitor.competitor else "",
        "items": [monitor_snapshot_out(s) for s in rows],
    }


@router.post(
    "/competitor-monitors/run-due",
    summary="立即运行到期的竞品监控（单商品）",
    dependencies=[Depends(require_editor)],
)
def run_due_for_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    results = monitor_service.run_due_monitors(db)
    # 只保留属于该商品的结果
    from ...models import Competitor as _C

    own_ids = {
        c.id for c in db.scalars(select(_C).where(_C.product_id == product_id))
    }
    filtered = [r for r in results if r["competitor_id"] in own_ids]
    return {"total": len(filtered), "items": filtered}
