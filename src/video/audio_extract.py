from __future__ import annotations

from pathlib import Path

from src.core.errors import PipelineError
from src.core.utils import ensure_dir, run_ffmpeg


def extract_full_audio(source_path: Path, output_wav: Path) -> Path:
    ensure_dir(output_wav.parent)
    args = [
        "-y",
        "-i",
        str(source_path),
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
    if result.returncode != 0 or not output_wav.exists():
        raise PipelineError(
            reason="ffmpeg 抽取音频失败",
            missing="可用的 ffmpeg 与可读的源媒体文件",
            recovery=[
                "确认系统已安装 ffmpeg（ffmpeg -version）",
                f"确认源文件存在: {source_path}",
                "修复后重跑该阶段",
            ],
            detail=(result.stderr or "")[:500],
        )
    return output_wav
