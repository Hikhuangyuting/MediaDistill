from __future__ import annotations

from src.core.config import Settings
from src.core.models import KnowledgeDoc, SegmentKnowledge
from src.core.registry import AssetRegistry
from src.core.utils import read_json, write_json
from src.knowledge.schemas import validate_knowledge, validate_segment_knowledge


class CollectError(Exception):
    pass


def collect_segment_result(asset_id: str, segment_id: str, settings: Settings) -> SegmentKnowledge:
    registry = AssetRegistry(settings)
    path = registry.segment_dir(asset_id, segment_id) / "knowledge.json"
    if not path.exists():
        raise CollectError(f"Missing {path}")
    data = read_json(path)
    errors = validate_segment_knowledge(data, settings)
    if errors:
        raise CollectError("; ".join(errors))
    return SegmentKnowledge.from_dict(data)


def collect_synthesis_result(asset_id: str, settings: Settings) -> KnowledgeDoc:
    registry = AssetRegistry(settings)
    candidates = [
        registry.knowledge_path(asset_id),
        registry.asset_dir(asset_id) / "knowledge.json",
        settings.paths.assets / asset_id / "knowledge.json",
    ]
    path = next((p for p in candidates if p.exists()), candidates[0])
    if not path.exists():
        raise CollectError(f"Missing {path}")
    data = read_json(path)
    errors = validate_knowledge(data, settings)
    if errors:
        raise CollectError("; ".join(errors))
    doc = KnowledgeDoc.from_dict(data)
    write_json(registry.knowledge_path(asset_id), doc.to_dict())
    return doc


def collect_all_segments(asset_id: str, settings: Settings) -> list[SegmentKnowledge]:
    registry = AssetRegistry(settings)
    seg_root = registry.segments_dir(asset_id)
    results: list[SegmentKnowledge] = []
    if not seg_root.exists():
        return results
    for seg_dir in sorted(seg_root.iterdir()):
        if not seg_dir.is_dir():
            continue
        if (seg_dir / "knowledge.json").exists():
            results.append(collect_segment_result(asset_id, seg_dir.name, settings))
    return results
