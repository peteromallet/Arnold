"""Subprocess-backed Step wrapper for existing megaplan handlers.

Each instance of :class:`HandlerStep` runs ``megaplan <phase> --plan
<name>`` as a subprocess, then reads the plan's ``state.json`` to
compute the appropriate :class:`StepResult.next` label and
``state_patch``. The cost / stall / escalate policy machinery in
``megaplan/auto.py`` is unaffected — :class:`HandlerStep` is the
per-phase dispatch primitive only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from megaplan._pipeline.types import StepContext, StepResult, Verdict


_PHASE_STATE: Mapping[str, str] = {
    "prep": "prepped",
    "plan": "planned",
    "critique": "critiqued",
    "gate": "gated",
    "revise": "planned",
    "finalize": "finalized",
    "execute": "executed",
    "review": "done",
    "feedback": "done",
    "tiebreaker-run": "tiebreaker_ready",
    "tiebreaker-decide": "critiqued",
}


@dataclass(frozen=True)
class HandlerStep:
    """A Step whose ``run`` invokes ``megaplan <phase>`` as a subprocess.

    Attributes match the :class:`Step` Protocol. ``slot`` is the profile
    slot key used to resolve the model (``"plan"``, ``"critique"``,
    etc.). ``prompt_key`` is unused at the Sprint-3 layer (handlers
    resolve prompts internally) but kept for forward compatibility with
    the frozen Protocol.

    ``phase`` is the literal ``megaplan`` CLI subcommand to invoke; if
    distinct from ``name`` (e.g. ``name="tiebreaker_run"``,
    ``phase="tiebreaker-run"``) the override is honoured.
    """

    name: str
    kind: str  # "produce" | "judge" | "decide" | "subloop" | "override"
    prompt_key: str | None = None
    slot: str | None = None
    phase: str | None = None
    extra_args: tuple[str, ...] = ()

    def run(self, ctx: StepContext) -> StepResult:
        phase = self.phase or self.name
        plan_name = _resolve_plan_name(ctx)

        before = _read_state(ctx.plan_dir)
        cmd: list[str] = [
            sys.executable,
            "-m",
            "megaplan",
            phase,
            "--plan",
            plan_name,
            *self.extra_args,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Stage {self.name!r} subprocess {' '.join(cmd)!r} "
                f"exited {proc.returncode}: stderr={proc.stderr[-500:]}"
            )

        after = _read_state(ctx.plan_dir)
        next_state = after.get("current_state", before.get("current_state", ""))

        next_label = _label_for(phase, next_state)
        verdict: Verdict | None = None
        if phase == "gate":
            verdict = Verdict(score=0.0, recommendation=_gate_recommendation(next_state))
        state_patch = _diff_state_patch(before, after)
        outputs = _collect_outputs(ctx.plan_dir, before, after)
        return StepResult(
            outputs=outputs,
            verdict=verdict,
            next=next_label,
            state_patch=state_patch,
        )


def _resolve_plan_name(ctx: StepContext) -> str:
    """Pull the plan name from ctx.state, or fall back to plan_dir.name."""
    state = ctx.state if isinstance(ctx.state, Mapping) else {}
    name = state.get("name") or state.get("plan_name")
    if isinstance(name, str) and name:
        return name
    return Path(ctx.plan_dir).name


def _read_state(plan_dir: Path) -> dict[str, Any]:
    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _label_for(phase: str, next_state: str) -> str:
    """Bare next-step label for the StepResult.next field.

    Sprint 4 Chunk A: gate no longer returns a packed
    ``gate_<rec>:<step>`` label — instead the Step returns a typed
    Verdict and the executor dispatches via ``Edge.kind == "gate"``.
    """
    if phase == "gate":
        rec = _gate_recommendation(next_state)
        return {
            "proceed": "gate",
            "iterate": "revise",
            "tiebreaker": "tiebreaker",
            "escalate": "override force-proceed",
        }.get(rec, "gate")
    if phase.startswith("override "):
        return phase
    return phase


def _gate_recommendation(next_state: str):
    return {
        "gated": "proceed",
        "planned": "iterate",
        "tiebreaker_pending": "tiebreaker",
        "aborted": "escalate",
    }.get(next_state, "proceed")


def _diff_state_patch(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for key in ("current_state", "iteration", "last_gate"):
        if after.get(key) != before.get(key):
            patch[key] = after.get(key)
    return patch


def _collect_outputs(
    plan_dir: Path, before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Path]:
    """Return artifact paths newly written by this phase.

    Compares ``plan_versions`` and a small whitelist of well-known
    filenames so the executor's verify-only contract has paths to check.
    """

    outputs: dict[str, Path] = {}

    before_versions = {pv.get("file") for pv in before.get("plan_versions", []) or []}
    after_versions = {pv.get("file") for pv in after.get("plan_versions", []) or []}
    new = (after_versions - before_versions) - {None}
    for filename in sorted(new):
        out = Path(plan_dir) / filename
        if out.exists():
            outputs[f"plan_version:{filename}"] = out

    for candidate in (
        "prep.json",
        "critique_output.json",
        "gate.json",
        "final.md",
        "execution.json",
        "review.json",
        "feedback.md",
    ):
        path = Path(plan_dir) / candidate
        if path.exists() and not _was_present_before(before, candidate):
            outputs[candidate] = path
    return outputs


def _was_present_before(before: Mapping[str, Any], filename: str) -> bool:
    """Best-effort check for whether ``filename`` existed pre-step.

    Conservative — the executor only fails on declared outputs that
    don't exist, so over-reporting outputs is safe.
    """
    return filename in (before.get("artifacts") or [])


def build_planning_steps() -> dict[str, HandlerStep]:
    """Return the canonical handler-backed Step set for the planning Pipeline.

    Keyed by stage name (matches the compiled Pipeline's stage names).
    Sprint-3 callers wire these into the Pipeline by replacing
    ``_RuntimeStep`` placeholders in ``megaplan/_pipeline/planning.py``.
    """

    return {
        "prepped": HandlerStep(name="prep", kind="produce", slot="prep", phase="prep"),
        "planned": HandlerStep(name="plan", kind="produce", slot="plan", phase="plan"),
        "critiqued": HandlerStep(
            name="critique", kind="judge", slot="critique", phase="critique"
        ),
        "gated": HandlerStep(name="gate", kind="decide", slot="gate", phase="gate"),
        "finalized": HandlerStep(
            name="finalize", kind="produce", slot="finalize", phase="finalize"
        ),
        "executed": HandlerStep(
            name="execute", kind="produce", slot="execute", phase="execute"
        ),
        "tiebreaker_pending": HandlerStep(
            name="tiebreaker_run",
            kind="subloop",
            slot="tiebreaker_researcher",
            phase="tiebreaker-run",
        ),
        "tiebreaker_ready": HandlerStep(
            name="tiebreaker_decide",
            kind="subloop",
            slot="tiebreaker_challenger",
            phase="tiebreaker-decide",
        ),
    }


def attach_handler_steps(stages: Iterable[Any]) -> None:
    """No-op hook reserved for the Sprint-3 auto.py integration."""
    return None
