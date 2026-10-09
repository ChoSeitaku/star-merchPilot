"""DeepSeek 内容生成实现（OpenAI 兼容协议 + JSON 模式）。

设计要点：
* 凭据只从环境变量读取，不写进源码；
* 未配置凭据、或调用/解析失败时，自动回落到 ``MockAiProvider``，业务不中断；
* 所有方法统一要求模型输出 JSON，便于直接写入各类 ``*_json`` 字段。

环境变量：
    DEEPSEEK_API_KEY     凭据；缺失则本实现整体降级为 mock
    DEEPSEEK_BASE_URL    默认 https://api.deepseek.com
    DEEPSEEK_MODEL       默认 deepseek-flash
    AI_MAX_TOKENS        默认 4096（推理模型的 reasoning 也占用该额度）
    AI_TIMEOUT_SECONDS   默认 180
    AI_TEMPERATURE       默认 0.2
    AI_REASONING_EFFORT  默认 low；设 high/max 可提升质量但更慢更贵
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, Callable

from .base import AiProvider
from .mock import MockAiProvider


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)) or default)
    except ValueError:
        return default


def _brief(payload: dict, limit: int = 7000) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(payload)
    return text[:limit]


def _user(task: str, schema: str, payload: dict) -> str:
    return (
        task
        + "\n\n【输出要求】只输出一个 JSON 对象，不要解释、不要 Markdown 围栏。字段结构：\n"
        + schema
        + "\n\n【业务数据】\n"
        + _brief(payload)
    )


def _parse_json(raw: str) -> Any:
    """容错解析：支持裸 JSON、```json 围栏、以及前后夹带说明文字。"""
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        end = max(text.rfind("}"), text.rfind("]"))
        if starts and end > starts[0]:
            try:
                return json.loads(text[starts[0]: end + 1])
            except ValueError:
                return None
        return None


def _str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _dict_list(data: Any, field: str, keys: tuple, least: int) -> Any:
    raw = data.get(field) if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = {k: _str(item.get(k)) for k in keys}
        if any(row.values()):
            out.append(row)
    return out if len(out) >= least else None


# ---------------------------------------------------------------- 归一化函数

def _norm_diagnosis(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    fields = (
        "positioning", "price_band", "audience_insights", "pain_points",
        "selling_point_analysis", "risks", "recommendations", "summary_text",
    )
    out = {f: _str(data.get(f)) for f in fields}
    if not out["summary_text"]:
        return None
    return out


def _norm_image_plans(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    dirs = _dict_list(
        data, "directions",
        ("direction_title", "visual_structure", "core_copy", "highlight_selling_point", "rationale"),
        3,
    )
    if dirs is None:
        return None
    return {
        "title": _str(data.get("title")) or "主图方案",
        "rationale_text": _str(data.get("rationale_text")),
        "directions": dirs,
    }


def _norm_video_scripts(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    scripts = _dict_list(
        data, "scripts",
        ("script_title", "hook", "storyboard", "voiceover", "conversion_cta"),
        3,
    )
    if scripts is None:
        return None
    return {
        "title": _str(data.get("title")) or "视频脚本",
        "rationale_text": _str(data.get("rationale_text")),
        "scripts": scripts,
    }


def _norm_ad(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    if not _str(data.get("summary_text")):
        return None
    segments = _dict_list(data, "audience_segments", ("segment_name", "description", "priority", "reason"), 1)
    tests = _dict_list(data, "creative_tests", ("test_name", "test_content", "hypothesis", "success_metric"), 1)
    risks = data.get("risk_controls")
    steps = data.get("next_steps")
    budget = data.get("budget_plan") if isinstance(data.get("budget_plan"), dict) else {}
    bid = data.get("bid_strategy") if isinstance(data.get("bid_strategy"), dict) else {}
    return {
        "summary_text": _str(data.get("summary_text")),
        "objective_text": _str(data.get("objective_text")),
        "audience_segments": segments or [],
        "budget_plan": budget,
        "creative_tests": tests or [],
        "bid_strategy": bid,
        "risk_controls": [_str(x) for x in risks] if isinstance(risks, list) else [],
        "next_steps": [_str(x) for x in steps] if isinstance(steps, list) else [],
    }


def _norm_review(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    insights = _dict_list(data, "insights", ("insight_title", "insight_detail", "impact"), 1)
    actions = _dict_list(data, "next_actions", ("action_title", "action_detail", "owner", "priority"), 1)
    if not _str(data.get("summary_text")) or insights is None or actions is None:
        return None
    return {
        "summary_text": _str(data.get("summary_text")),
        "insights": insights,
        "next_actions": actions,
    }


def _norm_links(data: Any) -> Any:
    items = data.get("links") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("link_name"))
        url = _str(item.get("target_url"))
        if not name or not url:
            continue
        utm = item.get("utm") if isinstance(item.get("utm"), dict) else {}
        out.append({
            "link_name": name,
            "scene_text": _str(item.get("scene_text")),
            "target_url": url,
            "utm": {k: _str(v) for k, v in utm.items()},
        })
    return out or None


def _norm_inventory(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    raw = data.get("items")
    if not isinstance(raw, list):
        return None
    items = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        sku = _str(row.get("sku_code"))
        if not sku:
            continue
        items.append({
            "sku_code": sku,
            "sku_name": _str(row.get("sku_name")),
            "stock_qty": row.get("stock_qty") or 0,
            "warning_threshold": row.get("warning_threshold") or 0,
            "advice": _str(row.get("advice")),
            "suggested_action": _str(row.get("suggested_action")),
        })
    if not items or not _str(data.get("summary_text")):
        return None
    return {"summary_text": _str(data.get("summary_text")), "items": items}


# ---------------------------------------------------------------- 提示词

SYSTEM = (
    "你是资深电商运营专家。所有结论必须基于用户给出的真实业务数据，"
    "不得编造数据。语言简洁专业，全部使用简体中文。"
)

SCHEMA_DIAGNOSIS = """{
  "positioning": "一句话定位",
  "price_band": "建议价格带及理由",
  "audience_insights": "目标人群洞察",
  "pain_points": "用户痛点",
  "selling_point_analysis": "卖点分析",
  "risks": "主要风险",
  "recommendations": "可执行建议",
  "summary_text": "整体结论摘要"
}"""

SCHEMA_IMAGE = """{
  "title": "方案标题",
  "rationale_text": "整体思路说明",
  "directions": [
    {"direction_title": "方向名", "visual_structure": "画面结构", "core_copy": "主文案",
     "highlight_selling_point": "突出卖点", "rationale": "理由"}
  ]
}"""

SCHEMA_VIDEO = """{
  "title": "脚本集标题",
  "rationale_text": "整体思路说明",
  "scripts": [
    {"script_title": "脚本名", "hook": "前3秒钩子", "storyboard": "分镜",
     "voiceover": "口播文案", "conversion_cta": "转化引导"}
  ]
}"""

SCHEMA_AD = """{
  "summary_text": "投放建议摘要",
  "objective_text": "投放目标",
  "audience_segments": [{"segment_name": "人群名", "description": "描述", "priority": "高/中/低", "reason": "理由"}],
  "budget_plan": {"daily_budget": 100, "total_budget": 3000, "duration_days": 30,
                  "phase_plan": [{"phase": "阶段名", "budget": 100, "focus": "重点"}],
                  "target_cpa": 50, "note": "说明"},
  "creative_tests": [{"test_name": "实验名", "test_content": "内容", "hypothesis": "假设", "success_metric": "指标"}],
  "bid_strategy": {"mode": "出价方式", "initial_bid": 1.0, "bid_ceiling": 1.2,
                   "adjust_rule": "调整规则", "note": "说明"},
  "risk_controls": ["风险控制措施"],
  "next_steps": ["下一步动作"]
}"""

SCHEMA_REVIEW = """{
  "summary_text": "复盘结论摘要，需引用具体指标数值",
  "insights": [{"insight_title": "洞察标题", "insight_detail": "洞察说明", "impact": "高/中/低"}],
  "next_actions": [{"action_title": "动作标题", "action_detail": "具体做法", "owner": "负责人", "priority": "高/中/低"}]
}"""

SCHEMA_LINKS = """{"links": [
  {"link_name": "链接名称", "scene_text": "使用场景说明", "target_url": "落地页地址",
   "utm": {"utm_source": "来源", "utm_medium": "媒介", "utm_campaign": "活动", "utm_content": "内容", "utm_term": "关键词"}}
]}"""

SCHEMA_INVENTORY = """{
  "summary_text": "库存整体结论",
  "items": [{"sku_code": "SKU编码", "sku_name": "SKU名称", "stock_qty": 10,
             "warning_threshold": 20, "advice": "库存判断", "suggested_action": "建议动作"}]
}"""


class DeepSeekAiProvider(AiProvider):
    """通过 DeepSeek 官方 API 生成内容；任何异常自动回落 mock。"""

    name = "deepseek"

    def __init__(self) -> None:
        self.cred = _env("DEEPSEEK_API_KEY")
        self.base = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = _env("DEEPSEEK_MODEL", "deepseek-flash")
        self.max_out = _env_int("AI_MAX_TOKENS", 4096)
        self.timeout = _env_int("AI_TIMEOUT_SECONDS", 180)
        self.temp = _env_float("AI_TEMPERATURE", 0.2)
        self.effort = _env("AI_REASONING_EFFORT", "low")
        self.mock = MockAiProvider()

    @property
    def ready(self) -> bool:
        return bool(self.cred)

    def _post(self, body: dict) -> str:
        req = urllib.request.Request(
            self.base + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + self.cred)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = (data.get("choices") or [{}])[0]
        return ((choice.get("message") or {}).get("content") or "").strip()

    def _ask(self, user: str) -> Any:
        if not self.ready:
            return None
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temp,
        }
        body["max_" + "tokens"] = self.max_out
        if self.effort:
            body["reasoning_effort"] = self.effort
        try:
            return _parse_json(self._post(body))
        except Exception:
            return None

    def _run(self, method: str, payload: dict, task: str, schema: str, build: Callable) -> Any:
        data = self._ask(_user(task, schema, payload))
        if data is not None:
            try:
                out = build(data)
            except Exception:
                out = None
            if out:
                return out
        return getattr(self.mock, method)(payload)

    # -- 诊断 -------------------------------------------------------------
    def generate_diagnosis(self, payload: dict) -> dict:
        return self._run(
            "generate_diagnosis", payload,
            "请基于商品、SKU、竞品与经营数据，输出该商品的经营诊断。",
            SCHEMA_DIAGNOSIS, _norm_diagnosis,
        )

    # -- 主图方案 ---------------------------------------------------------
    def generate_main_image_plans(self, payload: dict) -> dict:
        return self._run(
            "generate_main_image_plans", payload,
            "请输出至少 3 个差异化的主图方向，分别解决不同决策障碍。",
            SCHEMA_IMAGE, _norm_image_plans,
        )

    # -- 视频脚本 ---------------------------------------------------------
    def generate_video_scripts(self, payload: dict) -> dict:
        return self._run(
            "generate_video_scripts", payload,
            "请输出至少 3 条短视频脚本，覆盖不同内容形态。",
            SCHEMA_VIDEO, _norm_video_scripts,
        )

    # -- 投放建议 ---------------------------------------------------------
    def generate_ad_recommendation(self, payload: dict) -> dict:
        return self._run(
            "generate_ad_recommendation", payload,
            "请输出投放建议：人群、预算、创意实验、出价策略、风险控制与下一步。"
            "只做建议与实验计划，不涉及自动创建广告计划或自动扣费。",
            SCHEMA_AD, _norm_ad,
        )

    # -- 复盘报告 ---------------------------------------------------------
    def generate_review_report(self, payload: dict) -> dict:
        return self._run(
            "generate_review_report", payload,
            "请基于经营数据生成复盘报告：周期摘要、核心洞察、下一步动作。"
            "摘要必须引用具体指标数值（曝光、点击、成交、花费、成交金额、CTR、转化率、ROI、CPA 等）。",
            SCHEMA_REVIEW, _norm_review,
        )

    # -- 推广链接建议 -----------------------------------------------------
    def generate_promotion_link_suggestions(self, payload: dict) -> list:
        return self._run(
            "generate_promotion_link_suggestions", payload,
            "请输出 4 条推广链接建议，覆盖站内搜索、短视频挂车、私域社群、达人合作等场景。"
            "target_url 必须使用业务数据里的商品链接。",
            SCHEMA_LINKS, _norm_links,
        )

    # -- 库存建议 ---------------------------------------------------------
    def generate_inventory_advice(self, payload: dict) -> dict:
        return self._run(
            "generate_inventory_advice", payload,
            "请逐个 SKU 给出库存判断与处置建议，并给出整体结论。",
            SCHEMA_INVENTORY, _norm_inventory,
        )
