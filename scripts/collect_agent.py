#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.result_collector import (  # noqa: E402
    CollectError,
    collect_all_segments,
    collect_synthesis_result,
)
from src.core.config import load_settings  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Validate agent JSON outputs")
    p.add_argument("--asset", required=True)
    p.add_argument("--level", choices=["segment", "synthesis"], default="segment")
    args = p.parse_args()
    settings = load_settings()
    try:
        if args.level == "synthesis":
            doc = collect_synthesis_result(args.asset, settings)
            print(f"OK synthesis: {doc.topic or doc.asset_id}")
        else:
            segs = collect_all_segments(args.asset, settings)
            print(f"OK segments: {len(segs)}")
    except CollectError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
