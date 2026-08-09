from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from src.core.config import Settings
from src.core.utils import ensure_dir, read_json, write_json

StageStatus = Literal["pending", "running", "done", "skipped", "failed", "waiting_agent"]


class PipelineState:
    def __init__(self, settings: Settings, asset_id: str):
        self.settings = settings
        self.asset_id = asset_id
        self.path = settings.paths.state / f"{asset_id}.json"

    def load(self) -> dict[str, Any]:
        empty = {
            "asset_id": self.asset_id,
            "pipeline": "",
            "stages": {},
            "updated_at": None,
        }
        if not self.path.exists():
            return empty
        try:
            data = read_json(self.path)
        except Exception:
            # Corrupt / partial write — reset rather than crash --list / resume
            return empty
        if not isinstance(data, dict):
            return empty
        data.setdefault("stages", {})
        return data

    def save(self, data: dict[str, Any]) -> None:
        ensure_dir(self.path.parent)
        data["asset_id"] = self.asset_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(self.path, data)

    def get_stage(self, stage: str) -> StageStatus:
        data = self.load()
        return data.get("stages", {}).get(stage, "pending")  # type: ignore[return-value]

    def set_stage(self, stage: str, status: StageStatus, pipeline: str = "") -> None:
        data = self.load()
        if pipeline:
            data["pipeline"] = pipeline
        stages = data.setdefault("stages", {})
        stages[stage] = status
        self.save(data)

    def all_stages(self) -> dict[str, str]:
        return dict(self.load().get("stages", {}))
