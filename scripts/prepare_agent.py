#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.task_builder import build_segment_task, build_synthesis_task  # noqa: E402
from src.core.config import load_settings  # noqa: E402
from src.core.registry import AssetRegistry  # noqa: E402
from src.core.utils import read_json  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Generate Cursor Agent TASK.md files")
    p.add_argument("--asset", required=True)
    p.add_argument("--level", choices=["segment", "synthesis"], required=True)
    p.add_argument("--segment-id")
    args = p.parse_args()
    settings = load_settings()

    if args.level == "synthesis":
        path = build_synthesis_task(args.asset, settings)
        print(path)
        return

    registry = AssetRegistry(settings)
    boundaries = read_json(registry.boundaries_path(args.asset))
    seg_ids = (
        [args.segment_id]
        if args.segment_id
        else [s["segment_id"] for s in boundaries.get("segments", [])]
    )
    for sid in seg_ids:
        path = build_segment_task(args.asset, sid, settings)
        print(path)


if __name__ == "__main__":
    main()
