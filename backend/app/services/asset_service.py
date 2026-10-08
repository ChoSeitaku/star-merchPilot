"""素材文件生成（演示用占位素材）。

第一版不接入真实图像/视频模型，改为生成确定性的 SVG 占位素材：
- 图片素材：带方案标题、方向、卖点文案的版式示意
- 视频素材：一张 SVG 海报 + ``duration_sec`` 时长字段

这样做的好处是离线可跑、结果稳定、便于课程演示；
真实生成只需替换 ``render_asset_file``，其余链路（任务、事件、落库、审核）完全复用。
"""

from __future__ import annotations

import html
from pathlib import Path

from ..config import settings

# 不同用途使用不同的配色，便于在素材库里一眼区分
_SCENE_COLORS = {
    "主图": ("#1f6feb", "#0b3d91", "#e8f1ff"),
    "短视频": ("#d97706", "#7c2d12", "#fff7ed"),
    "详情页": ("#059669", "#064e3b", "#ecfdf5"),
    "投放素材": ("#7c3aed", "#4c1d95", "#f5f3ff"),
}
_DEFAULT_COLORS = ("#475569", "#1e293b", "#f1f5f9")


def _colors(scene: str) -> tuple[str, str, str]:
    return _SCENE_COLORS.get(scene or "", _DEFAULT_COLORS)


def _wrap_text(text: str, width: int) -> list[str]:
    """按显示宽度粗略折行（中文按 2 个宽度计）。"""
    lines: list[str] = []
    current = ""
    current_w = 0
    for ch in text:
        ch_w = 2 if ord(ch) > 0x2E80 else 1
        if current_w + ch_w > width and current:
            lines.append(current)
            current, current_w = ch, ch_w
        else:
            current += ch
            current_w += ch_w
    if current:
        lines.append(current)
    return lines or [""]


def render_image_svg(
    *,
    product_name: str,
    direction_title: str,
    core_copy: str,
    highlight: str,
    width: int = 800,
    height: int = 800,
    scene: str = "主图",
    version_no: int = 1,
) -> str:
    primary, dark, light = _colors(scene)
    title_lines = _wrap_text(direction_title, 30)
    copy_lines = _wrap_text(core_copy, 24)

    parts: list[str] = []
    y = 210
    for line in title_lines:
        parts.append(
            f'<text x="{width / 2}" y="{y}" text-anchor="middle" font-size="30" '
            f'font-weight="700" fill="#0f172a">{html.escape(line)}</text>'
        )
        y += 42
    y += 20
    for line in copy_lines:
        parts.append(
            f'<text x="{width / 2}" y="{y}" text-anchor="middle" font-size="24" '
            f'fill="{dark}">{html.escape(line)}</text>'
        )
        y += 36

    product_lines = _wrap_text(product_name, 26)
    py = height - 150
    product_parts = []
    for line in product_lines[:2]:
        product_parts.append(
            f'<text x="{width / 2}" y="{py}" text-anchor="middle" font-size="26" '
            f'font-weight="600" fill="#ffffff">{html.escape(line)}</text>'
        )
        py += 36

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{light}"/>
      <stop offset="100%" stop-color="#ffffff"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <rect x="24" y="24" width="{width - 48}" height="{height - 48}" rx="18"
        fill="none" stroke="{primary}" stroke-width="3" stroke-dasharray="10 8"/>
  <circle cx="{width / 2}" cy="120" r="52" fill="{primary}" opacity="0.14"/>
  <text x="{width / 2}" y="132" text-anchor="middle" font-size="30" font-weight="700"
        fill="{primary}">{html.escape(scene)}</text>
  <text x="{width / 2}" y="176" text-anchor="middle" font-size="18"
        fill="#64748b">素材版本 v{version_no} · 模拟生成占位图</text>
  {''.join(parts)}
  <rect x="0" y="{height - 210}" width="{width}" height="210" fill="{dark}"/>
  <text x="{width / 2}" y="{height - 172}" text-anchor="middle" font-size="18"
        fill="#ffffff" opacity="0.75">突出卖点：{html.escape(highlight)}</text>
  {''.join(product_parts)}
  <text x="{width / 2}" y="{height - 34}" text-anchor="middle" font-size="16"
        fill="#ffffff" opacity="0.6">电商运营助手 · 占位素材（非真实生成结果）</text>
</svg>
"""


def render_video_svg(
    *,
    product_name: str,
    script_title: str,
    hook: str,
    cta: str,
    duration_sec: float,
    width: int = 720,
    height: int = 1280,
    scene: str = "短视频",
    version_no: int = 1,
) -> str:
    """视频素材的海报帧（真实视频由后续接入的模型产出）。"""
    primary, dark, light = _colors(scene)
    hook_lines = _wrap_text(hook, 18)
    title_lines = _wrap_text(script_title, 22)

    hook_parts = []
    y = 380
    for line in hook_lines:
        hook_parts.append(
            f'<text x="{width / 2}" y="{y}" text-anchor="middle" font-size="44" '
            f'font-weight="700" fill="#0f172a">{html.escape(line)}</text>'
        )
        y += 62

    title_parts = []
    ty = 300
    for line in title_lines:
        title_parts.append(
            f'<text x="{width / 2}" y="{ty}" text-anchor="middle" font-size="24" '
            f'fill="{dark}">{html.escape(line)}</text>'
        )
        ty += 34

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="vbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{light}"/>
      <stop offset="100%" stop-color="#ffffff"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#vbg)"/>
  <rect x="20" y="20" width="{width - 40}" height="{height - 40}" rx="20"
        fill="none" stroke="{primary}" stroke-width="3" stroke-dasharray="12 9"/>
  <circle cx="{width / 2}" cy="200" r="70" fill="{primary}" opacity="0.16"/>
  <polygon points="{width / 2 - 22},{168} {width / 2 - 22},{232} {width / 2 + 30},{200}"
           fill="{primary}"/>
  <text x="{width / 2}" y="262" text-anchor="middle" font-size="20"
        fill="#64748b">{duration_sec:.0f} 秒 · 视频海报帧 · 模拟生成</text>
  {''.join(title_parts)}
  {''.join(hook_parts)}
  <rect x="60" y="{height - 320}" width="{width - 120}" height="200" rx="16"
        fill="{dark}" opacity="0.94"/>
  <text x="{width / 2}" y="{height - 262}" text-anchor="middle" font-size="20"
        fill="#ffffff" opacity="0.8">转化引导</text>
  <text x="{width / 2}" y="{height - 200}" text-anchor="middle" font-size="26"
        font-weight="600" fill="#ffffff">{html.escape(cta[:18])}</text>
  <text x="{width / 2}" y="{height - 90}" text-anchor="middle" font-size="22"
        font-weight="600" fill="#0f172a">{html.escape(product_name[:22])}</text>
  <text x="{width / 2}" y="{height - 52}" text-anchor="middle" font-size="16"
        fill="#64748b">素材版本 v{version_no}</text>
</svg>
"""


def asset_file_path(job_id: int, filename: str) -> Path:
    folder = settings.assets_dir / f"job_{job_id}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def write_asset_file(job_id: int, filename: str, content: str) -> tuple[Path, str]:
    """写入素材文件，返回 (磁盘路径, 对外访问 URL)。"""
    path = asset_file_path(job_id, filename)
    path.write_text(content, encoding="utf-8")
    rel = path.relative_to(settings.storage_dir).as_posix()
    return path, f"/static/{rel}"


def delete_asset_files(job_id: int) -> None:
    folder = settings.assets_dir / f"job_{job_id}"
    if not folder.exists():
        return
    for child in folder.iterdir():
        if child.is_file():
            child.unlink(missing_ok=True)
    folder.rmdir()
