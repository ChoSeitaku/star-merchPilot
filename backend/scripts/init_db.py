"""数据库初始化脚本（独立于 Web 服务）。

用途：
- 新环境首次准备数据库（建表 + 种子账号 + 系统默认参数）
- 需要重置数据时用 ``--reset`` 清空重建

用法：

    cd backend
    ../.venv/Scripts/python.exe scripts/init_db.py            # 建表 + 种子
    ../.venv/Scripts/python.exe scripts/init_db.py --reset    # 删库重建
    ../.venv/Scripts/python.exe scripts/init_db.py --demo     # 建表后再生成演示数据
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许直接以脚本方式运行（把 backend 目录加入模块搜索路径）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.database import engine, init_db, session_scope  # noqa: E402
from app.seed import DEFAULT_USERS, run_seed  # noqa: E402


def reset_database() -> None:
    """删除 SQLite 文件与生成素材，然后重建。"""
    from sqlalchemy import inspect

    db_path = settings.storage_dir / "app.db"
    engine.dispose()

    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()
            print(f"  已删除 {candidate.name}")

    assets = settings.assets_dir
    if assets.exists():
        import shutil

        shutil.rmtree(assets)
        print("  已清空 storage/assets")

    settings.ensure_dirs()
    init_db()
    print(f"  数据库已重建：{db_path}")

    with engine.connect() as conn:
        tables = sorted(inspect(conn).get_table_names())
    print(f"  共 {len(tables)} 张表")


def main() -> int:
    parser = argparse.ArgumentParser(description="电商运营助手数据库初始化")
    parser.add_argument("--reset", action="store_true", help="删除现有数据库后重建")
    parser.add_argument("--demo", action="store_true", help="初始化后生成演示数据")
    args = parser.parse_args()

    settings.ensure_dirs()

    print("=" * 58)
    print("电商运营助手 · 数据库初始化")
    print("=" * 58)
    print(f"数据库：{settings.database_url}")
    print(f"存储目录：{settings.storage_dir}")
    print()

    if args.reset:
        print("[1/3] 重置数据库…")
        reset_database()
    else:
        print("[1/3] 建表（幂等）…")
        init_db()
        print("  完成")

    print("[2/3] 写入种子数据（演示账号 + 系统默认参数）…")
    run_seed()
    for username, _password, display_name, role in DEFAULT_USERS:
        print(f"  - {username:10s} {display_name:8s} 角色={role}")
    print("  完成")

    if args.demo:
        print("[3/3] 生成演示数据…")
        from app.services import demo_service

        db = session_scope()
        try:
            result = demo_service.create_demo_data(db, force=args.reset)
            if result.get("created"):
                print(f"  店铺 ID={result['store_id']} 商品 ID={result['product_id']}")
                for key, value in result["counts"].items():
                    print(f"    {key}: {value}")
            else:
                print(f"  {result['message']}")
        finally:
            db.close()
    else:
        print("[3/3] 跳过演示数据（如需生成请加 --demo）")

    print()
    print("=" * 58)
    print("初始化完成。启动服务：")
    print("  cd backend")
    print("  ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8004")
    print("然后访问 http://127.0.0.1:8004  （接口文档 /docs）")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    sys.exit(main())
