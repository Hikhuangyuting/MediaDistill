from __future__ import annotations

import re
from typing import Any

# Template / boilerplate patterns that must never count as valuable vision.
_PLACEHOLDER_PATTERNS = [
    r"画面呈现\s*AI-Native",
    r"可用于知识提炼",
    r"课程片头/标题页：",
    r"讲解画面/讲者或 PPT：",
    r"界面演示/产品截图：",
    r"方法论图示：",
    r"交互细节特写：",
    r"对比/案例页：",
    r"总结/原则列表：",
    r"收尾/行动建议：",
]

_PLACEHOLDER_RE = re.compile("|".join(_PLACEHOLDER_PATTERNS))


def is_placeholder_vision(data: dict[str, Any]) -> bool:
    summary = str(data.get("summary") or "")
    if _PLACEHOLDER_RE.search(summary):
        return True
    # Generic repeated boilerplate ending
    if "相关设计信息，可用于知识提炼" in summary:
        return True
    return False


def evaluate_vision_value(data: dict[str, Any]) -> dict[str, Any]:
    """Return keep / value_score / reasons. Audio-first: only keep incremental visual value."""
    if is_placeholder_vision(data):
        return {
            "keep": False,
            "value_score": 0.0,
            "reason": "placeholder_or_template",
        }

    score = float(data.get("value_score") or 0.0)
    ocr = (data.get("ocr_text") or "").strip()
    ppt = [x for x in (data.get("ppt_points") or []) if str(x).strip()]
    ui = [x for x in (data.get("ui_elements") or []) if str(x).strip()]
    signals = [x for x in (data.get("design_signals") or []) if str(x).strip()]
    apps = [x for x in (data.get("app_hints") or []) if str(x).strip()]
    summary = (data.get("summary") or "").strip()

    # Explicit keep from agent wins only if not placeholder
    if "keep" in data and data.get("keep") is False:
        return {"keep": False, "value_score": score, "reason": "agent_keep_false"}

    if ocr and len(ocr) >= 8:
        score = max(score, 0.75)
    if len(ppt) >= 2 or len(ui) >= 2:
        score = max(score, 0.65)
    if apps:
        score = max(score, 0.7)
    if summary and len(summary) >= 40 and not is_placeholder_vision(data):
        # concrete summary without template markers
        if any(
            k in summary for k in ("PPT", "界面", "按钮", "流程图", "Figma", "Cursor", "浏览器")
        ):
            score = max(score, 0.65)

    # Prefer agent-provided score if higher and keep true
    if data.get("keep") is True and score < 0.6:
        score = max(score, 0.6)

    keep = score >= 0.6 and bool(summary or ocr or ppt or ui or apps)
    return {
        "keep": keep,
        "value_score": round(score, 3),
        "reason": "valuable" if keep else "low_value",
        "signals": signals[:8],
    }


def filter_valuable_vision(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    for item in items:
        gate = evaluate_vision_value(item)
        enriched = dict(item)
        enriched["keep"] = gate["keep"]
        enriched["value_score"] = gate["value_score"]
        enriched["value_reason"] = gate["reason"]
        if gate["keep"]:
            kept.append(enriched)
    return kept
