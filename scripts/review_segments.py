#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.config import load_settings  # noqa: E402
from src.review.segment_review import build_review_queue  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Build low-value segment review queue")
    p.add_argument("--asset")
    args = p.parse_args()
    payload = build_review_queue(load_settings(), asset_id=args.asset)
    print(f"Review queue: {payload['count']} items → review/segment_review.json")


if __name__ == "__main__":
    main()
