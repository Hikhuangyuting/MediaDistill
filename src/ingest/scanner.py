from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.core.models import AssetMeta, PipelineType, SourceInfo
from src.core.utils import asset_id_from_path, file_fingerprint


def route_extension(ext: str, settings: Settings) -> PipelineType | None:
    ext = ext.lower()
    if ext in settings.video_extensions:
        return PipelineType.VIDEO
    if ext in settings.audio_extensions:
        return PipelineType.AUDIO
    return None


def _iter_media_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    files: list[Path] = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            files.append(path)
    return files


def scan_assets(settings: Settings) -> list[AssetMeta]:
    """Scan videos/ (MOV + legacy M4A) and audio/ (M4A). Original media stays read-only."""
    seen_ids: set[str] = set()
    assets: list[AssetMeta] = []

    scan_plan: list[tuple[Path, PipelineType | None]] = []
    for path in _iter_media_files(settings.paths.video_input):
        ptype = route_extension(path.suffix, settings)
        if ptype is None and path.suffix.lower() == ".m4a":
            ptype = PipelineType.AUDIO
        if ptype:
            scan_plan.append((path, ptype))

    for path in _iter_media_files(settings.paths.audio_input):
        ptype = route_extension(path.suffix, settings)
        if ptype:
            scan_plan.append((path, ptype))

    for path, pipeline_type in scan_plan:
        asset_id = asset_id_from_path(path)
        if asset_id in seen_ids:
            asset_id = f"{asset_id}-{file_fingerprint(path)[:8]}"
        seen_ids.add(asset_id)

        assets.append(
            AssetMeta(
                asset_id=asset_id,
                pipeline_type=pipeline_type,
                source=SourceInfo(
                    type=pipeline_type.value,
                    filename=path.name,
                    filepath=str(path.resolve()),
                ),
                file_hash=file_fingerprint(path),
            )
        )

    return assets
