from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


class PipelineLogger:
    """Human-readable stage logging with optional file sink."""

    def __init__(self, log_dir: Path | None = None, run_id: str | None = None):
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_dir = log_dir
        self._file = None
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._file = (log_dir / "run.log").open("a", encoding="utf-8")

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def _write(self, msg: str) -> None:
        print(msg, flush=True)
        if self._file:
            self._file.write(msg + "\n")
            self._file.flush()

    def info(self, msg: str) -> None:
        self._write(msg)

    def stage_start(self, index: int, total: int, name: str) -> None:
        self._write(f"[{index}/{total}] {name}")
        self._write("处理中……")

    def stage_skip(self, index: int, total: int, name: str, reason: str = "缓存有效") -> None:
        self._write(f"[{index}/{total}] {name}")
        self._write(f"跳过（{reason}）")
        self._write("完成")
        self._write("——————————")

    def stage_done(self, index: int, total: int, name: str, detail: str = "") -> None:
        if detail:
            self._write(detail)
        self._write("完成")
        self._write("——————————")

    def progress(self, msg: str) -> None:
        self._write(msg)

    def error(self, msg: str) -> None:
        self._write(msg)
        print(msg, file=sys.stderr, flush=True)

    def waiting(self, msg: str) -> None:
        self._write("")
        self._write("[等待 Cursor Agent]")
        self._write(msg)
        self._write("")
