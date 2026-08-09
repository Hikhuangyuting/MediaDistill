from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.config import Settings
from src.core.utils import read_json


def _load_schema(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def _check_required(data: dict[str, Any], required: list[str]) -> list[str]:
    return [
        f"missing required field: {k}" for k in required if k not in data or data[k] in (None, "")
    ]


def validate_knowledge(data: dict[str, Any], settings: Settings) -> list[str]:
    schema = _load_schema(settings.knowledge_schema)
    errors = _check_required(data, schema.get("required", []))
    for field, spec in schema.get("properties", {}).items():
        if field not in data:
            continue
        expected = spec.get("type")
        val = data[field]
        if expected == "string" and not isinstance(val, str):
            errors.append(f"{field} must be string")
        elif expected == "array" and not isinstance(val, list):
            errors.append(f"{field} must be array")
        elif expected == "object" and not isinstance(val, dict):
            errors.append(f"{field} must be object")
    return errors


def validate_segment_knowledge(data: dict[str, Any], settings: Settings) -> list[str]:
    schema = _load_schema(settings.segment_schema)
    errors = _check_required(data, schema.get("required", []))
    if "low_value_score" in data:
        try:
            float(data["low_value_score"])
        except (TypeError, ValueError):
            errors.append("low_value_score must be number")
    return errors
