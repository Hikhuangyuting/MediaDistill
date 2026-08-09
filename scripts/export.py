#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.result_collector import collect_synthesis_result  # noqa: E402
from src.core.config import load_settings  # noqa: E402
from src.core.utils import ensure_dir  # noqa: E402
from src.export.markdown_renderer import render_designbrain_markdown  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Export DesignBrain markdown")
    p.add_argument("--asset", required=True)
    args = p.parse_args()
    settings = load_settings()
    doc = collect_synthesis_result(args.asset, settings)
    md = render_designbrain_markdown(doc)
    out_dir = ensure_dir(settings.paths.output)
    out_path = out_dir / f"{args.asset}.md"
    out_path.write_text(md, encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
