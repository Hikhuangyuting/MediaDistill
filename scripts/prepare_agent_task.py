#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.config import load_settings  # noqa: E402
from src.core.pipeline import PipelineRunner  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Cursor Agent task package")
    parser.add_argument("--asset", required=True)
    parser.add_argument(
        "--task",
        required=True,
        choices=["vision", "segment", "synthesis", "knowledge"],
    )
    parser.add_argument("--segment-id", help="Required for segment tasks")
    args = parser.parse_args()

    settings = load_settings()
    runner = PipelineRunner(settings)

    if args.task == "segment":
        if not args.segment_id:
            segments_dir = settings.workspace / args.asset / "transcript" / "segments"
            for seg_file in sorted(segments_dir.glob("seg_*.json")):
                task = runner.prepare_agent_task(args.asset, "segment", segment_id=seg_file.stem)
                print(f"Task ready: {task}")
        else:
            task = runner.prepare_agent_task(args.asset, "segment", segment_id=args.segment_id)
            print(f"Task ready: {task}")
    else:
        task = runner.prepare_agent_task(args.asset, args.task)
        print(f"Task ready: {task}")


if __name__ == "__main__":
    main()
