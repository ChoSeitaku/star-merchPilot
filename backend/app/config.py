"""应用配置。所有配置项均可通过环境变量覆盖（前缀 SM_）。"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SM_", env_file=".env", extra="ignore")

    app_name: str = "电商运营助手"
    api_prefix: str = "/api/v1"

    # 数据库：默认 SQLite 单文件，零配置
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'storage' / 'app.db').as_posix()}"

    # 运行时目录：数据库文件、生成素材、导入暂存
    storage_dir: Path = BACKEND_DIR / "storage"
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"

    # 鉴权
    jwt_secret: str = "star-merchpilot-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    token_ttl_minutes: int = 480

    # 开发期跨域来源（生产同源部署时无需 CORS）
    cors_origins: list[str] = [
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:8004",
        "http://127.0.0.1:8004",
    ]

    @property
    def assets_dir(self) -> Path:
        return self.storage_dir / "assets"

    @property
    def tmp_dir(self) -> Path:
        return self.storage_dir / "tmp"

    def ensure_dirs(self) -> None:
        for path in (self.storage_dir, self.assets_dir, self.tmp_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
