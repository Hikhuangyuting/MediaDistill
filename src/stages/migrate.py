from __future__ import annotations

import shutil
from pathlib import Path

from src.core.config import Settings
from src.core.utils import ensure_dir, read_json, write_json


def migrate_legacy_asset(settings: Settings, asset_id: str) -> str:
    """Map assets/{id} → workspace/{id} without reprocessing ASR."""
    legacy = settings.paths.assets / asset_id
    workspace = settings.paths.workspace / asset_id
    if not legacy.exists():
        return "无 legacy 缓存"

    ensure_dir(workspace)
    notes: list[str] = []

    legacy_meta = legacy / "meta.json"
    ws_meta = workspace / "meta.json"
    if legacy_meta.exists() and not ws_meta.exists():
        shutil.copy2(legacy_meta, ws_meta)
        notes.append("meta")

    for name in ("status.json",):
        src, dst = legacy / name, workspace / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    # Prefer symlink for heavy segment trees; fall back to copy tree pointer via junction-like link.
    legacy_segs = legacy / "segments"
    ws_segs = workspace / "segments"
    if legacy_segs.exists() and not ws_segs.exists():
        try:
            ws_segs.symlink_to(legacy_segs.resolve(), target_is_directory=True)
            notes.append("segments→symlink")
        except OSError:
            shutil.copytree(legacy_segs, ws_segs)
            notes.append("segments→copy")

    legacy_tasks = legacy / "agent_tasks"
    ws_tasks = workspace / "agent_tasks"
    if legacy_tasks.exists() and not ws_tasks.exists():
        try:
            ws_tasks.symlink_to(legacy_tasks.resolve(), target_is_directory=True)
            notes.append("agent_tasks→symlink")
        except OSError:
            shutil.copytree(legacy_tasks, ws_tasks)
            notes.append("agent_tasks→copy")

    # Promote per-segment speech into transcript/full.json when possible.
    transcript = workspace / "transcript" / "full.json"
    if not transcript.exists() and (workspace / "segments").exists():
        assembled = _assemble_from_segments(workspace / "segments")
        if assembled:
            ensure_dir(transcript.parent)
            write_json(transcript, assembled)
            notes.append("transcript")

    legacy_knowledge = legacy / "knowledge.json"
    ws_knowledge = workspace / "knowledge" / "knowledge.json"
    if legacy_knowledge.exists() and not ws_knowledge.exists():
        ensure_dir(ws_knowledge.parent)
        shutil.copy2(legacy_knowledge, ws_knowledge)
        notes.append("knowledge")

    return "迁移: " + (", ".join(notes) if notes else "已存在/无需")


def _assemble_from_segments(segments_dir: Path) -> dict | None:
    pieces = []
    texts = []
    language = None
    for seg_dir in sorted(segments_dir.iterdir()):
        if not seg_dir.is_dir():
            continue
        speech_path = seg_dir / "speech.json"
        if not speech_path.exists():
            continue
        data = read_json(speech_path)
        language = language or data.get("language")
        text = data.get("text", "")
        if text:
            texts.append(text)
        for s in data.get("segments", []):
            pieces.append(
                {
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "text": s.get("text", ""),
                    "segment_id": data.get("segment_id", seg_dir.name),
                }
            )
    if not texts and not pieces:
        return None
    return {
        "text": "\n".join(texts).strip(),
        "language": language,
        "segments": pieces,
        "source": "migrated_from_segment_speech",
        "coverage_ok": False,
        "coverage_ratio": 0.0,
    }
