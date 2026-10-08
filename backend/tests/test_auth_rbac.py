"""认证与角色权限矩阵测试（规格 1.5.2）。"""

from __future__ import annotations

import pytest

from .conftest import auth_headers


# ------------------------------------------------------------------ 认证
def test_login_success(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "admin"
    assert "access_token" in data


def test_login_wrong_password(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_user_same_message(client):
    """用户不存在与密码错误返回同一提示，避免暴露账号是否存在。"""
    a = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    b = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_me_returns_current_user(client, admin_headers):
    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/products", "get"),
        ("/api/v1/stores", "get"),
        ("/api/v1/users", "get"),
        ("/api/v1/workspace/dashboard", "get"),
    ],
)
def test_endpoints_require_login(client, path, method):
    response = getattr(client, method)(path)
    assert response.status_code == 401


def test_invalid_token_rejected(client):
    response = client.get("/api/v1/products", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


# ------------------------------------------------------------------ 角色矩阵
def test_viewer_cannot_write(client, viewer_headers, sample_store):
    """查看人员不能执行任何写操作。"""
    cases = [
        ("post", "/api/v1/products", {"store_id": sample_store["id"], "name": "viewer 不该能建"}),
        ("post", "/api/v1/stores", {"store_name": "viewer 不该能建"}),
        ("post", f"/api/v1/stores/{sample_store['id']}/inventory-advice/generate", None),
    ]
    for method, path, payload in cases:
        response = getattr(client, method)(path, json=payload, headers=viewer_headers)
        assert response.status_code == 403, f"{path} 期望 403，实际 {response.status_code}"


def test_viewer_can_read(client, viewer_headers):
    for path in ["/api/v1/products", "/api/v1/stores", "/api/v1/workspace/dashboard"]:
        response = client.get(path, headers=viewer_headers)
        assert response.status_code == 200, path


def test_operator_cannot_manage_users(client, operator_headers):
    assert client.get("/api/v1/users", headers=operator_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/users",
            json={"username": "x", "password": "123456", "role": "viewer"},
            headers=operator_headers,
        ).status_code
        == 403
    )


def test_operator_cannot_manage_stores(client, operator_headers):
    assert (
        client.post("/api/v1/stores", json={"store_name": "x"}, headers=operator_headers).status_code
        == 403
    )


def test_operator_can_edit_business_data(client, operator_headers, sample_store):
    response = client.post(
        "/api/v1/products",
        json={"store_id": sample_store["id"], "name": "运营人员可以创建", "platform": "jd"},
        headers=operator_headers,
    )
    assert response.status_code == 201


def test_admin_can_manage_users(client, admin_headers):
    response = client.post(
        "/api/v1/users",
        json={
            "username": "newbie",
            "password": "newbie123",
            "display_name": "新同事",
            "role": "operator",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["role"] == "operator"


def test_cannot_demote_self(client, admin_headers):
    """管理员不能把自己降级，避免把自己锁在系统外。"""
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    response = client.patch(
        f"/api/v1/users/{me['id']}", json={"role": "viewer"}, headers=admin_headers
    )
    assert response.status_code == 400


def test_cannot_disable_self(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    response = client.patch(
        f"/api/v1/users/{me['id']}", json={"status": "disabled"}, headers=admin_headers
    )
    assert response.status_code == 400


def test_role_change_takes_effect_immediately(client, admin_headers):
    """角色修改后无需重新登录，下一次请求即按新角色校验。"""
    created = client.post(
        "/api/v1/users",
        json={"username": "tmpuser", "password": "tmp12345", "role": "admin"},
        headers=admin_headers,
    ).json()
    tmp_headers = auth_headers(client, "operator")  # 复用 operator 令牌不影响本用例
    tmp_token = client.post(
        "/api/v1/auth/login", json={"username": "tmpuser", "password": "tmp12345"}
    ).json()["access_token"]
    tmp_auth = {"Authorization": f"Bearer {tmp_token}"}

    # 当前是 admin，可以访问用户管理
    assert client.get("/api/v1/users", headers=tmp_auth).status_code == 200

    # 降级为 viewer 后，同一个令牌立刻失去权限
    client.patch(f"/api/v1/users/{created['id']}", json={"role": "viewer"}, headers=admin_headers)
    assert client.get("/api/v1/users", headers=tmp_auth).status_code == 403

    assert tmp_headers  # 保持 fixture 引用，避免未使用告警


def test_disabled_user_cannot_use_token(client, admin_headers):
    created = client.post(
        "/api/v1/users",
        json={"username": "tobedisabled", "password": "pass1234", "role": "operator"},
        headers=admin_headers,
    ).json()
    token = client.post(
        "/api/v1/auth/login", json={"username": "tobedisabled", "password": "pass1234"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    client.patch(
        f"/api/v1/users/{created['id']}", json={"status": "disabled"}, headers=admin_headers
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403
