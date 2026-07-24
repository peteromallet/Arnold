from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from arnold_pipelines.megaplan.schemas.planning import TiebreakerDecision
from arnold_pipelines.megaplan.types import (
    CliError,
    PlanState,
    StepResponse,
)
from arnold_pipelines.megaplan.planning.state import (
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_CRITIQUED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
)
from arnold_pipelines.megaplan._core import (
    atomic_write_json,
    latest_plan_path,
    load_flag_registry,
    load_plan_locked,
    now_utc,
    read_json,
    require_state,
    save_flag_registry,
)
from arnold_pipelines.megaplan.replan_state import reset_replan_loop_state

_LEGACY_TIEBREAKER_RUN_STEP = "tiebreaker_run"
_LEGACY_TIEBREAKER_DECIDE_STEP = "tiebreaker_decide"
_CANONICAL_TIEBREAKER_RUN_STEPS = frozenset({
    "tiebreaker_researcher",
    "tiebreaker_challenger",
    "tiebreaker_synthesis",
})


def _build_tiebreaker_reprompt(
    agent_type: str, state: PlanState, plan_dir: Path, *, root: Path,
) -> str:
    if agent_type == "claude":
        base_prompt = create_claude_prompt("gate", state, plan_dir, root=root)
    elif agent_type == "hermes":
        base_prompt = create_hermes_prompt("gate", state, plan_dir, root=root)
    else:
        base_prompt = create_codex_prompt("gate", state, plan_dir, root=root)
    addendum = (
        "You recommended TIEBREAKER but no flag shows mechanical recurrence signal "
        "(addressed_then_reopened_count >= 2, or >=2 flags across >=2 iterations). "
        "Either identify specific flag(s) with iteration history or pick ITERATE."
    )
    return f"{base_prompt}\n\n{addendum}"


def _normalize_tiebreaker_action(args: argparse.Namespace) -> str:
    if getattr(args, "escalate", False):
        return "escalate"
    if getattr(args, "replan", False):
        return "replan"
    return "pick"


def _route_signal_for_tiebreaker_action(action: str) -> str:
    return {
        "pick": "proceed",
        "replan": "iterate",
        "escalate": "escalate",
    }.get(action, "escalate")


def _tiebreaker_phase_id(args: argparse.Namespace, *, default: str) -> str:
    node_id = getattr(args, "node_id", None)
    if isinstance(node_id, str) and node_id:
        return node_id
    return default


def _latest_json_artifact(plan_dir: Path, pattern: str, *, label: str) -> tuple[Path, dict[str, Any]]:
    files = sorted(plan_dir.glob(pattern))
    if not files:
        raise CliError("missing_tiebreaker_artifact", f"Missing {label} artifact for tiebreaker bridge")
    path = files[-1]
    data = read_json(path)
    if not isinstance(data, dict):
        raise CliError("invalid_tiebreaker_artifact", f"{label} artifact must be a JSON object")
    return path, data


def _latest_synthesis_artifact(plan_dir: Path) -> tuple[Path | None, str]:
    files = sorted(plan_dir.glob("tiebreaker*.md"))
    if not files:
        return None, ""
    path = files[-1]
    return path, path.read_text(encoding="utf-8")


def _build_tiebreaker_payload(
    *,
    question: str,
    researcher_data: dict[str, Any],
    challenger_data: dict[str, Any],
    synthesis_path: Path | None,
    synthesis_markdown: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "question": question,
        "research_findings": researcher_data,
        "challenge_findings": challenger_data,
        "synthesis_markdown": synthesis_markdown,
    }
    if synthesis_path is not None:
        payload["synthesis_artifact"] = synthesis_path.name
    return payload


def _tiebreaker_run_phase_outputs(
    phase_id: str,
    *,
    plan_dir: Path,
    question: str,
) -> tuple[dict[str, Any], list[str]]:
    researcher_path, researcher_data = _latest_json_artifact(
        plan_dir,
        "tiebreaker_researcher*.json",
        label="researcher",
    )
    challenger_path, challenger_data = _latest_json_artifact(
        plan_dir,
        "tiebreaker_challenger*.json",
        label="challenger",
    )
    synthesis_path, synthesis_markdown = _latest_synthesis_artifact(plan_dir)
    payload = _build_tiebreaker_payload(
        question=question,
        researcher_data=researcher_data,
        challenger_data=challenger_data,
        synthesis_path=synthesis_path,
        synthesis_markdown=synthesis_markdown,
    )

    if phase_id == "tiebreaker_researcher":
        return {"research_findings": researcher_data}, [researcher_path.name]
    if phase_id == "tiebreaker_challenger":
        return {"challenge_findings": challenger_data}, [challenger_path.name]

    artifacts = [researcher_path.name, challenger_path.name]
    if synthesis_path is not None:
        artifacts.append(synthesis_path.name)
    return {"tiebreaker_payload": payload}, artifacts


def handle_tiebreaker_run(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan._core import workflow_transition

    phase_id = _tiebreaker_phase_id(args, default=_LEGACY_TIEBREAKER_RUN_STEP)
    lock_step = phase_id.replace("_", "-")

    with load_plan_locked(root, args.plan, step=lock_step) as (plan_dir, state):
        gate_data = read_json(plan_dir / "gate.json")
        question = gate_data.get("tiebreaker_question", "")
        flag_ids = gate_data.get("tiebreaker_flag_ids", [])
        fuzzy_group_id = gate_data.get("tiebreaker_fuzzy_group_id", "")
        if not question:
            raise CliError("missing_tiebreaker_question", "Gate artifact missing tiebreaker_question")

        should_run_bridge = phase_id in {_LEGACY_TIEBREAKER_RUN_STEP, "tiebreaker_researcher"}
        if state["current_state"] == STATE_TIEBREAKER_PENDING:
            if not should_run_bridge:
                raise CliError(
                    "invalid_tiebreaker_phase_order",
                    f"{phase_id} requires the researcher bridge to complete first",
                )
            tb_args = argparse.Namespace(
                plan=args.plan, question=question, question_file=None,
                output=None, agent=getattr(args, "agent", None),
                hermes=getattr(args, "hermes", None),
                phase_model=list(getattr(args, "phase_model", [])),
                profile=getattr(args, "profile", None),
                fresh=getattr(args, "fresh", False),
                persist=getattr(args, "persist", False),
                ephemeral=getattr(args, "ephemeral", False),
            )
            from arnold_pipelines.megaplan.prompts.tiebreaker_orchestrator import _run_tiebreaker

            exit_code = _run_tiebreaker(root, plan_dir, state, tb_args)
            transition = workflow_transition(state, "tiebreaker-run")
            state["current_state"] = transition.next_state
        else:
            require_state(state, lock_step, {STATE_TIEBREAKER_READY})
            exit_code = 0

        phase_outputs, artifacts = _tiebreaker_run_phase_outputs(
            phase_id,
            plan_dir=plan_dir,
            question=question,
        )
        return {
            "success": exit_code == 0,
            "step": phase_id,
            "summary": f"{phase_id} bridge {'completed' if exit_code == 0 else 'failed'} for question: {question[:80]}",
            "state": state["current_state"],
            "plan": state["name"],
            "route_signal": "default",
            "artifacts": artifacts,
            "details": {
                "question": question,
                "flag_ids": flag_ids,
                "fuzzy_group_id": fuzzy_group_id,
            },
            **phase_outputs,
        }


def handle_tiebreaker_decide(root: Path, args: argparse.Namespace) -> StepResponse:
    phase_id = _tiebreaker_phase_id(args, default=_LEGACY_TIEBREAKER_DECIDE_STEP)
    lock_step = phase_id.replace("_", "-")

    with load_plan_locked(root, args.plan, step=lock_step) as (plan_dir, state):
        require_state(state, lock_step, {STATE_TIEBREAKER_READY})
        action = _normalize_tiebreaker_action(args)
        pick = getattr(args, "pick", None)
        rationale = getattr(args, "rationale", "")
        route_signal = _route_signal_for_tiebreaker_action(action)
        plan_file = latest_plan_path(plan_dir, state)

        gate_data = read_json(plan_dir / "gate.json")
        flag_ids = gate_data.get("tiebreaker_flag_ids", [])
        fuzzy_group_id = gate_data.get("tiebreaker_fuzzy_group_id", "")
        question = gate_data.get("tiebreaker_question", "")

        researcher_files = sorted(plan_dir.glob("tiebreaker_researcher*.json"))
        challenger_files = sorted(plan_dir.glob("tiebreaker_challenger*.json"))
        researcher_data = read_json(researcher_files[-1]) if researcher_files else {}
        challenger_data = read_json(challenger_files[-1]) if challenger_files else {}

        decision: TiebreakerDecision = {
            "fuzzy_group_id": fuzzy_group_id,
            "flag_ids": flag_ids,
            "question": question,
            "researcher_pick": researcher_data.get("recommendation", ""),
            "challenger_pick": challenger_data.get("recommendation", ""),
            "human_pick": pick or "",
            "action": action,
            "rationale": rationale,
            "timestamp": now_utc(),
            "plan_file": plan_file.name,
            "plan_iteration": state.get("iteration"),
        }

        decisions_path = plan_dir / "tiebreaker_decisions.json"
        existing = read_json(decisions_path) if decisions_path.exists() else []
        if not isinstance(existing, list):
            existing = []
        existing.append(decision)
        atomic_write_json(decisions_path, existing)

        from arnold_pipelines.megaplan.audits.audit_engine import record_tiebreaker_audit

        record_tiebreaker_audit(plan_dir, decision, researcher_data, challenger_data)

        if action == "pick" and flag_ids:
            registry = load_flag_registry(plan_dir)
            for flag in registry.get("flags", []):
                if flag["id"] in flag_ids:
                    flag["settled_by_tiebreaker"] = fuzzy_group_id
            save_flag_registry(plan_dir, registry)

        if action == "escalate":
            state["current_state"] = STATE_AWAITING_HUMAN_VERIFY
        elif action == "replan":
            reset_replan_loop_state(state, target_state=STATE_CRITIQUED)
        else:
            state["current_state"] = STATE_CRITIQUED

        return {
            "success": True,
            "step": phase_id,
            "summary": f"Tiebreaker decided: {action} — {rationale[:80]}",
            "state": state["current_state"],
            "plan": state["name"],
            "route_signal": route_signal,
            "decision": route_signal,
            "details": {
                "action": action,
                "pick": pick,
                "fuzzy_group_id": fuzzy_group_id,
                "flag_ids": flag_ids,
            },
        }
