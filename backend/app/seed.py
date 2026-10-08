"""初始化种子数据（幂等）：演示账号 + 系统默认参数。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import session_scope
from .models import SystemSetting, User
from .security import hash_password

# 演示账号：用户名 / 密码 / 展示名 / 角色
DEFAULT_USERS = [
    ("admin", "admin123", "系统管理员", "admin"),
    ("operator", "operator123", "运营专员", "operator"),
    ("viewer", "viewer123", "数据查看员", "viewer"),
]

# 系统默认配置项：(key, value, value_type, category, 说明, 是否可在设置页修改)
DEFAULT_SETTINGS = [
    # 模型配置
    ("ai_provider", "mock", "string", "model", "内容生成提供方（mock=内置模拟生成）", 0),
    ("ai_model_name", "mock-merchpilot-v1", "string", "model", "模型名称（展示用）", 0),
    ("ai_temperature", "0.7", "float", "model", "生成温度（模拟生成保留占位）", 1),
    ("image_model_name", "mock-image-gen-v1", "string", "model", "图片生成模型", 0),
    ("video_model_name", "mock-video-gen-v1", "string", "model", "视频生成模型", 0),
    # 任务队列配置
    ("queue_poll_interval_sec", "2", "int", "queue", "工作进程轮询间隔（秒）", 1),
    ("queue_job_timeout_sec", "120", "int", "queue", "任务超时判定阈值（秒）", 1),
    ("queue_max_attempts", "3", "int", "queue", "任务默认最大尝试次数", 1),
    ("queue_concurrency", "1", "int", "queue", "并发执行的生成任务数", 1),
    ("queue_simulate_seconds", "4", "int", "queue", "模拟生成耗时（秒，越小演示越快）", 1),
    # 系统参数
    ("system_default_warning_threshold", "10", "int", "system", "SKU 默认库存预警阈值", 1),
    ("system_low_stock_alert_enabled", "1", "int", "system", "是否开启低库存提示", 1),
    ("system_currency", "CNY", "string", "system", "货币单位", 0),
    # 合规说明项（只读）
    ("compliance_no_plaintext_credential", "1", "int", "compliance", "平台账号不保存明文密码/令牌/Cookie", 0),
    ("compliance_no_auto_ad_execution", "1", "int", "compliance", "不自动创建广告计划、不自动扣费", 0),
    ("compliance_public_data_only", "1", "int", "compliance", "仅使用开放接口、用户授权、文件导入与公开链接", 0),
]


def seed_users(db: Session) -> None:
    for username, password, display_name, role in DEFAULT_USERS:
        exists = db.scalar(select(User).where(User.username == username))
        if exists:
            continue
        db.add(
            User(
                username=username,
                display_name=display_name,
                password_hash=hash_password(password),
                role=role,
                status="active",
            )
        )
    db.commit()


def seed_settings(db: Session) -> None:
    for key, value, value_type, category, description, editable in DEFAULT_SETTINGS:
        exists = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if exists:
            continue
        db.add(
            SystemSetting(
                key=key,
                value=value,
                value_type=value_type,
                category=category,
                description=description,
                editable=editable,
            )
        )
    db.commit()


def seed_all(db: Session) -> None:
    seed_users(db)
    seed_settings(db)


def run_seed() -> None:
    """独立会话版本的种子入口，供 lifespan / init_db.py 调用。"""
    db = session_scope()
    try:
        seed_all(db)
    finally:
        db.close()
