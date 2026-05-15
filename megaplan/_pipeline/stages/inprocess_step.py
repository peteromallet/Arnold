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

from megaplan._pipeline.types import StepContext, StepResult


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

        state_patch: dict[str, Any] = {}
        for key in ("current_state", "iteration", "last_gate"):
            if after.get(key) != before.get(key):
                state_patch[key] = after.get(key)

        outputs = _collect_outputs(ctx.plan_dir, before, after)
        return StepResult(
            outputs=outputs,
            verdict=None,
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

    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _label_for(phase: str, response: Mapping[str, Any], next_state: str) -> str:
    if phase == "gate":
        return _gate_label(response, next_state)
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


def _gate_label(response: Mapping[str, Any], next_state: str) -> str:
    rec = (response or {}).get("recommendation", "").upper()
    if rec == "PROCEED":
        return "gate_proceed:gate"
    if rec == "ITERATE":
        return "gate_iterate:revise"
    if rec == "TIEBREAKER":
        return "gate_tiebreaker:tiebreaker"
    if rec == "ESCALATE":
        return "gate_escalate:override force-proceed"
    return {
        "gated": "gate_proceed:gate",
        "planned": "gate_iterate:revise",
        "tiebreaker_pending": "gate_tiebreaker:tiebreaker",
        "aborted": "gate_escalate:override abort",
    }.get(next_state, "gate_proceed:gate")


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
