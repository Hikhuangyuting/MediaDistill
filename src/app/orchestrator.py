from __future__ import annotations

from src.app.stage_runner import StageRunner, StageSpec
from src.core.cache import valid_json
from src.core.config import Settings, load_settings
from src.core.logging import PipelineLogger
from src.core.models import PipelineType
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.state import PipelineState
from src.ingest.router import run_ingest
from src.stages.export_stages import run_markdown
from src.stages.frames import run_extract_frames, run_scene_detect
from src.stages.knowledge import run_knowledge_extraction, run_text_analysis
from src.stages.multimodal import run_multimodal_merge
from src.stages.speech import run_extract_audio, run_speech, speech_cache_valid
from src.stages.vision import run_vision_analysis


class Orchestrator:
    def __init__(self, settings: Settings | None = None, logger: PipelineLogger | None = None):
        self.settings = settings or load_settings()
        self.logger = logger or PipelineLogger(self.settings.paths.logs)

    def ingest(self) -> list:
        self.logger.info("扫描素材……")
        assets = run_ingest(self.settings)
        self.logger.info(f"已登记 {len(assets)} 个素材 → workspace/catalog.json")
        return assets

    def list_assets(self) -> None:
        assets = self.ingest()
        for a in assets:
            state = PipelineState(self.settings, a.asset_id).all_stages()
            done = sum(1 for s in state.values() if s in ("done", "skipped"))
            self.logger.info(
                f"- {a.asset_id} [{a.pipeline_type.value}] stages_done={done}/{len(state) or '-'}"
            )

    def status(self, asset_id: str | None = None) -> None:
        registry = AssetRegistry(self.settings)
        catalog = self.settings.paths.catalog
        if not catalog.exists():
            self.ingest()
        from src.core.catalog import Catalog

        cat = Catalog(self.settings).load()
        rows = cat.get("assets", [])
        if asset_id:
            rows = [r for r in rows if r.get("asset_id") == asset_id]
        for row in rows:
            aid = row["asset_id"]
            st = PipelineState(self.settings, aid).load()
            self.logger.info(f"=== {aid} ({row.get('pipeline_type')}) ===")
            for k, v in st.get("stages", {}).items():
                self.logger.info(f"  {k}: {v}")
            if not st.get("stages"):
                try:
                    meta = registry.load_meta(aid)
                    self.logger.info(f"  meta.status: {meta.status.value}")
                except FileNotFoundError:
                    self.logger.info("  (no state yet)")

    def run_asset(
        self,
        asset_id: str,
        through: str | None = None,
        force: set[str] | None = None,
    ) -> str:
        registry = AssetRegistry(self.settings)
        meta = registry.load_meta(asset_id)
        wp = WorkspacePaths(self.settings, asset_id)
        state = PipelineState(self.settings, asset_id)
        runner = StageRunner(self.logger, state, meta.pipeline_type.value, force)
        progress = self.logger.progress

        if meta.pipeline_type == PipelineType.VIDEO:
            stages = self._video_stages(asset_id, wp, progress)
        else:
            stages = self._audio_stages(asset_id, wp, progress)

        # Number stages dynamically for logging clarity
        self.logger.info(f"开始处理: {asset_id} ({meta.pipeline_type.value})")
        return runner.run_all(stages, through=through)

    def run_all(self, through: str | None = None, force: set[str] | None = None) -> None:
        assets = self.ingest()
        for asset in assets:
            result = self.run_asset(asset.asset_id, through=through, force=force)
            if result == "waiting_agent":
                self.logger.info(f"暂停于 Agent 等待: {asset.asset_id}（继续处理其余素材）")
                continue
            if result == "failed":
                self.logger.info(f"失败: {asset.asset_id}（继续处理其余素材）")

    def _video_stages(self, asset_id: str, wp: WorkspacePaths, progress) -> list[StageSpec]:
        # Audio→Speech first (fast resume); then visual stages.
        s = self.settings
        return [
            StageSpec(
                "Extract Audio",
                "extract_audio",
                lambda: run_extract_audio(s, asset_id),
                [wp.source_wav],
                validator=lambda: wp.source_wav.exists() and wp.source_wav.stat().st_size > 1000,
            ),
            StageSpec(
                "Speech Recognition",
                "speech",
                lambda: run_speech(s, asset_id, progress),
                [wp.transcript_full],
                validator=lambda: speech_cache_valid(s, asset_id),
            ),
            StageSpec(
                "Scene Detection",
                "scene_detect",
                lambda: run_scene_detect(s, asset_id),
                [wp.scenes_json],
                validator=lambda: valid_json(wp.scenes_json, ["scenes"]),
            ),
            StageSpec(
                "Extract Frames",
                "extract_frames",
                lambda: run_extract_frames(s, asset_id),
                [wp.frames_manifest],
                validator=lambda: valid_json(wp.frames_manifest, ["frames"]),
            ),
            StageSpec(
                "Vision Analysis",
                "vision",
                lambda: run_vision_analysis(s, asset_id),
                [wp.vision_dir / "_stage_done.json"],
                validator=lambda: (wp.vision_dir / "_stage_done.json").exists(),
            ),
            StageSpec(
                "Multimodal Merge",
                "multimodal",
                lambda: run_multimodal_merge(s, asset_id),
                [wp.multimodal_timeline],
                validator=lambda: valid_json(wp.multimodal_timeline, ["timeline"]),
            ),
            StageSpec(
                "Knowledge Extraction",
                "knowledge",
                lambda: run_knowledge_extraction(s, asset_id),
                [wp.knowledge_json],
                validator=lambda: valid_json(wp.knowledge_json, ["asset_id", "topic"]),
            ),
            StageSpec(
                "Markdown",
                "markdown",
                lambda: run_markdown(s, asset_id),
                [s.paths.output_markdown / f"{asset_id}.md"],
            ),
        ]

    def _audio_stages(self, asset_id: str, wp: WorkspacePaths, progress) -> list[StageSpec]:
        s = self.settings
        return [
            StageSpec(
                "Speech Recognition",
                "speech",
                lambda: run_speech(s, asset_id, progress),
                [wp.transcript_full],
                validator=lambda: speech_cache_valid(s, asset_id),
            ),
            StageSpec(
                "Text Analysis",
                "text_analysis",
                lambda: run_text_analysis(s, asset_id),
                [wp.text_analysis],
                validator=lambda: valid_json(wp.text_analysis, ["chapters"]),
            ),
            StageSpec(
                "Knowledge Extraction",
                "knowledge",
                lambda: run_knowledge_extraction(s, asset_id),
                [wp.knowledge_json],
                validator=lambda: valid_json(wp.knowledge_json, ["asset_id", "topic"]),
            ),
            StageSpec(
                "Markdown",
                "markdown",
                lambda: run_markdown(s, asset_id),
                [s.paths.output_markdown / f"{asset_id}.md"],
            ),
        ]
