from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def exists_nonempty(path: Path, min_bytes: int = 1) -> bool:
    return path.is_file() and path.stat().st_size >= min_bytes


def valid_json(path: Path, required_keys: list[str] | None = None) -> bool:
    if not exists_nonempty(path):
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if required_keys:
        for key in required_keys:
            if key not in data:
                return False
            val = data[key]
            if val is None or val == "":
                return False
    return True


def dir_has_files(path: Path, pattern: str = "*") -> bool:
    if not path.is_dir():
        return False
    return any(path.glob(pattern))


def cache_hit(
    artifacts: list[Path],
    validator: Callable[[], bool] | None = None,
) -> bool:
    """True when all artifacts exist (and optional validator passes)."""
    for path in artifacts:
        if path.is_dir():
            if not dir_has_files(path):
                return False
        elif not exists_nonempty(path):
            return False
    if validator is not None:
        return validator()
    return True


def load_json_safe(path: Path) -> dict[str, Any] | None:
    if not exists_nonempty(path):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
