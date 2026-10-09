"""内容生成提供方。

默认按环境变量 ``AI_PROVIDER``（默认 ``deepseek``）选择实现；
若该实现未配置凭据（例如缺少大模型凭据），自动回落到 ``mock``，保证业务可用。
"""

from __future__ import annotations

import os

from .base import AiProvider
from .deepseek import DeepSeekAiProvider
from .mock import MockAiProvider
from .registry import (
    active_provider_name,
    available_providers,
    get_ai_provider,
    register_provider,
    set_active_provider,
)

register_provider("deepseek", DeepSeekAiProvider)

_DEFAULT_PROVIDER = "deepseek"


def _autoconfigure() -> str:
    """按 ``AI_PROVIDER`` 激活实现；未配置凭据时回落 mock。"""
    want = (os.getenv("AI_PROVIDER") or _DEFAULT_PROVIDER).strip().lower()
    if want not in available_providers():
        want = "mock"
    set_active_provider(want)
    if not getattr(get_ai_provider(), "ready", True):
        set_active_provider("mock")
    return active_provider_name()


active_provider = _autoconfigure()

__all__ = [
    "AiProvider",
    "MockAiProvider",
    "DeepSeekAiProvider",
    "get_ai_provider",
    "register_provider",
    "set_active_provider",
    "active_provider_name",
    "available_providers",
    "active_provider",
]
