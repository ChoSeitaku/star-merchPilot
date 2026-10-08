"""内置模拟生成实现。

设计要点：
1. **确定性**：所有随机取样都基于 ``random.Random(seed)``，种子由商品 ID 与用途派生，
   因此同一商品重复生成得到稳定结果 —— 便于课程演示、重试复现和自动化测试。
2. **数据驱动**：输出内容会真实引用商品的类目、价格、成本、卖点、SKU 数量、
   竞品价格区间与最近经营数据（CTR / 转化率 / ROI），让演示链路自洽。
3. **可编辑**：输出只是结构化初稿，全部字段均可在页面上人工修改后保存。
"""

from __future__ import annotations

import random
from typing import Any

from .base import AiProvider


def _rng(*parts: Any) -> random.Random:
    """由入参派生稳定随机源。"""
    return random.Random("|".join(str(p) for p in parts))


def _fmt_money(value: float) -> str:
    return f"¥{value:,.2f}"


def _margin_rate(price: float, cost: float) -> float:
    if price <= 0:
        return 0.0
    return (price - cost) / price * 100


class MockAiProvider(AiProvider):
    name = "mock"

    # ------------------------------------------------------------------ 诊断
    def generate_diagnosis(self, payload: dict[str, Any]) -> dict[str, Any]:
        product = payload.get("product", {})
        skus = payload.get("skus", []) or []
        competitors = payload.get("competitors", []) or []
        performance = payload.get("performance", []) or []
        prior_actions = payload.get("prior_actions", []) or []

        name = product.get("name") or "该商品"
        category = product.get("category") or "未分类"
        price = float(product.get("price") or 0)
        cost = float(product.get("cost") or 0)
        audience = product.get("target_audience") or "大众消费人群"
        selling_points = product.get("selling_points") or ""

        margin = _margin_rate(price, cost)
        comp_prices = [float(c.get("price") or 0) for c in competitors if (c.get("price") or 0) > 0]
        comp_low = min(comp_prices) if comp_prices else price * 0.85
        comp_high = max(comp_prices) if comp_prices else price * 1.25
        comp_avg = sum(comp_prices) / len(comp_prices) if comp_prices else price

        if price > comp_avg * 1.1:
            price_position = "高于竞品均价"
        elif price < comp_avg * 0.9:
            price_position = "低于竞品均价"
        else:
            price_position = "与竞品均价基本持平"

        # 经营表现（取最近一条优先）
        latest = performance[0] if performance else {}
        ctr = float(latest.get("ctr") or 0)
        cvr = float(latest.get("conversion_rate") or 0)
        roi = float(latest.get("roi") or 0)
        has_perf = bool(performance)

        sp_list = [s.strip() for s in str(selling_points).replace("，", ",").split(",") if s.strip()]
        sp_text = "、".join(sp_list) if sp_list else "商品核心卖点尚未录入"

        positioning = (
            f"{name}定位为「{category}」类目下的中{'高' if price > comp_avg else '低价位'}商品，"
            f"当前售价 {_fmt_money(price)}（{price_position}，竞品区间 {_fmt_money(comp_low)} ~ {_fmt_money(comp_high)}）。"
            f"目标人群为{audience}。毛利率约 {margin:.1f}%，"
            f"{'具备一定的价格竞争空间' if margin >= 30 else '毛利空间偏紧，需重点关注转化效率而非单纯降价'}。"
        )

        price_band = (
            f"主销价格带位于 {_fmt_money(comp_low)} ~ {_fmt_money(comp_high)} 之间，"
            f"本品 {_fmt_money(price)} 处于该带{'上沿' if price >= comp_avg else '下沿'}。"
            f"建议维持价格锚点不变，通过组合装/赠品方式提升客单价，避免直接价格战侵蚀 {margin:.1f}% 的毛利。"
        )

        audience_insights = (
            f"核心人群：{audience}。决策特征上，该类人群在{category}类目通常先看主图前 3 张判断"
            f"「解决什么问题」，再看评价区验证「是否耐用/是否踩坑」。"
            f"结合竞品表现（在录竞品 {len(competitors)} 个），"
            f"价格敏感度{'较高，促销信息需前置' if price > comp_avg else '中等，可强化品质与保障信息'}。"
        )

        pain_points = (
            "1）决策成本高：同类商品参数繁杂，用户难以快速比较，主图与详情页需要给出明确的对比结论；\n"
            "2）信任门槛：缺少真实使用场景与售后保障展示时，用户倾向转向评价更多的竞品；\n"
            f"3）价格顾虑：竞品区间跨度达 {_fmt_money(comp_high - comp_low)}，用户易陷入比价循环；\n"
            f"4）需求错配：{audience}更关注与自身场景贴合度，泛化卖点说服力不足。"
        )

        selling_point_analysis = (
            f"当前录入卖点：{sp_text}。\n"
            f"其中可优先放大的「第一卖点」建议选择最能降低决策成本的那一条，"
            f"并在主图第 1 张直接呈现场景化结果；次级卖点用于第 3-4 张图做支撑。\n"
            f"现有 SKU 共 {len(skus)} 个，"
            f"{'SKU 梯度较完整，可支撑组合推荐' if len(skus) >= 3 else 'SKU 偏少，建议补充入门款与升级款形成价格梯度'}。"
        )

        risks = (
            f"1）价格风险：{price_position}，若竞品发起降价，需评估 {margin:.1f}% 毛利能否承受；\n"
            f"2）库存风险：{'存在低库存 SKU，断货会直接损失已积累的流量权重' if payload.get('low_stock_count') else '当前库存水位正常，但需持续关注预警阈值'}；\n"
            f"3）素材风险：素材同质化会拉低点击率，需按方案做差异化测试；\n"
            f"4）合规风险：投放与素材描述需与商品实际能力一致，避免夸大宣传。"
        )

        perf_note = (
            f"最近周期 CTR {ctr:.2f}%、转化率 {cvr:.2f}%、ROI {roi:.2f}。"
            if has_perf
            else "尚无经营数据回填，建议先完成一轮投放并回填数据后再评估。"
        )
        recommendations = (
            f"{perf_note}\n"
            f"1）按「主图方案」标签页生成 3 个方向并完成素材测试，优先验证第一卖点假设；\n"
            f"2）补充 {max(0, 3 - len(competitors))} 个竞品记录，使价格与卖点对比更具代表性；\n"
            f"3）对本商品生成视频脚本，用 15 秒短视频承接「痛点—方案—结果」结构；\n"
            f"4）完成投放建议确认后小预算试跑，回填经营数据形成下一轮诊断输入。"
        )

        if prior_actions:
            recommendations += (
                "\n5）上一轮复盘遗留动作：" + "；".join(str(a) for a in prior_actions[:3]) + "。"
            )

        summary_text = (
            f"{name}｜{category}｜{_fmt_money(price)}｜{price_position}"
            f"｜竞品 {len(competitors)} 个｜毛利率 {margin:.1f}%"
        )

        return {
            "positioning": positioning,
            "price_band": price_band,
            "audience_insights": audience_insights,
            "pain_points": pain_points,
            "selling_point_analysis": selling_point_analysis,
            "risks": risks,
            "recommendations": recommendations,
            "summary_text": summary_text,
        }

    # -------------------------------------------------------------- 主图方案
    def generate_main_image_plans(self, payload: dict[str, Any]) -> dict[str, Any]:
        product = payload.get("product", {})
        competitors = payload.get("competitors", []) or []
        name = product.get("name") or "商品"
        category = product.get("category") or "该类目"
        audience = product.get("target_audience") or "目标人群"
        price = float(product.get("price") or 0)
        selling_points = [
            s.strip()
            for s in str(product.get("selling_points") or "").replace("，", ",").split(",")
            if s.strip()
        ]
        if not selling_points:
            selling_points = ["核心功能", "品质保障", "售后无忧"]

        sp1 = selling_points[0]
        sp2 = selling_points[1] if len(selling_points) > 1 else "品质保障"
        sp3 = selling_points[2] if len(selling_points) > 2 else "售后无忧"

        directions = [
            {
                "direction_title": "方向一：场景痛点直击型",
                "visual_structure": (
                    "第 1 张：左侧「痛点场景」实拍（用户使用前的困扰状态），右侧产品主体大图，"
                    "顶部 8 字以内痛点文案压条；\n"
                    "第 2 张：使用过程拆解 3 宫格，标注关键动作；\n"
                    "第 3 张：效果对比（使用前 / 使用后）左右分屏；\n"
                    "第 4 张：核心参数与规格表；\n"
                    "第 5 张：售后与保障信息（质保、运费险、7 天无理由）。"
                ),
                "core_copy": f"还在为{category}踩坑？{sp1}，一次选对",
                "highlight_selling_point": sp1,
                "rationale": (
                    f"{audience}在该类目的首要决策障碍是「怕买错」。"
                    "把痛点前置能显著提升首图点击率，并用对比图快速建立说服力。"
                ),
            },
            {
                "direction_title": "方向二：卖点堆叠利益型",
                "visual_structure": (
                    "第 1 张：产品居中，四周环绕 3 个卖点气泡，主标题强调第一利益点；\n"
                    "第 2 张：卖点逐条拆解（每屏一个卖点 + 图标 + 一句话说明）；\n"
                    "第 3 张：材质/工艺特写微距图，配参数标注；\n"
                    "第 4 张：与常见竞品差异对比表；\n"
                    "第 5 张：组合购买 / 赠品信息与价格锚点。"
                ),
                "core_copy": f"{sp1} · {sp2} · {sp3}",
                "highlight_selling_point": sp2,
                "rationale": (
                    f"本品售价 {_fmt_money(price)}，"
                    f"同价位竞品在录 {len(competitors)} 个，需用卖点密度拉开差异，"
                    "适合以理性比较为主的用户。"
                ),
            },
            {
                "direction_title": "方向三：人群场景代入型",
                "visual_structure": (
                    "第 1 张：真实人群使用场景大图，人物视线指向产品，文案落在使用收益上；\n"
                    "第 2 张：三种典型使用场景九宫格；\n"
                    "第 3 张：用户证言截图（评价/返图）拼版；\n"
                    "第 4 张：产品细节与尺寸示意；\n"
                    "第 5 张：限时权益与下单引导。"
                ),
                "core_copy": f"为{audience}准备的{name}，用起来才知道好在哪",
                "highlight_selling_point": sp3,
                "rationale": (
                    f"面向{audience}的场景化表达更容易触发「这就是为我准备的」感觉，"
                    "配合证言素材可降低信任门槛，适合作为长期主图沉淀。"
                ),
            },
        ]

        return {
            "title": f"{name} 主图方案（3 个方向）",
            "rationale_text": (
                f"围绕「{sp1}」这一核心卖点，输出 3 个差异化方向："
                "方向一解决决策速度，方向二解决理性比较，方向三解决人群代入。"
                "建议先各出 1 张首图做 A/B 测试，用点击率决定主推方向。"
            ),
            "directions": directions,
        }

    # -------------------------------------------------------------- 视频脚本
    def generate_video_scripts(self, payload: dict[str, Any]) -> dict[str, Any]:
        product = payload.get("product", {})
        name = product.get("name") or "商品"
        category = product.get("category") or "该类目"
        audience = product.get("target_audience") or "目标人群"
        price = float(product.get("price") or 0)
        selling_points = [
            s.strip()
            for s in str(product.get("selling_points") or "").replace("，", ",").split(",")
            if s.strip()
        ] or ["核心功能", "品质保障", "售后无忧"]

        sp1 = selling_points[0]
        sp2 = selling_points[1] if len(selling_points) > 1 else "品质保障"

        scripts = [
            {
                "script_title": "脚本一：痛点开场 15 秒转化型",
                "hook": f"别急着买{category}，先看这 3 秒。",
                "storyboard": (
                    "0-3s：手持镜头拍用户皱眉看着旧物件的特写，画面压字幕「又踩坑了？」；\n"
                    "3-7s：快速转场切产品上手，展示核心动作，特写关键部位；\n"
                    "7-11s：分屏对比使用前后，弹出卖点字幕；\n"
                    "11-15s：产品摆拍定格 + 价格与权益信息，引导点击下方链接。"
                ),
                "voiceover": (
                    f"很多人买{category}都吃过亏。这款{name}，{sp1}，"
                    f"上手就能感觉到差别。{_fmt_money(price)}，先领券再下单更划算。"
                ),
                "conversion_cta": "点击下方链接领券下单，7 天无理由退换。",
            },
            {
                "script_title": "脚本二：真实测评 30 秒信任型",
                "hook": "自己花钱买的，说点实在的。",
                "storyboard": (
                    "0-4s：桌面平铺产品与配件，口播开场；\n"
                    "4-12s：逐项验证卖点，镜头贴近细节，穿插尺子/秤等客观工具；\n"
                    "12-22s：模拟日常使用场景连续操作，展示稳定性；\n"
                    "22-27s：总结优缺点，明确适合人群；\n"
                    "27-30s：价格对比与购买建议，引导收藏。"
                ),
                "voiceover": (
                    f"这是我自用的{name}。优点很明确：{sp1}，{sp2}。"
                    f"缺点也说清楚，它更适合{audience}。"
                    f"同价位里 {_fmt_money(price)} 这个配置算实在。"
                ),
                "conversion_cta": "觉得有用先点收藏，需要的时候直接下单。",
            },
            {
                "script_title": "脚本三：场景种草 20 秒情绪型",
                "hook": f"如果你也是{audience}，这条一定要看完。",
                "storyboard": (
                    "0-5s：生活化空镜（晨光、桌面、通勤）过渡到产品出现；\n"
                    "5-12s：第一视角记录使用全过程，无口播，仅环境音 + 字幕；\n"
                    "12-17s：特写产品质感与细节，慢镜头；\n"
                    "17-20s：定格文案「把小事交给它」，附商品卡片。"
                ),
                "voiceover": (
                    f"（前段无口播，仅字幕）{audience}的日常，其实可以更省心。"
                    f"{name}，{sp1}。"
                ),
                "conversion_cta": "主页橱窗有同款，点进去看看。",
            },
        ]

        return {
            "title": f"{name} 视频脚本（3 条）",
            "rationale_text": (
                "三条脚本分别覆盖「痛点转化」「真实测评」「场景种草」三类主流内容形态："
                "第一条用于投放跑量，第二条用于沉淀信任，第三条用于自然流量种草。"
                "建议先拍第一条做投放测试，用 3 秒完播率判断钩子是否有效。"
            ),
            "scripts": scripts,
        }

    # -------------------------------------------------------------- 投放建议
    def generate_ad_recommendation(self, payload: dict[str, Any]) -> dict[str, Any]:
        product = payload.get("product", {})
        performance = payload.get("performance", []) or []
        competitors = payload.get("competitors", []) or []
        assets = payload.get("assets", []) or []
        links = payload.get("links", []) or []

        name = product.get("name") or "商品"
        category = product.get("category") or "该类目"
        audience = product.get("target_audience") or "目标人群"
        price = float(product.get("price") or 0)
        cost = float(product.get("cost") or 0)
        margin = _margin_rate(price, cost)

        latest = performance[0] if performance else {}
        hist_ctr = float(latest.get("ctr") or 0)
        hist_cvr = float(latest.get("conversion_rate") or 0)
        hist_roi = float(latest.get("roi") or 0)

        # 出价建议：按毛利反推可承受 CPA
        target_cpa = max(price * 0.15, price - cost - price * 0.1) if price > 0 else 20.0
        target_cpa = round(min(target_cpa, price * 0.5), 2) if price > 0 else 20.0
        daily_budget = round(max(100.0, price * 3), 2)

        summary_text = (
            f"本轮围绕「{name}」做小预算验证：以 {_fmt_money(daily_budget)}/天 起步，"
            f"目标 CPA 控制在 {_fmt_money(target_cpa)} 以内，"
            f"优先验证主图方向与视频钩子，用 3-5 天数据决定是否放量。"
        )

        objective_text = (
            f"本轮目标：{'以转化成本为核心，验证素材点击效率' if not performance else '在已有数据基础上优化转化效率'}。"
            f"核心指标：点击率 ≥ {max(hist_ctr, 2.5):.2f}%、"
            f"转化率 ≥ {max(hist_cvr, 1.5):.2f}%、"
            f"ROI ≥ {max(hist_roi, 1.5):.2f}。"
            f"毛利率 {margin:.1f}%，因此 ROI 低于 1.5 需立即收缩预算。"
        )

        audience_segments = [
            {
                "segment_name": "核心人群：高意向搜索人群",
                "description": f"近期搜索过「{category}」相关词、有明确购买意图的{audience}",
                "priority": "高",
                "reason": "意图明确、转化率通常最高，适合作为冷启动首选人群包",
            },
            {
                "segment_name": "拓展人群：类目行为人群",
                "description": f"近 30 天浏览/加购过同类{category}但未成交的人群",
                "priority": "中",
                "reason": "已有类目认知，用差异化卖点承接可争夺竞品流量",
            },
            {
                "segment_name": "拉新人群：相似商品人群",
                "description": f"与本品目标人群画像相似、但尚未触达的{audience}",
                "priority": "中",
                "reason": "用于扩大池子，需配合更有冲击力的素材",
            },
            {
                "segment_name": "排除人群",
                "description": "近 7 天已成交用户、以及明显低价薅羊毛人群",
                "priority": "—",
                "reason": "避免重复触达浪费预算、保护毛利",
            },
        ]

        budget_plan = {
            "daily_budget": daily_budget,
            "total_budget": round(daily_budget * 5, 2),
            "duration_days": 5,
            "phase_plan": [
                {"phase": "第 1-2 天 冷启动", "budget": round(daily_budget * 0.4, 2), "focus": "多素材小额跑量，测出点击率最高的方向"},
                {"phase": "第 3-4 天 择优放量", "budget": round(daily_budget * 0.35, 2), "focus": "预算向优胜素材与人群倾斜"},
                {"phase": "第 5 天 复盘决策", "budget": round(daily_budget * 0.25, 2), "focus": "验证 ROI 是否达标，决定放量或止损"},
            ],
            "target_cpa": target_cpa,
            "note": "以上为建议值，需人工确认后执行；系统不会自动调整平台预算。",
        }

        asset_names = [a.get("asset_url") or a.get("usage_scene") or f"素材{a.get('id')}" for a in assets[:4]]
        creative_tests = [
            {
                "test_name": f"主图方向测试 {i + 1}",
                "test_content": asset_names[i] if i < len(asset_names) else f"待生成的第 {i + 1} 组素材",
                "hypothesis": h,
                "success_metric": "点击率",
            }
            for i, h in enumerate(
                [
                    "痛点前置的首图点击率高于卖点堆叠型",
                    "人群场景代入型对转化率贡献更高",
                    "视频钩子「别急着买」比「自用测评」的完播率更高",
                ]
            )
        ]
        if links:
            creative_tests.append(
                {
                    "test_name": "落地链接对比",
                    "test_content": f"对比 {len(links)} 条推广链接的点击与转化差异",
                    "hypothesis": "带场景参数的链接转化优于裸链",
                    "success_metric": "转化率",
                }
            )

        bid_strategy = {
            "mode": "手动出价（建议）",
            "initial_bid": round(max(1.0, target_cpa * 0.6), 2),
            "bid_ceiling": round(target_cpa * 1.2, 2),
            "adjust_rule": "每 24 小时根据 CPA 表现调整一次，单次调整幅度不超过 15%",
            "note": "禁止使用自动放量策略；所有出价调整需人工在平台侧手动执行。",
        }

        risk_controls = [
            "设置单日预算上限，避免超投",
            "ROI 连续 2 天低于 1.5 时暂停投放并复盘",
            "素材需通过人工审核后才可用于投放，避免违规描述",
            f"监控竞品价格（在录 {len(competitors)} 个），竞品大幅降价时重新评估出价",
            "只做建议与实验计划，不自动创建广告计划、不自动扣费",
        ]

        next_steps = [
            "确认本建议后，按预算计划在平台侧手动创建计划",
            "先跑主图方向测试，24 小时后回填经营数据",
            "按复盘报告结论调整下一轮素材与人群",
        ]

        return {
            "summary_text": summary_text,
            "objective_text": objective_text,
            "audience_segments": audience_segments,
            "budget_plan": budget_plan,
            "creative_tests": creative_tests,
            "bid_strategy": bid_strategy,
            "risk_controls": risk_controls,
            "next_steps": next_steps,
        }

    # -------------------------------------------------------------- 复盘报告
    def generate_review_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        product = payload.get("product", {})
        records = payload.get("performance", []) or []
        diagnosis = payload.get("diagnosis") or {}
        plans = payload.get("plans", []) or []

        name = product.get("name") or "商品"
        period_start = payload.get("period_start") or ""
        period_end = payload.get("period_end") or ""

        if records:
            impressions = sum(int(r.get("impressions") or 0) for r in records)
            clicks = sum(int(r.get("clicks") or 0) for r in records)
            conversions = sum(int(r.get("conversions") or 0) for r in records)
            spend = sum(float(r.get("spend") or 0) for r in records)
            revenue = sum(float(r.get("revenue") or 0) for r in records)
            rows = len(records)
        else:
            impressions = clicks = conversions = rows = 0
            spend = revenue = 0.0

        ctr = (clicks / impressions * 100) if impressions else 0.0
        cvr = (conversions / clicks * 100) if clicks else 0.0
        roi = (revenue / spend) if spend else 0.0
        cpa = (spend / conversions) if conversions else 0.0

        if roi >= 2.5:
            verdict, verdict_action = "表现优秀", "可进入放量阶段，同时扩大人群池"
        elif roi >= 1.5:
            verdict, verdict_action = "表现达标", "维持预算并优化素材点击效率"
        elif roi > 0:
            verdict, verdict_action = "表现偏弱", "先收缩预算，重点修复转化环节"
        else:
            verdict, verdict_action = "数据不足", "先完成一轮小预算投放并回填经营数据"

        summary_text = (
            f"复盘周期 {period_start} ~ {period_end}，共回填 {rows} 条经营数据。"
            f"曝光 {impressions:,}、点击 {clicks:,}、成交 {conversions:,}；"
            f"花费 {_fmt_money(spend)}、成交金额 {_fmt_money(revenue)}。"
            f"CTR {ctr:.2f}%、转化率 {cvr:.2f}%、ROI {roi:.2f}、"
            f"单次成交成本 {_fmt_money(cpa) if cpa else '—'}。"
            f"整体结论：{verdict}。"
        )

        insights: list[dict[str, Any]] = []
        insights.append(
            {
                "insight_title": "流量效率",
                "insight_detail": (
                    f"点击率 {ctr:.2f}%"
                    f"{'高于' if ctr >= 2.5 else '低于'}类目常见水平（约 2.5%），"
                    f"说明{'主图与标题的吸引力已经成立' if ctr >= 2.5 else '首图吸引力不足，是当前最主要的优化点'}。"
                ),
                "impact": "高" if ctr < 2.5 else "中",
            }
        )
        insights.append(
            {
                "insight_title": "转化效率",
                "insight_detail": (
                    f"转化率 {cvr:.2f}%"
                    f"{'，处于健康区间' if cvr >= 1.5 else '，偏低，需检查详情页卖点表达、价格竞争力与评价区'}。"
                    f"{'竞品价格对比显示本品定价合理，可从信任要素入手' if product.get('price') else ''}"
                ),
                "impact": "高" if 0 < cvr < 1.5 else "中",
            }
        )
        insights.append(
            {
                "insight_title": "投入产出",
                "insight_detail": (
                    f"ROI {roi:.2f}，{'已具备放量条件' if roi >= 2.0 else '尚未达到健康水平（建议 ≥ 2.0）'}。"
                    f"{'建议按 20% 幅度逐步加预算' if roi >= 2.0 else '建议保持小预算，优先提升转化率再考虑放量'}。"
                ),
                "impact": "高",
            }
        )
        if diagnosis:
            insights.append(
                {
                    "insight_title": "与诊断结论的对照",
                    "insight_detail": (
                        f"本轮诊断结论为「{(diagnosis.get('positioning') or '')[:60]}…」，"
                        f"实际数据{'印证' if roi >= 1.5 else '尚未印证'}了该判断，"
                        f"下一轮应重点验证诊断中列出的主要风险项。"
                    ),
                    "impact": "中",
                }
            )
        if plans:
            insights.append(
                {
                    "insight_title": "素材版本对比",
                    "insight_detail": (
                        f"本周期共使用 {len(plans)} 个方案版本（含选中与归档方向）。"
                        "建议在下一轮保留点击率最高的方向作为基准，其余方向作为对照持续测试。"
                    ),
                    "impact": "中",
                }
            )

        next_actions = [
            {
                "action_title": "重跑商品诊断",
                "action_detail": (
                    f"将本轮复盘结论作为输入重新生成「{name}」的诊断，"
                    "更新价格带分析与风险点，形成下一轮优化基线。"
                ),
                "owner": "运营人员",
                "priority": "高",
            },
            {
                "action_title": "补充或替换主图素材",
                "action_detail": (
                    f"针对点击率 {ctr:.2f}% 的现状，"
                    f"{'保持现有方向并做微调' if ctr >= 2.5 else '重新生成 3 个方向主图并完成 A/B 测试'}。"
                ),
                "owner": "运营人员",
                "priority": "高" if ctr < 2.5 else "中",
            },
            {
                "action_title": verdict_action,
                "action_detail": f"依据 ROI {roi:.2f} 与 CPA {_fmt_money(cpa) if cpa else '—'} 调整下一轮预算计划。",
                "owner": "运营人员",
                "priority": "高",
            },
            {
                "action_title": "回填下一周期经营数据",
                "action_detail": "按周回填曝光、点击、成交、花费与成交金额，保证复盘结论可比较。",
                "owner": "运营人员",
                "priority": "中",
            },
        ]

        return {
            "summary_text": summary_text,
            "insights": insights,
            "next_actions": next_actions,
        }

    # ---------------------------------------------------------- 推广链接建议
    def generate_promotion_link_suggestions(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        product = payload.get("product", {})
        name = product.get("name") or "商品"
        category = product.get("category") or "该类目"
        target_url = product.get("product_url") or "https://example.com/item"

        scenes = [
            ("站内搜索承接", "承接类目搜索流量，强调核心卖点与价格优势"),
            ("短视频挂车", "配合视频脚本使用，落地页突出同款与权益"),
            ("私域社群", "用于社群与朋友圈分发，突出限时权益"),
            ("达人合作", "提供给合作达人使用，便于区分不同渠道效果"),
        ]
        suggestions = []
        for idx, (scene, desc) in enumerate(scenes, start=1):
            suggestions.append(
                {
                    "link_name": f"{name}-{scene}",
                    "scene_text": desc,
                    "target_url": target_url,
                    "utm": {
                        "utm_source": "merchpilot",
                        "utm_medium": "link",
                        "utm_campaign": f"p{product.get('id') or 0}",
                        "utm_content": f"scene{idx}",
                        "utm_term": category,
                    },
                }
            )
        return suggestions

    # -------------------------------------------------------------- 库存建议
    def generate_inventory_advice(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = payload.get("items", []) or []
        store_name = payload.get("store_name") or "店铺"

        advice_items = []
        low_count = 0
        overstock_count = 0
        for it in items:
            stock = int(it.get("stock_qty") or 0)
            threshold = int(it.get("warning_threshold") or 10)
            if stock <= threshold:
                low_count += 1
                action = "建议尽快补货"
            elif stock > threshold * 8:
                overstock_count += 1
                action = "库存偏高，建议控制补货节奏或做促销去化"
            else:
                action = "库存水位正常"
            advice_items.append(
                {
                    "sku_code": it.get("sku_code") or "",
                    "sku_name": it.get("sku_name") or "",
                    "stock_qty": stock,
                    "warning_threshold": threshold,
                    "advice": (
                        f"当前库存 {stock}，预警阈值 {threshold}，{action}。"
                        if stock <= threshold
                        else f"当前库存 {stock}，高于预警阈值 {threshold}，{action}。"
                    ),
                    "suggested_action": action,
                }
            )

        advice_items.sort(key=lambda x: x["stock_qty"])

        summary_text = (
            f"{store_name} 共 {len(items)} 个 SKU，其中 {low_count} 个低于预警阈值、"
            f"{overstock_count} 个库存偏高。"
            + ("建议优先处理低库存 SKU，避免断货影响流量权重。" if low_count else "整体库存结构健康，保持现有补货节奏即可。")
        )

        return {"summary_text": summary_text, "items": advice_items}
