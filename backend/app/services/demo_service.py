"""演示数据生成：一次性铺满整条单品运营闭环。

覆盖规格 1.5.11 要求的全部数据类型：
店铺、平台账号占位、商品、SKU、库存、竞品、主图方案、视频脚本、素材、
推广链接、投放建议、投放实验、经营数据、复盘报告。

在单个事务中完成，任意一步失败都会整体回滚，避免留下半套演示数据。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import (
    AdExperiment,
    AdRecommendation,
    Competitor,
    CompetitorMonitor,
    CreativePlan,
    GeneratedAsset,
    InventoryItem,
    InventoryMovement,
    PerformanceRecord,
    PlatformAccount,
    PlatformProductMapping,
    Product,
    ProductDiagnosis,
    ProductSku,
    PromotionLink,
    ReviewReport,
    Store,
)
from ..providers import get_ai_provider
from . import asset_service, context_service, link_service

DEMO_TAG = "[演示数据]"


def _demo_exists(db: Session, marker: str) -> bool:
    return (
        db.scalar(select(Store.id).where(Store.remark.like(f"%{marker}%"))) is not None
    )


def create_demo_data(db: Session, *, force: bool = False) -> dict[str, Any]:
    """创建完整演示数据。重复调用会跳过（除非 force=True）。"""
    marker = DEMO_TAG
    if _demo_exists(db, marker) and not force:
        existing_store = db.scalar(select(Store).where(Store.remark.like(f"%{marker}%")))
        return {
            "created": False,
            "message": "演示数据已存在，未重复创建（如需重建请传入 force=true 或先清理数据）",
            "store_id": existing_store.id if existing_store else None,
            "hint": "演示数据可在店铺/商品列表中按备注「[演示数据]」快速识别",
        }

    counts: dict[str, int] = {}
    provider = get_ai_provider()
    today = date.today()

    # ------------------------------------------------------------- 1. 店铺
    store = Store(
        store_name="星航优选旗舰店",
        platform="taobao",
        external_store_id="TB-STAR-0001",
        owner_name="演示运营员",
        remark=f"{marker} 用于课程演示与验收的完整闭环样例",
    )
    db.add(store)
    db.flush()
    counts["stores"] = 1

    # ------------------------------------------------------- 2. 平台账号占位
    account = PlatformAccount(
        store_id=store.id,
        platform="taobao",
        account_name="星航优选-主账号",
        auth_status="authorized",
        auth_meta_json={
            "scope": "item_read,order_read",
            "authorize_url": "https://example.com/oauth/authorize?client_id=mock-demo",
            "auth_code_masked": "demo****code",
            "authorized_at": utcnow().isoformat(),
            "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
            "credential_policy": "仅保存安全元数据，不保存明文密码 / 令牌 / Cookie",
        },
        remark="演示用授权占位，不含任何真实凭据",
    )
    db.add(account)
    counts["platform_accounts"] = 1

    # --------------------------------------------------------------- 3. 商品
    product = Product(
        store_id=store.id,
        name="轻量通勤双肩包 15.6 寸电脑仓",
        platform="taobao",
        category="箱包/双肩包",
        price=199.0,
        cost=86.0,
        target_audience="22-35 岁城市通勤上班族，日常需携带笔记本电脑",
        selling_points="仅480g轻量,防泼水面料,15.6寸独立电脑仓,防盗背部口袋",
        product_url="https://item.taobao.com/item.htm?id=100001",
        images_json=[],
        status="active",
    )
    db.add(product)
    db.flush()
    counts["products"] = 1

    # ------------------------------------------------------------- 4. 平台映射
    db.add(
        PlatformProductMapping(
            product_id=product.id,
            platform="taobao",
            platform_product_id="678901234567",
            platform_sku_id="SKU-DEMO-001",
            mapping_status="mapped",
            raw_payload_json={"source": "demo", "shop_id": "TB-STAR-0001"},
        )
    )
    counts["platform_product_mappings"] = 1

    # -------------------------------------------------------- 5. SKU 与库存
    sku_specs = [
        ("BAG-BLK-STD", "黑色标准款", {"颜色": "黑色", "尺寸": "标准"}, 199.0, 86.0, 12, 15, "A区-01-03"),
        ("BAG-GRY-STD", "灰色标准款", {"颜色": "灰色", "尺寸": "标准"}, 199.0, 86.0, 186, 20, "A区-01-04"),
        ("BAG-BLK-PRO", "黑色升级款", {"颜色": "黑色", "尺寸": "加大"}, 239.0, 102.0, 64, 15, "A区-02-01"),
    ]
    skus: list[ProductSku] = []
    for code, name, spec, price, cost, stock, threshold, location in sku_specs:
        sku = ProductSku(
            product_id=product.id,
            sku_code=code,
            sku_name=name,
            spec_json=spec,
            price=price,
            cost=cost,
            status="active",
            platform_sku_id=f"TB-{code}",
        )
        db.add(sku)
        db.flush()
        db.add(
            InventoryItem(
                sku_id=sku.id,
                stock_qty=stock,
                locked_qty=0,
                warning_threshold=threshold,
                location_text=location,
            )
        )
        db.add(
            InventoryMovement(
                sku_id=sku.id,
                movement_type="init",
                change_qty=stock,
                before_qty=0,
                after_qty=stock,
                reason_text="演示数据期初库存",
                reference_type="demo_data",
                reference_id=None,
            )
        )
        skus.append(sku)
    counts["product_skus"] = len(skus)
    counts["inventory_items"] = len(skus)
    counts["inventory_movements"] = len(skus)

    # 追加一条真实的销售出库流水，让库存流水页有变化可看
    first = skus[0]
    inv = first.inventory
    before = inv.stock_qty
    inv.stock_qty = before - 3
    db.add(
        InventoryMovement(
            sku_id=first.id,
            movement_type="sale",
            change_qty=-3,
            before_qty=before,
            after_qty=inv.stock_qty,
            reason_text="演示数据：演示期订单出库",
            reference_type="demo_data",
            reference_id=None,
        )
    )
    counts["inventory_movements"] += 1

    # --------------------------------------------------------------- 6. 竞品
    competitor_specs = [
        ("竞品A 轻商务双肩包", "taobao", 189.0, "月销 3200+", "轻商务,大容量,可放16寸", "轻便,做工好,拉链顺滑"),
        ("竞品B 通勤电脑包", "jd", 219.0, "月销 1800+", "防泼水,减压肩带,多隔层", "容量大,背负舒适,发货快"),
        ("竞品C 极简双肩包", "pdd", 129.0, "月销 8600+", "极致低价,基础款,多色可选", "便宜,轻,材质一般"),
    ]
    competitors: list[Competitor] = []
    for name, platform, price, sales, points, keywords in competitor_specs:
        competitor = Competitor(
            product_id=product.id,
            name=name,
            platform=platform,
            url=f"https://example.com/item/{abs(hash(name)) % 10**9}",
            price=price,
            sales_hint=sales,
            title=name,
            main_image="",
            selling_points=points,
            review_keywords=keywords,
        )
        db.add(competitor)
        competitors.append(competitor)
    db.flush()
    counts["competitors"] = len(competitors)

    # 为第一个竞品建立监控并产生一条快照
    monitor = CompetitorMonitor(
        competitor_id=competitors[0].id,
        monitor_status="active",
        interval_minutes=60,
        next_run_at=utcnow() + timedelta(minutes=60),
    )
    db.add(monitor)
    db.flush()
    from . import monitor_service

    monitor_service.take_snapshot(db, monitor, run_seq=1)
    counts["competitor_monitors"] = 1
    counts["competitor_monitor_snapshots"] = 1

    # -------------------------------------------------------------- 7. 诊断
    diagnosis_input = context_service.diagnosis_input(db, product)
    diagnosis_output = provider.generate_diagnosis(diagnosis_input)
    diagnosis = ProductDiagnosis(
        product_id=product.id,
        source_type="ai_mock",
        summary_text=diagnosis_output.get("summary_text", ""),
        positioning=diagnosis_output.get("positioning", ""),
        price_band=diagnosis_output.get("price_band", ""),
        audience_insights=diagnosis_output.get("audience_insights", ""),
        pain_points=diagnosis_output.get("pain_points", ""),
        selling_point_analysis=diagnosis_output.get("selling_point_analysis", ""),
        risks=diagnosis_output.get("risks", ""),
        recommendations=diagnosis_output.get("recommendations", ""),
        raw_output={"provider": provider.name, "generated_at": utcnow().isoformat(), "source": "demo_data"},
    )
    db.add(diagnosis)
    counts["product_diagnoses"] = 1

    # -------------------------------------------------- 8. 主图方案 / 视频脚本
    creative_input = context_service.creative_input(db, product)

    image_output = provider.generate_main_image_plans(creative_input)
    image_plan = CreativePlan(
        product_id=product.id,
        plan_type="main_image",
        title=image_output.get("title", f"{product.name} 主图方案"),
        content_json={
            "directions": image_output.get("directions", []),
            "provider": provider.name,
            "source": "demo_data",
        },
        rationale_text=image_output.get("rationale_text", ""),
        status="selected",
    )
    db.add(image_plan)

    video_output = provider.generate_video_scripts(creative_input)
    video_plan = CreativePlan(
        product_id=product.id,
        plan_type="video_script",
        title=video_output.get("title", f"{product.name} 视频脚本"),
        content_json={
            "scripts": video_output.get("scripts", []),
            "provider": provider.name,
            "source": "demo_data",
        },
        rationale_text=video_output.get("rationale_text", ""),
        status="selected",
    )
    db.add(video_plan)
    db.flush()
    counts["creative_plans"] = 2

    # --------------------------------------------------------------- 9. 素材
    assets: list[GeneratedAsset] = []
    directions = image_output.get("directions", [])
    for idx, direction in enumerate(directions[:3]):
        svg = asset_service.render_image_svg(
            product_name=product.name,
            direction_title=direction.get("direction_title", f"方向 {idx + 1}"),
            core_copy=direction.get("core_copy", product.name),
            highlight=direction.get("highlight_selling_point", "核心卖点"),
            scene="主图",
            version_no=1,
        )
        filename = f"image_d{idx}_v1.svg"
        _, url = asset_service.write_asset_file(0, filename, svg)
        asset = GeneratedAsset(
            product_id=product.id,
            creative_plan_id=image_plan.id,
            asset_type="image",
            asset_url=url,
            file_path=filename,
            model_name="mock-image-gen-v1",
            width=800,
            height=800,
            duration_sec=None,
            review_status="approved" if idx == 0 else "pending",
            version_no=1,
            usage_scene="主图",
            score=4.5 if idx == 0 else None,
            tags_json=[direction.get("direction_title", ""), "演示数据"],
            remark="演示数据：已审核通过的主图素材" if idx == 0 else "演示数据：待审核素材",
        )
        db.add(asset)
        assets.append(asset)

    scripts = video_output.get("scripts", [])
    for idx, script in enumerate(scripts[:2]):
        duration = 15.0 + idx * 5
        svg = asset_service.render_video_svg(
            product_name=product.name,
            script_title=script.get("script_title", f"脚本 {idx + 1}"),
            hook=script.get("hook", product.name),
            cta=script.get("conversion_cta", "点击下单"),
            duration_sec=duration,
            scene="短视频",
            version_no=1,
        )
        filename = f"video_s{idx}_v1.svg"
        _, url = asset_service.write_asset_file(0, filename, svg)
        asset = GeneratedAsset(
            product_id=product.id,
            creative_plan_id=video_plan.id,
            asset_type="video",
            asset_url=url,
            file_path=filename,
            model_name="mock-video-gen-v1",
            width=720,
            height=1280,
            duration_sec=duration,
            review_status="approved" if idx == 0 else "pending",
            version_no=1,
            usage_scene="短视频",
            score=4.0 if idx == 0 else None,
            tags_json=[script.get("script_title", ""), "演示数据"],
            remark="演示数据：视频海报帧",
        )
        db.add(asset)
        assets.append(asset)
    db.flush()
    counts["generated_assets"] = len(assets)

    # ----------------------------------------------------------- 10. 推广链接
    suggestions = provider.generate_promotion_link_suggestions(
        {"product": context_service.product_payload(db, product)}
    )
    links: list[PromotionLink] = []
    for idx, item in enumerate(suggestions[:2]):
        link = PromotionLink(
            product_id=product.id,
            link_name=item["link_name"],
            target_url=item["target_url"],
            tracking_code=link_service.generate_tracking_code(db),
            utm_json=item.get("utm", {}),
            status="active",
            click_count=12 if idx == 0 else 5,
            scene_text=item.get("scene_text", ""),
        )
        db.add(link)
        links.append(link)
    db.flush()
    counts["promotion_links"] = len(links)

    # 补几条点击记录，让点击统计页有数据
    from ..models import PromotionLinkClick

    for link in links:
        for i in range(3):
            db.add(
                PromotionLinkClick(
                    promotion_link_id=link.id,
                    clicked_at=utcnow() - timedelta(hours=i * 6 + 1),
                    client_ip=f"203.0.113.{10 + i}",
                    user_agent="Mozilla/5.0 (演示数据) DemoAgent/1.0",
                )
            )
    counts["promotion_link_clicks"] = len(links) * 3

    # ----------------------------------------------------------- 11. 投放建议
    ad_input = context_service.ad_input(db, product)
    ad_output = provider.generate_ad_recommendation(ad_input)
    recommendation = AdRecommendation(
        product_id=product.id,
        summary_text=ad_output.get("summary_text", ""),
        objective_text=ad_output.get("objective_text", ""),
        audience_segments_json=ad_output.get("audience_segments"),
        budget_plan_json=ad_output.get("budget_plan"),
        creative_tests_json=ad_output.get("creative_tests"),
        bid_strategy_json=ad_output.get("bid_strategy"),
        risk_controls_json=ad_output.get("risk_controls"),
        next_steps_json=ad_output.get("next_steps"),
        confirm_status="confirmed",
        confirmed_by=None,
        confirmed_at=utcnow() - timedelta(days=6),
        confirm_remark="演示数据：已由运营负责人确认，预算与出价将在平台侧手动执行",
    )
    db.add(recommendation)
    db.flush()
    counts["ad_recommendations"] = 1

    # ----------------------------------------------------------- 12. 投放实验
    budget_plan = ad_output.get("budget_plan") or {}
    experiment = AdExperiment(
        product_id=product.id,
        related_asset_id=assets[0].id if assets else None,
        related_link_id=links[0].id if links else None,
        experiment_name="主图方向一 vs 方向二 点击率对比实验",
        target_text=ad_output.get("objective_text", "验证主图点击效率，控制 CPA"),
        audience_text="高意向搜索人群",
        budget_amount=float(budget_plan.get("daily_budget") or 300.0),
        success_metric_text="点击率 ≥ 2.5% 且 ROI ≥ 1.5",
        hypothesis_text="痛点前置的首图点击率高于卖点堆叠型",
        experiment_status="finished",
    )
    db.add(experiment)
    db.flush()
    counts["ad_experiments"] = 1

    # ----------------------------------------------------------- 13. 经营数据
    # 4 周数据，形成可复盘的走势（第 1 周偏弱，逐步优化）
    weekly = [
        (7, 68000, 1420, 19, 980.0, 3781.0, "首周投放，主图方向一上线，点击率偏低"),
        (6, 92000, 2380, 39, 1360.0, 7761.0, "更换主图后点击率提升，转化同步改善"),
        (5, 118000, 3420, 64, 1720.0, 12736.0, "视频素材上线，完播率带动转化"),
        (4, 135000, 4180, 86, 1980.0, 17114.0, "稳定期，ROI 达到可放量水平"),
    ]
    records: list[PerformanceRecord] = []
    for weeks_ago, impressions, clicks, conversions, spend, revenue, note in weekly:
        period_end = today - timedelta(days=weeks_ago)
        period_start = period_end - timedelta(days=6)
        record = PerformanceRecord(
            product_id=product.id,
            creative_plan_id=image_plan.id,
            generated_asset_id=assets[0].id if assets else None,
            promotion_link_id=links[0].id if links else None,
            experiment_id=experiment.id,
            period_start=period_start,
            period_end=period_end,
            impressions=impressions,
            clicks=clicks,
            ctr=round(clicks / impressions * 100, 4),
            conversions=conversions,
            conversion_rate=round(conversions / clicks * 100, 4),
            spend=spend,
            revenue=revenue,
            roi=round(revenue / spend, 4),
            notes=f"{DEMO_TAG} {note}",
        )
        db.add(record)
        records.append(record)
    db.flush()
    counts["performance_records"] = len(records)

    # ----------------------------------------------------------- 14. 复盘报告
    review_input = context_service.review_input(
        db,
        product,
        period_start=min(r.period_start for r in records).isoformat(),
        period_end=max(r.period_end for r in records).isoformat(),
        records=records,
    )
    review_output = provider.generate_review_report(review_input)
    report = ReviewReport(
        product_id=product.id,
        period_start=min(r.period_start for r in records),
        period_end=max(r.period_end for r in records),
        summary_text=review_output.get("summary_text", ""),
        insights_json=review_output.get("insights", []),
        next_actions_json=review_output.get("next_actions", []),
    )
    db.add(report)
    counts["review_reports"] = 1

    db.commit()
    db.refresh(store)
    db.refresh(product)

    return {
        "created": True,
        "message": "演示数据已创建，可直接体验完整单品运营闭环",
        "store_id": store.id,
        "product_id": product.id,
        "counts": counts,
        "demo_tag": DEMO_TAG,
        "next_steps": [
            f"进入商品详情页查看「{product.name}」的 9 个标签页",
            "在「诊断」页点击生成诊断，系统会自动把最新复盘结论作为输入（闭环）",
            "在「任务」页可重试 / 取消生成任务，并查看事件时间线",
            "在「复盘」页查看报告，并把「下一步动作」带入下一轮诊断",
        ],
    }
