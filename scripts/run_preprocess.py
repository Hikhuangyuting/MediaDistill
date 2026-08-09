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
    parser = argparse.ArgumentParser(description="Run video/audio preprocess pipeline")
    parser.add_argument("--asset", required=True, help="Asset ID from manifest")
    args = parser.parse_args()

    settings = load_settings()
    runner = PipelineRunner(settings)
    meta = runner.run_preprocess(args.asset)
    print(f"Preprocess done: {meta.asset_id} (step={meta.current_step})")


if __name__ == "__main__":
    main()
