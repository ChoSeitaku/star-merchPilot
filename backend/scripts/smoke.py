"""端到端验收脚本：跑通一整条单品运营闭环。

用法（需先启动后端服务）：

    cd backend
    ../.venv/Scripts/python.exe scripts/smoke.py
    # 或指定地址：SMOKE_BASE=http://127.0.0.1:8004 python scripts/smoke.py

脚本会依次验证：
1. 三角色登录与角色权限（viewer 写操作应被拒绝）
2. 建店建档、平台账号占位与授权占位、库存建议
3. 商品 / SKU / 库存流水 / 竞品 / 公开链接解析 / 竞品监控
4. 诊断生成与编辑、主图方案、视频脚本
5. 图片与视频异步生成任务、事件时间线、素材审核
6. 推广链接建议与创建、短链跳转点击记录
7. 投放建议生成、人工确认（含权限校验）、实验计划与状态流转
8. 经营数据录入与 xlsx 导入（预览 → 确认）、复盘报告
9. 演示数据一键初始化
10. 任务负路径：取消、失败重试、超时扫描

每一步输出 PASS / FAIL，最后汇总。退出码非 0 表示存在失败项。
"""

from __future__ import annotations

import os
import sys
import time
from io import BytesIO
from typing import Any, Optional

import httpx

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8004")
API = f"{BASE}/api/v1"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


# ------------------------------------------------------------------ 断言工具
def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append((name, detail))
        print(f"  [FAIL] {name} :: {detail}")
    return condition


def section(title: str) -> None:
    print(f"\n=== {title} ===")


class Api:
    """带令牌的简易客户端。"""

    def __init__(self, base: str = API) -> None:
        self.client = httpx.Client(timeout=TIMEOUT, follow_redirects=False)
        self.token: Optional[str] = None

    def login(self, username: str, password: str) -> dict:
        r = self.client.post(f"{API}/auth/login", json={"username": username, "password": password})
        r.raise_for_status()
        data = r.json()
        self.token = data["access_token"]
        return data

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def get(self, path: str, **kw) -> httpx.Response:
        return self.client.get(path if path.startswith("http") else f"{API}{path}", headers=self.headers, **kw)

    def post(self, path: str, **kw) -> httpx.Response:
        return self.client.post(path if path.startswith("http") else f"{API}{path}", headers=self.headers, **kw)

    def patch(self, path: str, **kw) -> httpx.Response:
        return self.client.patch(path if path.startswith("http") else f"{API}{path}", headers=self.headers, **kw)


def poll_job(api: Api, product_id: int, job_id: int, *, want: tuple[str, ...], timeout: float = 90.0) -> dict:
    """轮询任务直到进入期望的终态。"""
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        r = api.get(f"/products/{product_id}/generation-jobs/{job_id}")
        if r.status_code == 200:
            last = r.json()
            if last.get("job_status") in want:
                return last
        time.sleep(1.2)
    return last


def build_xlsx(rows: list[list[Any]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "数据"
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------ 各阶段
def stage_auth(admin: Api) -> tuple[Api, Api]:
    section("1. 登录与角色权限")
    operator = Api()
    viewer = Api()

    admin_data = admin.login("admin", "admin123")
    check("管理员登录成功", admin_data["user"]["role"] == "admin", str(admin_data["user"]))
    operator.login("operator", "operator123")
    viewer_data = viewer.login("viewer", "viewer123")
    check("查看人员登录成功", viewer_data["user"]["role"] == "viewer")

    r = admin.get("/auth/me")
    check("GET /auth/me 返回当前用户", r.status_code == 200 and r.json()["username"] == "admin", r.text[:160])

    r = httpx.get(f"{API}/products", timeout=TIMEOUT)
    check("未登录访问接口返回 401", r.status_code == 401, f"status={r.status_code}")

    r = viewer.post("/products", json={"store_id": 1, "name": "viewer 不该能建"})
    check("viewer 创建商品被拒绝(403)", r.status_code == 403, f"status={r.status_code} {r.text[:120]}")

    r = operator.get("/users")
    check("operator 访问用户管理被拒绝(403)", r.status_code == 403, f"status={r.status_code}")

    r = viewer.get("/workspace/dashboard")
    check("viewer 可读取工作台数据", r.status_code == 200, f"status={r.status_code}")

    return operator, viewer


def stage_store(admin: Api, operator: Api) -> dict:
    section("2. 建店建档 / 平台账号 / 授权占位 / 库存建议")
    r = admin.post("/stores", json={
        "store_name": "验收测试旗舰店",
        "platform": "taobao",
        "external_store_id": "SMOKE-0001",
        "owner_name": "验收员",
        "remark": "smoke 脚本创建",
    })
    check("创建店铺", r.status_code == 201, r.text[:200])
    store = r.json()
    store_id = store["id"]

    r = operator.post("/stores", json={"store_name": "operator 不该能建店", "platform": "jd"})
    check("operator 创建店铺被拒绝(403)", r.status_code == 403, f"status={r.status_code}")

    r = admin.post(f"/stores/{store_id}/platform-accounts", json={
        "platform": "taobao", "account_name": "验收主账号", "remark": "占位"
    })
    check("创建平台账号占位", r.status_code == 201, r.text[:200])
    account = r.json()
    account_id = account["id"]
    check("平台账号不含明文凭据字段",
          "password" not in r.text and "cookie" not in r.text and "secret" not in r.text,
          "响应中出现了疑似明文凭据字段")

    r = admin.post(
        f"/stores/{store_id}/platform-accounts/{account_id}/authorization/start",
        json={"redirect_uri": f"{BASE}/callback", "scope": "item_read,order_read"},
    )
    check("生成授权占位信息", r.status_code == 200 and "authorize_url" in r.json(), r.text[:200])

    r = admin.post(
        f"/stores/{store_id}/platform-accounts/{account_id}/authorization/callback-placeholder",
        json={
            "auth_code_masked": "demo****code",
            "granted_scope": "item_read,order_read",
            "authorized_account_name": "验收主账号",
            "expires_at": "2026-12-31T23:59:59",
        },
    )
    check("保存授权元数据", r.status_code == 200 and r.json()["auth_status"] == "authorized", r.text[:200])

    r = operator.post(f"/stores/{store_id}/inventory-advice/generate")
    check("生成库存建议", r.status_code == 200 and "summary_text" in r.json(), r.text[:200])

    return {"store_id": store_id, "account_id": account_id}


def stage_product(operator: Api, store_id: int) -> dict:
    section("3. 商品 / SKU / 库存 / 竞品 / 链接解析 / 竞品监控")
    r = operator.post("/products", json={
        "store_id": store_id,
        "name": "验收测试商品 轻量双肩包",
        "platform": "taobao",
        "category": "箱包",
        "price": 199.0,
        "cost": 86.0,
        "target_audience": "通勤上班族",
        "selling_points": "轻量,防泼水,大容量",
        "product_url": "https://item.taobao.com/item.htm?id=999001",
        "status": "active",
    })
    check("创建商品", r.status_code == 201, r.text[:200])
    product = r.json()
    product_id = product["id"]

    r = operator.post(f"/products/{product_id}/platform-mappings", json={
        "platform": "taobao", "platform_product_id": "999001", "platform_sku_id": "TB-1"
    })
    check("创建平台映射", r.status_code == 201, r.text[:200])

    sku_ids = []
    for code, name, stock, threshold in [
        ("SMOKE-BLK", "黑色标准款", 5, 10),   # 故意低于阈值，制造低库存
        ("SMOKE-GRY", "灰色标准款", 120, 10),
    ]:
        r = operator.post(f"/products/{product_id}/skus", json={
            "sku_code": code, "sku_name": name, "price": 199.0, "cost": 86.0,
            "stock_qty": stock, "warning_threshold": threshold, "location_text": "T区",
        })
        if r.status_code == 201:
            sku_ids.append(r.json()["id"])
    check("创建 SKU（含期初库存）", len(sku_ids) == 2, "SKU 创建数量不符")

    r = operator.get(f"/products/{product_id}/inventory")
    inv = r.json()
    check("库存概览含低库存标记", r.status_code == 200 and inv["low_stock_count"] >= 1,
          f"low_stock_count={inv.get('low_stock_count')}")

    r = operator.post(f"/products/{product_id}/skus/{sku_ids[0]}/inventory/adjust", json={
        "change_qty": 20, "reason_text": "验收补货", "movement_type": "purchase"
    })
    check("库存调整写入流水", r.status_code == 200 and r.json()["stock_qty"] == 25, r.text[:200])

    r = operator.get(f"/products/{product_id}/inventory/movements")
    check("库存流水可查询", r.status_code == 200 and r.json()["total"] >= 3, r.text[:200])

    # 竞品
    competitor_ids = []
    for name, platform, price in [("验收竞品A", "taobao", 189.0), ("验收竞品B", "jd", 219.0)]:
        r = operator.post(f"/products/{product_id}/competitors", json={
            "name": name, "platform": platform, "url": f"https://item.jd.com/{abs(hash(name)) % 10**8}.html",
            "price": price, "sales_hint": "月销 1000+", "title": name,
            "selling_points": "便宜,好", "review_keywords": "质量不错",
        })
        if r.status_code == 201:
            competitor_ids.append(r.json()["id"])
    check("录入竞品", len(competitor_ids) == 2, "竞品创建数量不符")

    # 公开链接解析
    r = operator.post(f"/products/{product_id}/competitors/import-url-tasks", json={
        "urls": ["https://item.taobao.com/item.htm?id=555000111",
                 "https://item.jd.com/10023456789.html"],
        "auto_create_competitors": True,
    })
    check("创建公开链接解析任务", r.status_code == 201 and r.json()["total"] == 2, r.text[:200])
    task_ids = [t["id"] for t in r.json()["items"]]

    r = operator.post(f"/products/{product_id}/link-parse-tasks/{task_ids[0]}/run")
    parsed = r.json()
    check("运行链接解析任务", r.status_code == 200 and parsed["task_status"] == "succeeded", r.text[:200])
    check("解析结果标注数据来源与合规说明",
          bool(parsed.get("result_json", {}).get("compliance_note")),
          "缺少合规说明")

    r = operator.get(f"/products/{product_id}/competitors")
    check("解析后自动创建竞品", r.json()["total"] >= 3, f"total={r.json()['total']}")

    # 竞品监控
    r = operator.post(f"/products/{product_id}/competitors/{competitor_ids[0]}/monitor",
                      json={"interval_minutes": 60})
    check("创建竞品监控", r.status_code == 201, r.text[:200])
    monitor_id = r.json()["id"]

    r = operator.post(f"/products/{product_id}/competitor-monitors/run-due")
    check("运行到期监控生成快照", r.status_code == 200 and r.json()["total"] >= 1, r.text[:200])

    r = operator.get(f"/products/{product_id}/competitor-monitors/{monitor_id}/snapshots")
    check("监控快照可查询", r.status_code == 200 and r.json()["total"] >= 1, r.text[:200])

    return {"product_id": product_id, "sku_ids": sku_ids, "competitor_ids": competitor_ids}


def stage_diagnosis_and_plans(operator: Api, product_id: int) -> dict:
    section("4. 诊断 / 主图方案 / 视频脚本")
    r = operator.post(f"/products/{product_id}/diagnoses/generate", json={"source_type": "ai_mock"})
    check("生成商品诊断", r.status_code == 201, r.text[:300])
    diagnosis = r.json()
    diag_id = diagnosis["id"]
    required_fields = ["positioning", "price_band", "audience_insights", "pain_points",
                       "selling_point_analysis", "risks", "recommendations"]
    missing = [f for f in required_fields if not (diagnosis.get(f) or "").strip()]
    check("诊断输出包含全部结构化字段", not missing, f"缺失：{missing}")

    r = operator.patch(f"/products/{product_id}/diagnoses/{diag_id}", json={
        "recommendations": "（人工编辑）优先验证主图方向一的点击率表现。"
    })
    check("编辑保存诊断", r.status_code == 200 and "人工编辑" in r.json()["recommendations"], r.text[:200])

    r = operator.post(f"/products/{product_id}/creative-plans/main-images/generate")
    check("生成主图方案", r.status_code == 201, r.text[:300])
    image_plan = r.json()
    directions = image_plan["content_json"].get("directions", [])
    check("主图方案至少 3 个方向", len(directions) >= 3, f"实际 {len(directions)} 个")
    if directions:
        d = directions[0]
        need = ["direction_title", "visual_structure", "core_copy",
                "highlight_selling_point", "rationale"]
        check("主图方向包含规定字段", all(k in d for k in need), f"缺失 {[k for k in need if k not in d]}")

    r = operator.patch(f"/products/{product_id}/creative-plans/{image_plan['id']}",
                       json={"status": "selected"})
    check("主图方案标记为选中", r.status_code == 200 and r.json()["status"] == "selected", r.text[:200])

    r = operator.post(f"/products/{product_id}/creative-plans/video-scripts/generate")
    check("生成视频脚本", r.status_code == 201, r.text[:300])
    video_plan = r.json()
    scripts = video_plan["content_json"].get("scripts", [])
    check("视频脚本至少 3 条", len(scripts) >= 3, f"实际 {len(scripts)} 条")
    if scripts:
        need = ["hook", "storyboard", "voiceover", "conversion_cta"]
        check("视频脚本包含规定字段", all(k in scripts[0] for k in need),
              f"缺失 {[k for k in need if k not in scripts[0]]}")

    r = operator.patch(f"/products/{product_id}/creative-plans/{video_plan['id']}",
                       json={"status": "selected"})
    check("视频脚本标记为选中", r.status_code == 200 and r.json()["status"] == "selected", r.text[:200])

    return {"image_plan_id": image_plan["id"], "video_plan_id": video_plan["id"]}


def stage_jobs(operator: Api, admin: Api, product_id: int, plans: dict) -> dict:
    section("5. 图片 / 视频异步生成任务与素材审核")
    r = operator.post(
        f"/products/{product_id}/creative-plans/{plans['image_plan_id']}/images/generate",
        json={"direction_indexes": [0, 1], "count_per_direction": 1, "usage_scene": "主图"},
    )
    check("创建图片生成任务(202)", r.status_code == 202, r.text[:200])
    image_job_id = r.json()["id"]

    job = poll_job(operator, product_id, image_job_id, want=("succeeded", "failed", "timeout"))
    check("图片任务执行成功", job.get("job_status") == "succeeded",
          f"status={job.get('job_status')} err={job.get('error_message')}")

    r = operator.get(f"/products/{product_id}/generation-jobs/{image_job_id}/events")
    events = r.json()["items"]
    types = [e["event_type"] for e in events]
    check("任务事件时间线覆盖入队与运行中", "enqueued" in types and "running" in types, str(types))
    check("任务事件时间线包含成功节点", "succeeded" in types, str(types))

    r = operator.post(f"/products/{product_id}/assets/sync")
    check("同步素材", r.status_code == 200, r.text[:200])

    r = operator.get(f"/products/{product_id}/assets")
    assets = r.json()["items"]
    check("素材库有图片素材", any(a["asset_type"] == "image" for a in assets), f"共 {len(assets)} 个")

    image_assets = [a for a in assets if a["asset_type"] == "image"]
    if image_assets:
        ids = [a["id"] for a in image_assets]
        r = operator.patch(f"/products/{product_id}/creative-plans/{plans['image_plan_id']}/assets",
                           json={"asset_ids": ids, "review_status": "approved",
                                 "score": 4.5, "tags_json": ["验收", "主图"], "remark": "验收通过"})
        check("更新素材审核字段", r.status_code == 200, r.text[:200])
        r = operator.get(f"/products/{product_id}/assets?review_status=approved")
        check("素材审核状态生效", r.json()["total"] >= 1, r.text[:200])

    # 视频任务
    r = operator.post(
        f"/products/{product_id}/creative-plans/{plans['video_plan_id']}/videos/generate",
        json={"script_indexes": [0], "duration_sec": 20, "usage_scene": "短视频"},
    )
    check("创建视频生成任务(202)", r.status_code == 202, r.text[:200])
    video_job_id = r.json()["id"]
    job = poll_job(operator, product_id, video_job_id, want=("succeeded", "failed", "timeout"))
    check("视频任务执行成功", job.get("job_status") == "succeeded",
          f"status={job.get('job_status')} err={job.get('error_message')}")

    r = operator.get(f"/products/{product_id}/assets?asset_type=video")
    videos = r.json()["items"]
    check("视频素材含时长字段", bool(videos) and (videos[0].get("duration_sec") or 0) > 0,
          f"videos={len(videos)}")

    return {"image_job_id": image_job_id, "video_job_id": video_job_id}


def stage_job_negative(operator: Api, admin: Api, product_id: int, plans: dict) -> None:
    section("10. 任务负路径：取消 / 失败重试 / 超时扫描")
    # 取消：入队后立刻取消
    r = operator.post(
        f"/products/{product_id}/creative-plans/{plans['image_plan_id']}/images/generate",
        json={"direction_indexes": [0], "count_per_direction": 1},
    )
    cancel_job_id = r.json()["id"]
    r = operator.post(f"/products/{product_id}/generation-jobs/{cancel_job_id}/cancel")
    cancelled_ok = r.status_code == 200 and r.json()["job_status"] == "cancelled"
    if not cancelled_ok:
        # 任务可能已被工作进程抢走，此时取消应返回 409（已进入终态或不可取消）
        cancelled_ok = r.status_code == 409
    check("取消任务（或状态冲突提示）", cancelled_ok, f"status={r.status_code} {r.text[:160]}")

    # 失败 → 自动重试 → 终态失败
    r = operator.post(
        f"/products/{product_id}/creative-plans/{plans['image_plan_id']}/images/generate",
        json={"direction_indexes": [1], "count_per_direction": 1},
    )
    fail_job_id = r.json()["id"]
    r = admin.post(f"/products/{product_id}/generation-jobs/{fail_job_id}/simulate-failure",
                   json={"reason": "验收脚本注入的失败"})
    check("标记模拟失败", r.status_code == 200, r.text[:200])

    job = poll_job(operator, product_id, fail_job_id, want=("failed", "succeeded"), timeout=180)
    r = operator.get(f"/products/{product_id}/generation-jobs/{fail_job_id}/events")
    types = [e["event_type"] for e in r.json()["items"]]
    check("失败任务产生失败事件", "failed" in types or "retry" in types, str(types))
    if job.get("job_status") == "failed":
        r = operator.post(f"/products/{product_id}/generation-jobs/{fail_job_id}/retry")
        check("失败任务可重试", r.status_code == 200 and r.json()["job_status"] == "pending", r.text[:200])

    # 超时扫描
    r = admin.post("/workspace/generation-jobs/sweep-timeouts")
    check("超时任务扫描接口可用", r.status_code == 200 and "marked_count" in r.json(), r.text[:200])

    # viewer 不能重试/取消
    r = httpx.post(f"{API}/products/{product_id}/generation-jobs/{fail_job_id}/retry",
                   headers={"Authorization": "Bearer invalid"}, timeout=TIMEOUT)
    check("非法令牌访问被拒绝", r.status_code == 401, f"status={r.status_code}")


def stage_links(operator: Api, product_id: int) -> None:
    section("6. 推广链接建议 / 创建 / 短链点击")
    r = operator.post(f"/products/{product_id}/promotion-links/generate")
    check("生成推广链接建议", r.status_code == 200 and r.json()["total"] >= 3, r.text[:200])
    suggestion = r.json()["items"][0]

    r = operator.post(f"/products/{product_id}/promotion-links", json={
        "link_name": suggestion["link_name"],
        "target_url": suggestion["target_url"],
        "scene_text": suggestion["scene_text"],
        "utm_json": suggestion["utm"],
    })
    check("创建推广链接", r.status_code == 201, r.text[:200])
    link = r.json()
    tracking_code = link["tracking_code"]

    r = operator.get(f"/products/{product_id}/promotion-links")
    check("推广链接列表可查询", r.status_code == 200 and r.json()["total"] >= 1, r.text[:200])

    # 短链跳转（无需登录，禁止自动跟随重定向）
    r = httpx.get(f"{API}/r/{tracking_code}", timeout=TIMEOUT, follow_redirects=False)
    check("短链跳转返回 302", r.status_code == 302, f"status={r.status_code}")
    check("短链跳转指向目标地址", r.headers.get("location") == link["target_url"],
          f"location={r.headers.get('location')}")

    r = operator.get(f"/products/{product_id}/promotion-links/{link['id']}/clicks")
    check("点击已被记录", r.status_code == 200 and r.json()["click_count"] >= 1, r.text[:200])


def stage_ads(operator: Api, viewer: Api, product_id: int) -> None:
    section("7. 投放建议 / 人工确认 / 实验计划")
    r = operator.post(f"/products/{product_id}/ad-recommendations/generate",
                      json={"objective": "转化", "daily_budget": 300.0})
    check("生成投放建议", r.status_code == 201, r.text[:300])
    rec = r.json()
    rec_id = rec["id"]
    need = ["summary_text", "objective_text", "audience_segments_json", "budget_plan_json",
            "creative_tests_json", "bid_strategy_json", "risk_controls_json", "next_steps_json"]
    empty = [k for k in need if not rec.get(k)]
    check("投放建议包含全部规定字段", not empty, f"为空的字段：{empty}")
    check("投放建议初始为待确认", rec["confirm_status"] == "pending", rec["confirm_status"])
    check("投放建议含合规说明", "compliance_note" in rec, "缺少 compliance_note")

    # viewer 不能确认
    r = viewer.patch(f"/products/{product_id}/ad-recommendations/{rec_id}/confirmation",
                     json={"confirm_status": "confirmed", "confirm_remark": "viewer 不该能确认"})
    check("viewer 确认投放建议被拒绝(403)", r.status_code == 403, f"status={r.status_code}")

    # operator 可以确认
    r = operator.patch(f"/products/{product_id}/ad-recommendations/{rec_id}/confirmation",
                       json={"confirm_status": "confirmed", "confirm_remark": "验收确认"})
    check("运营人员确认投放建议", r.status_code == 200 and r.json()["confirm_status"] == "confirmed",
          r.text[:200])

    # 重复确认应冲突
    r = operator.patch(f"/products/{product_id}/ad-recommendations/{rec_id}/confirmation",
                       json={"confirm_status": "rejected"})
    check("重复确认被拒绝(409)", r.status_code == 409, f"status={r.status_code}")

    # 实验计划
    r = operator.post(f"/products/{product_id}/ad-experiments/generate",
                      json={"experiment_name": "验收实验", "budget_amount": 300.0})
    check("生成投放实验计划", r.status_code == 201, r.text[:300])
    exp = r.json()
    exp_id = exp["id"]
    check("实验计划初始为草稿", exp["experiment_status"] == "draft", exp["experiment_status"])

    # 状态流转 draft → confirmed → running → finished
    ok_flow = True
    flow_detail = ""
    for target in ("confirmed", "running", "finished"):
        r = operator.patch(f"/products/{product_id}/ad-experiments/{exp_id}",
                           json={"experiment_status": target})
        if r.status_code != 200 or r.json()["experiment_status"] != target:
            ok_flow = False
            flow_detail = f"切到 {target} 失败：{r.status_code} {r.text[:160]}"
            break
    check("实验状态按 draft→confirmed→running→finished 流转", ok_flow, flow_detail)

    # 非法流转应被拒绝
    r = operator.patch(f"/products/{product_id}/ad-experiments/{exp_id}",
                       json={"experiment_status": "draft"})
    check("终态实验不允许回退(409)", r.status_code == 409, f"status={r.status_code}")


def stage_performance_and_review(operator: Api, viewer: Api, product_id: int) -> None:
    section("8. 经营数据录入 / 导入 / 复盘报告")
    r = operator.post(f"/products/{product_id}/performance-records", json={
        "period_start": "2026-09-01", "period_end": "2026-09-07",
        "impressions": 100000, "clicks": 3000, "conversions": 60,
        "spend": 1500.0, "revenue": 5400.0, "notes": "验收录入",
    })
    check("录入经营数据", r.status_code == 201, r.text[:200])
    rec = r.json()
    check("派生指标自动计算", rec["ctr"] == 3.0 and rec["roi"] == 3.6,
          f"ctr={rec.get('ctr')} roi={rec.get('roi')}")

    r = viewer.post(f"/products/{product_id}/performance-records", json={
        "period_start": "2026-09-08", "period_end": "2026-09-14", "impressions": 1000,
    })
    check("viewer 录入经营数据被拒绝(403)", r.status_code == 403, f"status={r.status_code}")

    # 模板下载
    r = operator.get("/workspace/templates/performance-records")
    check("下载经营数据模板", r.status_code == 200 and len(r.content) > 2000, f"size={len(r.content)}")
    template_bytes = r.content

    # 用模板结构构造一份含错误行的数据，验证「部分成功」
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(template_bytes))
    ws = wb["数据"]
    ws.delete_rows(2, ws.max_row)  # 清掉示例行
    ws.append(["2026-09-15", "2026-09-21", 80000, 2400, 48, 1200.0, 4320.0, None, None, None, "验收导入A"])
    ws.append(["2026-09-22", "2026-09-28", 90000, 2900, 58, 1400.0, 5220.0, None, None, None, "验收导入B"])
    ws.append(["日期格式错误", "2026-09-30", 1000, 100, 1, 10.0, 20.0, None, None, None, "错误行：日期非法"])
    ws.append(["2026-10-01", "2026-10-07", 5000, 9000, 1, 10.0, 20.0, None, None, None, "错误行：点击>曝光"])
    buffer = BytesIO()
    wb.save(buffer)
    upload = buffer.getvalue()

    r = operator.post(
        f"/products/{product_id}/performance-records/import?preview_only=true",
        files={"file": ("performance.xlsx", upload,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    check("经营数据导入预览", r.status_code == 200, r.text[:300])
    preview = r.json()
    check("预览识别出错误行", preview["invalid_rows"] and len(preview["invalid_rows"]) == 2,
          f"invalid_rows={preview.get('invalid_rows')}")
    check("预览统计有效行数正确", preview["valid_rows"] == 2, f"valid_rows={preview.get('valid_rows')}")
    check("预览未写入数据库(需要 import_id)", bool(preview.get("import_id")), "缺少 import_id")
    error_rows = preview["invalid_rows"]
    check("错误行包含行号与原因",
          all(e.get("row_no") and e.get("errors") for e in error_rows), str(error_rows))

    import_id = preview["import_id"]
    r = operator.post(
        f"/products/{product_id}/performance-records/import"
        f"?preview_only=false&import_id={import_id}"
    )
    check("确认导入（部分成功）", r.status_code == 200, r.text[:300])
    result = r.json()
    check("部分成功统计正确", result["success_rows"] == 2 and result["failed_rows"] == 2,
          f"success={result.get('success_rows')} failed={result.get('failed_rows')}")

    r = operator.get(f"/products/{product_id}/performance-records")
    check("导入的数据已落库", r.json()["total"] >= 3, f"total={r.json()['total']}")

    # 复盘报告
    r = operator.post(f"/products/{product_id}/review-reports/generate",
                      json={"period_start": "2026-09-01", "period_end": "2026-09-30"})
    check("生成复盘报告", r.status_code == 201, r.text[:300])
    report = r.json()
    check("复盘报告包含核心洞察", bool(report["insights_json"]), "insights 为空")
    check("复盘报告包含下一步动作", bool(report["next_actions_json"]), "next_actions 为空")

    # 闭环：复盘结论应进入下一轮诊断
    r = operator.post(f"/products/{product_id}/diagnoses/generate",
                      json={"include_review_actions": True})
    check("基于复盘结论生成下一轮诊断（闭环）", r.status_code == 201, r.text[:300])
    note = r.json().get("closed_loop_note", "")
    check("诊断标注了闭环输入", "复盘" in note, f"note={note}")


def stage_imports(operator: Api, store_id: int) -> None:
    section("9. 导入中心：商品 / SKU 库存 / 平台字段映射")
    for import_type, label in [("products", "商品"), ("sku-inventory", "SKU 库存"),
                               ("platform-mappings", "平台字段映射")]:
        r = operator.get(f"/workspace/templates/{import_type}")
        check(f"下载{label}导入模板", r.status_code == 200 and len(r.content) > 2000,
              f"size={len(r.content)}")

    # 商品导入（含 1 个错误行）
    store_name = "验收测试旗舰店"
    wb_rows = [
        ["店铺名称 *", "商品名称 *", "平台 *", "类目 *", "售价 *", "成本",
         "目标人群", "核心卖点", "商品链接", "商品状态"],
        [store_name, "验收导入商品A", "taobao", "箱包", 159.0, 70.0, "学生", "轻,便宜", "", "draft"],
        [store_name, "验收导入商品B", "jd", "箱包", 259.0, 120.0, "商务", "耐用", "", "draft"],
        [store_name, "X", "不存在的平台", "箱包", 100.0, 50.0, "", "", "", "draft"],  # 错误行
    ]
    upload = build_xlsx(wb_rows)
    r = operator.post("/imports/products/preview",
                      files={"file": ("products.xlsx", upload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    check("商品导入预览", r.status_code == 200, r.text[:300])
    preview = r.json()
    check("商品导入识别错误行", len(preview["invalid_rows"]) == 1, str(preview.get("invalid_rows")))
    r = operator.post(f"/imports/products/confirm?import_id={preview['import_id']}")
    check("商品导入确认（部分成功）", r.status_code == 200 and r.json()["success_rows"] == 2,
          r.text[:300])

    # SKU 库存导入
    sku_rows = [
        ["商品名称 *", "SKU编码 *", "SKU名称", "规格", "售价", "成本", "库存数量", "预警阈值", "库位"],
        ["验收导入商品A", "IMP-A-001", "导入款A", "颜色:黑色", 159.0, 70.0, 88, 10, "I区-01"],
        ["不存在的商品", "IMP-X-001", "导入款X", "", 100.0, 50.0, 5, 2, "I区-02"],  # 错误行
    ]
    upload = build_xlsx(sku_rows)
    r = operator.post("/imports/sku-inventory/preview",
                      files={"file": ("sku.xlsx", upload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    check("SKU 库存导入预览", r.status_code == 200, r.text[:300])
    preview = r.json()
    check("SKU 导入识别错误行（商品不存在）", len(preview["invalid_rows"]) == 1,
          str(preview.get("invalid_rows")))
    r = operator.post(f"/imports/sku-inventory/confirm?import_id={preview['import_id']}")
    check("SKU 库存导入确认", r.status_code == 200 and r.json()["success_rows"] == 1, r.text[:300])

    # 平台字段映射导入
    map_rows = [
        ["商品名称 *", "平台 *", "平台商品ID *", "平台SKU编码", "映射状态"],
        ["验收导入商品A", "taobao", "888001", "TB-888001", "mapped"],
    ]
    upload = build_xlsx(map_rows)
    r = operator.post("/imports/platform-mappings/preview",
                      files={"file": ("map.xlsx", upload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    preview = r.json()
    check("平台字段映射导入预览", r.status_code == 200 and preview["valid_rows"] == 1, r.text[:300])
    r = operator.post(f"/imports/platform-mappings/confirm?import_id={preview['import_id']}")
    check("平台字段映射导入确认", r.status_code == 200 and r.json()["success_rows"] == 1, r.text[:300])


def stage_demo_data(admin: Api) -> None:
    section("11. 演示数据与全局列表")
    r = admin.post("/workspace/demo-data")
    check("创建演示数据接口可用", r.status_code == 200, r.text[:400])
    data = r.json()
    if data.get("created"):
        counts = data["counts"]
        expected = ["stores", "platform_accounts", "products", "product_skus", "inventory_items",
                    "competitors", "creative_plans", "generated_assets", "promotion_links",
                    "ad_recommendations", "ad_experiments", "performance_records", "review_reports"]
        missing = [k for k in expected if not counts.get(k)]
        check("演示数据覆盖全部要求的数据类型", not missing, f"缺失：{missing}")
    else:
        check("演示数据已存在（跳过重复创建）", True, "")

    r = admin.get("/workspace/dashboard")
    check("工作台概览接口", r.status_code == 200 and "stores" in r.json(), r.text[:200])

    for path, label in [("/stores", "店铺"), ("/products", "商品"), ("/users", "用户")]:
        r = admin.get(path)
        check(f"{label}列表非空", r.status_code == 200 and r.json()["total"] >= 1,
              f"status={r.status_code}")

    r = admin.get("/workspace/settings")
    check("系统设置可读取", r.status_code == 200 and "runtime" in r.json(), r.text[:200])

    r = admin.patch("/workspace/settings", json={"items": [{"key": "queue_simulate_seconds", "value": "3"}]})
    check("系统设置可更新", r.status_code == 200 and "queue_simulate_seconds" in r.json()["updated"],
          r.text[:200])

    r = admin.patch("/workspace/settings", json={"items": [{"key": "compliance_no_auto_ad_execution", "value": "0"}]})
    check("只读合规项不可修改", r.status_code == 200 and r.json()["rejected"], r.text[:200])


def main() -> int:
    print(f"目标服务：{BASE}")
    try:
        httpx.get(f"{BASE}/api/health", timeout=10).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"\n无法连接服务 {BASE}：{exc}")
        print("请先启动：cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8004")
        return 2

    admin = Api()
    operator, viewer = stage_auth(admin)
    store = stage_store(admin, operator)
    product = stage_product(operator, store["store_id"])
    plans = stage_diagnosis_and_plans(operator, product["product_id"])
    stage_jobs(operator, admin, product["product_id"], plans)
    stage_links(operator, product["product_id"])
    stage_ads(operator, viewer, product["product_id"])
    stage_performance_and_review(operator, viewer, product["product_id"])
    stage_imports(operator, store["store_id"])
    stage_demo_data(admin)
    stage_job_negative(operator, admin, product["product_id"], plans)

    print("\n" + "=" * 62)
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        print("\n失败明细：")
        for name, detail in FAILED:
            print(f"  - {name}: {detail}")
    print("=" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
