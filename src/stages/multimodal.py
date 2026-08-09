from __future__ import annotations

from src.core.config import Settings
from src.core.paths import WorkspacePaths
from src.multimodal.merge import merge_multimodal
from src.stages.speech import media_duration_for_asset


def run_multimodal_merge(settings: Settings, asset_id: str) -> str:
    wp = WorkspacePaths(settings, asset_id)
    duration = media_duration_for_asset(settings, asset_id)
    # Ensure frame transcript windows are current before merge
    if wp.frames_manifest.exists() and wp.transcript_full.exists():
        from src.core.utils import read_json
        from src.video.frame_extract import attach_transcript_windows

        attach_transcript_windows(wp.frames_manifest, read_json(wp.transcript_full))
    payload = merge_multimodal(
        wp.transcript_full,
        wp.vision_dir,
        wp.scenes_json,
        wp.multimodal_dir,
        duration_sec=duration,
    )
    return (
        f"融合单元: {payload['count']}；"
        f"said={payload['units_with_said']}；"
        f"valuable_seen={payload['units_with_valuable_seen']}；"
        f"speech_coverage={payload['speech_coverage_ratio']:.0%}"
    )
