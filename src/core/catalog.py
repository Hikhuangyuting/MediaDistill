from __future__ import annotations

from datetime import datetime, timezone

from src.core.config import Settings
from src.core.models import AssetMeta
from src.core.utils import ensure_dir, read_json, write_json


class Catalog:
    def __init__(self, settings: Settings):
        self.path = settings.paths.catalog

    def load(self) -> dict:
        if not self.path.exists():
            return {"version": 2, "updated_at": None, "assets": []}
        return read_json(self.path)

    def save(self, assets: list[AssetMeta]) -> None:
        ensure_dir(self.path.parent)
        payload = {
            "version": 2,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(assets),
            "assets": [a.to_dict() for a in assets],
        }
        write_json(self.path, payload)

    def upsert_all(self, assets: list[AssetMeta]) -> None:
        self.save(assets)

    def get_asset(self, asset_id: str) -> AssetMeta | None:
        data = self.load()
        for row in data.get("assets", []):
            if row.get("asset_id") == asset_id:
                return AssetMeta.from_dict(row)
        return None
