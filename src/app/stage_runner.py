from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.core.cache import cache_hit
from src.core.errors import PipelineError, WaitingForAgent
from src.core.logging import PipelineLogger
from src.core.state import PipelineState
from src.core.utils import write_json


@dataclass
class StageSpec:
    name: str
    key: str
    run: Callable[[], str]
    artifacts: list
    validator: Callable[[], bool] | None = None
    force: bool = False


class StageRunner:
    def __init__(
        self,
        logger: PipelineLogger,
        state: PipelineState,
        pipeline: str,
        force_stages: set[str] | None = None,
    ):
        self.logger = logger
        self.state = state
        self.pipeline = pipeline
        self.force_stages = force_stages or set()

    def run_all(self, stages: list[StageSpec], through: str | None = None) -> str:
        """Returns 'ok' | 'waiting_agent' | 'failed'."""
        total = len(stages)
        cascade_force = False
        for index, stage in enumerate(stages, start=1):
            explicitly_forced = stage.key in self.force_stages or "all" in self.force_stages
            if explicitly_forced:
                cascade_force = True
            result = self._run_one(index, total, stage, cascade_force=cascade_force)
            if result != "ok":
                return result
            if through and stage.key == through:
                return "ok"
        return "ok"

    def _run_one(
        self, index: int, total: int, stage: StageSpec, cascade_force: bool = False
    ) -> str:
        force = (
            stage.force
            or cascade_force
            or stage.key in self.force_stages
            or "all" in self.force_stages
        )
        try:
            if not force and cache_hit(stage.artifacts, stage.validator):
                self.state.set_stage(stage.key, "skipped", self.pipeline)
                self.logger.stage_skip(index, total, stage.name)
                return "ok"

            self.logger.stage_start(index, total, stage.name)
            self.state.set_stage(stage.key, "running", self.pipeline)
            detail = stage.run() or ""
            self.state.set_stage(stage.key, "done", self.pipeline)
            self.logger.stage_done(index, total, stage.name, detail)
            return "ok"

        except WaitingForAgent as wait:
            self.state.set_stage(stage.key, "waiting_agent", self.pipeline)
            self.logger.waiting(wait.message)
            for path in wait.task_paths:
                self.logger.progress(f"  任务: {path}")
            return "waiting_agent"

        except PipelineError as err:
            err.stage = err.stage or stage.name
            self.state.set_stage(stage.key, "failed", self.pipeline)
            self._persist_error(err)
            self.logger.error(err.format())
            return "failed"

        except Exception as exc:  # noqa: BLE001 — convert to structured error
            err = PipelineError(
                reason=str(exc) or exc.__class__.__name__,
                missing="未知",
                recovery=[
                    "查看 logs/ 下 error.json",
                    f"修复后重跑: python run.py --asset {self.state.asset_id} --force {stage.key}",
                ],
                stage=stage.name,
                asset_id=self.state.asset_id,
                detail=exc.__class__.__name__,
            )
            self.state.set_stage(stage.key, "failed", self.pipeline)
            self._persist_error(err)
            self.logger.error(err.format())
            return "failed"

    def _persist_error(self, err: PipelineError) -> None:
        log_root = self.logger.log_dir
        if log_root is None:
            return
        write_json(log_root / "error.json", err.to_dict())
