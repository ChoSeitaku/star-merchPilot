"""API v1 路由聚合。

约定：**所有**写操作都在各自路由内挂 ``Depends(require_editor)`` 等权限依赖，
读接口统一要求登录（在此处对整组路由加 ``get_current_user`` 依赖）。
仅 ``auth`` 与推广短链跳转 ``r`` 不需要登录。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from . import (
    ad,
    assets,
    auth,
    competitors,
    creative_plans,
    diagnoses,
    imports,
    jobs,
    links,
    performance,
    products,
    review,
    stores,
    users,
    workspace,
)

# 无需登录的路由（登录接口、推广短链跳转）
public_router = APIRouter()
public_router.include_router(auth.router)
public_router.include_router(links.public_router)

# 需要登录的路由
protected_router = APIRouter(dependencies=[Depends(get_current_user)])
protected_router.include_router(users.router)
protected_router.include_router(stores.router)
protected_router.include_router(products.router)
protected_router.include_router(competitors.router)
protected_router.include_router(diagnoses.router)
protected_router.include_router(creative_plans.router)
protected_router.include_router(jobs.router)
protected_router.include_router(assets.router)
protected_router.include_router(links.router)
protected_router.include_router(ad.router)
protected_router.include_router(performance.router)
protected_router.include_router(review.router)
protected_router.include_router(imports.router)
protected_router.include_router(workspace.router)

api_router = APIRouter()
api_router.include_router(public_router)
api_router.include_router(protected_router)
