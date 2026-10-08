"""单个生成任务的执行逻辑。

真实场景下这里会调用图像/视频生成模型；第一版产出确定性的 SVG 占位素材，
但任务状态流转、事件记录、失败重试与素材落库完全按生产结构实现。
"""

from __future__ import annotations

from typing import Any

from ..database import session_scope
from ..models import CreativePlan, GeneratedAsset, GenerationJob, Product
from ..services import asset_service, job_service

# 演示用：把任务参数里带 ``force_fail`` 的任务强制失败，用于展示失败与重试链路
FORCE_FAIL_KEY = "force_fail"


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_image_assets(
    db, job: GenerationJob, simulate_seconds: int
) -> tuple[list[GeneratedAsset], str]:
    """按主图方案的方向生成图片素材。"""
    product = db.get(Product, job.product_id)
    plan = db.get(CreativePlan, job.creative_plan_id) if job.creative_plan_id else None
    if product is None:
        raise RuntimeError("商品不存在，无法生成素材")

    params = job.params_json or {}
    content = (plan.content_json or {}) if plan else {}
    directions = content.get("directions") or []
    indexes = [i for i in params.get("direction_indexes", []) if isinstance(i, int)]
    if not indexes:
        indexes = list(range(len(directions))) or [0]
    count_per = max(1, _safe_int(params.get("count_per_direction"), 1))
    scene = str(params.get("usage_scene") or "主图")

    assets: list[GeneratedAsset] = []
    for idx in indexes:
        direction = directions[idx] if 0 <= idx < len(directions) else {}
        direction_title = str(direction.get("direction_title") or f"方向 {idx + 1}")
        core_copy = str(direction.get("core_copy") or product.name)
        highlight = str(direction.get("highlight_selling_point") or "核心卖点")

        for c in range(count_per):
            version_no = c + 1
            svg = asset_service.render_image_svg(
                product_name=product.name,
                direction_title=direction_title,
                core_copy=core_copy,
                highlight=highlight,
                scene=scene,
                version_no=version_no,
            )
            filename = f"image_d{idx}_v{version_no}.svg"
            _, url = asset_service.write_asset_file(job.id, filename, svg)
            assets.append(
                GeneratedAsset(
                    product_id=job.product_id,
                    creative_plan_id=job.creative_plan_id,
                    asset_type="image",
                    asset_url=url,
                    file_path=filename,
                    model_name="mock-image-gen-v1",
                    width=800,
                    height=800,
                    duration_sec=None,
                    review_status="pending",
                    version_no=version_no,
                    usage_scene=scene,
                    tags_json=[direction_title, "模拟生成"],
                    remark=f"由方向「{direction_title}」生成",
                )
            )

    # 保证 id 在写 result_json 前可用
    db.flush()
    summary = (
        f"图片生成完成：共 {len(assets)} 张（{len(indexes)} 个方向，每方向 {count_per} 张），"
        f"耗时约 {simulate_seconds} 秒"
    )
    return assets, summary


def _build_video_assets(
    db, job: GenerationJob, simulate_seconds: int
) -> tuple[list[GeneratedAsset], str]:
    """按视频脚本生成视频素材（海报帧 + 时长）。"""
    product = db.get(Product, job.product_id)
    plan = db.get(CreativePlan, job.creative_plan_id) if job.creative_plan_id else None
    if product is None:
        raise RuntimeError("商品不存在，无法生成素材")

    params = job.params_json or {}
    content = (plan.content_json or {}) if plan else {}
    scripts = content.get("scripts") or []
    indexes = [i for i in params.get("script_indexes", []) if isinstance(i, int)]
    if not indexes:
        indexes = list(range(len(scripts))) or [0]
    duration = max(5, _safe_int(params.get("duration_sec"), 15))
    scene = str(params.get("usage_scene") or "短视频")

    assets: list[GeneratedAsset] = []
    for idx in indexes:
        script = scripts[idx] if 0 <= idx < len(scripts) else {}
        script_title = str(script.get("script_title") or f"脚本 {idx + 1}")
        hook = str(script.get("hook") or product.name)
        cta = str(script.get("conversion_cta") or "点击下方链接下单")
        # 每条脚本时长略有差异，便于演示时区分
        item_duration = float(duration + (idx % 3) * 5)

        svg = asset_service.render_video_svg(
            product_name=product.name,
            script_title=script_title,
            hook=hook,
            cta=cta,
            duration_sec=item_duration,
            scene=scene,
            version_no=1,
        )
        filename = f"video_s{idx}_v1.svg"
        _, url = asset_service.write_asset_file(job.id, filename, svg)
        assets.append(
            GeneratedAsset(
                product_id=job.product_id,
                creative_plan_id=job.creative_plan_id,
                asset_type="video",
                asset_url=url,
                file_path=filename,
                model_name="mock-video-gen-v1",
                width=720,
                height=1280,
                duration_sec=item_duration,
                review_status="pending",
                version_no=1,
                usage_scene=scene,
                tags_json=[script_title, "模拟生成"],
                remark=f"由脚本「{script_title}」生成（海报帧）",
            )
        )

    db.flush()
    summary = (
        f"视频生成完成：共 {len(assets)} 条（时长 {duration} 秒起），"
        f"耗时约 {simulate_seconds} 秒"
    )
    return assets, summary


def execute_job(job_id: int, simulate_seconds: int) -> None:
    """在独立线程中执行一次任务尝试（不持有连接，可安全阻塞）。

    注意：调用方已经通过 ``claim_next_job`` 把任务置为 running，
    这里只负责产出结果或记录失败。
    """
    db = session_scope()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None or job.job_status != "running":
            return

        # 演示/测试用：强制失败路径
        if (job.params_json or {}).get(FORCE_FAIL_KEY):
            job_service.fail_job(db, job, "模拟生成失败（演示用，已按参数强制失败）")
            return

        try:
            if job.job_kind == "image":
                assets, summary = _build_image_assets(db, job, simulate_seconds)
            else:
                assets, summary = _build_video_assets(db, job, simulate_seconds)
        except Exception as exc:  # noqa: BLE001  失败要落库，不能吞掉
            db.rollback()
            job = db.get(GenerationJob, job_id)
            if job is not None:
                job_service.fail_job(db, job, f"生成过程出错：{exc}")
            return

        # 执行期间可能被人工取消，这里重新判定
        db.refresh(job)
        if job.job_status == "cancelled":
            return

        job_service.complete_job(db, job, assets, summary)
    finally:
        db.close()
