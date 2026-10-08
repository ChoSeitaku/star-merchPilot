"""密码哈希与访问令牌。

口令使用标准库 ``hashlib.pbkdf2_hmac``（SHA-256，10 万次迭代），
避免引入 bcrypt/passlib 在 Windows 上的编译与版本兼容问题。
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import timedelta
from typing import Any, Optional

import jwt

from .config import settings

_ALGORITHM = settings.jwt_algorithm
_ITERATIONS = 100_000
_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """返回 ``pbkdf2_sha256$迭代次数$salt_hex$hash_hex``。"""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_PREFIX}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """常量时间比较，任何格式异常都视为校验失败。"""
    try:
        prefix, iterations, salt_hex, hash_hex = stored.split("$")
        if prefix != _PREFIX:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    from .database import utcnow

    now = utcnow()
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """解码失败（过期 / 签名错误 / 格式错误）统一返回 None。"""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
