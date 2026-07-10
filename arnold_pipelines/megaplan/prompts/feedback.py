"""Feedback-phase prompt builder — assembles per-stage artifact digests
and a retrospective evaluation rubric for the AI rater.

The calling handler (``handle_feedback`` workflow branch in ``cli.py``) passes
the ``plan_dir`` and ``state``; this module reads whatever artifacts exist and
returns a prompt string that asks a model to rate each phase 0-10 with a
one-sentence comment.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    latest_plan_path,
    latest_plan_meta_path,
    read_json,
)
from arnold_pipelines.megaplan.orchestration.feedback import STAGES


# ---------------------------------------------------------------------------
# Per-stage digest helpers
# ---------------------------------------------------------------------------

def _try_read_json(path: Path) -> dict | None:
    """Return parsed JSON dict, or None if the file is missing / unreadable."""
    try:
        return read_json(path)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _try_read_text(path: Path) -> str | None:
    """Return file text, or None if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _digest_prep(plan_dir: Path) -> str:
    data = _try_read_json(plan_dir / "prep.json")
    if data is None:
        return "Prep did not run; do not rate."

    # Extract key facts: research scope, findings count
    findings = data.get("findings", [])
    scope = data.get("scope", data.get("research_scope", ""))
    key_files = data.get("key_files", [])

    parts: list[str] = []
    if scope:
        parts.append(f"Research scope: {scope}")
    if key_files:
        parts.append(
            f"Examined {len(key_files)} key files: "
            + ", ".join(str(f) for f in key_files[:5])
            + ("..." if len(key_files) > 5 else "")
        )
    if findings:
        parts.append(f"Produced {len(findings)} research findings")

    if parts:
        return "Prep: " + "; ".join(parts) + "."
    return "Prep: ran but produced no structured output."


def _digest_plan(plan_dir: Path, state: dict) -> str:
    plan_versions = state.get("plan_versions", [])
    if not plan_versions:
        return "Plan phase did not run; do not rate."

    latest = plan_versions[-1]
    file_name = latest.get("file", "unknown")

    # Try to read the plan text for summary stats
    plan_path = plan_dir / file_name
    plan_text = _try_read_text(plan_path)
    sections = 0
    if plan_text:
        sections = plan_text.count("## ")

    version_count = len(plan_versions)
    parts = [
        f"Produced {version_count} plan version(s)",
        f"Final plan: {file_name}",
    ]
    if sections:
        parts.append(f"{sections} major sections")
    return "Plan: " + "; ".join(parts) + "."


def _digest_critique(plan_dir: Path, state: dict) -> str:
    # Find latest critique output — try critique_output.json then critique_vN.json
    crit_data = _try_read_json(plan_dir / "critique_output.json")
    if crit_data is None:
        iteration = state.get("iteration", 1)
        for i in range(iteration, 0, -1):
            crit_data = _try_read_json(plan_dir / f"critique_v{i}.json")
            if crit_data is not None:
                break

    if crit_data is None:
        return "Critique did not run; do not rate."

    # Count flags/issues
    flags = crit_data.get("flags", [])
    if not flags:
        # critique_output.json uses a different key
        flags = crit_data.get("findings", [])
    if isinstance(crit_data, dict) and "checks" in crit_data:
        # Parallel critique format
        checks = crit_data["checks"]
        flag_count = sum(
            len(check.get("flags", check.get("findings", [])))
            for check in checks
            if isinstance(check, dict)
        )
    else:
        flag_count = len(flags)

    # Top issue categories
    categories: dict[str, int] = {}
    for flag in flags if isinstance(flags, list) else []:
        if isinstance(flag, dict):
            cat = flag.get("category", flag.get("type", "uncategorized"))
            categories[cat] = categories.get(cat, 0) + 1

    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:3]
    cat_str = ", ".join(f"{cat} ({n})" for cat, n in top_cats) if top_cats else "none"

    return (
        f"Critique: raised {flag_count} flag(s); "
        f"top categories: {cat_str}."
    )


def _digest_revise(plan_dir: Path, state: dict) -> str:
    plan_versions = state.get("plan_versions", [])
    if len(plan_versions) <= 1:
        return "Revise did not run (only one plan version); do not rate."

    v1 = plan_versions[0].get("file", "v1")
    vn = plan_versions[-1].get("file", "vN")
    
    # Check what changed: count of new/changed sections via diff
    if len(plan_versions) >= 2:
        v1_text = _try_read_text(plan_dir / plan_versions[0]["file"])
        vn_text = _try_read_text(plan_dir / plan_versions[-1]["file"])
        if v1_text and vn_text:
            v1_sections = set(
                line.strip()
                for line in v1_text.splitlines()
                if line.startswith("## ")
            )
            vn_sections = set(
                line.strip()
                for line in vn_text.splitlines()
                if line.startswith("## ")
            )
            added = vn_sections - v1_sections
            removed = v1_sections - vn_sections
            delta_parts = []
            if added:
                delta_parts.append(f"{len(added)} sections added")
            if removed:
                delta_parts.append(f"{len(removed)} sections removed")
            delta_str = "; ".join(delta_parts) if delta_parts else "minor textual edits"
        else:
            delta_str = "unable to compare versions"
    else:
        delta_str = "no comparison available"

    return (
        f"Revise: {len(plan_versions)} plan versions (v1 → vN); "
        f"changes: {delta_str}."
    )


def _digest_gate(plan_dir: Path) -> str:
    data = _try_read_json(plan_dir / "gate.json")
    if data is None:
        return "Gate did not run; do not rate."

    recommendation = data.get("recommendation", data.get("verdict", "unknown"))
    passed = data.get("passed", data.get("gate_passed", None))

    parts = [f"Recommendation: {recommendation}"]
    if passed is not None:
        parts.append("Gate passed" if passed else "Gate did not pass")
    return "Gate: " + "; ".join(parts) + "."


def _digest_tiebreaker(plan_dir: Path) -> str:
    # Check for tiebreaker artifacts
    import glob
    tb_files = sorted(plan_dir.glob("tiebreaker*.json"))
    if not tb_files:
        return "Tiebreaker did not run; do not rate."

    # Try to get the outcome
    tb_data = _try_read_json(tb_files[-1])
    if tb_data is None:
        return f"Tiebreaker: ran ({len(tb_files)} artifact(s)) but output unreadable."

    winner = tb_data.get("winner", tb_data.get("selected_branch", "unknown"))
    return f"Tiebreaker: ran ({len(tb_files)} artifact(s)); winner: {winner}."


def _digest_finalize(plan_dir: Path, state: dict) -> str:
    data = _try_read_json(plan_dir / "finalize.json")
    if data is None:
        # Check for final.md
        final_text = _try_read_text(plan_dir / "final.md")
        if final_text is None:
            return "Finalize did not run; do not rate."
        # Count tasks from final.md
        task_count = final_text.count("- [ ]") + final_text.count("- [x]")
        return f"Finalize: final.md produced with ~{task_count} task(s)."

    tasks = data.get("tasks", [])
    batches = data.get("batches", data.get("batch_count", 1))
    return (
        f"Finalize: {len(tasks)} task(s) across "
        f"{batches if isinstance(batches, int) else len(batches) if isinstance(batches, list) else '?'} batch(es)."
    )


def _digest_execute(plan_dir: Path, state: dict) -> str:
    exec_data = _try_read_json(plan_dir / "execution.json")
    if exec_data is None:
        return "Execute did not run; do not rate."

    tasks = exec_data.get("tasks", [])
    done = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "done")
    skipped = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "skipped")
    blocked = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "blocked")

    audit = _try_read_json(plan_dir / "execution_audit.json")
    files_changed = 0
    if audit:
        files_changed = len(audit.get("changed_files", audit.get("files", [])))

    # Count batch files
    batch_count = len(list(list_batch_artifacts(plan_dir)))

    parts = [
        f"{done} done, {skipped} skipped, {blocked} blocked",
        f"{batch_count} batch(es)",
    ]
    if files_changed:
        parts.append(f"{files_changed} file(s) changed")
    elif audit:
        parts.append("no files changed detected")

    return "Execute: " + "; ".join(parts) + "."


def _digest_review(plan_dir: Path) -> str:
    data = _try_read_json(plan_dir / "review.json")
    if data is None:
        return "Review did not run; do not rate."

    verdict = data.get("review_verdict", data.get("verdict", "unknown"))
    summary = data.get("summary", "")
    issues = data.get("issues", [])

    parts = [f"Verdict: {verdict}"]
    if issues:
        parts.append(f"{len(issues)} issue(s) raised")
    if summary:
        parts.append(f"Summary: {summary[:120]}{'...' if len(summary) > 120 else ''}")

    return "Review: " + "; ".join(parts) + "."


def _build_run_meta(state: dict) -> str:
    """Assemble run-level metadata block."""
    config = state.get("config", {})
    meta = state.get("meta", {})

    robustness = config.get("robustness", "unknown")
    profile = config.get("profile", "unknown")
    iteration = state.get("iteration", 1)
    total_cost = meta.get("total_cost_usd", 0.0)

    # Per-phase durations from history
    durations: dict[str, int] = {}
    for entry in state.get("history", []):
        if isinstance(entry, dict):
            step = entry.get("step", "")
            dur = entry.get("duration_ms", 0)
            if step:
                durations[step] = durations.get(step, 0) + dur

    dur_lines = []
    for stage in STAGES:
        if stage in durations:
            dur_lines.append(f"  {stage}: {durations[stage] / 1000:.1f}s")

    dur_block = "\n".join(dur_lines) if dur_lines else "  (no phase timing data)"

    return (
        f"Robustness: {robustness}\n"
        f"Profile: {profile}\n"
        f"Iteration: {iteration}\n"
        f"Total cost: ${total_cost:.4f} USD\n"
        f"Phase durations:\n{dur_block}"
    )


# ---------------------------------------------------------------------------
# Main prompt builder
# ---------------------------------------------------------------------------

_RUBRIC = """You are a retrospective evaluator. Your job is to rate the quality of each
phase of a completed megaplan run.

This rating feeds into rubric tuning. Be honest. Errors of leniency cost
more than errors of severity — if a phase produced mediocre output that
later phases worked around, mark it ~5, not ~8.

Rate quality only, not cost-effectiveness. A great run that burned $50 is
still a 9 if the output is excellent. A cheap run with sloppy output is
not a 9 because it was cheap.

Scale (0-10):
- 10: textbook; no notes.
- 8: solid; minor polish only.
- 6: workable but with real issues — wasted iterations, missed flags,
     over/under-engineering.
- 4: degraded; the phase didn't do its job, downstream had to compensate.
- 2: actively harmful; produced output that hurt later stages.
- 0: complete failure.

Per-stage rubric:
- prep: did research surface useful info, or was it filler?
- plan: did the plan structure the work appropriately?
- critique: did it catch real issues, or stamp / over-flag?
- revise: did revise actually address critique flags?
- gate: was the decision well-calibrated?
- tiebreaker: did the decision pick the better branch on available evidence?
- finalize: did the final plan land cleanly?
- execute: did the executor follow the plan? Add/remove unnecessary scope?
- review: did review catch real issues, or rubber-stamp?

Overall: weighted impression of run quality.

Each comment must be one sentence — what specifically drove the rating."""


def build_feedback_prompt(plan_dir: Path, state: dict) -> str:
    """Build the full feedback evaluation prompt with per-stage digests.

    Args:
        plan_dir: Path to the plan's artifact directory.
        state: The plan state dict (as loaded from state.json).

    Returns:
        A prompt string suitable for sending to a rating model.
    """

    # Build per-stage digests
    digests: dict[str, str] = {
        "prep": _digest_prep(plan_dir),
        "plan": _digest_plan(plan_dir, state),
        "critique": _digest_critique(plan_dir, state),
        "revise": _digest_revise(plan_dir, state),
        "gate": _digest_gate(plan_dir),
        "tiebreaker": _digest_tiebreaker(plan_dir),
        "finalize": _digest_finalize(plan_dir, state),
        "execute": _digest_execute(plan_dir, state),
        "review": _digest_review(plan_dir),
    }

    # Determine which stages ran
    ran_stages = [
        stage for stage in STAGES
        if "did not run" not in digests.get(stage, "")
    ]

    # Build digest block
    digest_lines = ["## Phase digests", ""]
    for stage in STAGES:
        digest_lines.append(f"### {stage}")
        digest_lines.append(digests.get(stage, f"{stage}: no data available."))
        digest_lines.append("")

    digest_block = "\n".join(digest_lines)

    # Run meta
    run_meta = _build_run_meta(state)

    # Response schema instruction
    response_instruction = f"""Respond with strict JSON only:
{{"overall": {{"rating": int, "comment": str}},
 "stages": {{"<stage>": {{"rating": int, "comment": str}}, ...}}}}

Only include stages that actually ran. Stages that ran: {", ".join(ran_stages) if ran_stages else "(none)"}."""

    return "\n\n".join([
        _RUBRIC,
        "## Run metadata",
        run_meta,
        digest_block,
        response_instruction,
    ])
