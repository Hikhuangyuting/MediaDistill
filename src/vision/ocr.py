from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def run_ocr(image_path: Path, lang: str = "chi_sim+eng") -> dict:
    """Optional OCR via system tesseract. Never installs packages."""
    if not image_path.exists():
        return {"ocr_status": "missing_image", "ocr_text": ""}
    if not tesseract_available():
        return {"ocr_status": "unavailable", "ocr_text": ""}
    try:
        proc = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", lang],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ocr_status": "error", "ocr_text": "", "detail": str(exc)[:200]}
    text = (proc.stdout or "").strip()
    if proc.returncode != 0 and not text:
        return {
            "ocr_status": "error",
            "ocr_text": "",
            "detail": (proc.stderr or "")[:200],
        }
    return {
        "ocr_status": "ok" if text else "empty",
        "ocr_text": text,
    }


def detect_app_hints(ocr_text: str, summary: str = "") -> list[str]:
    blob = f"{ocr_text}\n{summary}".lower()
    mapping = {
        "figma": ["figma"],
        "cursor": ["cursor"],
        "browser": ["chrome", "safari", "firefox", "edge", "浏览器"],
        "vscode": ["visual studio code", "vscode"],
        "terminal": ["terminal", "iterm", "zsh", "bash"],
        "notion": ["notion"],
        "slide": ["keynote", "powerpoint", "ppt", "幻灯"],
    }
    found = []
    for label, keys in mapping.items():
        if any(k in blob for k in keys):
            found.append(label)
    return found
