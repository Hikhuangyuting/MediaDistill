from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.utils import ensure_dir, slugify


def build_frontmatter(
    title: str,
    tags: list[str],
    source: str,
    asset_id: str,
    pipeline: str,
) -> str:
    tag_line = ", ".join(tags) if tags else "designbrain"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return "\n".join(
        [
            "---",
            f'title: "{_escape(title)}"',
            f"tags: [{tag_line}]",
            f'source: "{_escape(source)}"',
            f"asset_id: {asset_id}",
            f"pipeline: {pipeline}",
            f"date: {date}",
            "type: designbrain",
            "---",
            "",
        ]
    )


def export_note(
    markdown_body: str,
    output_path: Path,
    title: str,
    tags: list[str],
    source: str,
    asset_id: str,
    pipeline: str,
) -> Path:
    """写入包含 YAML frontmatter 的独立 Markdown 笔记。"""
    ensure_dir(output_path.parent)
    fm = build_frontmatter(title, tags, source, asset_id, pipeline)
    body = markdown_body
    if body.startswith("# "):
        body = body.split("\n", 1)[1].lstrip("\n")
    output_path.write_text(fm + body, encoding="utf-8")
    return output_path


def note_filename(title: str, asset_id: str) -> str:
    base = slugify(asset_id) or slugify(title) or "note"
    return f"{base}.md"


def update_index(index_path: Path, entry: dict[str, Any]) -> None:
    import json

    ensure_dir(index_path.parent)
    data = {"version": 1, "assets": []}
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    assets = [a for a in data.get("assets", []) if a.get("asset_id") != entry["asset_id"]]
    assets.append(entry)
    data["assets"] = sorted(assets, key=lambda x: x.get("asset_id", ""))
    data["count"] = len(assets)
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _escape(text: str) -> str:
    return text.replace('"', '\\"')
