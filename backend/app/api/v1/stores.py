"""店铺与平台账号路由。

权限：读取需登录；店铺与平台账号的写操作**仅管理员**（规格 1.5.2）。
合规：平台账号只落安全元数据，接口不接收任何明文密码 / token / cookie 字段。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db, utcnow
from ...models import (
    InventoryItem,
    PlatformAccount,
    Product,
    ProductSku,
    Store,
)
from ...providers import get_ai_provider
from ...schemas import (
    AuthorizationCallbackPlaceholder,
    AuthorizationStartRequest,
    PlatformAccountCreate,
    StoreCreate,
    StoreUpdate,
)
from ...serializers import (
    movement_out,
    platform_account_out,
    sku_out,
    store_out,
)
from ...models import InventoryMovement
from ..deps import require_admin, require_editor

router = APIRouter(prefix="/stores", tags=["店铺管理"])


# ------------------------------------------------------------------ 辅助查询
def _store_metrics(db: Session, store_ids: list[int]) -> dict[int, dict[str, int]]:
    """批量统计店铺的商品数与低库存 SKU 数。"""
    if not store_ids:
        return {}
    product_counts = dict(
        db.execute(
            select(Product.store_id, func.count(Product.id))
            .where(Product.store_id.in_(store_ids))
            .group_by(Product.store_id)
        ).all()
    )
    low_stock = dict(
        db.execute(
            select(Product.store_id, func.count(InventoryItem.id))
            .join(ProductSku, ProductSku.product_id == Product.id)
            .join(InventoryItem, InventoryItem.sku_id == ProductSku.id)
            .where(
                Product.store_id.in_(store_ids),
                InventoryItem.stock_qty <= InventoryItem.warning_threshold,
            )
            .group_by(Product.store_id)
        ).all()
    )
    return {
        sid: {"product_count": product_counts.get(sid, 0), "low_stock_count": low_stock.get(sid, 0)}
        for sid in store_ids
    }


def _get_store_or_404(db: Session, store_id: int) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    return store


# -------------------------------------------------------------------- 店铺
@router.get("", summary="店铺列表")
def list_stores(
    db: Session = Depends(get_db),
    keyword: str = Query(default="", description="按店铺名 / 负责人模糊搜索"),
    platform: str = Query(default="", description="按平台过滤"),
) -> dict:
    stmt = select(Store)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((Store.store_name.like(like)) | (Store.owner_name.like(like)))
    if platform:
        stmt = stmt.where(Store.platform == platform)
    stores = list(db.scalars(stmt.order_by(Store.id.desc())))
    metrics = _store_metrics(db, [s.id for s in stores])
    return {
        "total": len(stores),
        "items": [
            store_out(
                s,
                product_count=metrics.get(s.id, {}).get("product_count", 0),
                low_stock_count=metrics.get(s.id, {}).get("low_stock_count", 0),
            )
            for s in stores
        ],
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="创建店铺",
    dependencies=[Depends(require_admin)],
)
def create_store(payload: StoreCreate, db: Session = Depends(get_db)) -> dict:
    store = Store(**payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store_out(store)


@router.get("/{store_id}", summary="店铺详情（含库存概览与最近流水）")
def get_store(store_id: int, db: Session = Depends(get_db)) -> dict:
    store = _get_store_or_404(db, store_id)
    metrics = _store_metrics(db, [store.id]).get(store.id, {})

    products = list(
        db.scalars(select(Product).where(Product.store_id == store_id).order_by(Product.id.desc()))
    )
    skus = list(
        db.scalars(
            select(ProductSku)
            .join(Product, Product.id == ProductSku.product_id)
            .where(Product.store_id == store_id)
            .order_by(ProductSku.id.desc())
        )
    )
    sku_map = {s.id: s for s in skus}

    inventories = list(
        db.scalars(
            select(InventoryItem)
            .join(ProductSku, ProductSku.id == InventoryItem.sku_id)
            .where(ProductSku.product_id.in_([p.id for p in products] or [0]))
        )
    )
    total_stock = sum(i.stock_qty for i in inventories)
    total_locked = sum(i.locked_qty for i in inventories)
    low_stock_items = [i for i in inventories if i.stock_qty <= i.warning_threshold]

    movements = list(
        db.scalars(
            select(InventoryMovement)
            .where(InventoryMovement.sku_id.in_(list(sku_map.keys()) or [0]))
            .order_by(InventoryMovement.id.desc())
            .limit(20)
        )
    )

    return {
        **store_out(
            store,
            product_count=metrics.get("product_count", 0),
            low_stock_count=metrics.get("low_stock_count", 0),
        ),
        "platform_accounts": [platform_account_out(a) for a in store.accounts],
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "platform": p.platform,
                "category": p.category,
                "price": p.price,
                "status": p.status,
            }
            for p in products
        ],
        "inventory_overview": {
            "sku_count": len(skus),
            "total_stock": total_stock,
            "total_locked": total_locked,
            "total_available": total_stock - total_locked,
            "low_stock_sku_count": len(low_stock_items),
        },
        "low_stock_items": [
            {
                "sku_id": i.sku_id,
                "sku_code": sku_map[i.sku_id].sku_code if i.sku_id in sku_map else "",
                "sku_name": sku_map[i.sku_id].sku_name if i.sku_id in sku_map else "",
                "stock_qty": i.stock_qty,
                "warning_threshold": i.warning_threshold,
                "available_qty": i.available_qty,
            }
            for i in sorted(low_stock_items, key=lambda x: x.stock_qty)[:20]
        ],
        "recent_movements": [
            movement_out(
                m,
                sku_code=sku_map[m.sku_id].sku_code if m.sku_id in sku_map else "",
                sku_name=sku_map[m.sku_id].sku_name if m.sku_id in sku_map else "",
            )
            for m in movements
        ],
    }


@router.patch(
    "/{store_id}", summary="更新店铺", dependencies=[Depends(require_admin)]
)
def update_store(store_id: int, payload: StoreUpdate, db: Session = Depends(get_db)) -> dict:
    store = _get_store_or_404(db, store_id)
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(store, field, value)
    db.commit()
    db.refresh(store)
    metrics = _store_metrics(db, [store.id]).get(store.id, {})
    return store_out(
        store,
        product_count=metrics.get("product_count", 0),
        low_stock_count=metrics.get("low_stock_count", 0),
    )


# ---------------------------------------------------------------- 平台账号
@router.get("/{store_id}/platform-accounts", summary="平台账号列表")
def list_platform_accounts(store_id: int, db: Session = Depends(get_db)) -> dict:
    _get_store_or_404(db, store_id)
    accounts = list(
        db.scalars(
            select(PlatformAccount)
            .where(PlatformAccount.store_id == store_id)
            .order_by(PlatformAccount.id.desc())
        )
    )
    return {"total": len(accounts), "items": [platform_account_out(a) for a in accounts]}


@router.post(
    "/{store_id}/platform-accounts",
    status_code=status.HTTP_201_CREATED,
    summary="创建平台账号占位",
    dependencies=[Depends(require_admin)],
)
def create_platform_account(
    store_id: int, payload: PlatformAccountCreate, db: Session = Depends(get_db)
) -> dict:
    _get_store_or_404(db, store_id)
    account = PlatformAccount(
        store_id=store_id,
        platform=payload.platform,
        account_name=payload.account_name or f"{store_id}-{payload.platform}",
        auth_status="unauthorized",
        auth_meta_json={"scope": "", "authorize_url": "", "note": "尚未发起授权"},
        remark=payload.remark,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return platform_account_out(account)


@router.post(
    "/{store_id}/platform-accounts/{account_id}/authorization/start",
    summary="生成授权占位信息",
    dependencies=[Depends(require_admin)],
)
def start_authorization(
    store_id: int,
    account_id: int,
    payload: AuthorizationStartRequest,
    db: Session = Depends(get_db),
) -> dict:
    """生成授权占位信息。

    合规说明：真实环境应跳转平台官方 OAuth 授权页；
    本项目只生成**占位**授权链接与状态，不做任何凭据采集或代持。
    """
    _get_store_or_404(db, store_id)
    account = db.get(PlatformAccount, account_id)
    if account is None or account.store_id != store_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="平台账号不存在")

    authorize_url = (
        f"https://example.com/oauth/authorize"
        f"?client_id=mock-client-{account.id}&response_type=code"
        f"&scope={payload.scope}&state=mock-state-{account.id}"
    )
    if payload.redirect_uri:
        authorize_url += f"&redirect_uri={payload.redirect_uri}"

    account.auth_status = "pending_authorization"
    account.auth_meta_json = {
        "scope": payload.scope,
        "authorize_url": authorize_url,
        "redirect_uri": payload.redirect_uri,
        "started_at": utcnow().isoformat(),
        "note": "占位授权链接，真实接入时替换为平台官方 OAuth 地址",
    }
    db.commit()
    db.refresh(account)
    return {
        **platform_account_out(account),
        "authorize_url": authorize_url,
        "hint": "演示环境不会真正跳转平台；请在平台侧完成授权后回到系统提交授权元数据",
    }


@router.post(
    "/{store_id}/platform-accounts/{account_id}/authorization/callback-placeholder",
    summary="保存授权元数据（占位回调）",
    dependencies=[Depends(require_admin)],
)
def authorization_callback(
    store_id: int,
    account_id: int,
    payload: AuthorizationCallbackPlaceholder,
    db: Session = Depends(get_db),
) -> dict:
    """保存授权元数据。

    合规说明：**只保存**安全元数据（掩码后的授权码、授权范围、过期时间等），
    不接受也不保存任何明文密码、明文 token 或 cookie。
    """
    _get_store_or_404(db, store_id)
    account = db.get(PlatformAccount, account_id)
    if account is None or account.store_id != store_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="平台账号不存在")

    meta = dict(account.auth_meta_json or {})
    meta.update(
        {
            "auth_code_masked": payload.auth_code_masked,
            "scope": payload.granted_scope or meta.get("scope", ""),
            "authorized_account_name": payload.authorized_account_name,
            "expires_at": payload.expires_at,
            "authorized_at": utcnow().isoformat(),
            "credential_policy": "仅保存安全元数据，不保存明文凭据",
        }
    )
    meta.update(payload.extra_meta or {})

    account.auth_meta_json = meta
    account.auth_status = "authorized"
    if payload.authorized_account_name:
        account.account_name = payload.authorized_account_name
    db.commit()
    db.refresh(account)
    return platform_account_out(account)


# ---------------------------------------------------------------- 库存建议
@router.post(
    "/{store_id}/inventory-advice/generate",
    summary="生成库存建议",
    dependencies=[Depends(require_editor)],
)
def generate_inventory_advice(store_id: int, db: Session = Depends(get_db)) -> dict:
    store = _get_store_or_404(db, store_id)
    products = list(db.scalars(select(Product).where(Product.store_id == store_id)))
    product_ids = [p.id for p in products] or [0]
    skus = list(
        db.scalars(
            select(ProductSku)
            .where(ProductSku.product_id.in_(product_ids))
            .order_by(ProductSku.id)
        )
    )
    items: list[dict[str, Any]] = []
    for s in skus:
        inv = s.inventory
        items.append(
            {
                "sku_id": s.id,
                "sku_code": s.sku_code,
                "sku_name": s.sku_name,
                "product_id": s.product_id,
                "stock_qty": inv.stock_qty if inv else 0,
                "warning_threshold": inv.warning_threshold if inv else 0,
            }
        )

    advice = get_ai_provider().generate_inventory_advice(
        {"store_name": store.store_name, "items": items}
    )
    return {
        "store_id": store.id,
        "store_name": store.store_name,
        "generated_at": utcnow().isoformat(),
        "summary_text": advice["summary_text"],
        "items": advice["items"],
        "compliance_note": "库存建议仅为参考，不自动创建采购单或修改库存",
    }


# 供店铺详情页复用：单个 SKU 的库存快照
@router.get("/{store_id}/sku-stock", summary="店铺 SKU 库存快照")
def store_sku_stock(store_id: int, db: Session = Depends(get_db)) -> dict:
    _get_store_or_404(db, store_id)
    skus = list(
        db.scalars(
            select(ProductSku)
            .join(Product, Product.id == ProductSku.product_id)
            .where(Product.store_id == store_id)
            .order_by(ProductSku.id)
        )
    )
    return {"total": len(skus), "items": [sku_out(s) for s in skus]}
