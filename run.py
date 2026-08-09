#!/usr/bin/env python3
"""MediaDistill 统一入口。"""

from __future__ import annotations

import sys
from pathlib import Path


def _configure_console_encoding() -> None:
    """在 Windows 等非 UTF-8 控制台中稳定输出中文日志。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


_configure_console_encoding()

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
