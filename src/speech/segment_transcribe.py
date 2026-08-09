from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.models import SegmentSpeech
from src.core.utils import write_json
from src.speech.asr_engine import transcribe_audio


def transcribe_segment(
    segment_id: str,
    audio_wav: Path,
    settings: Settings,
    output_json: Path | None = None,
) -> SegmentSpeech:
    if not audio_wav.exists():
        raise FileNotFoundError(audio_wav)

    result = transcribe_audio(audio_wav, settings.speech)
    speech = SegmentSpeech(
        segment_id=segment_id,
        text=result["text"],
        language=result.get("language"),
        segments=result.get("segments", []),
    )
    if output_json:
        write_json(output_json, speech.to_dict())
    return speech
