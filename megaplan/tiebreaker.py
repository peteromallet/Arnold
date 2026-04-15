"""Tiebreaker subcommand — structured decision support for architectural questions.

Runs two independent subagents (researcher → challenger) then synthesizes
their output into a human-readable decision brief.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from megaplan._core import (
    atomic_write_json,
    atomic_write_text,
    read_json,
    resolve_plan_dir,
)
from megaplan.prompts.tiebreaker_challenger import challenger_prompt
from megaplan.prompts.tiebreaker_researcher import researcher_prompt
from megaplan.prompts.tiebreaker_synthesis import render_synthesis
from megaplan.types import CliError, PlanState
from megaplan.workers import run_step_with_worker


# ---------------------------------------------------------------------------
# Version-suffix logic
# ---------------------------------------------------------------------------


def _next_version_suffix(plan_dir: Path) -> str:
    """Scan for existing tiebreaker_researcher* artifacts and return the next suffix.

    First run → "", second → "_v2", third → "_v3", etc.
    """
    existing = sorted(plan_dir.glob("tiebreaker_researcher*.json"))
    count = len(existing)
    if count == 0:
        return ""
    return f"_v{count + 1}"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _run_tiebreaker(
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
) -> int:
    question = _resolve_question(args)
    suffix = _next_version_suffix(plan_dir)

    researcher_file = f"tiebreaker_researcher{suffix}.json"
    challenger_file = f"tiebreaker_challenger{suffix}.json"
    synthesis_file = f"tiebreaker{suffix}.md"

    # -- Researcher pass --
    r_prompt = researcher_prompt(question, state, plan_dir, root=root)
    resolved = _build_resolved(args, "tiebreaker_researcher")

    researcher_result, r_agent, _, _ = run_step_with_worker(
        "tiebreaker_researcher",
        dict(state),  # FLAG-003: shallow copy to prevent state pollution
        plan_dir,
        args,
        root=root,
        resolved=resolved,
        prompt_override=r_prompt,
    )
    if not researcher_result.success:
        payload = {
            "success": False,
            "error": "researcher_failed",
            "message": researcher_result.error or "Researcher step failed",
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 1

    researcher_data = researcher_result.parsed or {}
    atomic_write_json(plan_dir / researcher_file, researcher_data)
    sys.stderr.write(f"[tiebreaker] researcher done → {researcher_file}\n")

    # -- Challenger pass --
    c_prompt = challenger_prompt(
        question, researcher_data, state, plan_dir, root=root
    )
    resolved_c = _build_resolved(args, "tiebreaker_challenger")

    challenger_result, c_agent, _, _ = run_step_with_worker(
        "tiebreaker_challenger",
        dict(state),  # FLAG-003: shallow copy
        plan_dir,
        args,
        root=root,
        resolved=resolved_c,
        prompt_override=c_prompt,
    )
    if not challenger_result.success:
        payload = {
            "success": False,
            "error": "challenger_failed",
            "message": challenger_result.error or "Challenger step failed",
            "researcher_artifact": researcher_file,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 1

    challenger_data = challenger_result.parsed or {}
    atomic_write_json(plan_dir / challenger_file, challenger_data)
    sys.stderr.write(f"[tiebreaker] challenger done → {challenger_file}\n")

    # -- Synthesis --
    synthesis_md = render_synthesis(question, researcher_data, challenger_data)
    atomic_write_text(plan_dir / synthesis_file, synthesis_md)
    sys.stderr.write(f"[tiebreaker] synthesis → {synthesis_file}\n")

    output_path = getattr(args, "output", None)
    if output_path:
        Path(output_path).write_text(synthesis_md, encoding="utf-8")
        sys.stderr.write(f"[tiebreaker] also written to {output_path}\n")

    payload = {
        "success": True,
        "plan": state["name"],
        "question": question,
        "researcher_agent": r_agent,
        "challenger_agent": c_agent,
        "artifacts": {
            "researcher": researcher_file,
            "challenger": challenger_file,
            "synthesis": synthesis_file,
        },
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


def _build_resolved(
    args: argparse.Namespace, step: str
) -> tuple[str, str, bool, str | None]:
    """Build a resolved tuple for ephemeral mode (FLAG-002)."""
    from megaplan.workers import resolve_agent_mode

    agent, _mode, _refreshed, model = resolve_agent_mode(step, args)
    return (agent, "ephemeral", True, model)


def _resolve_question(args: argparse.Namespace) -> str:
    question_file = getattr(args, "question_file", None)
    question_inline = getattr(args, "question", None)
    if question_file:
        path = Path(question_file)
        if not path.exists():
            raise CliError("missing_file", f"Question file not found: {question_file}")
        return path.read_text(encoding="utf-8").strip()
    if question_inline:
        return question_inline.strip()
    raise CliError("invalid_args", "Provide --question or --question-file")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def _run_tiebreaker_status(
    root: Path,
    plan_dir: Path,
    state: PlanState,
) -> int:
    researcher_files = sorted(plan_dir.glob("tiebreaker_researcher*.json"))
    challenger_files = sorted(plan_dir.glob("tiebreaker_challenger*.json"))
    synthesis_files = sorted(plan_dir.glob("tiebreaker*.md"))

    runs: list[dict[str, Any]] = []
    for rf in researcher_files:
        suffix = rf.stem.replace("tiebreaker_researcher", "")
        cf = plan_dir / f"tiebreaker_challenger{suffix}.json"
        sf = plan_dir / f"tiebreaker{suffix}.md"
        runs.append({
            "suffix": suffix or "(first)",
            "researcher": rf.name,
            "challenger": cf.name if cf.exists() else None,
            "synthesis": sf.name if sf.exists() else None,
            "complete": cf.exists() and sf.exists(),
        })

    payload = {
        "success": True,
        "plan": state["name"],
        "runs": runs,
        "total_runs": len(runs),
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def _add_common_agent_args(parser: argparse.ArgumentParser) -> None:
    """Add the agent/session flags that resolve_agent_mode expects (FLAG-001)."""
    parser.add_argument(
        "--agent",
        choices=["claude", "codex", "hermes"],
        default=None,
        help="Agent to use for tiebreaker steps",
    )
    parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent. Optional: specify model",
    )
    parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-step model override, e.g. --phase-model tiebreaker_researcher=hermes:openai/gpt-5",
    )
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--ephemeral", action="store_true")


def build_tiebreaker_parser(subparsers: Any) -> None:
    tb_parser = subparsers.add_parser(
        "tiebreaker",
        help="Run structured decision support for architectural questions",
    )
    tb_sub = tb_parser.add_subparsers(dest="tiebreaker_action")

    # Default (run) action args live on the top-level tiebreaker parser.
    tb_parser.add_argument("--plan", default=None, help="Plan name")
    question_group = tb_parser.add_mutually_exclusive_group()
    question_group.add_argument("--question", help="Decision question (inline)")
    question_group.add_argument("--question-file", help="Path to decision question file")
    tb_parser.add_argument("--output", help="Additional output path for the synthesis markdown")
    _add_common_agent_args(tb_parser)

    # Status subcommand
    status_parser = tb_sub.add_parser("status", help="Show tiebreaker run status")
    status_parser.add_argument("--plan", default=None, help="Plan name")


def run_tiebreaker_cli(root: Path, args: argparse.Namespace) -> int:
    action = getattr(args, "tiebreaker_action", None)
    plan_name = getattr(args, "plan", None)

    plan_dir = resolve_plan_dir(root, plan_name)
    state: PlanState = read_json(plan_dir / "state.json")

    if action == "status":
        return _run_tiebreaker_status(root, plan_dir, state)

    return _run_tiebreaker(root, plan_dir, state, args)
