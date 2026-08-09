from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.utils import ensure_dir


class WorkspacePaths:
    """Unified workspace layout under workspace/{asset_id}/."""

    def __init__(self, settings: Settings, asset_id: str):
        self.settings = settings
        self.asset_id = asset_id
        self.root = settings.paths.workspace / asset_id

    def ensure(self) -> Path:
        return ensure_dir(self.root)

    @property
    def meta(self) -> Path:
        return self.root / "meta.json"

    @property
    def audio_dir(self) -> Path:
        return self.root / "audio"

    @property
    def source_wav(self) -> Path:
        return self.audio_dir / "source.wav"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def frames_manifest(self) -> Path:
        return self.frames_dir / "manifest.json"

    @property
    def scenes_dir(self) -> Path:
        return self.root / "scenes"

    @property
    def scenes_json(self) -> Path:
        return self.scenes_dir / "scenes.json"

    @property
    def segments_dir(self) -> Path:
        return self.root / "segments"

    def segment_dir(self, segment_id: str) -> Path:
        return self.segments_dir / segment_id

    @property
    def boundaries(self) -> Path:
        return self.segments_dir / "boundaries.json"

    @property
    def transcript_dir(self) -> Path:
        return self.root / "transcript"

    @property
    def transcript_full(self) -> Path:
        return self.transcript_dir / "full.json"

    @property
    def vision_dir(self) -> Path:
        return self.root / "vision"

    @property
    def multimodal_dir(self) -> Path:
        return self.root / "multimodal"

    @property
    def multimodal_timeline(self) -> Path:
        return self.multimodal_dir / "timeline.json"

    @property
    def knowledge_dir(self) -> Path:
        return self.root / "knowledge"

    @property
    def knowledge_json(self) -> Path:
        return self.knowledge_dir / "knowledge.json"

    @property
    def summary_dir(self) -> Path:
        return self.root / "summary"

    @property
    def text_analysis(self) -> Path:
        return self.summary_dir / "text_analysis.json"

    @property
    def course_summary(self) -> Path:
        return self.summary_dir / "course.json"

    @property
    def agent_tasks_dir(self) -> Path:
        return self.root / "agent_tasks"

    @property
    def legacy_dir(self) -> Path:
        return self.settings.paths.assets / self.asset_id
