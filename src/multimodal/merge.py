from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.utils import ensure_dir, format_timestamp, read_json, write_json
from src.vision.value_gate import evaluate_vision_value, filter_valuable_vision


def merge_multimodal(
    transcript_path: Path,
    vision_dir: Path,
    scenes_path: Path,
    out_dir: Path,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    ensure_dir(out_dir)
    transcript = read_json(transcript_path) if transcript_path.exists() else {}
    scenes = read_json(scenes_path).get("scenes", []) if scenes_path.exists() else []

    vision_raw: list[dict] = []
    if vision_dir.exists():
        for path in sorted(vision_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            item = read_json(path)
            gate = evaluate_vision_value(item)
            item = dict(item)
            item["keep"] = gate["keep"]
            item["value_score"] = gate["value_score"]
            item["value_reason"] = gate["reason"]
            vision_raw.append(item)

    valuable_vision = filter_valuable_vision(vision_raw)
    speech_segs = transcript.get("segments", [])

    if scenes:
        units = scenes
        id_key = "scene_id"
    else:
        units = _chunk_from_speech(speech_segs, 300.0)
        id_key = "scene_id"

    timeline = []
    segment_rows = []
    units_with_said = 0
    units_with_valuable_seen = 0
    said_duration = 0.0

    for unit in units:
        start = float(unit.get("start_sec", 0))
        end = float(unit.get("end_sec", start + 1))
        uid = unit.get(id_key) or unit.get("segment_id") or f"unit_{start}"
        said = [
            s
            for s in speech_segs
            if _overlap(float(s.get("start", 0)), float(s.get("end", 0)), start, end)
        ]
        seen_items = [v for v in valuable_vision if _vision_in_range(v, start, end)]
        low_value_in_range = [
            v for v in vision_raw if _vision_in_range(v, start, end) and not v.get("keep")
        ]
        text = " ".join(s.get("text", "") for s in said).strip()
        vision_summary = " ".join(
            v.get("summary") or v.get("caption") or "" for v in seen_items
        ).strip()

        if text:
            units_with_said += 1
            said_duration += max(0.0, end - start)
        if seen_items:
            units_with_valuable_seen += 1

        if text:
            speech_status = "present"
        else:
            speech_status = "missing"

        if seen_items:
            vision_status = "present"
        elif low_value_in_range:
            vision_status = "skipped_low_value"
        else:
            vision_status = "missing"

        row = {
            "unit_id": uid,
            "start_sec": start,
            "end_sec": end,
            "start": format_timestamp(start),
            "end": format_timestamp(end),
            "said": text,
            "seen": vision_summary,
            "speech_status": speech_status,
            "vision_status": vision_status,
            "speech_segments": said,
            "vision": seen_items,
        }
        timeline.append(row)
        seg_path = out_dir / "segments" / f"{uid}.json"
        ensure_dir(seg_path.parent)
        write_json(seg_path, row)
        segment_rows.append(str(seg_path))

    dur = float(duration_sec or transcript.get("duration_sec") or 0)
    if dur <= 0 and timeline:
        dur = max(float(u["end_sec"]) for u in timeline)
    # Prefer transcript coverage_ratio when present
    speech_coverage_ratio = float(transcript.get("coverage_ratio") or 0)
    if speech_coverage_ratio <= 0 and dur > 0:
        last_end = 0.0
        for s in speech_segs:
            last_end = max(last_end, float(s.get("end", 0) or 0))
        speech_coverage_ratio = min(1.0, last_end / dur)

    payload = {
        "count": len(timeline),
        "timeline": timeline,
        "segment_files": segment_rows,
        "speech_coverage_ratio": round(speech_coverage_ratio, 4),
        "units_with_said": units_with_said,
        "units_with_valuable_seen": units_with_valuable_seen,
        "valuable_vision_count": len(valuable_vision),
        "vision_raw_count": len(vision_raw),
        "audio_first": True,
    }
    write_json(out_dir / "timeline.json", payload)
    return payload


def _overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return a0 < b1 and b0 < a1


def _vision_in_range(v: dict[str, Any], start: float, end: float) -> bool:
    t = v.get("time_sec")
    if t is None:
        return False
    return start <= float(t) < end or (end - start < 1e-6 and abs(float(t) - start) < 1.0)


def _chunk_from_speech(speech_segs: list[dict], size: float) -> list[dict]:
    if not speech_segs:
        return [{"scene_id": "scene_0001", "start_sec": 0.0, "end_sec": size}]
    max_end = max(float(s.get("end", 0)) for s in speech_segs)
    units = []
    t = 0.0
    i = 1
    while t < max_end:
        units.append(
            {
                "scene_id": f"scene_{i:04d}",
                "start_sec": t,
                "end_sec": min(t + size, max_end),
            }
        )
        t += size
        i += 1
    return units
