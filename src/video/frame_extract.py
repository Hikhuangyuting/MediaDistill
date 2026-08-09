from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from src.core.config import Settings
from src.core.errors import PipelineError
from src.core.utils import (
    ensure_dir,
    format_timestamp,
    probe_media_duration_sec,
    run_ffmpeg,
    write_json,
)


def extract_keyframes(
    video_path: Path,
    frames_dir: Path,
    settings: Settings,
    scene_times: list[float] | None = None,
    scenes: list[dict] | None = None,
    transcript: dict[str, Any] | None = None,
    window_sec: float = 15.0,
) -> dict:
    """Adaptive interval + visual-cut sampling → frames/manifest.json."""
    ensure_dir(frames_dir)
    duration = probe_media_duration_sec(video_path)
    if duration <= 0:
        raise PipelineError(
            reason="无法读取视频时长",
            missing="ffprobe 可读的视频时长",
            recovery=[f"检查文件: {video_path}", "确认 ffprobe 可用"],
        )

    configured_interval = max(1.0, float(settings.vision.keyframe_interval_sec))
    # Short, visually dense demos need much tighter coverage than long talks.
    if duration <= 120:
        interval = min(configured_interval, 3.0)
    elif duration <= 600:
        interval = min(configured_interval, 10.0)
    else:
        interval = min(configured_interval, 30.0)
    times: list[float] = []
    t = interval / 2
    while t < duration:
        times.append(round(t, 3))
        t += interval

    for st in scene_times or []:
        if 0.75 <= st < duration:
            # Scene boundaries often land on a blended transition frame.
            times.append(round(min(duration - 0.05, st + 0.4), 3))

    visual_cuts = _visual_cut_times(video_path, min(settings.segment.scene_threshold, 0.30))
    for cut in visual_cuts:
        if cut >= 0.75:
            times.append(round(min(duration - 0.05, cut + 0.4), 3))

    times = _deduplicate_times(times, min_gap_sec=0.75)
    entries = []
    for i, ts in enumerate(times, start=1):
        name = f"frame_{i:04d}.jpg"
        out = frames_dir / name
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
        if result.returncode != 0 or not out.exists():
            continue
        try:
            rel = str(out.relative_to(settings.root))
        except ValueError:
            rel = str(out)
        entry = {
            "frame_id": f"frame_{i:04d}",
            "path": rel,
            "time_sec": ts,
            "time": format_timestamp(ts),
            "scene_id": _scene_for_time(ts, scenes),
            "transcript_window": build_transcript_window(ts, transcript, window_sec),
        }
        entries.append(entry)

    candidate_count = len(entries)
    entries, rejected = _filter_frame_candidates(entries, settings.root, duration)

    if not entries:
        raise PipelineError(
            reason="未能提取任何关键帧",
            missing="可解码的视频画面",
            recovery=["确认视频编码可被 ffmpeg 读取", "降低抽帧间隔后重试"],
        )

    manifest = {
        "count": len(entries),
        "duration_sec": duration,
        "interval_sec": interval,
        "configured_interval_sec": configured_interval,
        "visual_cut_count": len(visual_cuts),
        "candidate_count": candidate_count,
        "rejected_count": len(rejected),
        "rejected": rejected,
        "strategy": "adaptive_candidates+quality_gate+perceptual_dedup",
        "frames": entries,
    }
    # Remove obsolete managed images left by an older, larger manifest.
    keep = {Path(row["path"]).name for row in entries}
    for old in frames_dir.glob("frame_*.jpg"):
        if old.name not in keep:
            old.unlink()
    write_json(frames_dir / "manifest.json", manifest)
    return manifest


def _deduplicate_times(times: list[float], min_gap_sec: float) -> list[float]:
    selected: list[float] = []
    for value in sorted(set(round(t, 3) for t in times if t >= 0)):
        if not selected or value - selected[-1] >= min_gap_sec:
            selected.append(value)
    return selected


def _visual_cut_times(video_path: Path, threshold: float) -> list[float]:
    """Detect real visual cuts independently from audio-first timeline scenes."""
    filt = f"scale=240:-1,fps=2,select='gt(scene,{threshold})',showinfo"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-an",
        "-i",
        str(video_path),
        "-vf",
        filt,
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    log = (proc.stderr or "") + (proc.stdout or "")
    return [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", log)]


def _filter_frame_candidates(
    entries: list[dict], root: Path, duration: float
) -> tuple[list[dict], list[dict]]:
    """Reject weak/duplicate candidates, then keep temporally diverse high-value frames."""
    try:
        import numpy as np
    except ImportError:
        return entries, []

    measured: list[tuple[dict, Any]] = []
    rejected: list[dict] = []
    for entry in entries:
        image_path = root / entry["path"]
        pixels = _read_gray_preview(image_path)
        if pixels is None:
            rejected.append({"frame_id": entry["frame_id"], "reason": "unreadable"})
            continue
        gx = np.abs(np.diff(pixels, axis=1))
        gy = np.abs(np.diff(pixels, axis=0))
        edge = float(((gx > 0.08).mean() + (gy > 0.08).mean()) / 2)
        lap = (
            pixels[1:-1, 1:-1] * 4
            - pixels[:-2, 1:-1]
            - pixels[2:, 1:-1]
            - pixels[1:-1, :-2]
            - pixels[1:-1, 2:]
        )
        sharpness = float(np.var(lap))
        hist = np.histogram(pixels, bins=32, range=(0, 1), density=True)[0]
        probs = hist / max(float(hist.sum()), 1e-9)
        entropy = float(-(probs[probs > 0] * np.log2(probs[probs > 0])).sum() / 5.0)
        score = min(1.0, edge * 2.4 + sharpness * 5.0 + entropy * 0.35)
        entry["quality"] = {
            "score": round(score, 3),
            "edge_density": round(edge, 4),
            "sharpness": round(sharpness, 4),
            "entropy": round(entropy, 3),
        }
        if sharpness < 0.010 or edge < 0.035:
            rejected.append({"frame_id": entry["frame_id"], "reason": "blur_or_low_information"})
            continue
        if score < 0.60:
            rejected.append({"frame_id": entry["frame_id"], "reason": "low_visual_information"})
            continue
        measured.append((entry, pixels))

    # Deduplicate nearby shots. If two frames are strongly correlated, keep the
    # clearer/more information-dense one rather than simply keeping the first.
    deduped: list[tuple[dict, Any]] = []
    for entry, pixels in measured:
        if deduped:
            prev_entry, prev_pixels = deduped[-1]
            gap = float(entry["time_sec"]) - float(prev_entry["time_sec"])
            corr = float(np.corrcoef(pixels.ravel(), prev_pixels.ravel())[0, 1])
            mae = float(np.mean(np.abs(pixels - prev_pixels)))
            if gap <= 5.0 and (corr >= 0.70 or mae <= 0.07):
                winner, loser = (
                    (entry, prev_entry)
                    if entry["quality"]["score"] > prev_entry["quality"]["score"]
                    else (prev_entry, entry)
                )
                rejected.append(
                    {
                        "frame_id": loser["frame_id"],
                        "reason": "near_duplicate",
                        "similar_to": winner["frame_id"],
                    }
                )
                if winner is entry:
                    deduped[-1] = (entry, pixels)
                continue
        deduped.append((entry, pixels))

    # Cap excessive candidates without losing timeline coverage: select the
    # strongest frame in each temporal bucket.
    max_keep = max(8, min(24, round(duration / 4)))
    if len(deduped) > max_keep:
        bucket_size = duration / max_keep
        buckets: dict[int, list[tuple[dict, Any]]] = {}
        for row in deduped:
            index = min(max_keep - 1, int(float(row[0]["time_sec"]) / bucket_size))
            buckets.setdefault(index, []).append(row)
        selected = []
        selected_ids = set()
        for rows in buckets.values():
            best = max(rows, key=lambda x: x[0]["quality"]["score"])
            selected.append(best)
            selected_ids.add(best[0]["frame_id"])
        for entry, _ in deduped:
            if entry["frame_id"] not in selected_ids:
                rejected.append(
                    {"frame_id": entry["frame_id"], "reason": "lower_value_in_time_bucket"}
                )
        deduped = sorted(selected, key=lambda x: float(x[0]["time_sec"]))

    return [entry for entry, _ in deduped], rejected


def _read_gray_preview(image_path: Path):
    try:
        import numpy as np

        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(image_path),
                "-vf",
                "scale=160:90,format=gray",
                "-f",
                "rawvideo",
                "-",
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0 or len(proc.stdout) != 160 * 90:
            return None
        return np.frombuffer(proc.stdout, dtype=np.uint8).reshape(90, 160).astype(float) / 255.0
    except (OSError, subprocess.TimeoutExpired):
        return None


def attach_transcript_windows(
    manifest_path: Path,
    transcript: dict[str, Any] | None,
    window_sec: float = 15.0,
) -> dict:
    """Update existing manifest frames with transcript_window (P0-D)."""
    from src.core.utils import read_json

    if not manifest_path.exists():
        return {}
    manifest = read_json(manifest_path)
    frames = manifest.get("frames", [])
    for frame in frames:
        ts = float(frame.get("time_sec", 0))
        frame["transcript_window"] = build_transcript_window(ts, transcript, window_sec)
    write_json(manifest_path, manifest)
    return manifest


def build_transcript_window(
    time_sec: float,
    transcript: dict[str, Any] | None,
    window_sec: float = 15.0,
) -> dict[str, Any]:
    start = max(0.0, time_sec - window_sec)
    end = time_sec + window_sec
    if not transcript:
        return {"start": start, "end": end, "text": "", "segment_count": 0}
    pieces = []
    for s in transcript.get("segments") or []:
        s0 = float(s.get("start", 0) or 0)
        s1 = float(s.get("end", 0) or 0)
        if s0 < end and start < s1:
            text = (s.get("text") or "").strip()
            if text:
                pieces.append(text)
    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "text": " ".join(pieces).strip(),
        "segment_count": len(pieces),
    }


def _scene_for_time(ts: float, scenes: list[dict] | None) -> str | None:
    if not scenes:
        return None
    for scene in scenes:
        start = float(scene.get("start_sec", 0))
        end = float(scene.get("end_sec", start))
        if start <= ts < end:
            return scene.get("scene_id")
    last = scenes[-1]
    if ts >= float(last.get("start_sec", 0)):
        return last.get("scene_id")
    return None
