from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, read_json, write_json

LOW_VALUE_THRESHOLD = 0.65


def _load_segment_knowledge(seg_dir: Path) -> dict | None:
    path = seg_dir / "knowledge.json"
    if not path.exists():
        return None
    return read_json(path)


def build_review_queue(settings: Settings, asset_id: str | None = None) -> dict:
    registry = AssetRegistry(settings)
    review_dir = ensure_dir(settings.paths.review)
    assets = (
        [asset_id] if asset_id else [p.name for p in settings.paths.assets.iterdir() if p.is_dir()]
    )

    queue: list[dict] = []
    for aid in sorted(assets):
        seg_root = registry.segments_dir(aid)
        if not seg_root.exists():
            continue
        for seg_dir in sorted(seg_root.iterdir()):
            if not seg_dir.is_dir():
                continue
            data = _load_segment_knowledge(seg_dir)
            if not data:
                continue
            score = float(data.get("low_value_score", 0))
            if score < LOW_VALUE_THRESHOLD:
                continue
            queue.append(
                {
                    "asset_id": aid,
                    "segment_id": seg_dir.name,
                    "low_value_score": score,
                    "low_value_reason": data.get("low_value_reason", ""),
                    "topic": data.get("topic", ""),
                    "recommendation": "review",
                    "note": "Recommendation only — no auto skip",
                }
            )

    payload = {
        "threshold": LOW_VALUE_THRESHOLD,
        "count": len(queue),
        "items": queue,
    }
    write_json(review_dir / "segment_review.json", payload)
    _write_markdown(review_dir / "segment_review.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Segment review queue",
        "",
        f"Threshold: {payload['threshold']} (recommendation only, no auto skip)",
        "",
        f"Items: {payload['count']}",
        "",
    ]
    for item in payload.get("items", []):
        lines.append(
            f"- **{item['asset_id']}** / `{item['segment_id']}` "
            f"(score {item['low_value_score']:.2f}): {item.get('low_value_reason') or item.get('topic', '')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
