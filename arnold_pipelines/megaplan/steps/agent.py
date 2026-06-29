"""Product-local agent step used by migrated Megaplan pipeline mirrors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.step_types import StepContext, StepResult


WorkerFn = Callable[..., Any]


def _next_version(output_dir: Path) -> int:
    versions = []
    for path in output_dir.glob("v*.md"):
        try:
            versions.append(int(path.stem[1:]))
        except ValueError:
            pass
    return max(versions, default=0) + 1


@dataclass
class AgentStep:
    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    _prompt_ref: str = ""
    _pipeline_dir: Path = field(default_factory=Path)
    _pipeline_name: str = ""
    _input_refs: list[str] = field(default_factory=list)
    _produces: str = "markdown"
    _worker: WorkerFn | None = None
    _prompt_registry: Callable[[str], str] | None = None
    _panel_reviewer_order: dict[str, list[str]] = field(default_factory=dict)
    _mode: str = ""
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        output_dir = ctx.plan_dir / self.name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"v{_next_version(output_dir)}.md"

        if self._worker is not None:
            result_text = self._worker(
                prompt=self._prompt_ref,
                step_name=self.name,
                pipeline_name=self._pipeline_name,
                inputs={key: str(value) for key, value in ctx.inputs.items()},
                mode=self._mode or ctx.mode,
            )
        else:
            result_text = f"[AgentStep {self.name}] prompt: {self._prompt_ref}"

        output_path.write_text(str(result_text), encoding="utf-8")
        return StepResult(outputs={self.name: output_path}, next="done")
