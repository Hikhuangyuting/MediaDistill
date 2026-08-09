from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.utils import project_root, read_json


@dataclass
class PathsConfig:
    video_input: Path
    audio_input: Path
    assets: Path
    workspace: Path
    catalog: Path
    output_markdown: Path
    review: Path
    logs: Path
    state: Path


@dataclass
class SegmentConfig:
    max_segment_sec: float = 480.0
    min_segment_sec: float = 60.0
    fallback_interval_sec: float = 300.0
    silence_threshold_db: float = -35.0
    silence_min_duration_sec: float = 1.5
    scene_threshold: float = 0.35


@dataclass
class VisionConfig:
    max_frames_per_segment: int = 5
    keyframe_interval_sec: float = 30.0
    frames_per_batch: int = 8
    scene_fallback_interval_sec: float = 60.0
    task_mode: str = "per_scene"


@dataclass
class SpeechConfig:
    model: str = "medium"
    language: str = "zh"
    device: str = "cpu"
    compute_type: str = "int8"
    auto_install: bool = False


@dataclass
class Settings:
    root: Path
    paths: PathsConfig
    video_extensions: tuple[str, ...]
    audio_extensions: tuple[str, ...]
    segment: SegmentConfig
    vision: VisionConfig
    speech: SpeechConfig

    @property
    def input_dirs(self) -> list[Path]:
        return [self.paths.video_input, self.paths.audio_input]

    @property
    def knowledge_schema(self) -> Path:
        return self.root / "config" / "knowledge_schema.json"

    @property
    def segment_schema(self) -> Path:
        return self.root / "config" / "segment_schema.json"


def _pick(raw: dict, cls: type, **defaults):
    fields = cls.__dataclass_fields__  # type: ignore[attr-defined]
    kwargs = {k: defaults.get(k) for k in fields if k in defaults}
    for k in fields:
        if k in raw:
            kwargs[k] = raw[k]
    return cls(**kwargs)


def load_settings(root: Path | None = None) -> Settings:
    root = root or project_root()
    cfg_path = root / "config" / "settings.json"
    raw = read_json(cfg_path) if cfg_path.exists() else {}
    local_cfg_path = root / "config" / "settings.local.json"
    if local_cfg_path.exists():
        raw = _merge_dicts(raw, read_json(local_cfg_path))
    paths_raw = raw.get("paths", {})
    routing = raw.get("routing", {})
    seg = raw.get("segment", {})
    vis = raw.get("vision", {})
    sp = raw.get("speech", {})

    paths = PathsConfig(
        video_input=root / paths_raw.get("video_input", "videos"),
        audio_input=root / paths_raw.get("audio_input", "audio"),
        assets=root / paths_raw.get("assets", "assets"),
        workspace=root / paths_raw.get("workspace", "workspace"),
        catalog=root / paths_raw.get("catalog", "workspace/catalog.json"),
        output_markdown=root / paths_raw.get("output_markdown", "output/markdown"),
        review=root / paths_raw.get("review", "review"),
        logs=root / paths_raw.get("logs", "logs"),
        state=root / paths_raw.get("state", "workspace/state"),
    )
    return Settings(
        root=root,
        paths=paths,
        video_extensions=tuple(routing.get("video_extensions", [".mov", ".mp4", ".mkv", ".webm"])),
        audio_extensions=tuple(routing.get("audio_extensions", [".m4a", ".mp3", ".wav", ".flac"])),
        segment=_pick(seg, SegmentConfig),
        vision=_pick(vis, VisionConfig),
        speech=_pick(sp, SpeechConfig, auto_install=False),
    )


def _merge_dicts(base: dict, override: dict) -> dict:
    """递归合并本机配置，避免把私人路径提交到公开仓库。"""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged
