from __future__ import annotations

import argparse
from pathlib import Path

from megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from megaplan.types import (
    CliError,
    PlanState,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_PLANNED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
    StepResponse,
)
from megaplan._core import atomic_write_json, load_flag_registry, load_plan_locked, now_utc, read_json, require_state, save_flag_registry

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

def handle_tiebreaker_run(root: Path, args: argparse.Namespace) -> StepResponse:
    from megaplan._core import workflow_transition
    with load_plan_locked(root, args.plan, step="tiebreaker-run") as (plan_dir, state):
        require_state(state, "tiebreaker-run", {STATE_TIEBREAKER_PENDING})
        gate_data = read_json(plan_dir / "gate.json")
        question = gate_data.get("tiebreaker_question", "")
        flag_ids = gate_data.get("tiebreaker_flag_ids", [])
        fuzzy_group_id = gate_data.get("tiebreaker_fuzzy_group_id", "")
        if not question:
            raise CliError("missing_tiebreaker_question", "Gate artifact missing tiebreaker_question")

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
        from megaplan.prompts.tiebreaker_orchestrator import _run_tiebreaker
        exit_code = _run_tiebreaker(root, plan_dir, state, tb_args)
        transition = workflow_transition(state, "tiebreaker-run")
        state["current_state"] = transition.next_state
        return {
            "success": exit_code == 0,
            "step": "tiebreaker-run",
            "summary": f"Tiebreaker run {'completed' if exit_code == 0 else 'failed'} for question: {question[:80]}",
            "state": state["current_state"],
            "plan": state["name"],
            "next_step": "tiebreaker decide",
            "details": {
                "question": question,
                "flag_ids": flag_ids,
                "fuzzy_group_id": fuzzy_group_id,
            },
        }

def handle_tiebreaker_decide(root: Path, args: argparse.Namespace) -> StepResponse:
    from megaplan._core import workflow_transition
    with load_plan_locked(root, args.plan, step="tiebreaker-decide") as (plan_dir, state):
        require_state(state, "tiebreaker-decide", {STATE_TIEBREAKER_READY})
        action = getattr(args, "tiebreaker_decide_action", "pick")
        pick = getattr(args, "pick", None)
        escalate = getattr(args, "escalate", False)
        replan = getattr(args, "replan", False)
        rationale = getattr(args, "rationale", "")
        if escalate:
            action = "escalate"
        elif replan:
            action = "replan"
        else:
            action = "pick"

        gate_data = read_json(plan_dir / "gate.json")
        flag_ids = gate_data.get("tiebreaker_flag_ids", [])
        fuzzy_group_id = gate_data.get("tiebreaker_fuzzy_group_id", "")
        question = gate_data.get("tiebreaker_question", "")

        researcher_files = sorted(plan_dir.glob("tiebreaker_researcher*.json"))
        challenger_files = sorted(plan_dir.glob("tiebreaker_challenger*.json"))
        researcher_data = read_json(researcher_files[-1]) if researcher_files else {}
        challenger_data = read_json(challenger_files[-1]) if challenger_files else {}

        from megaplan.types import TiebreakerDecision
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
        }

        decisions_path = plan_dir / "tiebreaker_decisions.json"
        existing = read_json(decisions_path) if decisions_path.exists() else []
        if not isinstance(existing, list):
            existing = []
        existing.append(decision)
        atomic_write_json(decisions_path, existing)

        from megaplan.audits.audit_engine import record_tiebreaker_audit
        record_tiebreaker_audit(plan_dir, decision, researcher_data, challenger_data)

        if action == "pick" and flag_ids:
            registry = load_flag_registry(plan_dir)
            for flag in registry.get("flags", []):
                if flag["id"] in flag_ids:
                    flag["settled_by_tiebreaker"] = fuzzy_group_id
            save_flag_registry(plan_dir, registry)

        if action == "escalate":
            state["current_state"] = STATE_AWAITING_HUMAN_VERIFY
            next_step_val = "override add-note"
        elif action == "replan":
            state["current_state"] = STATE_PLANNED
            next_step_val = "critique"
        else:
            transition = workflow_transition(state, "tiebreaker-decide")
            state["current_state"] = transition.next_state
            next_step_val = "revise"

        return {
            "success": True,
            "step": "tiebreaker-decide",
            "summary": f"Tiebreaker decided: {action} — {rationale[:80]}",
            "state": state["current_state"],
            "plan": state["name"],
            "next_step": next_step_val,
            "details": {
                "action": action,
                "pick": pick,
                "fuzzy_group_id": fuzzy_group_id,
                "flag_ids": flag_ids,
            },
        }
