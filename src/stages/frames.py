from __future__ import annotations

import shutil
from pathlib import Path

from src.core.cache import valid_json
from src.core.config import Settings
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.utils import read_json
from src.video.frame_extract import extract_keyframes
from src.video.scene_detect import detect_scenes


def run_scene_detect(settings: Settings, asset_id: str) -> str:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)

    speech_boundaries = None
    if wp.boundaries.exists():
        speech_boundaries = read_json(wp.boundaries).get("segments") or []

    payload = detect_scenes(
        Path(meta.source.filepath),
        wp.scenes_json,
        settings,
        speech_boundaries=speech_boundaries,
    )
    method = payload.get("method") or (
        payload["scenes"][0].get("method", "?") if payload["scenes"] else "n/a"
    )
    note = ""
    if payload.get("degraded"):
        note = f"；降级原因={payload.get('fallback_reason')}"
    return (
        f"场景数: {payload['count']}（method={method}，"
        f"coverage_ok={payload.get('coverage_ok')}{note}）"
    )


def run_extract_frames(settings: Settings, asset_id: str) -> str:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    scenes: list[dict] = []
    scene_times: list[float] = []
    if valid_json(wp.scenes_json, ["scenes"]):
        scenes = read_json(wp.scenes_json).get("scenes", [])
        scene_times = [float(s["start_sec"]) for s in scenes]

    transcript = None
    if wp.transcript_full.exists():
        transcript = read_json(wp.transcript_full)

    old_signature = None
    if wp.frames_manifest.exists():
        old = read_json(wp.frames_manifest)
        old_signature = [
            (f.get("frame_id"), f.get("time_sec"), f.get("scene_id")) for f in old.get("frames", [])
        ]

    manifest = extract_keyframes(
        Path(meta.source.filepath),
        wp.frames_dir,
        settings,
        scene_times,
        scenes,
        transcript=transcript,
    )
    nonempty = sum(
        1 for f in manifest.get("frames", []) if (f.get("transcript_window") or {}).get("text")
    )
    new_signature = [
        (f.get("frame_id"), f.get("time_sec"), f.get("scene_id"))
        for f in manifest.get("frames", [])
    ]
    if old_signature is not None and old_signature != new_signature:
        _invalidate_after_frames(settings, wp, asset_id)
    return f"关键帧: {manifest['count']} 张；transcript_window 非空 {nonempty}"


def _invalidate_after_frames(settings: Settings, wp: WorkspacePaths, asset_id: str) -> None:
    """Frame identity changed: prevent stale vision/knowledge/exports from being reused."""
    for path in (
        wp.vision_dir / "_stage_done.json",
        wp.vision_dir / "frame_index.json",
        wp.multimodal_timeline,
        wp.knowledge_json,
        wp.course_summary,
        settings.paths.output_markdown / f"{asset_id}.md",
    ):
        if path.exists() and path.is_file():
            path.unlink()
    for path in (
        wp.multimodal_dir / "segments",
        wp.agent_tasks_dir / "vision",
        wp.agent_tasks_dir / "knowledge",
        wp.agent_tasks_dir / "knowledge_segments",
    ):
        if path.exists():
            shutil.rmtree(path)
