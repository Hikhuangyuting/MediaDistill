from __future__ import annotations

from src.core.cache import valid_json
from src.core.config import Settings
from src.core.errors import PipelineError
from src.core.models import KnowledgeDoc
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, format_timestamp, read_json, write_json
from src.markdown.exporter import export_note, update_index
from src.markdown.renderer import render_course_markdown


def run_markdown(settings: Settings, asset_id: str) -> str:
    """Single DesignBrain export → output/markdown/{asset_id}.md (YAML + body)."""
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    if not valid_json(wp.knowledge_json, ["asset_id", "topic"]):
        raise PipelineError(
            reason="缺少知识库 JSON",
            missing=f"workspace/{asset_id}/knowledge/knowledge.json",
            recovery=[
                "先完成 Knowledge Extraction（Cursor Agent 写入结果）",
                f"然后: python run.py --asset {asset_id}",
            ],
            asset_id=asset_id,
        )
    doc = KnowledgeDoc.from_dict(read_json(wp.knowledge_json))
    course = read_json(wp.course_summary) if wp.course_summary.exists() else None
    chapters = _load_chapters(wp)

    if chapters:
        doc.timeline_refs = _refs_from_chapters(chapters)
        write_json(wp.knowledge_json, doc.to_dict())

    body = render_course_markdown(doc, course, chapters)
    out_dir = ensure_dir(settings.paths.output_markdown)
    out_path = out_dir / f"{asset_id}.md"
    title = doc.topic or meta.source.filename
    export_note(
        body,
        out_path,
        title=title,
        tags=doc.tags or ["designbrain", meta.pipeline_type.value],
        source=meta.source.filename,
        asset_id=asset_id,
        pipeline=meta.pipeline_type.value,
    )
    update_index(
        settings.root / "output" / "index.json",
        {
            "asset_id": asset_id,
            "title": title,
            "pipeline": meta.pipeline_type.value,
            "markdown": str(out_path.relative_to(settings.root)),
            "tags": doc.tags,
        },
    )
    done = wp.root / "export" / "markdown.done"
    ensure_dir(done.parent)
    write_json(done, {"path": str(out_path.relative_to(settings.root)), "title": title})
    return f"Markdown → {out_path.relative_to(settings.root)}"


def _load_chapters(wp: WorkspacePaths) -> list[dict] | None:
    if wp.text_analysis.exists():
        raw = read_json(wp.text_analysis).get("chapters") or []
        return [
            {
                "chapter_id": c.get("chapter_id"),
                "title": c.get("title") or _title_from_summary(c.get("summary", "")),
                "summary": (c.get("summary") or "").strip(),
                "topics": c.get("topics") or [],
                "start_sec": c.get("start_sec"),
                "end_sec": c.get("end_sec"),
            }
            for c in raw
        ]
    if wp.multimodal_timeline.exists():
        timeline = read_json(wp.multimodal_timeline).get("timeline", [])
        chapters = []
        for row in timeline:
            topics = []
            for v in row.get("vision") or []:
                for s in v.get("design_signals") or []:
                    if s and s not in topics:
                        topics.append(s)
            said = (row.get("said") or "").strip()
            chapters.append(
                {
                    "chapter_id": row.get("unit_id"),
                    "title": _title_from_summary(said),
                    "summary": said,
                    "topics": topics,
                    "start_sec": row.get("start_sec"),
                    "end_sec": row.get("end_sec"),
                }
            )
        return chapters
    return None


def _title_from_summary(text: str) -> str:
    text = (text or "").strip().replace("\n", " ")
    if not text:
        return ""
    for sep in ("。", "！", "？", ".", "!", "?"):
        if sep in text[:80]:
            return text.split(sep, 1)[0][:40]
    return text[:40]


def _refs_from_chapters(chapters: list[dict]) -> list[dict]:
    refs = []
    for ch in chapters:
        start = float(ch.get("start_sec") or 0)
        end = ch.get("end_sec")
        quote = (ch.get("summary") or "").strip()
        if not quote:
            continue
        ref = {
            "time": format_timestamp(start),
            "quote": quote,
            "segment_id": ch.get("chapter_id"),
        }
        if end is not None:
            ref["end"] = format_timestamp(float(end))
        refs.append(ref)
    return refs
