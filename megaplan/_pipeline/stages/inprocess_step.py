"""In-process handler Step — calls ``handle_<phase>`` directly.

Counterpart to :class:`HandlerStep` (which shells out via subprocess).
The in-process variant is what tests use: it inherits the calling
process's monkeypatches (``MEGAPLAN_MOCK_WORKERS=1``, mocked
``shutil.which``, mocked config dir, etc.) so the Pipeline can drive
the same mock E2E flow the legacy tests do.

Production callers (``megaplan/auto.py`` after Sprint 3 integration)
should use :class:`HandlerStep` so the existing per-phase subprocess
boundary — and its stall / cost / context-retry policy in
``auto.py`` — is preserved.
"""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from megaplan._pipeline.types import StepContext, StepResult, PipelineVerdict


@dataclass(frozen=True)
class InProcessHandlerStep:
    """A Step whose ``run`` calls ``handle_<phase>(root, args)`` in-process.

    ``handler`` is the imported ``handle_*`` callable. ``arg_factory``
    builds the ``argparse.Namespace`` passed to it; the default uses
    :func:`_default_arg_factory` which delegates to the plan name in
    ``ctx.state`` and the project dir hidden in ``ctx.profile`` (the
    test harness passes a small dict as ``profile``).
    """

    name: str
    kind: str
    handler: Callable[[Path, Namespace], Mapping[str, Any]]
    prompt_key: str | None = None
    slot: str | None = None
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        state = ctx.state if isinstance(ctx.state, Mapping) else {}
        plan_name = state.get("name") or state.get("plan_name") or Path(ctx.plan_dir).name
        root = _resolve_root(ctx)

        before = _read_state(ctx.plan_dir)

        ns_kwargs: dict[str, Any] = {
            "plan": plan_name,
            "idea": state.get("idea", "test idea"),
            "name": plan_name,
            "project_dir": str(_resolve_project_dir(ctx)),
            "auto_approve": None,
            "robustness": state.get("config", {}).get("robustness"),
            "agent": None,
            "ephemeral": False,
            "fresh": False,
            "persist": False,
            "confirm_destructive": True,
            "user_approved": False,
            "confirm_self_review": False,
            "batch": None,
            "override_action": None,
            "note": None,
            "reason": "",
            "strict_notes": None,
            "source": "user",
        }
        ns_kwargs.update(self.arg_overrides)
        args = Namespace(**ns_kwargs)

        response = self.handler(root, args)

        after = _read_state(ctx.plan_dir)
        next_state = after.get("current_state", before.get("current_state", ""))
        next_label = _label_for(self.name, response, next_state)

        verdict: PipelineVerdict | None = None
        if self.name == "gate":
            rec = _gate_recommendation(response, next_state)
            verdict = PipelineVerdict(score=0.0, recommendation=rec)

        state_patch: dict[str, Any] = {}
        for key in ("current_state", "iteration", "last_gate"):
            if after.get(key) != before.get(key):
                state_patch[key] = after.get(key)

        outputs = _collect_outputs(ctx.plan_dir, before, after)
        return StepResult(
            outputs=outputs,
            verdict=verdict,
            next=next_label,
            state_patch=state_patch,
        )


def _resolve_root(ctx: StepContext) -> Path:
    if isinstance(ctx.profile, Mapping):
        root = ctx.profile.get("root")
        if isinstance(root, Path):
            return root
        if isinstance(root, str):
            return Path(root)
    # Fallback — assume plan_dir is <root>/.megaplan/plans/<plan>
    return Path(ctx.plan_dir).parents[2]


def _resolve_project_dir(ctx: StepContext) -> Path:
    if isinstance(ctx.profile, Mapping):
        project_dir = ctx.profile.get("project_dir")
        if isinstance(project_dir, (Path, str)) and project_dir:
            return Path(project_dir)
    return Path(ctx.plan_dir).parents[2]


def _read_state(plan_dir: Path) -> dict[str, Any]:
    import json

    from megaplan.types import CliError

    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        raise CliError(
            "corrupt_state_read",
            "M3B_HALT_CORRUPT_STATE_READ: state.json cannot be parsed as JSON",
        ) from None
    if not isinstance(data, dict):
        raise CliError(
            "invalid_state_shape",
            "M3B_HALT_INVALID_STATE_SHAPE: state.json is valid JSON but not a dict",
        )
    return data


def _label_for(phase: str, response: Mapping[str, Any], next_state: str) -> str:
    """Return the executor's bare `next` label for a phase result.

    Sprint 4 Chunk A: the gate phase no longer returns a packed
    `gate_<rec>:<step>` label. Instead, the Step returns a PipelineVerdict
    whose `recommendation` field drives `kind="gate"` edge dispatch.
    The `next` string returned here is just the bare next step name
    for debug readability — the executor matches on the PipelineVerdict.
    """
    if phase == "gate":
        return _gate_next_step(response, next_state)
    if phase == "revise":
        return "critique"
    if phase == "review":
        return "review"
    if phase == "execute":
        return "review"  # executed → review edge per WORKFLOW
    if phase == "finalize":
        return "execute"  # finalized → execute edge
    if phase == "critique":
        return "gate_unset:gate"
    if phase == "plan":
        return "critique"
    if phase == "prep":
        return "plan"
    return phase


def _gate_recommendation(response: Mapping[str, Any], next_state: str):
    """Return the typed gate recommendation for a gate response.

    Reads the response's `recommendation` field first; falls back to
    a state-name mapping when absent.
    """
    rec = (response or {}).get("recommendation", "").upper()
    if rec == "PROCEED":
        return "proceed"
    if rec == "ITERATE":
        return "iterate"
    if rec == "TIEBREAKER":
        return "tiebreaker"
    if rec == "ESCALATE":
        return "escalate"
    return {
        "gated": "proceed",
        "planned": "iterate",
        "tiebreaker_pending": "tiebreaker",
        "aborted": "escalate",
    }.get(next_state, "proceed")


def _gate_next_step(response: Mapping[str, Any], next_state: str) -> str:
    """Bare next-step name corresponding to the gate's recommendation."""
    rec = _gate_recommendation(response, next_state)
    return {
        "proceed": "gate",
        "iterate": "revise",
        "tiebreaker": "tiebreaker",
        "escalate": "override force-proceed",
    }.get(rec, "gate")


def _collect_outputs(
    plan_dir: Path, before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    before_versions = {pv.get("file") for pv in before.get("plan_versions", []) or []}
    after_versions = {pv.get("file") for pv in after.get("plan_versions", []) or []}
    for filename in sorted((after_versions - before_versions) - {None}):
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
    ):
        path = Path(plan_dir) / candidate
        if path.exists():
            before_present = any(
                entry.get("output_file") == candidate
                for entry in before.get("history", []) or []
            )
            if not before_present:
                outputs[candidate] = path
    return outputs


def build_inprocess_planning_steps() -> dict[str, InProcessHandlerStep]:
    """Return the in-process handler-backed Step set for the planning Pipeline."""
    import megaplan

    return {
        "prepped": InProcessHandlerStep(
            name="prep", kind="produce", slot="prep",
            handler=megaplan.handlers.handle_prep,
        ),
        "planned": InProcessHandlerStep(
            name="plan", kind="produce", slot="plan",
            handler=megaplan.handle_plan,
        ),
        "critiqued": InProcessHandlerStep(
            name="critique", kind="judge", slot="critique",
            handler=megaplan.handle_critique,
        ),
        "gated": InProcessHandlerStep(
            name="gate", kind="decide", slot="gate",
            handler=megaplan.handle_gate,
        ),
        "finalized": InProcessHandlerStep(
            name="finalize", kind="produce", slot="finalize",
            handler=megaplan.handle_finalize,
        ),
        "executed": InProcessHandlerStep(
            name="execute", kind="produce", slot="execute",
            handler=megaplan.handle_execute,
            arg_overrides={"user_approved": True, "confirm_destructive": True},
        ),
    }


def build_revise_step() -> InProcessHandlerStep:
    """Special-case Step for the revise transition (not on a normal phase edge)."""
    import megaplan

    return InProcessHandlerStep(
        name="revise", kind="produce", slot="revise",
        handler=megaplan.handle_revise,
    )


def build_review_step() -> InProcessHandlerStep:
    import megaplan

    return InProcessHandlerStep(
        name="review", kind="judge", slot="review",
        handler=megaplan.handle_review,
    )
