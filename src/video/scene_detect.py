from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from src.core.config import Settings
from src.core.errors import PipelineError
from src.core.utils import ensure_dir, format_timestamp, probe_media_duration_sec, write_json

MIN_SCENE_SEC = 2.0
# Fine fallback when ffmpeg fails — never use 300s coarse chunks silently.
DEFAULT_SCENE_FALLBACK_SEC = 60.0


def detect_scenes(
    video_path: Path,
    scenes_json: Path,
    settings: Settings,
    speech_boundaries: list[dict[str, Any]] | None = None,
) -> dict:
    """Build timeline units (audio-first).

    Priority:
      1) Speech segment boundaries (covers full talk structure)
      2) ffmpeg scene cuts (visual cuts, then merge micros)
      3) fine interval fallback (default 60s) with degraded flag
    """
    ensure_dir(scenes_json.parent)
    duration = probe_media_duration_sec(video_path)
    threshold = settings.segment.scene_threshold
    degraded = False
    fallback_reason = ""

    # Audio boundaries provide speech coverage, while visual cuts provide the
    # actual shot structure. Use both when available so visual-heavy videos do
    # not collapse into one or two giant "scenes".
    if speech_boundaries:
        visual_cuts, _ = _ffmpeg_scene_cuts(video_path, min(threshold, 0.30))
        if visual_cuts:
            speech_cuts = [float(b.get("start_sec", 0)) for b in speech_boundaries]
            speech_cuts += [float(b.get("end_sec", 0)) for b in speech_boundaries]
            cuts = sorted(set([0.0, *visual_cuts, *speech_cuts]))
            cuts = [c for c in cuts if 0 <= c < duration]
            raw_scenes = []
            for i, start in enumerate(cuts):
                end = cuts[i + 1] if i + 1 < len(cuts) else duration
                raw_scenes.append(
                    {
                        "start_sec": round(start, 3),
                        "end_sec": round(end, 3),
                        "duration_sec": round(max(0.0, end - start), 3),
                        "method": "speech+visual_boundary",
                    }
                )
            raw_scenes = _merge_micro_scenes(raw_scenes, MIN_SCENE_SEC)
            method = "speech+visual_boundary"
        else:
            raw_scenes = _from_speech_boundaries(speech_boundaries, duration)
            method = "speech_boundary"
    else:
        cuts, method = _ffmpeg_scene_cuts(video_path, threshold)
        if not cuts:
            interval = float(
                getattr(settings.vision, "scene_fallback_interval_sec", None)
                or DEFAULT_SCENE_FALLBACK_SEC
            )
            cuts = []
            t = 0.0
            while t < duration:
                cuts.append(t)
                t += interval
            method = "interval"
            degraded = True
            fallback_reason = "ffmpeg_timeout_or_no_cuts"

        cuts = sorted(set(c for c in cuts if 0 <= c < duration))
        if not cuts or cuts[0] > 0.5:
            cuts = [0.0] + cuts

        raw_scenes = []
        for i, start in enumerate(cuts):
            end = cuts[i + 1] if i + 1 < len(cuts) else duration
            raw_scenes.append(
                {
                    "start_sec": round(start, 3),
                    "end_sec": round(end, 3),
                    "duration_sec": round(max(0.0, end - start), 3),
                    "method": method,
                }
            )
        if method == "ffmpeg_scene":
            raw_scenes = _merge_micro_scenes(raw_scenes, MIN_SCENE_SEC)

    scenes = []
    for i, sc in enumerate(raw_scenes, start=1):
        scenes.append(
            {
                "scene_id": f"scene_{i:04d}",
                "start_sec": sc["start_sec"],
                "end_sec": sc["end_sec"],
                "duration_sec": sc["duration_sec"],
                "start": format_timestamp(sc["start_sec"]),
                "end": format_timestamp(sc["end_sec"]),
                "method": sc.get("method", method),
            }
        )

    # Coverage gate: last scene must reach end of media
    if scenes and scenes[-1]["end_sec"] < duration - 1.0:
        scenes[-1]["end_sec"] = round(duration, 3)
        scenes[-1]["duration_sec"] = round(duration - scenes[-1]["start_sec"], 3)
        scenes[-1]["end"] = format_timestamp(duration)

    payload = {
        "count": len(scenes),
        "raw_cut_count": len(raw_scenes),
        "merged_micro": 0 if method == "speech_boundary" else max(0, len(raw_scenes) - len(scenes)),
        "min_scene_sec": MIN_SCENE_SEC,
        "threshold": threshold,
        "duration_sec": duration,
        "method": method,
        "degraded": degraded,
        "fallback_reason": fallback_reason,
        "scenes": scenes,
        "cut_times": [s["start_sec"] for s in scenes],
        "coverage_ok": bool(scenes) and scenes[-1]["end_sec"] >= duration - 1.0,
    }
    write_json(scenes_json, payload)
    return payload


def _from_speech_boundaries(boundaries: list[dict[str, Any]], duration: float) -> list[dict]:
    rows = []
    for b in boundaries:
        start = float(b.get("start_sec", 0))
        end = float(b.get("end_sec", start))
        if end <= start:
            continue
        rows.append(
            {
                "start_sec": round(start, 3),
                "end_sec": round(min(end, duration), 3),
                "duration_sec": round(min(end, duration) - start, 3),
                "method": "speech_boundary",
                "segment_id": b.get("segment_id"),
            }
        )
    if not rows:
        return [
            {
                "start_sec": 0.0,
                "end_sec": duration,
                "duration_sec": duration,
                "method": "speech_boundary",
            }
        ]
    # ensure start at 0 and end at duration
    if rows[0]["start_sec"] > 0.5:
        rows.insert(
            0,
            {
                "start_sec": 0.0,
                "end_sec": rows[0]["start_sec"],
                "duration_sec": rows[0]["start_sec"],
                "method": "speech_boundary",
            },
        )
    if rows[-1]["end_sec"] < duration - 1.0:
        rows.append(
            {
                "start_sec": rows[-1]["end_sec"],
                "end_sec": round(duration, 3),
                "duration_sec": round(duration - rows[-1]["end_sec"], 3),
                "method": "speech_boundary",
            }
        )
    return rows


def _merge_micro_scenes(scenes: list[dict], min_sec: float) -> list[dict]:
    if not scenes:
        return []
    out: list[dict] = []
    for sc in scenes:
        if not out:
            out.append(dict(sc))
            continue
        if sc["duration_sec"] < min_sec:
            prev = out[-1]
            prev["end_sec"] = sc["end_sec"]
            prev["duration_sec"] = round(prev["end_sec"] - prev["start_sec"], 3)
            prev["method"] = f"{prev.get('method', 'ffmpeg_scene')}+merge"
            continue
        if out[-1]["duration_sec"] < min_sec:
            prev = out[-1]
            prev["end_sec"] = sc["end_sec"]
            prev["duration_sec"] = round(prev["end_sec"] - prev["start_sec"], 3)
            continue
        out.append(dict(sc))
    if len(out) >= 2 and out[-1]["duration_sec"] < min_sec:
        last = out.pop()
        out[-1]["end_sec"] = last["end_sec"]
        out[-1]["duration_sec"] = round(out[-1]["end_sec"] - out[-1]["start_sec"], 3)
    return out


def _ffmpeg_scene_cuts(video_path: Path, threshold: float) -> tuple[list[float], str]:
    # Faster filter for long screen recordings; still best-effort.
    filt = f"scale=160:-1,fps=1,select='gt(scene,{threshold})',showinfo"
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
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
    except FileNotFoundError as exc:
        raise PipelineError(
            reason="未找到 ffmpeg",
            missing="系统 PATH 中的 ffmpeg",
            recovery=["安装 ffmpeg 后重试"],
        ) from exc
    except subprocess.TimeoutExpired:
        return [], "interval"

    cuts: list[float] = []
    log = (proc.stderr or "") + (proc.stdout or "")
    for match in re.finditer(r"pts_time:([\d.]+)", log):
        cuts.append(float(match.group(1)))
    if cuts:
        return cuts, "ffmpeg_scene"
    return [], "interval"
