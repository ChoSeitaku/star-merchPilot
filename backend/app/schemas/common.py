"""公共 Pydantic 基类与通用响应结构。"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PageResult(ApiModel, Generic[T]):
    total: int = 0
    items: list[T] = Field(default_factory=list)


class MessageOut(ApiModel):
    message: str
    detail: Optional[dict[str, Any]] = None


class ErrorRow(ApiModel):
    """导入校验中的错误行。"""

    row_no: int
    errors: list[str] = Field(default_factory=list)


class ImportPreview(ApiModel):
    """导入预览（确认前返回，不落库）。"""

    import_id: str
    import_type: str
    total_rows: int
    valid_rows: int
    invalid_rows: list[ErrorRow] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class ImportResult(ApiModel):
    """导入结果（允许部分成功）。"""

    import_id: str
    import_type: str
    total_rows: int
    success_rows: int
    failed_rows: int
    errors: list[ErrorRow] = Field(default_factory=list)
    created_ids: list[int] = Field(default_factory=list)
