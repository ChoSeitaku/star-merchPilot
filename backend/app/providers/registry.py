"""提供方注册表：业务代码一律通过 ``get_ai_provider()`` 取用实现。"""

from __future__ import annotations

from .base import AiProvider
from .mock import MockAiProvider

_PROVIDERS: dict[str, type[AiProvider]] = {
    "mock": MockAiProvider,
}

_instance: AiProvider | None = None
_active_name = "mock"


def register_provider(name: str, provider_cls: type[AiProvider]) -> None:
    """注册新的提供方实现（例如接入真实大模型时）。"""
    _PROVIDERS[name] = provider_cls


def set_active_provider(name: str) -> None:
    global _instance, _active_name
    if name not in _PROVIDERS:
        raise ValueError(f"未注册的内容生成提供方：{name}")
    _active_name = name
    _instance = None


def get_ai_provider() -> AiProvider:
    global _instance
    if _instance is None:
        _instance = _PROVIDERS[_active_name]()
    return _instance


def active_provider_name() -> str:
    return _active_name


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)
