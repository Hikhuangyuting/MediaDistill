from __future__ import annotations

from typing import Any

from src.core.models import KnowledgeDoc
from src.core.utils import format_timestamp, read_json

REQUIRED_SECTIONS = [
    ("核心观点", "core_ideas"),
    ("设计原则", "principles"),
    ("方法论", "methods"),
    ("最佳实践", "practices"),
    ("案例", "cases"),
    ("设计启发", "insights"),
    ("AI总结", "ai_summary"),
]


def render_course_markdown(
    doc: KnowledgeDoc,
    course: dict[str, Any] | None = None,
    chapters: list[dict[str, Any]] | None = None,
) -> str:
    title = (course or {}).get("title") or doc.topic or doc.asset_id
    lines = [f"# {title}", ""]

    lines.append("## 概述")
    lines.append("")
    lines.append(doc.design_context or doc.design_approach or "_（待补充）_")
    lines.append("")

    section_data = {
        "core_ideas": _as_list(doc.core_problem) + _as_list(doc.design_approach),
        "principles": doc.design_principles,
        "methods": doc.borrowable_methods,
        "practices": doc.interaction_patterns or doc.components,
        "cases": doc.components or doc.design_systems,
        "insights": _as_list(doc.my_reflection) + _as_list(doc.reusable_experience),
        "ai_summary": doc.designbrain_knowledge or doc.reusable_experience,
    }
    if course:
        for _, key in REQUIRED_SECTIONS:
            if course.get(key):
                section_data[key] = course.get(key)

    for title_zh, key in REQUIRED_SECTIONS:
        lines.append(f"## {title_zh}")
        lines.append("")
        val = section_data.get(key)
        if isinstance(val, list):
            items = [x for x in val if x]
            if items:
                lines.extend(f"- {x}" for x in items)
            else:
                lines.append("_（待补充）_")
        else:
            lines.append(str(val or "_（待补充）_"))
        lines.append("")

    if chapters:
        lines.append("## 章节要点")
        lines.append("")
        for ch in chapters:
            cid = ch.get("chapter_id") or ch.get("unit_id") or "章节"
            ch_title = (ch.get("title") or "").strip()
            start = ch.get("start_sec")
            end = ch.get("end_sec")
            time_label = ""
            if start is not None and end is not None:
                time_label = f" `{format_timestamp(float(start))}`–`{format_timestamp(float(end))}`"
            heading = f"### {cid}"
            if ch_title:
                heading += f" {ch_title}"
            heading += time_label
            lines.append(heading)
            lines.append("")
            summary = (ch.get("summary") or "").strip()
            if summary:
                lines.append(summary)
                lines.append("")
            topics = [t for t in (ch.get("topics") or []) if t]
            if topics:
                lines.append("**要点：** " + " · ".join(topics))
                lines.append("")

    timeline_refs = list(doc.timeline_refs or [])
    if len(timeline_refs) < 2 and chapters:
        timeline_refs = _timeline_from_chapters(chapters)

    if timeline_refs:
        lines.append("## 时间轴引用")
        lines.append("")
        for ref in timeline_refs:
            t0 = ref.get("time", "")
            t1 = ref.get("end")
            time_span = f"`{t0}`–`{t1}`" if t1 else f"`{t0}`"
            seg = f" ({ref.get('segment_id')})" if ref.get("segment_id") else ""
            quote = (ref.get("quote") or "").strip()
            lines.append(f"- {time_span}{seg}")
            lines.append("")
            lines.append(f"  {quote}")
            lines.append("")

    if doc.screenshot_refs:
        lines.append("## 截图引用")
        lines.append("")
        for ref in doc.screenshot_refs:
            lines.append(
                f"- `{ref.get('time', '')}` `{ref.get('frame_id', '')}` — {ref.get('caption', '')}"
            )
        lines.append("")

    if doc.tags:
        lines.append("## 标签")
        lines.append("")
        lines.append(" ".join(f"#{t}" for t in doc.tags))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _timeline_from_chapters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for ch in chapters:
        start = float(ch.get("start_sec") or 0)
        end = ch.get("end_sec")
        quote = (ch.get("summary") or "").strip()
        if not quote:
            continue
        ref: dict[str, Any] = {
            "time": format_timestamp(start),
            "quote": quote,
            "segment_id": ch.get("chapter_id") or ch.get("unit_id"),
        }
        if end is not None:
            ref["end"] = format_timestamp(float(end))
        refs.append(ref)
    return refs


def render_from_paths(knowledge_path, course_path=None, text_analysis_path=None) -> str:
    data = read_json(knowledge_path)
    doc = KnowledgeDoc.from_dict(data)
    course = read_json(course_path) if course_path and course_path.exists() else None
    chapters = None
    if text_analysis_path and text_analysis_path.exists():
        chapters = read_json(text_analysis_path).get("chapters")
    return render_course_markdown(doc, course, chapters)


def _as_list(value: str | list | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return [str(value)]
