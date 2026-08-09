from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.config import Settings
from src.core.errors import PipelineError
from src.core.models import PipelineType, SegmentBoundary
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, probe_media_duration_sec, read_json, write_json
from src.segment.boundary import boundaries_summary, detect_boundaries
from src.segment.extractor import extract_segment_audio
from src.segment.merger import merge_and_split
from src.speech.asr_engine import transcribe_audio
from src.speech.segment_transcribe import transcribe_segment
from src.video.audio_extract import extract_full_audio

COVERAGE_RATIO = 0.90


def transcript_last_end(transcript: dict[str, Any]) -> float:
    segs = transcript.get("segments") or []
    if not segs:
        return 0.0
    return max(float(s.get("end", 0) or 0) for s in segs)


def transcript_coverage_ratio(duration_sec: float, transcript: dict[str, Any]) -> float:
    if duration_sec <= 0:
        return 0.0
    # ASR coverage describes how much media was actually processed, not where
    # the final spoken sentence ended. A video may legitimately contain a long
    # silent/music-only tail after its last line of speech.
    processed = transcript.get("asr_processed_duration_sec")
    if processed is not None:
        return min(1.0, float(processed or 0) / duration_sec)
    return min(1.0, transcript_last_end(transcript) / duration_sec)


def transcript_coverage_ok(
    duration_sec: float,
    transcript: dict[str, Any],
    min_ratio: float = COVERAGE_RATIO,
) -> bool:
    if not (transcript.get("text") or "").strip():
        return False
    # Partial migrations are never considered complete.
    if transcript.get("source") == "migrated_from_segment_speech":
        return False
    if transcript.get("coverage_ok") is False:
        return False
    return transcript_coverage_ratio(duration_sec, transcript) >= min_ratio


def media_duration_for_asset(settings: Settings, asset_id: str) -> float:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    if wp.source_wav.exists():
        return probe_media_duration_sec(wp.source_wav)
    if meta.source.duration_sec:
        return float(meta.source.duration_sec)
    return probe_media_duration_sec(Path(meta.source.filepath))


def speech_cache_valid(settings: Settings, asset_id: str) -> bool:
    wp = WorkspacePaths(settings, asset_id)
    if not wp.transcript_full.exists():
        return False
    try:
        data = read_json(wp.transcript_full)
        dur = media_duration_for_asset(settings, asset_id)
        return transcript_coverage_ok(dur, data)
    except Exception:  # noqa: BLE001
        return False


def invalidate_speech_dependents(wp: WorkspacePaths) -> list[str]:
    """Remove downstream caches that assume complete transcript."""
    removed: list[str] = []
    for path in (
        wp.multimodal_timeline,
        wp.multimodal_dir / "segments",
        wp.knowledge_json,
        wp.course_summary,
        wp.root / "export" / "markdown.done",
    ):
        if path.is_file():
            path.unlink()
            removed.append(str(path))
        elif path.is_dir():
            import shutil

            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(path))
    return removed


def ensure_source_wav(settings: Settings, asset_id: str) -> Path:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    ensure_dir(wp.audio_dir)
    source = Path(meta.source.filepath)
    if not source.exists():
        raise PipelineError(
            reason="源媒体文件不存在",
            missing=str(source),
            recovery=["确认 videos/ 或 audio/ 中文件未被移动", "重新扫描: python run.py"],
            asset_id=asset_id,
        )

    if wp.source_wav.exists() and wp.source_wav.stat().st_size > 1000:
        return wp.source_wav

    extract_full_audio(source, wp.source_wav)
    return wp.source_wav


def run_extract_audio(settings: Settings, asset_id: str) -> str:
    wav = ensure_source_wav(settings, asset_id)
    dur = probe_media_duration_sec(wav)
    return f"已写入 source.wav ({dur / 60:.1f} min)"


def run_speech(settings: Settings, asset_id: str, logger_progress=None) -> str:
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    ensure_dir(wp.transcript_dir)

    source = Path(meta.source.filepath)
    wav = ensure_source_wav(settings, asset_id)
    duration = probe_media_duration_sec(wav) or float(meta.source.duration_sec or 0)

    if wp.transcript_full.exists():
        data = read_json(wp.transcript_full)
        if transcript_coverage_ok(duration, data):
            ratio = transcript_coverage_ratio(duration, data)
            return (
                f"transcript 缓存有效（coverage={ratio:.0%}，{len(data.get('segments', []))} 句）"
            )
        # Incomplete — invalidate dependents and continue ASR
        removed = invalidate_speech_dependents(wp)
        if logger_progress:
            last = transcript_last_end(data)
            logger_progress(
                f"检测到不完整 transcript（last_end={last:.1f}s / duration={duration:.1f}s），"
                f"将补齐 ASR；已失效下游 {len(removed)} 项"
            )

    # Segment + per-segment ASR
    if not wp.boundaries.exists():
        raw = detect_boundaries(source, meta.pipeline_type, settings)
        segments = merge_and_split(raw, settings.segment)
        write_json(wp.boundaries, boundaries_summary(segments))
    else:
        rows = read_json(wp.boundaries).get("segments", [])
        segments = [SegmentBoundary.from_dict(r) for r in rows]

    all_pieces: list[dict] = []
    texts: list[str] = []
    language = None
    total = len(segments)
    for i, seg in enumerate(segments, start=1):
        if logger_progress:
            logger_progress(f"处理中…… 片段 {i}/{total}")
        seg_dir = ensure_dir(wp.segment_dir(seg.segment_id))
        seg_wav = seg_dir / "audio.wav"
        if not seg_wav.exists():
            extract_segment_audio(
                source if meta.pipeline_type == PipelineType.VIDEO else wav,
                seg,
                seg_wav,
            )
        speech_path = seg_dir / "speech.json"
        if speech_path.exists():
            speech = read_json(speech_path)
        else:
            try:
                result = transcribe_segment(seg.segment_id, seg_wav, settings, speech_path)
                speech = result.to_dict()
            except ImportError as exc:
                raise PipelineError(
                    reason="faster-whisper 不可用",
                    missing="本地 faster-whisper 与模型权重",
                    recovery=[
                        "确认 .venv 中 faster-whisper 已安装",
                        "检查模型缓存是否完整",
                        f"修复后: python run.py --asset {asset_id} --force speech",
                    ],
                    asset_id=asset_id,
                    detail=str(exc),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise PipelineError(
                    reason=f"语音识别失败: {exc.__class__.__name__}",
                    missing="可识别的音频片段",
                    recovery=[
                        f"检查 {seg_wav}",
                        f"重跑: python run.py --asset {asset_id} --force speech",
                    ],
                    asset_id=asset_id,
                    detail=str(exc)[:300],
                ) from exc

        language = language or speech.get("language")
        if speech.get("text"):
            texts.append(speech["text"])
        offset = seg.start_sec
        for s in speech.get("segments", []):
            all_pieces.append(
                {
                    "start": round(float(s.get("start", 0)) + offset, 3),
                    "end": round(float(s.get("end", 0)) + offset, 3),
                    "text": s.get("text", ""),
                    "segment_id": seg.segment_id,
                }
            )

    if not texts:
        try:
            full = transcribe_audio(wav, settings.speech)
            texts = [full.get("text", "")]
            language = full.get("language")
            all_pieces = full.get("segments", [])
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(
                reason="整轨转写失败",
                missing="可识别音频",
                recovery=[f"检查 {wav}", "确认 Whisper 模型可用"],
                asset_id=asset_id,
                detail=str(exc)[:300],
            ) from exc

    last_end = max((float(p.get("end", 0)) for p in all_pieces), default=0.0)
    # Reaching the end of every planned source segment proves complete ASR
    # processing even when Whisper finds no speech in the final segment(s).
    processed_end = max((float(seg.end_sec) for seg in segments), default=0.0)
    ratio = (processed_end / duration) if duration > 0 else 0.0
    payload = {
        "asset_id": asset_id,
        "text": "\n".join(texts).strip(),
        "language": language,
        "segments": all_pieces,
        "segment_count": total,
        "duration_sec": duration,
        "last_end_sec": last_end,
        "speech_content_end_sec": last_end,
        "asr_processed_duration_sec": processed_end,
        "coverage_ratio": round(ratio, 4),
        "coverage_ok": ratio >= COVERAGE_RATIO and bool(texts),
        "source": "segment_asr",
    }
    if not payload["text"]:
        raise PipelineError(
            reason="转写结果为空",
            missing="有效语音内容",
            recovery=["检查音频是否静音", "尝试更大 Whisper 模型"],
            asset_id=asset_id,
        )
    write_json(wp.transcript_full, payload)
    # Refresh frame↔transcript index when frames already exist (P0-D)
    if wp.frames_manifest.exists():
        from src.video.frame_extract import attach_transcript_windows

        attach_transcript_windows(wp.frames_manifest, payload)
    if not payload["coverage_ok"]:
        raise PipelineError(
            reason=f"转写覆盖不足（coverage={ratio:.0%}，要求 ≥{COVERAGE_RATIO:.0%}）",
            missing=(
                f"ASR 需处理至约 {duration * COVERAGE_RATIO:.0f}s，"
                f"当前 processed_end={processed_end:.1f}s"
            ),
            recovery=[
                f"检查 segments 是否齐全（当前 {total} 段）",
                f"python run.py --asset {asset_id} --force speech",
            ],
            asset_id=asset_id,
        )
    return f"转写完成：{total} 片段，{len(all_pieces)} 句，coverage={ratio:.0%}"
