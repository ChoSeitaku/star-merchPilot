"""公开链接解析（有限信息提取）。

**合规边界**（规格 1.5.12）：
- 只识别链接所属平台，并从 URL 片段中提取公开可见的有限信息；
- 不做任何网络抓取，不绕过登录、验证码、风控或访问控制；
- 真实接入时应使用平台开放接口或用户授权数据，本模块为演示占位实现。
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, urlparse

# 域名 → 平台
_DOMAIN_PLATFORM = {
    "taobao.com": "taobao",
    "tmall.com": "tmall",
    "jd.com": "jd",
    "yangkeduo.com": "pdd",
    "pinduoduo.com": "pdd",
    "douyin.com": "douyin",
    "xiaohongshu.com": "xiaohongshu",
    "xhslink.com": "xiaohongshu",
}

# 从链接中可公开读到的商品 ID 参数名
_ID_KEYS = ("id", "item_id", "itemId", "sku_id", "goods_id", "product_id")


def detect_platform(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "other"
    for domain, platform in _DOMAIN_PLATFORM.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return "other"


def extract_product_id(url: str) -> str:
    try:
        query = parse_qs(urlparse(url).query)
    except ValueError:
        return ""
    for key in _ID_KEYS:
        if key in query and query[key]:
            return str(query[key][0])[:64]
    # 兜底：从路径里找连续数字段
    match = re.search(r"/(\d{5,})", urlparse(url).path or "")
    return match.group(1) if match else ""


def _stable_digest(url: str, salt: str) -> int:
    raw = f"{url}|{salt}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def parse_public_link(url: str, *, fallback_name: str = "") -> dict:
    """从链接本身可公开获得的信息中整理出结构化结果。

    明确声明数据来源，便于界面上标注「有限信息提取」。
    """
    url = (url or "").strip()
    if not url:
        return {
            "ok": False,
            "error_message": "链接为空",
        }
    try:
        parsed = urlparse(url)
    except ValueError:
        return {"ok": False, "error_message": "链接格式无法解析"}

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return {"ok": False, "error_message": "仅支持 http/https 公开链接"}

    platform = detect_platform(url)
    product_id = extract_product_id(url)
    digest = _stable_digest(url, "price")

    # 演示用的确定性占位值：真实接入时替换为开放接口返回的公开数据
    price_hint = round(29 + (digest % 24000) / 100, 2)
    sales_hint = f"月销 {100 + digest % 4900}+"

    return {
        "ok": True,
        "platform": platform,
        "source_url": url,
        "host": parsed.hostname,
        "extracted": {
            "platform_product_id": product_id,
            "title": fallback_name or f"公开链接商品 {product_id or parsed.hostname}",
            "price": price_hint,
            "sales_hint": sales_hint,
            "main_image": "",
        },
        "data_source": "公开链接有限信息提取（未抓取页面内容）",
        "compliance_note": (
            "仅识别平台与链接中的公开参数，不做页面抓取、"
            "不绕过登录/验证码/风控；价格与销量为演示占位值，"
            "真实数据请通过平台开放接口或用户授权获取。"
        ),
    }
