"""AI 内容生成提供方抽象。

第一版内置 ``MockAiProvider``（确定性模板 + 真实业务数据），
接口按可替换设计：后续接入真实大模型只需新增实现并在 registry 中注册，
业务路由始终通过 ``get_ai_provider()`` 取用，不直接依赖具体实现。

所有方法的入参均为普通 dict（由调用方从 ORM 对象序列化），
返回值也是普通 dict / list，便于直接写入各类 ``*_json`` 字段。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AiProvider(ABC):
    """内容生成接口。"""

    name: str = "base"

    # -- 诊断 ---------------------------------------------------------------
    @abstractmethod
    def generate_diagnosis(self, payload: dict[str, Any]) -> dict[str, Any]:
        """生成商品诊断。

        payload 至少包含 product / skus / competitors / performance / prior_actions。
        返回：positioning, price_band, audience_insights, pain_points,
        selling_point_analysis, risks, recommendations, summary_text
        （均为中文字符串，除 summary_text 外与 product_diagnoses 列一一对应）。
        """

    # -- 主图方案 -----------------------------------------------------------
    @abstractmethod
    def generate_main_image_plans(self, payload: dict[str, Any]) -> dict[str, Any]:
        """生成主图方案，至少 3 个方向。

        返回：{"title": str, "rationale_text": str, "directions": [
            {"direction_title","visual_structure","core_copy","highlight_selling_point","rationale"}
        ]}
        """

    # -- 视频脚本 -----------------------------------------------------------
    @abstractmethod
    def generate_video_scripts(self, payload: dict[str, Any]) -> dict[str, Any]:
        """生成视频脚本，至少 3 条。

        返回：{"title": str, "rationale_text": str, "scripts": [
            {"script_title","hook","storyboard","voiceover","conversion_cta"}
        ]}
        """

    # -- 投放建议 -----------------------------------------------------------
    @abstractmethod
    def generate_ad_recommendation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """生成投放建议。

        返回：summary_text, objective_text, audience_segments, budget_plan,
        creative_tests, bid_strategy, risk_controls, next_steps
        """

    # -- 复盘报告 -----------------------------------------------------------
    @abstractmethod
    def generate_review_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        """生成复盘报告。

        返回：{"summary_text": str, "insights": [...], "next_actions": [...]}
        next_actions 会作为下一轮诊断的输入，形成优化闭环。
        """

    # -- 推广链接建议 -------------------------------------------------------
    @abstractmethod
    def generate_promotion_link_suggestions(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """生成推广链接建议。

        返回：[{"link_name","scene_text","target_url","utm":{...}}]
        """

    # -- 库存建议 -----------------------------------------------------------
    @abstractmethod
    def generate_inventory_advice(self, payload: dict[str, Any]) -> dict[str, Any]:
        """生成库存建议。

        返回：{"summary_text": str, "items": [
            {"sku_code","sku_name","stock_qty","warning_threshold","advice","suggested_action"}
        ]}
        """
