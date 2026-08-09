from __future__ import annotations

from src.core.config import SegmentConfig
from src.core.models import SegmentBoundary


def merge_and_split(
    segments: list[SegmentBoundary],
    cfg: SegmentConfig,
) -> list[SegmentBoundary]:
    if not segments:
        return []

    merged: list[SegmentBoundary] = []
    buf_start = segments[0].start_sec
    buf_end = segments[0].end_sec
    buf_method = segments[0].method

    for seg in segments[1:]:
        span = buf_end - buf_start
        if span < cfg.min_segment_sec:
            buf_end = seg.end_sec
            buf_method = f"{buf_method}+merge"
            continue
        merged.append(
            SegmentBoundary(
                segment_id="",
                start_sec=buf_start,
                end_sec=buf_end,
                method=buf_method,
            )
        )
        buf_start, buf_end, buf_method = seg.start_sec, seg.end_sec, seg.method

    merged.append(
        SegmentBoundary(segment_id="", start_sec=buf_start, end_sec=buf_end, method=buf_method)
    )

    final: list[SegmentBoundary] = []
    for item in merged:
        duration = item.end_sec - item.start_sec
        if duration <= cfg.max_segment_sec:
            final.append(item)
            continue
        start = item.start_sec
        while start < item.end_sec:
            end = min(start + cfg.max_segment_sec, item.end_sec)
            final.append(
                SegmentBoundary(
                    segment_id="",
                    start_sec=start,
                    end_sec=end,
                    method=f"{item.method}+split",
                )
            )
            start = end

    renumbered: list[SegmentBoundary] = []
    for i, seg in enumerate(final, start=1):
        renumbered.append(
            SegmentBoundary(
                segment_id=f"seg_{i:04d}",
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                method=seg.method,
            )
        )
    return renumbered
