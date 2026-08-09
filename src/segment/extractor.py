from __future__ import annotations

from pathlib import Path

from src.core.models import SegmentBoundary
from src.core.utils import ensure_dir, run_ffmpeg


def extract_segment_audio(
    source_path: Path,
    boundary: SegmentBoundary,
    output_wav: Path,
) -> Path:
    ensure_dir(output_wav.parent)
    start = boundary.start_sec
    duration = boundary.duration_sec
    args = [
        "-y",
        "-ss",
        str(start),
        "-i",
        str(source_path),
        "-t",
        str(duration),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_wav),
    ]
    result = run_ffmpeg(args)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg extract failed: {result.stderr}")
    return output_wav
