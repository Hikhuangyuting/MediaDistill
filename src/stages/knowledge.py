from __future__ import annotations

from src.core.cache import valid_json
from src.core.config import Settings
from src.core.errors import PipelineError, WaitingForAgent
from src.core.models import PipelineType
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, read_json, write_json
from src.knowledge.schemas import validate_knowledge
from src.stages.speech import COVERAGE_RATIO, speech_cache_valid
from src.vision.value_gate import filter_valuable_vision


def run_text_analysis(settings: Settings, asset_id: str) -> str:
    wp = WorkspacePaths(settings, asset_id)
    ensure_dir(wp.summary_dir)
    if not speech_cache_valid(settings, asset_id):
        raise PipelineError(
            reason="Transcript 覆盖不足，无法做可靠文本分析",
            missing=f"coverage ≥ {COVERAGE_RATIO:.0%} 的 transcript/full.json",
            recovery=[f"python run.py --asset {asset_id} --force speech"],
            asset_id=asset_id,
        )
    transcript = read_json(wp.transcript_full)
    segments = transcript.get("segments", [])
    chapters = _chapterize(segments, chunk_sec=300.0)
    payload = {
        "asset_id": asset_id,
        "language": transcript.get("language"),
        "chapter_count": len(chapters),
        "chapters": chapters,
        "full_text_preview": (transcript.get("text") or "")[:1500],
    }
    write_json(wp.text_analysis, payload)
    return f"文本分析章节: {len(chapters)}"


def run_knowledge_extraction(settings: Settings, asset_id: str) -> str:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    ensure_dir(wp.knowledge_dir)
    ensure_dir(wp.summary_dir)
    ensure_dir(wp.agent_tasks_dir)

    # Audio-hard gate: incomplete speech blocks knowledge completion
    if not speech_cache_valid(settings, asset_id):
        raise PipelineError(
            reason="Transcript 覆盖不足，Knowledge 不得标记完成",
            missing=f"coverage ≥ {COVERAGE_RATIO:.0%} 的全片转写",
            recovery=[
                f"python run.py --asset {asset_id} --force speech",
                "完成 ASR 后再跑 Knowledge",
            ],
            asset_id=asset_id,
            stage="Knowledge Extraction",
        )

    if valid_json(wp.knowledge_json, ["asset_id", "topic", "design_principles"]):
        errors = validate_knowledge(read_json(wp.knowledge_json), settings)
        if not errors:
            _ensure_course_summary(wp)
            return "知识库已存在且通过校验"

    valuable_vision = []
    if wp.vision_dir.exists():
        raw = []
        for path in sorted(wp.vision_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            raw.append(read_json(path))
        valuable_vision = filter_valuable_vision(raw)

    task_dir = ensure_dir(wp.agent_tasks_dir / "knowledge")
    task_path = task_dir / "TASK.md"
    prompt = _read_prompt(settings, "03_knowledge_extract.md")
    synth_prompt = _read_prompt(settings, "04_synthesis.md")

    inputs = [
        f"- transcript (PRIMARY): `workspace/{asset_id}/transcript/full.json`",
    ]
    if wp.multimodal_timeline.exists():
        inputs.append(
            f"- multimodal timeline (said 为主，seen 仅 valuable): "
            f"`workspace/{asset_id}/multimodal/timeline.json`"
        )
    if wp.text_analysis.exists():
        inputs.append(f"- text_analysis: `workspace/{asset_id}/summary/text_analysis.json`")
    if valuable_vision:
        inputs.append(
            f"- valuable vision only ({len(valuable_vision)} frames): "
            f"`workspace/{asset_id}/vision/*.json` where keep=true"
        )
    else:
        inputs.append("- valuable vision: none（不要编造画面结论）")

    body = f"""# Knowledge extraction: {asset_id}

Source: {meta.source.filename} ({meta.pipeline_type.value})

## Priority

**音频为主。** Transcript / said 是主证据。关键帧与 Vision 仅在 `keep=true` 时作为补充。
无价值视觉结果时，禁止编造 PPT/UI/Demo 结论。

## Instructions

{prompt}

## Synthesis

{synth_prompt}

## Inputs

{chr(10).join(inputs)}

## Output requirements (DesignBrain)

Write JSON to `workspace/{asset_id}/knowledge/knowledge.json` matching `config/knowledge_schema.json`.

Must include:
- design_principles / borrowable_methods / reusable_experience / designbrain_knowledge / tags

`screenshot_refs` 仅引用 keep=true 的帧；没有则 `[]`。

Also write `workspace/{asset_id}/summary/course.json`.
"""
    task_path.write_text(body, encoding="utf-8")

    if meta.pipeline_type == PipelineType.VIDEO and wp.multimodal_dir.exists():
        _build_segment_knowledge_tasks(settings, asset_id, wp)

    raise WaitingForAgent(
        message=(
            "已生成知识提炼任务（音频为主）。请在 Cursor 中执行 TASK.md，写入 knowledge JSON 后重跑 "
            f"`python run.py --asset {asset_id}`。"
        ),
        task_paths=[str(task_path.relative_to(settings.root))],
    )


def _ensure_course_summary(wp: WorkspacePaths) -> None:
    if wp.course_summary.exists():
        return
    doc = read_json(wp.knowledge_json)
    write_json(
        wp.course_summary,
        {
            "title": doc.get("topic") or wp.asset_id,
            "core_ideas": [doc.get("core_problem", ""), doc.get("design_approach", "")],
            "principles": doc.get("design_principles", []),
            "methods": doc.get("borrowable_methods", []),
            "practices": doc.get("interaction_patterns", []),
            "cases": doc.get("components", []),
            "insights": [doc.get("my_reflection", "")],
            "ai_summary": doc.get("designbrain_knowledge", ""),
        },
    )


def _build_segment_knowledge_tasks(settings: Settings, asset_id: str, wp: WorkspacePaths) -> None:
    seg_root = wp.multimodal_dir / "segments"
    if not seg_root.exists():
        return
    prompt = _read_prompt(settings, "01_segment_analysis.md")
    for path in sorted(seg_root.glob("*.json"))[:30]:
        data = read_json(path)
        # Skip units with neither said nor valuable seen
        if not (data.get("said") or "").strip() and data.get("vision_status") != "present":
            continue
        uid = data.get("unit_id", path.stem)
        out = wp.knowledge_dir / "segments" / f"{uid}.json"
        if out.exists():
            continue
        task_dir = ensure_dir(wp.agent_tasks_dir / "knowledge_segments" / uid)
        task = task_dir / "TASK.md"
        task.write_text(
            f"""# Segment knowledge: {uid}

## Instructions
{prompt}

## Content (audio-first)
Said: {data.get("said", "")}
Seen (only if valuable): {data.get("seen", "")}
speech_status: {data.get("speech_status")}
vision_status: {data.get("vision_status")}

## Output
Write JSON to `workspace/{asset_id}/knowledge/segments/{uid}.json`
""",
            encoding="utf-8",
        )


def _read_prompt(settings: Settings, name: str) -> str:
    path = settings.root / "config" / "prompts" / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"(missing prompt: {name})"


def _chapterize(segments: list[dict], chunk_sec: float) -> list[dict]:
    if not segments:
        return []
    chapters = []
    bucket: list[dict] = []
    start = float(segments[0].get("start", 0))
    for s in segments:
        t = float(s.get("start", 0))
        if bucket and t - start >= chunk_sec:
            chapters.append(_chapter_row(len(chapters) + 1, bucket))
            bucket = []
            start = t
        bucket.append(s)
    if bucket:
        chapters.append(_chapter_row(len(chapters) + 1, bucket))
    return chapters


def _chapter_row(index: int, bucket: list[dict]) -> dict:
    text = " ".join(s.get("text", "") for s in bucket).strip()
    start = float(bucket[0].get("start", 0))
    end = float(bucket[-1].get("end", start))
    title = ""
    for sep in ("。", "！", "？", ",", "，"):
        if sep in text[:60]:
            title = text.split(sep, 1)[0][:36]
            break
    if not title:
        title = text[:36]
    return {
        "chapter_id": f"ch_{index:02d}",
        "title": title,
        "start_sec": start,
        "end_sec": end,
        "summary": text[:500],
        "topics": _guess_topics(text),
    }


def _guess_topics(text: str) -> list[str]:
    keywords = ["设计", "交互", "体验", "AI", "Agent", "审美", "组件", "系统", "原则", "方法"]
    return [k for k in keywords if k.lower() in text.lower()][:6]
