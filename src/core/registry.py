from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.models import AssetMeta, AssetStatus
from src.core.paths import WorkspacePaths
from src.core.utils import ensure_dir, read_json, write_json


class AssetRegistry:
    """Asset filesystem layout rooted at workspace/ (legacy assets/ supported)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.assets_root = settings.paths.workspace
        self.legacy_root = settings.paths.assets

    def asset_dir(self, asset_id: str) -> Path:
        return self.assets_root / asset_id

    def paths(self, asset_id: str) -> WorkspacePaths:
        return WorkspacePaths(self.settings, asset_id)

    def meta_path(self, asset_id: str) -> Path:
        return self.asset_dir(asset_id) / "meta.json"

    def status_path(self, asset_id: str) -> Path:
        return self.asset_dir(asset_id) / "status.json"

    def segments_dir(self, asset_id: str) -> Path:
        return self.asset_dir(asset_id) / "segments"

    def segment_dir(self, asset_id: str, segment_id: str) -> Path:
        return self.segments_dir(asset_id) / segment_id

    def boundaries_path(self, asset_id: str) -> Path:
        return self.segments_dir(asset_id) / "boundaries.json"

    def agent_tasks_dir(self, asset_id: str) -> Path:
        return self.asset_dir(asset_id) / "agent_tasks"

    def knowledge_path(self, asset_id: str) -> Path:
        return self.paths(asset_id).knowledge_json

    def init_meta(self, asset: AssetMeta) -> AssetMeta:
        ensure_dir(self.asset_dir(asset.asset_id))
        ensure_dir(self.segments_dir(asset.asset_id))
        ensure_dir(self.agent_tasks_dir(asset.asset_id))

        existing = self.meta_path(asset.asset_id)
        if existing.exists():
            prev = AssetMeta.from_dict(read_json(existing))
            if prev.file_hash == asset.file_hash:
                return prev
            asset.status = prev.status

        write_json(self.meta_path(asset.asset_id), asset.to_dict())
        self._write_status(asset.asset_id, asset.status)
        return asset

    def load_meta(self, asset_id: str) -> AssetMeta:
        path = self.meta_path(asset_id)
        if not path.exists():
            legacy = self.legacy_root / asset_id / "meta.json"
            if legacy.exists():
                return AssetMeta.from_dict(read_json(legacy))
            raise FileNotFoundError(f"meta not found for {asset_id}")
        return AssetMeta.from_dict(read_json(path))

    def update_status(self, asset_id: str, status: AssetStatus) -> None:
        meta = self.load_meta(asset_id)
        meta.status = status
        write_json(self.meta_path(asset_id), meta.to_dict())
        self._write_status(asset_id, status)

    def _write_status(self, asset_id: str, status: AssetStatus) -> None:
        write_json(
            self.status_path(asset_id),
            {"asset_id": asset_id, "status": status.value},
        )
