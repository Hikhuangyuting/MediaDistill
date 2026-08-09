#!/usr/bin/env python3
"""Install faster-whisper for per-segment ASR."""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "faster-whisper>=1.0.0"],
        check=True,
    )
    print("Installed faster-whisper")


if __name__ == "__main__":
    main()
