"""FastAPI 应用工厂。

启动顺序（很关键）：
1. lifespan：建表 → 种子数据 → 启动生成任务工作进程
2. 注册 API 路由（``/api/v1``）
3. 挂载素材静态目录（``/static``）
4. 挂载前端构建产物（``/``）+ SPA history 兜底路由（**必须最后注册**，
   否则会把 ``/api`` 与 ``/static`` 一并吞掉）

前端未构建时后端仍可独立运行，根路径会返回一段说明。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.v1.router import api_router
from .config import settings
from .database import init_db
from .seed import run_seed
from .worker import worker_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("merchpilot")

DESCRIPTION = """
面向中小电商团队的**单品运营闭环工作台**。

闭环主线：建店建档 → 录入商品 → 补充竞品 → 生成诊断 → 生成主图方案 → 生成视频脚本
→ 生成素材 → 人工审核素材 → 生成投放建议 → 人工确认 → 回填经营数据 → 生成复盘报告
→ 复盘结论回到诊断环节，形成下一轮优化闭环。

**角色权限**：`admin`（全部） / `operator`（业务编辑 + 投放确认，不能管用户与店铺） / `viewer`（只读）

**合规边界**：不保存明文密码 / 令牌 / Cookie；不实现绕过登录、验证码或风控的抓取；
投放只产出建议与实验计划，不自动创建广告计划、不自动扣费、不直接修改预算。
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    run_seed()
    logger.info("数据库已就绪：%s", settings.database_url)

    await worker_manager.start()
    try:
        yield
    finally:
        await worker_manager.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        description=DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # 1) API 路由
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/api/health", tags=["系统"], summary="健康检查")
    def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "worker": worker_manager.status(),
            "docs": "/docs",
        }

    # 2) 素材静态目录
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(settings.storage_dir)), name="static")

    # 3) 前端构建产物
    dist = settings.frontend_dist
    if dist.exists() and (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="frontend-assets")
        logger.info("已挂载前端构建产物：%s", dist)
    else:
        logger.warning("未找到前端构建产物（%s），仅提供 API。请先在 frontend 目录执行 npm run build", dist)

    # 4) SPA history 兜底（最后注册，且排除 api / static / docs 前缀）
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request):
        index = settings.frontend_dist / "index.html"
        if full_path.startswith(("api/", "static/", "docs", "redoc", "openapi.json")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            {
                "detail": "前端尚未构建",
                "hint": "请执行：cd frontend && npm install && npm run build",
                "api_docs": "/docs",
            },
            status_code=200,
        )

    return app


app = create_app()
