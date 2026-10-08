"""前端 UI 冒烟检查（Playwright，可选）。

用真实浏览器走一遍关键页面，确认前端能正常渲染、登录可用、9 个标签页可打开、
看板与 RBAC 表现符合预期，并截图留档到 backend/storage/ui-shots/。

**本脚本是可选的**：应用本身不需要它，手动用浏览器打开验收同样有效。

浏览器选择（按顺序探测，避免额外下载 Playwright 自带的 Chromium）：
  1. 环境变量 ``UI_BROWSER_CHANNEL``（msedge / chrome）
  2. 系统已安装的 Edge
  3. 系统已安装的 Chrome
  4. Playwright 自带 Chromium（需先执行 ``playwright install chromium``）

用法（需先启动后端，且前端已 npm run build）：

    cd backend
    ../.venv/Scripts/python.exe scripts/ui_check.py
    # 指定浏览器：UI_BROWSER_CHANNEL=chrome python scripts/ui_check.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("UI_BASE", "http://127.0.0.1:8004")
SHOTS = Path(__file__).resolve().parent.parent / "storage" / "ui-shots"
SHOTS.mkdir(parents=True, exist_ok=True)

# 系统浏览器可执行文件常见位置（Windows）
_CHANNEL_PATHS = {
    "msedge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
}


def pick_browser(playwright):
    """返回 (browser, 说明)。优先复用系统已安装的浏览器，避免额外下载。"""
    forced = os.environ.get("UI_BROWSER_CHANNEL", "").strip()
    candidates = [forced] if forced else ["msedge", "chrome"]

    for channel in candidates:
        if not channel:
            continue
        paths = _CHANNEL_PATHS.get(channel, [])
        if paths and not any(Path(p).exists() for p in paths):
            continue
        try:
            browser = playwright.chromium.launch(channel=channel)
            return browser, f"系统浏览器 {channel}"
        except Exception:  # noqa: BLE001  探测失败就换下一个
            continue

    browser = playwright.chromium.launch()
    return browser, "Playwright 自带 Chromium"

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []

TAB_NAMES = [
    "商品&竞品",
    "诊断",
    "主图",
    "视频",
    "任务",
    "素材库",
    "链接",
    "投放",
    "复盘",
]


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append((name, detail))
        print(f"  [FAIL] {name} :: {detail}")


def shot(page, name: str) -> None:
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


def login(page, username: str, password: str) -> None:
    page.goto(f"{BASE}/#/login", wait_until="networkidle")
    page.fill('input[placeholder="用户名"]', username)
    page.fill('input[placeholder="密码"]', password)
    page.click('button:has-text("登录")')
    page.wait_for_url("**/#/dashboard", timeout=15000)
    page.wait_for_load_state("networkidle")


def main() -> int:
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser, browser_desc = pick_browser(p)
        print(f"使用浏览器：{browser_desc}")
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )

        # ---------------------------------------------------------- 1. 登录页
        print("\n=== 1. 登录页 ===")
        page.goto(f"{BASE}/#/login", wait_until="networkidle")
        check("登录页渲染", page.locator("text=电商运营助手").first.is_visible())
        check("演示账号可一键填充", page.locator("text=admin / admin123").is_visible())
        shot(page, "01-login")

        # ---------------------------------------------------------- 2. 管理员
        print("\n=== 2. 管理员登录与工作台 ===")
        login(page, "admin", "admin123")
        check("登录成功跳转工作台", "/#/dashboard" in page.url)
        check("工作台标题渲染", page.locator("h1:has-text('首页工作台')").is_visible())
        page.wait_for_timeout(1200)
        shot(page, "02-dashboard-admin")

        # 创建演示数据（若已存在会提示跳过）
        demo_btn = page.locator('button:has-text("创建演示数据")')
        check("管理员可见「创建演示数据」按钮", demo_btn.is_visible())
        demo_btn.click()
        page.wait_for_timeout(700)
        confirm_btn = page.locator('.el-message-box__btns button:has-text("创建")')
        if confirm_btn.count():
            confirm_btn.click()
            page.wait_for_timeout(3500)
        shot(page, "03-dashboard-demo")

        # ---------------------------------------------------------- 3. 商品池
        print("\n=== 3. 商品池与商品详情 9 标签 ===")
        page.click('.el-menu-item:has-text("商品池")')
        page.wait_for_url("**/#/products", timeout=10000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        row_count = page.locator(".el-table__body tbody tr").count()
        check("商品列表有数据", row_count > 0, f"行数={row_count}")
        shot(page, "04-products")

        if row_count:
            page.locator(".el-table__body tbody tr").first.locator("a, .el-link").first.click()
            page.wait_for_url("**/#/products/*", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(900)
            check("商品详情页渲染", page.locator(".page-title").first.is_visible())
            check("闭环进度条渲染", page.locator("text=运营闭环进度").is_visible())
            shot(page, "05-product-detail")

            # 依次点击 9 个标签页，确认都能渲染且无致命错误
            opened: list[str] = []
            for idx, name in enumerate(TAB_NAMES):
                tab = page.locator(f'.el-tabs__item:has-text("{name}")').first
                if not tab.count():
                    check(f"标签页「{name}」存在", False, "未找到标签")
                    continue
                tab.click()
                page.wait_for_timeout(1400)
                body_text = page.locator(".el-tabs__content").first.inner_text()
                opened.append(name)
                if idx in (0, 1, 4, 8):
                    shot(page, f"06-tab-{idx}-{name.replace('&', '')}")
            check("9 个标签页全部可打开", len(opened) == 9, f"实际打开 {len(opened)} 个：{opened}")

            # 在诊断页尝试生成诊断（验证写操作 + 闭环提示）
            print("\n=== 4. 诊断生成（闭环） ===")
            page.locator('.el-tabs__item:has-text("诊断")').first.click()
            page.wait_for_timeout(800)
            gen = page.locator('button:has-text("生成诊断")').first
            if gen.count():
                gen.click()
                page.wait_for_timeout(3000)
                text = page.locator(".el-tabs__content").first.inner_text()
                has_fields = "商品定位" in text and "优化建议" in text
                check("诊断生成后展示结构化字段", has_fields, "未看到规定字段")
                shot(page, "07-diagnosis-generated")
            else:
                check("诊断页存在生成按钮", False, "未找到按钮")

        # ---------------------------------------------------------- 5. 导入中心
        print("\n=== 5. 导入中心 ===")
        page.click('.el-menu-item:has-text("导入中心")')
        page.wait_for_url("**/#/imports", timeout=10000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(700)
        tabs_text = page.locator(".el-tabs__nav").first.inner_text()
        has_all = all(k in tabs_text for k in ["商品导入", "SKU 库存导入", "平台字段映射导入", "经营数据导入"])
        check("导入中心包含 4 类导入", has_all, tabs_text.replace("\n", " "))
        shot(page, "08-imports")

        # ---------------------------------------------------------- 6. 店铺
        print("\n=== 6. 店铺列表与详情 ===")
        page.click('.el-menu-item:has-text("店铺列表")')
        page.wait_for_url("**/#/stores", timeout=10000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        store_rows = page.locator(".el-table__body tbody tr").count()
        check("店铺列表有数据", store_rows > 0, f"行数={store_rows}")
        shot(page, "09-stores")

        if store_rows:
            page.locator(".el-table__body tbody tr").first.locator(".el-link").first.click()
            page.wait_for_url("**/#/stores/*", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(900)
            check("店铺详情渲染", page.locator("text=库存概览") .count() > 0 or
                  page.locator(".stat-label").count() > 0)
            shot(page, "10-store-detail")

        # ---------------------------------------------------------- 7. 设置页
        print("\n=== 7. 系统设置 ===")
        page.click('.el-menu-item:has-text("系统设置")')
        page.wait_for_url("**/#/settings", timeout=10000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        settings_text = page.locator(".el-tabs__nav").first.inner_text()
        check(
            "设置页包含四类配置",
            all(k in settings_text for k in ["模型配置", "任务队列配置", "用户角色", "系统参数"]),
            settings_text.replace("\n", " "),
        )
        shot(page, "11-settings")

        # ------------------------------------------------------ 8. 只读角色
        print("\n=== 8. 查看人员（只读） ===")
        context2 = browser.new_context(viewport={"width": 1600, "height": 1000})
        page2 = context2.new_page()
        page2.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        login(page2, "viewer", "viewer123")
        page2.wait_for_timeout(1200)
        viewer_text = page2.locator("body").inner_text()
        check("viewer 看不到「创建演示数据」", "创建演示数据" not in viewer_text)
        shot(page2, "12-dashboard-viewer")

        page2.goto(f"{BASE}/#/products", wait_until="networkidle")
        page2.wait_for_timeout(1000)
        viewer_products = page2.locator("body").inner_text()
        check("viewer 看不到「创建商品」按钮", "创建商品" not in viewer_products)

        page2.goto(f"{BASE}/#/settings", wait_until="networkidle")
        page2.wait_for_timeout(1000)
        viewer_settings = page2.locator("body").inner_text()
        check(
            "viewer 看不到「创建用户」按钮",
            "创建用户" not in viewer_settings,
            "只读角色不应看到用户管理写操作",
        )
        shot(page2, "13-settings-viewer")
        context2.close()

        browser.close()

    # ------------------------------------------------------------ 汇总
    # 过滤掉浏览器对 favicon 之类的无关报错
    real_errors = [
        e
        for e in console_errors
        if "favicon" not in e.lower() and "Failed to load resource" not in e
    ]
    print("\n=== 9. 控制台错误 ===")
    check("前端无控制台错误", not real_errors, "; ".join(real_errors[:4]))

    print("\n" + "=" * 60)
    print(f"UI 检查：通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        print("\n失败明细：")
        for name, detail in FAILED:
            print(f"  - {name}: {detail}")
    print(f"截图目录：{SHOTS}")
    print("=" * 60)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
