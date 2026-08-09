#!/usr/bin/env python3
"""Analyze one asset end-to-end with audio-first local knowledge synthesis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.orchestrator import Orchestrator
from src.core.config import load_settings
from src.core.errors import WaitingForAgent
from src.core.logging import PipelineLogger
from src.core.utils import ensure_dir
from src.knowledge.local_synthesize import synthesize_from_transcript
from src.stages.speech import speech_cache_valid


def analyze_one(asset_id: str) -> int:
    settings = load_settings()
    ensure_dir(settings.paths.logs)
    logger = PipelineLogger(settings.paths.logs / "batch")
    orch = Orchestrator(settings, logger)
    orch.ingest()

    logger.info(f"======== 开始分析: {asset_id} ========")
    result = orch.run_asset(asset_id)

    # If waiting on knowledge agent, synthesize locally (audio-first) and continue
    if result == "waiting_agent" or (
        speech_cache_valid(settings, asset_id)
        and not (settings.paths.workspace / asset_id / "knowledge" / "knowledge.json").exists()
    ):
        if speech_cache_valid(settings, asset_id):
            logger.info(f"[Knowledge] 本地音频优先合成: {asset_id}")
            synthesize_from_transcript(settings, asset_id)
            result = orch.run_asset(asset_id)

    logger.info(f"======== 结束: {asset_id} → {result} ========")
    logger.close()
    return 0 if result in ("ok", "waiting_agent") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True)
    args = p.parse_args()
    try:
        return analyze_one(args.asset)
    except WaitingForAgent as w:
        print(w.message)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
