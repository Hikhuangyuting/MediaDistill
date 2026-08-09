#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.result_parser import parse_knowledge, validate_knowledge_json  # noqa: E402
from src.markdown.writer import render_markdown, update_index  # noqa: E402

from src.core.config import load_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble final DesignBrain Markdown")
    parser.add_argument("--asset", required=True)
    args = parser.parse_args()

    settings = load_settings()
    final_json = settings.workspace / args.asset / "knowledge" / "final.json"

    ok, errors = validate_knowledge_json(final_json, settings.schema_path)
    if not ok:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    doc = parse_knowledge(final_json)
    md_path = render_markdown(doc, settings)
    update_index(doc, md_path, settings)
    print(f"Markdown written: {md_path}")


if __name__ == "__main__":
    main()
