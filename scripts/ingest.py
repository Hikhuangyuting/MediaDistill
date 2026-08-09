#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingest.router import run_ingest  # noqa: E402


def main() -> None:
    argparse.ArgumentParser(description="Scan videos/ and audio/ into catalog").parse_args()
    assets = run_ingest()
    print(f"Ingested {len(assets)} assets → data/catalog.json")
    for a in assets:
        print(f"  [{a.pipeline_type.value}] {a.asset_id} ← {a.source.filename}")


if __name__ == "__main__":
    main()
