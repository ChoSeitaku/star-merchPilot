"""推广链接工具：追踪码生成与点击统计。"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import PromotionLink, PromotionLinkClick

# 去除易混淆字符，便于口头/截图传递
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


def generate_tracking_code(db: Session, length: int = 10) -> str:
    """生成全局唯一的短链追踪码。"""
    for _ in range(20):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        exists = db.scalar(select(PromotionLink.id).where(PromotionLink.tracking_code == code))
        if exists is None:
            return code
    # 极端情况下退化为更长的码
    return "".join(secrets.choice(_ALPHABET) for _ in range(length + 6))


def record_click(db: Session, link: PromotionLink, client_ip: str, user_agent: str) -> None:
    db.add(
        PromotionLinkClick(
            promotion_link_id=link.id,
            client_ip=(client_ip or "")[:64],
            user_agent=(user_agent or "")[:512],
        )
    )
    link.click_count = (link.click_count or 0) + 1
    db.commit()


def click_stats(db: Session, link_ids: list[int]) -> dict[int, dict]:
    """按链接统计点击次数与最近点击时间。"""
    if not link_ids:
        return {}
    rows = db.execute(
        select(
            PromotionLinkClick.promotion_link_id,
            func.count(PromotionLinkClick.id),
            func.max(PromotionLinkClick.clicked_at),
        )
        .where(PromotionLinkClick.promotion_link_id.in_(link_ids))
        .group_by(PromotionLinkClick.promotion_link_id)
    ).all()
    return {
        link_id: {"click_records": count, "last_clicked_at": last.isoformat() if last else None}
        for link_id, count, last in rows
    }


def append_utm(url: str, utm: dict | None) -> str:
    """把 UTM 参数拼到目标链接上（用于展示真实投放链接形态）。"""
    if not utm:
        return url
    pairs = [f"{k}={v}" for k, v in utm.items() if v not in (None, "")]
    if not pairs:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{'&'.join(pairs)}"


def random_name_suffix(length: int = 4) -> str:
    return "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length))
