from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(text: str, max_len: int = 80) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "asset"


def asset_id_from_path(path: Path) -> str:
    return slugify(path.stem)


def write_json(path: Path, data: Any) -> None:
    """Atomic JSON write (temp + replace) to avoid truncated/corrupt state files."""
    ensure_dir(path.parent)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_fingerprint(path: Path, chunk_size: int = 8192) -> str:
    stat = path.stat()
    h = hashlib.md5()
    h.update(str(stat.st_size).encode())
    h.update(str(int(stat.st_mtime)).encode())
    with path.open("rb") as f:
        h.update(f.read(chunk_size))
        if stat.st_size > chunk_size:
            f.seek(max(0, stat.st_size - chunk_size))
            h.update(f.read(chunk_size))
    return h.hexdigest()


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def run_ffprobe(args: list[str]) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-of", "json", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def pip_install(package: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", package, "-q"], check=True)


def probe_media_duration_sec(media_path: Path) -> float:
    """Duration via ffprobe, falling back to ffmpeg -i parse."""
    try:
        data = run_ffprobe(["-show_entries", "format=duration", str(media_path)])
        return float(data.get("format", {}).get("duration", 0))
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError):
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(media_path)],
            capture_output=True,
            text=True,
        )
        log = proc.stderr or proc.stdout or ""
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", log)
        if not m:
            return 0.0
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mi * 60 + s
