from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PipelineType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class AssetStatus(str, Enum):
    INGESTED = "ingested"
    SEGMENTED = "segmented"
    SPEECH = "speech"
    VISION = "vision"
    AGENT_SEGMENT = "agent_segment"
    AGENT_SYNTHESIS = "agent_synthesis"
    EXPORTED = "exported"


@dataclass
class SourceInfo:
    type: str
    filename: str
    filepath: str
    duration_sec: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type,
            "filename": self.filename,
            "filepath": self.filepath,
        }
        if self.duration_sec is not None:
            d["duration_sec"] = self.duration_sec
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceInfo:
        return cls(
            type=data["type"],
            filename=data["filename"],
            filepath=data["filepath"],
            duration_sec=data.get("duration_sec"),
        )


@dataclass
class AssetMeta:
    asset_id: str
    pipeline_type: PipelineType
    source: SourceInfo
    file_hash: str
    status: AssetStatus = AssetStatus.INGESTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "pipeline_type": self.pipeline_type.value,
            "source": self.source.to_dict(),
            "file_hash": self.file_hash,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetMeta:
        return cls(
            asset_id=data["asset_id"],
            pipeline_type=PipelineType(data["pipeline_type"]),
            source=SourceInfo.from_dict(data["source"]),
            file_hash=data["file_hash"],
            status=AssetStatus(data.get("status", AssetStatus.INGESTED.value)),
        )


@dataclass
class SegmentBoundary:
    segment_id: str
    start_sec: float
    end_sec: float
    method: str = "unknown"

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration_sec": self.duration_sec,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SegmentBoundary:
        return cls(
            segment_id=data["segment_id"],
            start_sec=float(data["start_sec"]),
            end_sec=float(data["end_sec"]),
            method=data.get("method", "unknown"),
        )


@dataclass
class SegmentSpeech:
    segment_id: str
    text: str
    language: str | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "text": self.text,
            "language": self.language,
            "segments": self.segments,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SegmentSpeech:
        return cls(
            segment_id=data["segment_id"],
            text=data.get("text", ""),
            language=data.get("language"),
            segments=data.get("segments", []),
        )


@dataclass
class SegmentKnowledge:
    segment_id: str
    topic: str = ""
    summary: str = ""
    design_signals: list[str] = field(default_factory=list)
    low_value_score: float = 0.0
    low_value_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "topic": self.topic,
            "summary": self.summary,
            "design_signals": self.design_signals,
            "low_value_score": self.low_value_score,
            "low_value_reason": self.low_value_reason,
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SegmentKnowledge:
        return cls(
            segment_id=data["segment_id"],
            topic=data.get("topic", ""),
            summary=data.get("summary", ""),
            design_signals=data.get("design_signals", []),
            low_value_score=float(data.get("low_value_score", 0)),
            low_value_reason=data.get("low_value_reason", ""),
            raw=data.get("raw", data),
        )


@dataclass
class KnowledgeDoc:
    asset_id: str
    source: dict[str, Any]
    topic: str = ""
    design_context: str = ""
    core_problem: str = ""
    design_approach: str = ""
    design_principles: list[str] = field(default_factory=list)
    borrowable_methods: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    design_systems: list[str] = field(default_factory=list)
    interaction_patterns: list[str] = field(default_factory=list)
    reusable_experience: str = ""
    my_reflection: str = ""
    designbrain_knowledge: str = ""
    tags: list[str] = field(default_factory=list)
    timeline_refs: list[dict[str, Any]] = field(default_factory=list)
    screenshot_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source": self.source,
            "topic": self.topic,
            "design_context": self.design_context,
            "core_problem": self.core_problem,
            "design_approach": self.design_approach,
            "design_principles": self.design_principles,
            "borrowable_methods": self.borrowable_methods,
            "components": self.components,
            "design_systems": self.design_systems,
            "interaction_patterns": self.interaction_patterns,
            "reusable_experience": self.reusable_experience,
            "my_reflection": self.my_reflection,
            "designbrain_knowledge": self.designbrain_knowledge,
            "tags": self.tags,
            "timeline_refs": self.timeline_refs,
            "screenshot_refs": self.screenshot_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeDoc:
        return cls(
            asset_id=data["asset_id"],
            source=data["source"],
            topic=data.get("topic", ""),
            design_context=data.get("design_context", ""),
            core_problem=data.get("core_problem", ""),
            design_approach=data.get("design_approach", ""),
            design_principles=data.get("design_principles", []),
            borrowable_methods=data.get("borrowable_methods", []),
            components=data.get("components", []),
            design_systems=data.get("design_systems", []),
            interaction_patterns=data.get("interaction_patterns", []),
            reusable_experience=data.get("reusable_experience", ""),
            my_reflection=data.get("my_reflection", ""),
            designbrain_knowledge=data.get("designbrain_knowledge", ""),
            tags=data.get("tags", []),
            timeline_refs=data.get("timeline_refs", []),
            screenshot_refs=data.get("screenshot_refs", []),
        )
