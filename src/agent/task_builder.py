from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.models import PipelineType
from src.core.registry import AssetRegistry
from src.core.utils import read_json


def _read_prompt(settings: Settings, name: str) -> str:
    path = settings.root / "config" / "prompts" / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"(missing prompt: {name})"


def build_segment_task(
    asset_id: str,
    segment_id: str,
    settings: Settings,
) -> Path:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    seg_dir = registry.segment_dir(asset_id, segment_id)
    task_dir = registry.agent_tasks_dir(asset_id) / "segment" / segment_id
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / "TASK.md"

    prompt_name = (
        "video_segment_analyze.md"
        if meta.pipeline_type == PipelineType.VIDEO
        else "audio_segment_analyze.md"
    )
    prompt = _read_prompt(settings, prompt_name)

    speech_path = seg_dir / "speech.json"
    speech_block = ""
    if speech_path.exists():
        speech = read_json(speech_path)
        speech_block = f"\n\n## Transcript\n\n{speech.get('text', '')}\n"

    frames = sorted(seg_dir.glob("frames/frame_*.jpg"))
    frames_block = "\n".join(f"- `{f.relative_to(settings.root)}`" for f in frames)

    body = f"""# Segment analysis: {segment_id}

Asset: `{asset_id}` ({meta.pipeline_type.value})

## Instructions

{prompt}

## Inputs

- Segment folder: `workspace/{asset_id}/segments/{segment_id}/`
- Speech: `speech.json`{speech_block}
- Frames:
{frames_block or "- (none)"}

## Output

Write JSON to `workspace/{asset_id}/segments/{segment_id}/knowledge.json` matching `config/segment_schema.json`.
"""
    task_path.write_text(body, encoding="utf-8")
    return task_path


def build_synthesis_task(asset_id: str, settings: Settings) -> Path:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    task_dir = registry.agent_tasks_dir(asset_id) / "synthesis"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / "TASK.md"
    prompt = _read_prompt(settings, "knowledge_synthesize.md")

    body = f"""# Knowledge synthesis: {asset_id}

Source: {meta.source.filename} ({meta.pipeline_type.value})

## Instructions

{prompt}

## Inputs

- Segment knowledge under `workspace/{asset_id}/segments/*/knowledge.json`
- Transcript: `workspace/{asset_id}/transcript/full.json`
- Multimodal: `workspace/{asset_id}/multimodal/timeline.json`

## Output

Write consolidated JSON to `workspace/{asset_id}/knowledge/knowledge.json` matching `config/knowledge_schema.json`.
"""
    task_path.write_text(body, encoding="utf-8")
    return task_path
