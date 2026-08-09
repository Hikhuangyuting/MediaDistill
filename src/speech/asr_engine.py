from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.config import SpeechConfig
from src.core.utils import pip_install

_MODEL = None


def _ensure_whisper(speech: SpeechConfig):
    global _MODEL
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        if not speech.auto_install:
            raise ImportError(
                "faster-whisper is not installed. Run scripts/setup.py or pip install faster-whisper"
            )
        pip_install("faster-whisper")
    if _MODEL is None:
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(
            speech.model,
            device=speech.device,
            compute_type=speech.compute_type,
        )
    return _MODEL


def transcribe_audio(
    audio_path: Path,
    speech: SpeechConfig,
) -> dict[str, Any]:
    model = _ensure_whisper(speech)
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=speech.language or None,
        vad_filter=True,
    )
    pieces: list[dict[str, Any]] = []
    texts: list[str] = []
    for seg in segments_iter:
        piece = {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        }
        pieces.append(piece)
        if piece["text"]:
            texts.append(piece["text"])
    return {
        "text": " ".join(texts).strip(),
        "language": getattr(info, "language", speech.language),
        "segments": pieces,
    }
