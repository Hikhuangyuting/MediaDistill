from __future__ import annotations

from pathlib import Path

from src.core.config import Settings, load_settings
from src.core.models import AssetStatus, PipelineType, SegmentBoundary
from src.core.registry import AssetRegistry
from src.core.utils import read_json, write_json
from src.segment.boundary import boundaries_summary, detect_boundaries, probe_duration_sec
from src.segment.extractor import extract_segment_audio
from src.segment.merger import merge_and_split
from src.speech.segment_transcribe import transcribe_segment
from src.vision.frame_sampler import sample_segment_frames


class PipelineRunner:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.registry = AssetRegistry(self.settings)

    def _source_path(self, asset_id: str) -> Path:
        meta = self.registry.load_meta(asset_id)
        return Path(meta.source.filepath)

    def run_segment(self, asset_id: str) -> list[SegmentBoundary]:
        meta = self.registry.load_meta(asset_id)
        source = Path(meta.source.filepath)
        duration = probe_duration_sec(source)
        meta.source.duration_sec = duration
        write_json(self.registry.meta_path(asset_id), meta.to_dict())

        raw = detect_boundaries(source, meta.pipeline_type, self.settings)
        segments = merge_and_split(raw, self.settings.segment)
        write_json(
            self.registry.boundaries_path(asset_id),
            boundaries_summary(segments),
        )

        for seg in segments:
            seg_dir = self.registry.segment_dir(asset_id, seg.segment_id)
            seg_dir.mkdir(parents=True, exist_ok=True)
            wav = seg_dir / "audio.wav"
            extract_segment_audio(source, seg, wav)

        self.registry.update_status(asset_id, AssetStatus.SEGMENTED)
        return segments

    def run_speech(self, asset_id: str, segment_id: str | None = None) -> None:
        boundaries = read_json(self.registry.boundaries_path(asset_id))
        seg_ids = (
            [segment_id]
            if segment_id
            else [s["segment_id"] for s in boundaries.get("segments", [])]
        )
        for sid in seg_ids:
            seg_dir = self.registry.segment_dir(asset_id, sid)
            transcribe_segment(
                sid,
                seg_dir / "audio.wav",
                self.settings,
                seg_dir / "speech.json",
            )
        self.registry.update_status(asset_id, AssetStatus.SPEECH)

    def run_vision(self, asset_id: str, segment_id: str | None = None) -> None:
        meta = self.registry.load_meta(asset_id)
        if meta.pipeline_type != PipelineType.VIDEO:
            return
        source = self._source_path(asset_id)
        boundaries = read_json(self.registry.boundaries_path(asset_id))
        seg_rows = boundaries.get("segments", [])
        if segment_id:
            seg_rows = [s for s in seg_rows if s["segment_id"] == segment_id]

        for row in seg_rows:
            boundary = SegmentBoundary.from_dict(row)
            frames_dir = self.registry.segment_dir(asset_id, boundary.segment_id) / "frames"
            sample_segment_frames(source, boundary, frames_dir, self.settings)
        self.registry.update_status(asset_id, AssetStatus.VISION)

    def run_video(self, asset_id: str, through: str = "all") -> None:
        if through in ("segment", "all"):
            self.run_segment(asset_id)
        if through in ("speech", "all"):
            self.run_speech(asset_id)
        if through in ("vision", "all"):
            self.run_vision(asset_id)

    def run_audio(self, asset_id: str, through: str = "all") -> None:
        if through in ("segment", "all"):
            self.run_segment(asset_id)
        if through in ("speech", "all"):
            self.run_speech(asset_id)
