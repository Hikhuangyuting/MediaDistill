from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineError(Exception):
    """Structured pipeline error — never dump raw tracebacks to the user."""

    reason: str
    missing: str = ""
    recovery: list[str] = field(default_factory=list)
    stage: str = ""
    asset_id: str = ""
    detail: str = ""

    def __str__(self) -> str:
        return self.format()

    def format(self) -> str:
        lines = [f"[错误] {self.stage or 'Pipeline'} 失败"]
        if self.asset_id:
            lines.append(f"素材: {self.asset_id}")
        lines.append(f"原因: {self.reason}")
        if self.missing:
            lines.append(f"缺少: {self.missing}")
        if self.recovery:
            lines.append("如何恢复:")
            for i, step in enumerate(self.recovery, start=1):
                lines.append(f"  {i}. {step}")
        if self.detail:
            lines.append(f"详情: {self.detail}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "asset_id": self.asset_id,
            "reason": self.reason,
            "missing": self.missing,
            "recovery": self.recovery,
            "detail": self.detail,
        }


class WaitingForAgent(Exception):
    """Stage paused until Cursor Agent writes result files."""

    def __init__(self, message: str, task_paths: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.task_paths = task_paths or []
