from __future__ import annotations

from src.core.catalog import Catalog
from src.core.config import Settings, load_settings
from src.core.models import AssetMeta
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, write_json
from src.ingest.scanner import scan_assets
from src.stages.migrate import migrate_legacy_asset


def run_ingest(settings: Settings | None = None) -> list[AssetMeta]:
    settings = settings or load_settings()
    ensure_dir(settings.paths.workspace)
    ensure_dir(settings.paths.state)
    registry = AssetRegistry(settings)
    catalog = Catalog(settings)

    assets = scan_assets(settings)
    initialized: list[AssetMeta] = []
    for asset in assets:
        migrate_legacy_asset(settings, asset.asset_id)
        initialized.append(registry.init_meta(asset))

    catalog.upsert_all(initialized)
    # dual-write legacy data/catalog.json for older scripts
    legacy_catalog = settings.root / "data" / "catalog.json"
    write_json(
        legacy_catalog,
        {
            "version": 2,
            "count": len(initialized),
            "assets": [a.to_dict() for a in initialized],
        },
    )
    return initialized
