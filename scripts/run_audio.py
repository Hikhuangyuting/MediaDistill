#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.pipeline import PipelineRunner  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Audio pipeline (segment-first)")
    p.add_argument("--asset", required=True)
    p.add_argument("--through", choices=["segment", "speech", "all"], default="all")
    args = p.parse_args()
    PipelineRunner().run_audio(args.asset, through=args.through)
    print(f"Audio pipeline through={args.through} done for {args.asset}")


if __name__ == "__main__":
    main()
