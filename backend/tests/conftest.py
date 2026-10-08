"""测试夹具。

使用独立的临时 SQLite 文件库，并覆盖 FastAPI 的 ``get_db`` 依赖，
同时屏蔽掉 lifespan 中的后台工作进程，避免测试相互干扰。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

# 让测试能直接 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app import models  # noqa: E402,F401  导入以注册全部表
from app.database import Base, get_db  # noqa: E402
from app.seed import seed_all  # noqa: E402


@pytest.fixture()
def db(tmp_path) -> Iterator[Session]:
    """每个测试一个**全新的临时数据库**，测试结束后销毁。

    为什么不是「共用库 + 事务回滚」：SQLite 的 pysqlite 驱动有自己的隐式事务控制，
    与 SAVEPOINT 组合时隔离并不可靠（实测会出现测试间数据串扰）。
    每个测试建一个新库代价很小（约几十毫秒），换来的是完全确定的结果。
    """
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSession()
    seed_all(session)

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db, monkeypatch) -> Iterator[TestClient]:
    """覆盖 get_db 并禁用后台工作进程的测试客户端。"""
    from app.main import create_app
    from app.worker import worker_manager

    # 测试中不启动后台轮询，任务状态由测试直接驱动
    async def _noop_start() -> None:
        return None

    async def _noop_stop() -> None:
        return None

    monkeypatch.setattr(worker_manager, "start", _noop_start)
    monkeypatch.setattr(worker_manager, "stop", _noop_stop)

    # 不允许测试写真实的 storage 目录
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.run_seed", lambda: None)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ------------------------------------------------------------------ 便捷登录
def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(client: TestClient, role: str = "admin") -> dict[str, str]:
    credentials = {
        "admin": ("admin", "admin123"),
        "operator": ("operator", "operator123"),
        "viewer": ("viewer", "viewer123"),
    }[role]
    return {"Authorization": f"Bearer {_login(client, *credentials)}"}


@pytest.fixture()
def admin_headers(client) -> dict[str, str]:
    return auth_headers(client, "admin")


@pytest.fixture()
def operator_headers(client) -> dict[str, str]:
    return auth_headers(client, "operator")


@pytest.fixture()
def viewer_headers(client) -> dict[str, str]:
    return auth_headers(client, "viewer")


@pytest.fixture()
def sample_store(client, admin_headers) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={"store_name": "测试店铺", "platform": "taobao", "owner_name": "测试员"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def sample_product(client, operator_headers, sample_store) -> dict:
    response = client.post(
        "/api/v1/products",
        json={
            "store_id": sample_store["id"],
            "name": "测试商品 双肩包",
            "platform": "taobao",
            "category": "箱包",
            "price": 199.0,
            "cost": 86.0,
            "target_audience": "通勤上班族",
            "selling_points": "轻量,防泼水,大容量",
            "status": "active",
        },
        headers=operator_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()
