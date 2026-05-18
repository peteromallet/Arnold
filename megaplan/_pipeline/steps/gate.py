"""Structured gate step: agent emits a Verdict → routed edges.

Uses the existing gate executor semantics: the step's prompt produces
a Verdict JSON, and the executor matches ``kind="gate"`` edges by
``recommendation``.

Writes ``<plan_dir>/<stage_id>/v<n>.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from megaplan._pipeline.steps.agent import (
    _interpolate_inputs,
    _next_version,
    _resolve_inputs,
    _resolve_prompt_text,
)
from megaplan._pipeline.types import StepContext, StepResult, Verdict

WorkerFn = Callable[..., str]


@dataclass
class GateStep:
    """Structured gate: agent emits a Verdict → routed edges.

    Uses the existing gate executor semantics: the step's prompt produces
    a Verdict JSON, and the executor matches ``kind="gate"`` edges by
    ``recommendation``.
    """

    name: str
    kind: str = "judge"
    prompt_key: str | None = None
    slot: str | None = None

    _prompt_ref: str = ""
    _pipeline_dir: Path = field(default_factory=Path)
    _pipeline_name: str = ""
    _input_refs: list[str] = field(default_factory=list)
    _worker: WorkerFn | None = None
    _prompt_registry: Callable[[str], str] | None = None
    _panel_reviewer_order: dict[str, list[str]] = field(default_factory=dict)
    _mode: str = ""

    def run(self, ctx: StepContext) -> StepResult:
        inputs = _resolve_inputs(
            self._input_refs,
            ctx,
            panel_reviewer_order=self._panel_reviewer_order,
        )
        prompt_text = _resolve_prompt_text(
            self._prompt_ref,
            self._pipeline_dir,
            prompt_registry=self._prompt_registry,
        )
        rendered = _interpolate_inputs(prompt_text, inputs)

        output_dir = ctx.plan_dir / self.name
        output_dir.mkdir(parents=True, exist_ok=True)
        version = _next_version(output_dir)
        output_path = output_dir / f"v{version}.json"

        if self._worker is not None:
            worker_inputs = {k: str(v) for k, v in inputs.items()}
            result_text = self._worker(
                prompt=rendered,
                step_name=self.name,
                pipeline_name=self._pipeline_name,
                inputs=worker_inputs,
                mode=self._mode or ctx.mode,
            )
        else:
            result_text = json.dumps(
                {"recommendation": "proceed", "score": 0.5}
            )

        output_path.write_text(result_text, encoding="utf-8")

        # Parse verdict JSON from result
        try:
            verdict_data = json.loads(result_text)
        except json.JSONDecodeError:
            verdict_data = {"recommendation": "proceed", "score": 0.0}

        recommendation = verdict_data.get("recommendation", "proceed")
        valid_recs = {"proceed", "iterate", "tiebreaker", "escalate"}
        if recommendation not in valid_recs:
            recommendation = "proceed"

        return StepResult(
            outputs={self.name: output_path},
            verdict=Verdict(
                score=float(verdict_data.get("score", 0.5)),
                flags=tuple(verdict_data.get("flags", [])),
                notes=str(verdict_data.get("notes", "")),
                payload=verdict_data.get("payload", {}),
                recommendation=recommendation,
            ),
            next=recommendation,
        )
