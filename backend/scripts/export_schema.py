"""从 SQLAlchemy 模型导出 schema.sql。

模型是唯一事实来源（source of truth），本脚本把 DDL 导出成可读的 SQL 文件，
便于课程验收时直接查看表结构、或在其它工具中建库。

用法：

    cd backend
    ../.venv/Scripts/python.exe scripts/export_schema.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app import models  # noqa: E402,F401  导入以注册全部表
from app.database import Base  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "schema.sql"

HEADER = """-- ============================================================================
-- 电商运营助手 · 数据库结构（SQLite）
-- ============================================================================
-- 本文件由 backend/scripts/export_schema.py 从 SQLAlchemy 模型自动导出，
-- 模型（backend/app/models/）是唯一事实来源，请勿手工修改本文件后直接使用；
-- 如需调整表结构，请修改模型后重新执行：
--
--     cd backend && ../.venv/Scripts/python.exe scripts/export_schema.py
--
-- 应用启动时会自动建表（Base.metadata.create_all），本文件用于：
--   1) 课程验收时直接查看表结构
--   2) 在其它工具或环境中手工建库
--
-- 生成时间：{generated_at}
-- 表数量：{table_count}
-- ============================================================================

PRAGMA foreign_keys = ON;

"""

FOOTER = """
-- ============================================================================
-- 种子数据（演示账号 + 系统默认参数）
-- ============================================================================
-- 说明：密码使用 PBKDF2-SHA256（10 万次迭代）哈希，盐值随机，
-- 因此下方不提供固定哈希值；请通过应用启动自动写入，或执行：
--
--     cd backend && ../.venv/Scripts/python.exe scripts/init_db.py
--
-- 默认演示账号：
--   admin    / admin123      管理员
--   operator / operator123   运营人员
--   viewer   / viewer123     查看人员
--
-- 一键生成完整演示数据（店铺、商品、竞品、方案、素材、投放、经营数据、复盘）：
--   POST /api/v1/workspace/demo-data   （需 admin 登录）
-- ============================================================================
"""


def main() -> int:
    # 用内存库导出 DDL，不触碰真实数据文件
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    parts: list[str] = []
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(engine)).strip()
        parts.append(f"{ddl};\n")

        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            parts.append(f"{str(CreateIndex(index).compile(engine)).strip()};\n")

        parts.append("\n")

    tables = sorted(Base.metadata.tables.keys())
    header = HEADER.format(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        table_count=len(tables),
    )
    listing = "-- 表清单：\n" + "".join(f"--   {i:2d}. {name}\n" for i, name in enumerate(tables, 1))
    listing += "\n"

    OUTPUT.write_text(header + listing + "".join(parts) + FOOTER, encoding="utf-8")
    print(f"已导出 {len(tables)} 张表 -> {OUTPUT}")
    for i, name in enumerate(tables, 1):
        print(f"  {i:2d}. {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
