from __future__ import annotations

import shutil
from pathlib import Path

from src.core.cache import valid_json
from src.core.config import Settings
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, read_json, write_json
from src.vision.ocr import detect_app_hints, run_ocr
from src.vision.value_gate import evaluate_vision_value, is_placeholder_vision

_INVALID_README = """# vision/_invalid 说明

本目录用于**隔离无效/模板占位**的 Vision JSON，防止污染 Multimodal 融合。

- 来源：早期验收写入的套话结果（如「画面呈现…可用于知识提炼」）
- 处理：价值门控判定为 placeholder 后移入此处
- **不要**把这里的文件当作有效视觉证据
- 有效结果应写在上级目录 `vision/frame_XXXX.json`，且 `keep: true`
"""


def select_frames_for_vision(settings: Settings, asset_id: str) -> list[dict]:
    """Select optional analysis targets covering the full timeline.

    Strategy (audio-first, frames as reference):
    - Build index for ALL keyframes
    - Create Agent tasks for **one representative frame per scene**
      (full timeline coverage without requiring every JPG to be analyzed)
    - Analysis remains optional: keep=false is valid
    """
    wp = WorkspacePaths(settings, asset_id)
    if not valid_json(wp.frames_manifest, ["frames"]):
        return []
    frames = read_json(wp.frames_manifest).get("frames", [])
    if not frames:
        return []

    # Prefer one frame near the middle of each scene
    scenes = []
    if valid_json(wp.scenes_json, ["scenes"]):
        scenes = read_json(wp.scenes_json).get("scenes", [])

    if scenes:
        duration = max(float(f.get("time_sec", 0)) for f in frames)
        # Short visual demos often have only one or two audio-derived scenes.
        # Analyze a denser, evenly distributed subset instead of collapsing the
        # whole video to one frame per speech segment.
        if duration <= 120:
            limit = min(len(frames), 16)
            if len(frames) <= limit:
                return frames
            step = len(frames) / limit
            return [frames[min(len(frames) - 1, int(i * step))] for i in range(limit)]
        selected = []
        used = set()
        for scene in scenes:
            start = float(scene.get("start_sec", 0))
            end = float(scene.get("end_sec", start))
            mid = (start + end) / 2
            candidates = [
                f
                for f in frames
                if start <= float(f.get("time_sec", 0)) < end
                or abs(float(f.get("time_sec", 0)) - start) < 1
            ]
            if not candidates:
                # nearest frame to mid
                candidates = sorted(frames, key=lambda f: abs(float(f.get("time_sec", 0)) - mid))
            pick = min(candidates, key=lambda f: abs(float(f.get("time_sec", 0)) - mid))
            if pick["frame_id"] not in used:
                used.add(pick["frame_id"])
                selected.append(pick)
        return selected

    # Fallback: evenly sample up to frames_per_batch * 3, at least cover duration
    batch = max(1, settings.vision.frames_per_batch)
    limit = min(len(frames), max(batch, 8))
    if len(frames) <= limit:
        return frames
    step = len(frames) / limit
    return [frames[int(i * step)] for i in range(limit)]


def vision_stage_prepared(settings: Settings, asset_id: str) -> bool:
    wp = WorkspacePaths(settings, asset_id)
    return (wp.vision_dir / "_stage_done.json").exists()


def purge_placeholder_vision(wp: WorkspacePaths) -> int:
    if not wp.vision_dir.exists():
        return 0
    junk = ensure_dir(wp.vision_dir / "_invalid")
    readme = junk / "README.md"
    if not readme.exists():
        readme.write_text(_INVALID_README, encoding="utf-8")
    moved = 0
    for path in list(wp.vision_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = read_json(path)
        if is_placeholder_vision(data):
            dest = junk / path.name
            path.replace(dest)
            moved += 1
    return moved


def _write_full_frame_index(wp: WorkspacePaths, frames: list[dict], selected_ids: set[str]) -> Path:
    index = {
        "total_keyframes": len(frames),
        "analysis_targets": len(selected_ids),
        "note": "全量关键帧已索引；Agent 任务仅针对 timeline 代表帧（每 scene 一帧）。分析可选，keep=false 合法。",
        "frames": [
            {
                "frame_id": f.get("frame_id"),
                "time_sec": f.get("time_sec"),
                "time": f.get("time"),
                "scene_id": f.get("scene_id"),
                "path": f.get("path"),
                "is_analysis_target": f.get("frame_id") in selected_ids,
                "status": "target" if f.get("frame_id") in selected_ids else "indexed_only",
            }
            for f in frames
        ],
    }
    path = wp.vision_dir / "frame_index.json"
    write_json(path, index)
    return path


def run_vision_analysis(settings: Settings, asset_id: str) -> str:
    """Prepare optional vision tasks; never block pipeline (audio-first)."""
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    ensure_dir(wp.vision_dir)
    ensure_dir(wp.agent_tasks_dir)

    moved = purge_placeholder_vision(wp)
    all_frames = []
    if valid_json(wp.frames_manifest, ["frames"]):
        all_frames = read_json(wp.frames_manifest).get("frames", [])
    selected = select_frames_for_vision(settings, asset_id)
    selected_ids = {f["frame_id"] for f in selected}
    _write_full_frame_index(wp, all_frames, selected_ids)

    # Remove stale tasks from an earlier frame manifest.
    vision_tasks = wp.agent_tasks_dir / "vision"
    if vision_tasks.exists():
        for task_dir in vision_tasks.iterdir():
            if task_dir.is_dir() and task_dir.name not in selected_ids:
                shutil.rmtree(task_dir)

    if not selected:
        write_json(
            wp.vision_dir / "_stage_done.json",
            {
                "status": "skipped_no_frames",
                "note": "无关键帧；音频主链路继续",
                "moved_placeholders": moved,
            },
        )
        return "无关键帧，Vision 跳过（音频为主）"

    prompt_path = settings.root / "config" / "prompts" / "02_vision_analysis.md"
    prompt = (
        prompt_path.read_text(encoding="utf-8")
        if prompt_path.exists()
        else "分析画面中的 PPT、UI、操作步骤与设计要点。"
    )

    pending = 0
    valuable = 0
    for frame in selected:
        frame_id = frame["frame_id"]
        result_path = wp.vision_dir / f"{frame_id}.json"
        if result_path.exists():
            data = read_json(result_path)
            if is_placeholder_vision(data):
                ensure_dir(wp.vision_dir / "_invalid")
                result_path.replace(wp.vision_dir / "_invalid" / f"{frame_id}.json")
            else:
                img = settings.root / frame.get("path", "")
                if not (data.get("ocr_text") or "").strip() and img.exists():
                    ocr = run_ocr(img)
                    data.update(ocr)
                    if not data.get("app_hints"):
                        data["app_hints"] = detect_app_hints(
                            ocr.get("ocr_text", ""), data.get("summary", "")
                        )
                gate = evaluate_vision_value(data)
                data["keep"] = gate["keep"]
                data["value_score"] = gate["value_score"]
                data["value_reason"] = gate["reason"]
                write_json(result_path, data)
                if gate["keep"]:
                    valuable += 1
                continue

        window = frame.get("transcript_window") or {}
        window_text = window.get("text") or ""
        task_dir = ensure_dir(wp.agent_tasks_dir / "vision" / frame_id)
        task_path = task_dir / "TASK.md"
        body = f"""# Vision analysis (optional reference): {frame_id}

Asset: `{asset_id}` ({meta.pipeline_type.value})
Time: {frame.get("time", "")} ({frame.get("time_sec")}s)
Scene: {frame.get("scene_id", "")}

## Priority

**音频为主。** 本帧是该 scene 的代表关键帧（全时间轴覆盖策略：每 scene 一帧）。
若画面没有对 Transcript 的增量信息，输出 `keep: false`，不要编造。

## Instructions

{prompt}

## Nearby transcript window (±15s)

```
{window_text or "(no transcript window yet)"}
```

## Inputs

- Frame image: `{frame.get("path", "")}`
- Full keyframe index: `workspace/{asset_id}/vision/frame_index.json`

## Output

Write JSON to `workspace/{asset_id}/vision/{frame_id}.json`:

```json
{{
  "frame_id": "{frame_id}",
  "time_sec": {frame.get("time_sec", 0)},
  "scene_id": "{frame.get("scene_id") or ""}",
  "summary": "具体画面描述（禁止套话）",
  "ocr_text": "",
  "ui_elements": [],
  "design_signals": [],
  "ppt_points": [],
  "app_hints": [],
  "value_score": 0.0,
  "keep": false
}}
```
"""
        task_path.write_text(body, encoding="utf-8")
        write_json(
            task_dir / "input.json",
            {
                "frame_id": frame_id,
                "time_sec": frame.get("time_sec"),
                "frame_path": frame.get("path"),
                "transcript_window": window,
                "asset_id": asset_id,
                "optional": True,
                "covers_scene": frame.get("scene_id"),
            },
        )
        pending += 1

    write_json(
        wp.vision_dir / "_stage_done.json",
        {
            "status": "prepared_optional",
            "total_keyframes": len(all_frames),
            "selected_targets": len(selected),
            "pending_tasks": pending,
            "valuable_ready": valuable,
            "moved_placeholders": moved,
            "strategy": "dense_short_video" if len(all_frames) <= 40 else "one_frame_per_scene",
            "note": "全量关键帧见 frame_index.json；短视频密集取样，长视频覆盖各 scene；分析可选",
        },
    )
    return (
        f"Vision：全量索引 {len(all_frames)} 帧；"
        f"时间轴代表任务 {len(selected)}（待填 {pending}，有价值 {valuable}）；"
        f"隔离模板 {moved}"
    )
