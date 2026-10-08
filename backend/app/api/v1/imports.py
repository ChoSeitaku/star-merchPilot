"""导入中心路由。

覆盖四类导入：商品、SKU 库存、经营数据、平台字段映射。
（经营数据在商品维度下另有一个入口 `POST /products/{id}/performance-records/import`，
两者共用同一套导入服务。）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from ...database import get_db
from ...services import import_service, template_service
from ..deps import require_editor

router = APIRouter(prefix="/imports", tags=["导入中心"])

SUPPORTED = {
    "products": "商品导入",
    "sku-inventory": "SKU 库存导入",
    "platform-mappings": "平台字段映射导入",
    "performance": "经营数据导入",
}


@router.get("", summary="导入中心支持的导入类型")
def list_import_types() -> dict:
    return {
        "items": [
            {
                "import_type": key,
                "label": label,
                "template_endpoint": _template_endpoint(key),
                "preview_endpoint": f"/api/v1/imports/{key}/preview",
                "confirm_endpoint": f"/api/v1/imports/{key}/confirm",
                "note": template_service.TEMPLATES[key]["description"],
            }
            for key, label in SUPPORTED.items()
        ]
    }


def _template_endpoint(import_type: str) -> str:
    return {
        "products": "/api/v1/workspace/templates/products",
        "sku-inventory": "/api/v1/workspace/templates/sku-inventory",
        "performance-records": "/api/v1/workspace/templates/performance-records",
        "performance": "/api/v1/workspace/templates/performance-records",
        "platform-mappings": "/api/v1/workspace/templates/platform-mappings",
    }.get(import_type, "")


def _check_type(import_type: str) -> str:
    if import_type not in SUPPORTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的导入类型「{import_type}」，可选：{'、'.join(SUPPORTED)}",
        )
    return import_type


@router.post(
    "/{import_type}/preview",
    summary="上传并预览导入（校验 + 错误行提示，不写库）",
    dependencies=[Depends(require_editor)],
)
async def preview_import(
    import_type: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(..., description="按模板填写的 xlsx 文件"),
    product_id: int = Query(default=0, description="经营数据导入时需要指定商品"),
) -> dict:
    _check_type(import_type)
    return await import_service.handle_import(
        db,
        import_type=import_type,
        file=file,
        preview_only=True,
        product_id=product_id or None,
    )


@router.post(
    "/{import_type}/confirm",
    summary="确认导入（允许部分成功）",
    dependencies=[Depends(require_editor)],
)
async def confirm_import(
    import_type: str,
    db: Session = Depends(get_db),
    import_id: str = Query(..., description="预览阶段返回的 import_id"),
    product_id: int = Query(default=0, description="经营数据导入时需要指定商品"),
) -> dict:
    _check_type(import_type)
    return await import_service.handle_import(
        db,
        import_type=import_type,
        file=None,  # type: ignore[arg-type]  确认阶段从暂存文件读取
        preview_only=False,
        import_id=import_id,
        product_id=product_id or None,
    )
