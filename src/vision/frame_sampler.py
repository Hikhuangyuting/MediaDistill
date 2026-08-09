from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.models import SegmentBoundary
from src.core.utils import ensure_dir, run_ffmpeg


def sample_segment_frames(
    video_path: Path,
    boundary: SegmentBoundary,
    frames_dir: Path,
    settings: Settings,
) -> list[Path]:
    ensure_dir(frames_dir)
    max_n = settings.vision.max_frames_per_segment
    duration = boundary.duration_sec
    if duration <= 0:
        return []

    if max_n == 1:
        offsets = [duration / 2]
    else:
        step = duration / (max_n + 1)
        offsets = [step * (i + 1) for i in range(max_n)]

    saved: list[Path] = []
    for i, offset in enumerate(offsets, start=1):
        ts = boundary.start_sec + offset
        out = frames_dir / f"frame_{i:02d}.jpg"
        args = [
            "-y",
            "-ss",
            str(ts),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out),
        ]
        result = run_ffmpeg(args)
        if result.returncode == 0 and out.exists():
            saved.append(out)
    return saved
