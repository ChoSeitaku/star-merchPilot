"""推广链接路由。

包含两个路由组：
- ``router``        需要登录，挂在商品下，负责建议生成与链接创建
- ``public_router`` **无需登录**，仅处理 ``/r/{tracking_code}`` 短链跳转与点击记录
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import PromotionLink, PromotionLinkClick
from ...providers import get_ai_provider
from ...schemas import PromotionLinkCreate, PromotionLinkUpdate
from ...serializers import promotion_link_out
from ...services import context_service, link_service
from ..deps import require_editor
from .products import get_product_or_404

router = APIRouter(prefix="/products/{product_id}/promotion-links", tags=["推广链接"])
public_router = APIRouter(tags=["推广链接"])


def _link_out_with_stats(db: Session, link: PromotionLink) -> dict:
    data = promotion_link_out(link)
    stats = link_service.click_stats(db, [link.id]).get(link.id, {})
    data.update(
        {
            "click_records": stats.get("click_records", 0),
            "last_clicked_at": stats.get("last_clicked_at"),
            "full_track_url": link_service.append_utm(link.target_url, link.utm_json or {}),
        }
    )
    return data


@router.get("", summary="推广链接列表")
def list_links(product_id: int, db: Session = Depends(get_db)) -> dict:
    get_product_or_404(db, product_id)
    rows = list(
        db.scalars(
            select(PromotionLink)
            .where(PromotionLink.product_id == product_id)
            .order_by(PromotionLink.id.desc())
        )
    )
    return {"total": len(rows), "items": [_link_out_with_stats(db, link) for link in rows]}


@router.post(
    "/generate",
    summary="生成推广链接建议",
    dependencies=[Depends(require_editor)],
)
def generate_link_suggestions(product_id: int, db: Session = Depends(get_db)) -> dict:
    """生成推广链接建议。

    注意：本接口只返回**建议**，不直接创建链接；
    由用户确认后再调用创建接口，避免误创建。
    """
    product = get_product_or_404(db, product_id)
    suggestions = get_ai_provider().generate_promotion_link_suggestions(
        {"product": context_service.product_payload(db, product)}
    )
    return {
        "product_id": product_id,
        "total": len(suggestions),
        "items": suggestions,
        "hint": "确认无误后调用创建接口落库，或直接修改后创建",
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="创建推广链接",
    dependencies=[Depends(require_editor)],
)
def create_link(
    product_id: int, payload: PromotionLinkCreate, db: Session = Depends(get_db)
) -> dict:
    get_product_or_404(db, product_id)
    link = PromotionLink(
        product_id=product_id,
        link_name=payload.link_name,
        target_url=payload.target_url,
        tracking_code=link_service.generate_tracking_code(db),
        utm_json=payload.utm_json or {},
        status=payload.status,
        click_count=0,
        scene_text=payload.scene_text,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return {
        **_link_out_with_stats(db, link),
        "message": "推广链接已创建，可通过 track_url 访问并自动记录点击",
    }


@router.patch(
    "/{link_id}", summary="更新推广链接", dependencies=[Depends(require_editor)]
)
def update_link(
    product_id: int,
    link_id: int,
    payload: PromotionLinkUpdate,
    db: Session = Depends(get_db),
) -> dict:
    get_product_or_404(db, product_id)
    link = db.get(PromotionLink, link_id)
    if link is None or link.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="推广链接不存在")
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(link, field, value)
    db.commit()
    db.refresh(link)
    return _link_out_with_stats(db, link)


@router.get("/{link_id}/clicks", summary="推广链接点击明细")
def link_clicks(
    product_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    get_product_or_404(db, product_id)
    link = db.get(PromotionLink, link_id)
    if link is None or link.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="推广链接不存在")
    rows = list(
        db.scalars(
            select(PromotionLinkClick)
            .where(PromotionLinkClick.promotion_link_id == link_id)
            .order_by(PromotionLinkClick.id.desc())
            .limit(limit)
        )
    )
    return {
        "link_id": link_id,
        "tracking_code": link.tracking_code,
        "click_count": link.click_count,
        "total": len(rows),
        "items": [
            {
                "id": c.id,
                "clicked_at": c.clicked_at.isoformat() if c.clicked_at else None,
                "client_ip": c.client_ip,
                "user_agent": c.user_agent,
            }
            for c in rows
        ],
    }


# ------------------------------------------------------------ 公开短链跳转
@public_router.get(
    "/r/{tracking_code}",
    summary="推广链接跳转并记录点击（无需登录）",
    response_class=RedirectResponse,
)
def redirect_tracking(tracking_code: str, request: Request, db: Session = Depends(get_db)):
    """记录点击后 302 跳转到目标地址。

    该接口无需登录（外部分发场景），因此只做最小必要的记录，
    不返回任何业务数据，避免信息泄露。
    """
    link = db.scalar(select(PromotionLink).where(PromotionLink.tracking_code == tracking_code))
    if link is None or link.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="推广链接不存在或已停用")

    client_ip = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")

    link_service.record_click(db, link, client_ip, user_agent)

    target = link.target_url or "/"
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
