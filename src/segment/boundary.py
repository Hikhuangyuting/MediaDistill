from __future__ import annotations

import re
import subprocess
from pathlib import Path

from src.core.config import SegmentConfig, Settings
from src.core.models import PipelineType, SegmentBoundary
from src.core.utils import probe_media_duration_sec


def probe_duration_sec(media_path: Path) -> float:
    return probe_media_duration_sec(media_path)


def _silence_boundaries(
    media_path: Path,
    cfg: SegmentConfig,
    audio_only: bool,
) -> list[float]:
    """Return split points (seconds) from ffmpeg silencedetect."""
    noise = cfg.silence_threshold_db
    dur = cfg.silence_min_duration_sec
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(media_path),
        "-af",
        f"silencedetect=noise={noise}dB:d={dur}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = (proc.stderr or "") + (proc.stdout or "")
    points: list[float] = []
    for m in re.finditer(r"silence_end:\s*([\d.]+)", log):
        points.append(float(m.group(1)))
    return sorted(set(points))


def _scene_boundaries(video_path: Path, cfg: SegmentConfig) -> list[float]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video_path),
        "-filter:v",
        f"select=gt(scene\\,{cfg.scene_threshold}),showinfo",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stderr or ""
    points: list[float] = []
    for m in re.finditer(r"pts_time:([\d.]+)", log):
        points.append(float(m.group(1)))
    return sorted(set(points))


def _fallback_intervals(duration: float, interval: float) -> list[float]:
    points: list[float] = []
    t = interval
    while t < duration:
        points.append(t)
        t += interval
    return points


def _points_to_segments(points: list[float], duration: float, method: str) -> list[SegmentBoundary]:
    edges = [0.0] + [p for p in points if 0 < p < duration] + [duration]
    segments: list[SegmentBoundary] = []
    for i in range(len(edges) - 1):
        start, end = edges[i], edges[i + 1]
        if end <= start:
            continue
        seg_id = f"seg_{i + 1:04d}"
        segments.append(
            SegmentBoundary(segment_id=seg_id, start_sec=start, end_sec=end, method=method)
        )
    return segments


def detect_boundaries(
    media_path: Path,
    pipeline_type: PipelineType,
    settings: Settings,
) -> list[SegmentBoundary]:
    cfg = settings.segment
    duration = probe_duration_sec(media_path)
    if duration <= 0:
        return []

    if pipeline_type == PipelineType.AUDIO:
        points = _silence_boundaries(media_path, cfg, audio_only=True)
        method = "silence"
        if len(points) < 2:
            points = _fallback_intervals(duration, cfg.fallback_interval_sec)
            method = "fallback_interval"
    else:
        scene_pts = _scene_boundaries(media_path, cfg)
        silence_pts = _silence_boundaries(media_path, cfg, audio_only=False)
        points = sorted(set(scene_pts + silence_pts))
        method = "scene+silence"
        if len(points) < 2:
            points = _fallback_intervals(duration, cfg.fallback_interval_sec)
            method = "fallback_interval"

    return _points_to_segments(points, duration, method)


def boundaries_summary(segments: list[SegmentBoundary]) -> dict:
    return {
        "count": len(segments),
        "segments": [s.to_dict() for s in segments],
    }
