"""Review-phase prompt builders."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from pathlib import Path
from typing import Any

from megaplan._core import (
    collect_git_diff_patch,
    collect_git_diff_summary,
    intent_brief_reference,
    is_prose_mode,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
)
from megaplan.types import PlanState

from ._shared import _gate_summary_or_skipped

log = logging.getLogger(__name__)

LARGE_REVIEW_DIFF_MAX_BYTES = 120 * 1024
LARGE_REVIEW_DIFF_MAX_FILES = 40


def _changed_files_from_patch(patch: str) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for line in patch.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        rel_path = parts[3]
        if rel_path.startswith("b/"):
            rel_path = rel_path[2:]
        if rel_path and rel_path not in seen:
            seen.add(rel_path)
            files.append(rel_path)
    return files


def _review_diff_is_large(patch: str, changed_files: list[str]) -> bool:
    return (
        len(patch.encode("utf-8")) > LARGE_REVIEW_DIFF_MAX_BYTES
        or len(changed_files) > LARGE_REVIEW_DIFF_MAX_FILES
    )


def _prior_unmet_review_block(plan_dir: Path, state: PlanState) -> str:
    if state.get("iteration", 1) <= 1:
        return ""
    prior_path = plan_dir / "review.json"
    if not prior_path.exists():
        return ""
    try:
        prior = read_json(prior_path)
    except (OSError, ValueError):
        return ""
    unmet: dict[str, Any] = {
        "criteria": [],
        "rework_items": [],
    }
    for criterion in prior.get("criteria", []) or []:
        if not isinstance(criterion, dict):
            continue
        if criterion.get("priority") == "must" and criterion.get("pass") in (False, "fail"):
            unmet["criteria"].append(criterion)
    for item in prior.get("rework_items", []) or []:
        if isinstance(item, dict):
            unmet["rework_items"].append(item)
    if not unmet["criteria"] and not unmet["rework_items"]:
        return ""
    return textwrap.dedent(
        f"""
        Re-review focus:
        This is review iteration {state.get("iteration", 1)}. Treat the prior review's still-unmet items below as the active scope and verify the delta from the last review with repository inspection and commands. Do not re-review unrelated cumulative branch history unless one of these items requires it.
        {json_dump(unmet).strip()}
        """
    ).strip()


def _large_diff_context_block(
    *,
    project_dir: Path,
    diff_summary: str,
    changed_files: list[str],
    prior_unmet_block: str,
) -> str:
    file_list = "\n".join(f"- {path}" for path in changed_files) or "- No changed files detected."
    threshold = (
        f"{LARGE_REVIEW_DIFF_MAX_BYTES // 1024} KB or "
        f"{LARGE_REVIEW_DIFF_MAX_FILES} changed files"
    )
    prior = f"\n\n{prior_unmet_block}" if prior_unmet_block else ""
    return textwrap.dedent(
        f"""
        Large git diff mode:
        The full patch exceeds the review prompt threshold ({threshold}), so it is intentionally not pasted here. Use your repository tools in {project_dir} to inspect the actual files and run focused checks before writing a verdict.

        Git diff summary:
        {diff_summary}

        Changed files:
        {file_list}{prior}

        Tool-driven verification requirements:
        - Verify every criterion/check against the actual workspace, not only this summary.
        - Inspect relevant files with read/grep tools and run focused commands when behavior or tests are part of the criterion.
        - Emit concrete per-criterion checks: pass/fail plus repository-backed evidence.
        - For every `rework_items` entry, populate `evidence_file` with the file where the issue was observed.
        - If repository inspection or commands cannot complete because of infrastructure, size, or premature output, report a review infrastructure failure; do not invent implementation rework such as "the diff does not contain the work."
        """
    ).strip()


def _check_field(check: Any, name: str) -> Any:
    if isinstance(check, dict):
        return check.get(name)
    return getattr(check, name)


def _review_check_flag_id(check_id: str, index: int) -> str:
    stem = re.sub(r"[^A-Z0-9]+", "_", check_id.upper()).strip("_") or "CHECK"
    return f"REVIEW-{stem}-{index:03d}"


def _latest_meta_without_state(plan_dir: Path) -> dict[str, Any]:
    candidates = sorted(plan_dir.glob("plan_v*.meta.json"))
    if not candidates:
        return {}
    try:
        return read_json(candidates[-1])
    except (OSError, ValueError):
        return {}


def _criteria_from_plan_artifacts(plan_dir: Path, state: PlanState | None) -> list[dict[str, str]]:
    """Return review criteria from the durable plan artifact, with gate fallback."""
    criteria: list[dict[str, str]] = []
    if state is None:
        meta = _latest_meta_without_state(plan_dir)
    else:
        try:
            meta = read_json(latest_plan_meta_path(plan_dir, state))
        except (OSError, ValueError):
            meta = {}

    raw_criteria = meta.get("success_criteria", [])
    if not isinstance(raw_criteria, list) or not raw_criteria:
        gate = _gate_summary_or_skipped(plan_dir)
        criteria_check = gate.get("criteria_check", {})
        if isinstance(criteria_check, dict):
            raw_criteria = criteria_check.get("items", [])

    if not isinstance(raw_criteria, list):
        return criteria

    for crit in raw_criteria:
        if not isinstance(crit, dict):
            continue
        name = crit.get("name") or crit.get("criterion")
        if not isinstance(name, str) or not name.strip():
            continue
        priority = crit.get("priority", "must")
        if priority not in {"must", "should", "info"}:
            priority = "must"
        criteria.append({
            "name": name,
            "priority": str(priority),
            "pass": "",
            "evidence": "",
        })
    return criteria


def _review_template_payload(plan_dir: Path, state: PlanState | None = None) -> dict[str, object]:
    finalize_data = read_json(plan_dir / "finalize.json")

    task_verdicts = []
    for task in finalize_data.get("tasks", []):
        task_id = task.get("id", "")
        if task_id:
            task_verdicts.append({
                "task_id": task_id,
                "reviewer_verdict": "",
                "evidence_files": [],
            })

    sense_check_verdicts = []
    for sc in finalize_data.get("sense_checks", []):
        sc_id = sc.get("id", "")
        if sc_id:
            sense_check_verdicts.append({
                "sense_check_id": sc_id,
                "verdict": "",
            })

    criteria = _criteria_from_plan_artifacts(plan_dir, state)

    return {
        "review_verdict": "",
        "criteria": criteria,
        "issues": [],
        "rework_items": [],
        "summary": "",
        "task_verdicts": task_verdicts,
        "sense_check_verdicts": sense_check_verdicts,
    }


def _parallel_review_context(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    project_dir = Path(state["config"]["project_dir"])
    gate = _gate_summary_or_skipped(plan_dir)
    settled_decisions = gate.get("settled_decisions", [])
    if not isinstance(settled_decisions, list):
        settled_decisions = []
    plan_mode = state["config"].get("mode", "code")
    if is_prose_mode(state):
        output_path = Path(state["config"]["output_path"])
        if not output_path.is_absolute():
            output_path = project_dir / output_path
        try:
            git_diff = output_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            git_diff = ""
        changed_files: list[str] = []
        large_diff = False
        diff_summary = ""
    else:
        git_diff = collect_git_diff_patch(project_dir)
        changed_files = _changed_files_from_patch(git_diff)
        large_diff = _review_diff_is_large(git_diff, changed_files)
        diff_summary = collect_git_diff_summary(project_dir) if large_diff else ""
    return {
        "project_dir": project_dir,
        "intent_block": intent_brief_reference(state),
        "git_diff": git_diff,
        "large_diff": large_diff,
        "diff_summary": diff_summary,
        "changed_files": changed_files,
        "prior_unmet_block": _prior_unmet_review_block(plan_dir, state) if large_diff else "",
        "finalize_data": read_json(plan_dir / "finalize.json"),
        "settled_decisions": settled_decisions,
        "prior_flags": load_flag_registry(plan_dir).get("flags", []),
    }


def _flag_text(flag: dict[str, Any]) -> str:
    return f"{flag.get('concern', '')} {flag.get('evidence', '')}".lower()


def _filtered_prior_flags(check: Any, flags: list[Any]) -> list[dict[str, Any]]:
    check_id = str(_check_field(check, "id") or "")
    filtered: list[dict[str, Any]] = []
    for raw_flag in flags:
        if not isinstance(raw_flag, dict):
            continue
        status = str(raw_flag.get("status", "open"))
        category = str(raw_flag.get("category", "other"))
        text = _flag_text(raw_flag)
        include = status == "addressed"
        if check_id == "coverage":
            include = include or category in {"completeness", "scope"}
        elif check_id == "placement":
            include = include or (category == "correctness" and ("/" in text or ".py" in text or "`" in text))
        elif check_id == "adjacent_calls":
            include = include or (category == "correctness" and any(term in text for term in ("caller", "call site", "downstream", "sibling")))
        elif check_id == "simplicity":
            include = include or category == "maintainability"
        if not include:
            continue
        filtered.append(
            {
                "id": str(raw_flag.get("id", "")),
                "concern": str(raw_flag.get("concern", "")),
                "category": category,
                "status": status,
                "severity": str(raw_flag.get("severity") or raw_flag.get("severity_hint") or "uncertain"),
                "evidence": str(raw_flag.get("evidence", "")),
            }
        )
    return filtered


def _build_review_checks_template(
    plan_dir: Path,
    state: PlanState,
    checks: tuple[Any, ...],
) -> list[dict[str, object]]:
    checks_template: list[dict[str, object]] = []
    for check in checks:
        entry: dict[str, object] = {
            "id": _check_field(check, "id"),
            "question": _check_field(check, "question"),
            "guidance": _check_field(check, "guidance") or "",
            "findings": [],
            "concerned_task_ids": [],
        }
        checks_template.append(entry)

    if state.get("iteration", 1) <= 1:
        return checks_template

    prior_path = plan_dir / "review.json"
    if not prior_path.exists():
        return checks_template

    prior = read_json(prior_path)
    active_check_ids = {_check_field(check, "id") for check in checks}
    prior_checks = {
        check.get("id"): check
        for check in prior.get("checks", [])
        if isinstance(check, dict) and check.get("id") in active_check_ids
    }
    registry = load_flag_registry(plan_dir)
    flag_status = {flag["id"]: flag.get("status", "open") for flag in registry.get("flags", [])}

    for entry in checks_template:
        check_id = str(entry["id"])
        prior_check = prior_checks.get(check_id)
        if not isinstance(prior_check, dict):
            continue
        prior_findings = []
        flagged_index = 0
        for finding in prior_check.get("findings", []):
            if not isinstance(finding, dict):
                continue
            flagged = bool(finding.get("flagged"))
            status = "n/a"
            if flagged:
                flagged_index += 1
                status = flag_status.get(_review_check_flag_id(check_id, flagged_index), "open")
            prior_findings.append({
                "detail": finding.get("detail", ""),
                "flagged": flagged,
                "status": finding.get("status", status),
            })
        if prior_findings:
            entry["prior_findings"] = prior_findings
    return checks_template


def _write_single_check_review_template(
    plan_dir: Path,
    state: PlanState,
    check: Any,
    filename: str,
) -> Path:
    template: dict[str, object] = {
        "checks": _build_review_checks_template(plan_dir, state, (check,)),
        "flags": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path = plan_dir / filename
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path


def _write_criteria_verdict_review_template(
    plan_dir: Path,
    state: PlanState,
    filename: str,
) -> Path:
    output_path = plan_dir / filename
    output_path.write_text(json.dumps(_review_template_payload(plan_dir, state), indent=2), encoding="utf-8")
    return output_path


def _settled_decision_lines(settled_decisions: list[object]) -> list[str]:
    lines: list[str] = []
    for item in settled_decisions:
        if isinstance(item, dict):
            decision_id = item.get("id", "DECISION")
            decision = item.get("decision", "")
            rationale = item.get("rationale", "")
            line = f"- {decision_id}: {decision}"
            if rationale:
                line += f" ({rationale})"
            lines.append(line)
            continue
        if isinstance(item, str):
            log.warning(
                "Legacy string settled_decision encountered; producer (gate) should emit dicts. "
                "Promoting in-place for this render."
            )
            lines.append(f"- [unknown id]: {item}")
    return lines


def _settled_decisions_review_block(settled_decisions: list[object]) -> str:
    if not settled_decisions:
        return "Settled decisions from gate (`gate.json`): []"
    rendered = "\n".join(_settled_decision_lines(settled_decisions))
    return textwrap.dedent(
        f"""
        Settled decisions from gate (`gate.json`):
        {rendered}
        """
    ).strip()


def single_check_review_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    check: Any,
    output_path: Path,
    pre_check_flags: list[dict[str, Any]],
    prior_flags: list[dict[str, Any]] | None = None,
) -> str:
    del root
    context = _parallel_review_context(state, plan_dir)
    check_id = _check_field(check, "id")
    question = _check_field(check, "question")
    guidance = _check_field(check, "guidance") or ""
    prior_flags = _filtered_prior_flags(check, context["prior_flags"]) if prior_flags is None else prior_flags
    prior_flags_block = ""
    if prior_flags:
        prior_flags_block = textwrap.dedent(
            f"""
            Critique flagged these concerns related to your check:
            {json_dump(prior_flags).strip()}

            For each concern above, verify in the diff whether it was resolved. Mark `verified_flag_ids: [...]` for resolved ones and `disputed_flag_ids: [...]` for unresolved ones.
            """
        ).strip()
    iteration = state.get("iteration", 1)
    iteration_context = ""
    if iteration > 1:
        iteration_context = (
            "\n\nThis is review iteration {iteration}. The template may include prior findings with their current "
            "flag status. Verify whether previously raised concerns were actually fixed before you carry them forward."
        ).format(iteration=iteration)
    if context["large_diff"]:
        diff_context = _large_diff_context_block(
            project_dir=context["project_dir"],
            diff_summary=context["diff_summary"],
            changed_files=context["changed_files"],
            prior_unmet_block=context["prior_unmet_block"],
        )
        return textwrap.dedent(
            f"""
            You are an independent parallel-review checker. Review one focused dimension of the executed patch against the original issue text.

            Project directory:
            {context["project_dir"]}

            {context["intent_block"]}

            {diff_context}

            Execution tracking state (`finalize.json`):
            {json_dump(context["finalize_data"]).strip()}

            {_settled_decisions_review_block(context["settled_decisions"])}

            Advisory mechanical pre-check flags (copy these verbatim into `pre_check_flags` in the output file):
            {json_dump(pre_check_flags).strip()}

            {prior_flags_block}

            Your output template is at: {output_path}
            Read this file first. It contains exactly one check slot.

            Check ID: {check_id}
            Question: {question}
            Guidance: {guidance}

            Requirements:
            - Anchor your reasoning to the original issue text and repository-backed inspection of the changed files above, not to any approved plan.
            - Investigate only this check.
            - Use your tools to inspect the workspace and verify this check before writing the output JSON.
            - finalize.json executor notes and claims record what the executor BELIEVED at execution time; they may be STALE (written mid-execution, before later fixes in the same run) or self-serving, and are NOT authoritative evidence. For any check backed by an objective gate — a test command, a conformance scan, a golden-file comparison — you MUST run that gate yourself with your tools and trust the LIVE result over any pass/fail count in finalize.json. If finalize.json says a gate reported N problems but the gate passes when you run it now, the gate PASSES; do not flag it as blocking on the strength of the stale note alone.
            - Populate the existing `checks[0].findings` array with concrete findings. Each finding should include:
              - `detail`: a full sentence describing what you checked and what you found
              - `flagged`: `true` when the finding represents a risk, mismatch, or unresolved question
              - `status`: use `blocking`, `significant`, `minor`, or `n/a`
              - `evidence_file` when a file path makes the finding easier to act on
            - If a concern overlaps with a settled gate decision, do NOT raise it as `blocking`. Mark it `significant` and explain that the severity was downgraded because the gate already settled that concern.
            - Use `blocking` only for issue-anchored gaps that should force another revise/execute pass.
            - Use `significant` for meaningful but non-blocking concerns, including settled-decision downgrades.
            - Use `minor` for informational quality notes that do not justify rework.
            - Use `flagged: false` with `status: "n/a"` only when the finding is purely informational and poses no downside.
            - Leave `flags` empty unless you discover an additional concern that does not fit the focused check.
            - Keep `verified_flag_ids` and `disputed_flag_ids` empty unless you are explicitly confirming or disputing an existing flag from the prior-flag block above.
            - Populate `checks[0].concerned_task_ids` with the real finalize task IDs affected by any blocking finding. Leave it empty when no specific task is implicated.
            - Preserve the `pre_check_flags` list verbatim in the output file.{iteration_context}
            """
        ).strip()
    return textwrap.dedent(
        f"""
        You are an independent parallel-review checker. Review one focused dimension of the executed patch against the original issue text.

        Project directory:
        {context["project_dir"]}

        {context["intent_block"]}

        Full git diff:
        {context["git_diff"]}

        Execution tracking state (`finalize.json`):
        {json_dump(context["finalize_data"]).strip()}

        {_settled_decisions_review_block(context["settled_decisions"])}

        Advisory mechanical pre-check flags (copy these verbatim into `pre_check_flags` in the output file):
        {json_dump(pre_check_flags).strip()}

        {prior_flags_block}

        Your output template is at: {output_path}
        Read this file first. It contains exactly one check slot.

        Check ID: {check_id}
        Question: {question}
        Guidance: {guidance}

        Requirements:
        - Anchor your reasoning to the original issue text and the full diff above, not to any approved plan.
        - Investigate only this check.
        - Populate the existing `checks[0].findings` array with concrete findings. Each finding should include:
          - `detail`: a full sentence describing what you checked and what you found
          - `flagged`: `true` when the finding represents a risk, mismatch, or unresolved question
          - `status`: use `blocking`, `significant`, `minor`, or `n/a`
          - `evidence_file` when a file path makes the finding easier to act on
        - If a concern overlaps with a settled gate decision, do NOT raise it as `blocking`. Mark it `significant` and explain that the severity was downgraded because the gate already settled that concern.
        - Use `blocking` only for issue-anchored gaps that should force another revise/execute pass.
        - Use `significant` for meaningful but non-blocking concerns, including settled-decision downgrades.
        - Use `minor` for informational quality notes that do not justify rework.
        - Use `flagged: false` with `status: "n/a"` only when the finding is purely informational and poses no downside.
        - Leave `flags` empty unless you discover an additional concern that does not fit the focused check.
        - Keep `verified_flag_ids` and `disputed_flag_ids` empty unless you are explicitly confirming or disputing an existing flag from the prior-flag block above.
        - Populate `checks[0].concerned_task_ids` with the real finalize task IDs affected by any blocking finding. Leave it empty when no specific task is implicated.
        - Preserve the `pre_check_flags` list verbatim in the output file.{iteration_context}
        """
    ).strip()


def parallel_criteria_review_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    output_path: Path,
) -> str:
    """Build the parallel-mode criteria review prompt.

    This intentionally does not wrap `_review_prompt()`. The brief literally
    asked to keep `_review_prompt()` as the parallel criteria check, but that would
    leak plan/gate/execution context that conflicts with the stronger
    issue-anchored review contract. This divergence is deliberate.
    """
    del root
    context = _parallel_review_context(state, plan_dir)
    if context["large_diff"]:
        diff_context = _large_diff_context_block(
            project_dir=context["project_dir"],
            diff_summary=context["diff_summary"],
            changed_files=context["changed_files"],
            prior_unmet_block=context["prior_unmet_block"],
        )
        return textwrap.dedent(
            f"""
            Review the execution against the original issue text and the finalized execution criteria.

            Project directory:
            {context["project_dir"]}

            {context["intent_block"]}

            {diff_context}

            Execution tracking state (`finalize.json`):
            {json_dump(context["finalize_data"]).strip()}

            {_settled_decisions_review_block(context["settled_decisions"])}

            Your output template is at: {output_path}
            Read the file first and write your final answer into that JSON structure.

            Requirements:
            - Use only the issue text, repository-backed inspection of the changed files above, `finalize.json`, and the settled decisions shown here.
            - Do not rely on any approved plan, plan metadata, gate summary, execution summary, or execution audit that are not present here.
            - Judge against the success criteria from `finalize.json`, but stay anchored to the original issue text when deciding whether the work actually solved the problem.
            - Verify each criterion with file inspection and focused commands where applicable before setting `pass`.
            - Every criterion entry is a per-criterion check: populate `pass` and concrete evidence from the files or commands you inspected.
            - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
              - `must` criteria are hard gates. A `must` criterion that fails means `needs_rework`.
              - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
              - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
              - If a criterion cannot be verified in this context, mark it `waived` with an explanation.
            - Set `review_verdict` to `needs_rework` only when at least one `must` criterion fails or actual implementation work is incomplete. Use `approved` when all `must` criteria pass, even if some `should` criteria are flagged.
            - The settled decisions above are already approved. Verify implementation against them, but do not re-litigate them.
            - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
            - `rework_items` must be structured and directly actionable. Populate `evidence_file` for every rework item with the file where the issue was observed. Populate `issues` as one-line summaries derived from `rework_items`.
            - When approved, keep both `issues` and `rework_items` empty arrays.
            """
        ).strip()
    return textwrap.dedent(
        f"""
        Review the execution against the original issue text and the finalized execution criteria.

        Project directory:
        {context["project_dir"]}

        {context["intent_block"]}

        Full git diff:
        {context["git_diff"]}

        Execution tracking state (`finalize.json`):
        {json_dump(context["finalize_data"]).strip()}

        {_settled_decisions_review_block(context["settled_decisions"])}

        Your output template is at: {output_path}
        Read the file first and write your final answer into that JSON structure.

        Requirements:
        - Use only the issue text, full git diff, `finalize.json`, and the settled decisions shown above.
        - Do not rely on any approved plan, plan metadata, gate summary, execution summary, or execution audit that are not present here.
        - Judge against the success criteria from `finalize.json`, but stay anchored to the original issue text when deciding whether the work actually solved the problem.
        - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
          - `must` criteria are hard gates. A `must` criterion that fails means `needs_rework`.
          - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
          - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
          - If a criterion cannot be verified in this context, mark it `waived` with an explanation.
        - Set `review_verdict` to `needs_rework` only when at least one `must` criterion fails or actual implementation work is incomplete. Use `approved` when all `must` criteria pass, even if some `should` criteria are flagged.
        - The settled decisions above are already approved. Verify implementation against them, but do not re-litigate them.
        - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
        - `rework_items` must be structured and directly actionable. Populate `issues` as one-line summaries derived from `rework_items`.
        - When approved, keep both `issues` and `rework_items` empty arrays.
        """
    ).strip()


def _settled_decisions_block(gate: dict[str, object]) -> str:
    settled_decisions = gate.get("settled_decisions", [])
    if not isinstance(settled_decisions, list) or not settled_decisions:
        return ""
    lines = ["Settled decisions (verify the executor implemented these correctly):"]
    lines.extend(_settled_decision_lines(settled_decisions))
    lines.append("")
    return "\n".join(lines)


def _settled_decisions_instruction(gate: dict[str, object]) -> str:
    settled_decisions = gate.get("settled_decisions", [])
    if not isinstance(settled_decisions, list) or not settled_decisions:
        return ""
    return "- The decisions listed above were settled at the gate stage. Verify that the executor implemented each settled decision correctly. Flag deviations from these decisions, but do not question the decisions themselves."


def _write_review_template(plan_dir: Path, state: PlanState) -> Path:
    """Write a pre-populated review output template and return its path.

    Pre-fills ``task_verdicts`` and ``sense_check_verdicts`` with the actual
    task IDs and sense-check IDs from ``finalize.json`` so the model only has
    to fill in verdict text instead of inventing IDs from scratch.  This is
    the same pattern used for critique templates and fixes MiniMax-M2.7's
    tendency to return empty verdict arrays.
    """
    finalize_data = read_json(plan_dir / "finalize.json")

    task_verdicts = []
    for task in finalize_data.get("tasks", []):
        task_id = task.get("id", "")
        if task_id:
            task_verdicts.append({
                "task_id": task_id,
                "reviewer_verdict": "",
                "evidence_files": [],
            })

    sense_check_verdicts = []
    for sc in finalize_data.get("sense_checks", []):
        sc_id = sc.get("id", "")
        if sc_id:
            sense_check_verdicts.append({
                "sense_check_id": sc_id,
                "verdict": "",
            })

    criteria = _criteria_from_plan_artifacts(plan_dir, state)

    template = {
        "review_verdict": "",
        "criteria": criteria,
        "issues": [],
        "rework_items": [],
        "summary": "",
        "task_verdicts": task_verdicts,
        "sense_check_verdicts": sense_check_verdicts,
    }

    output_path = plan_dir / "review_output.json"
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path


def _review_prompt(
    state: PlanState,
    plan_dir: Path,
    *,
    review_intro: str,
    criteria_guidance: str,
    task_guidance: str,
    sense_check_guidance: str,
    pre_check_flags: list[dict[str, Any]] | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    execution = read_json(plan_dir / "execution.json")
    gate = _gate_summary_or_skipped(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    settled_decisions_block = _settled_decisions_block(gate)
    settled_decisions_instruction = _settled_decisions_instruction(gate)
    diff_summary = collect_git_diff_summary(project_dir)
    audit_path = plan_dir / "execution_audit.json"
    if audit_path.exists():
        audit_block = textwrap.dedent(
            f"""
            Execution audit (`execution_audit.json`):
            {json_dump(read_json(audit_path)).strip()}
            """
        ).strip()
    else:
        audit_block = "Execution audit (`execution_audit.json`): not present. Skip that artifact gracefully and rely on `finalize.json`, `execution.json`, and the git diff."
    flag_reverify_items: list[dict[str, str]] = []
    for flag in load_flag_registry(plan_dir).get("flags", []):
        if not isinstance(flag, dict):
            continue
        status = str(flag.get("status", "open"))
        if status not in {"open", "addressed", "verified", "disputed"}:
            continue
        flag_reverify_items.append(
            {
                "id": str(flag.get("id", "")),
                "concern": str(flag.get("concern", "")),
                "severity": str(flag.get("severity") or flag.get("severity_hint") or "uncertain"),
                "status": status,
            }
        )
    flag_reverify_block = ""
    if flag_reverify_items:
        flag_reverify_block = textwrap.dedent(
            f"""
            Critique flags to re-verify against the final diff:
            {json_dump(flag_reverify_items).strip()}

            For each flag above that was raised during critique, verify whether the final diff actually addresses the concern.
            A flag is resolved only if the final diff contains code that directly addresses the concern.
            Do not trust pre-execute promises or plan claims; check the diff itself.
            Add resolved flag IDs to `verified_flag_ids`.
            For any unresolved flag, add a `rework_items` entry with `task_id: "REVIEW"`, `issue`, `expected`, `actual`, `evidence_file`, `flag_id`, and `source: "review_flag_reverify"`.
            """
        ).strip()
    pre_check_block = ""
    if pre_check_flags:
        pre_check_block = textwrap.dedent(
            f"""
            Advisory mechanical pre-check flags:
            {json_dump(pre_check_flags).strip()}

            Copy this list verbatim into the output `pre_check_flags` field.
            """
        ).strip()
    extra_sections = ""
    if flag_reverify_block:
        extra_sections += f"\n\n{flag_reverify_block}"
    if pre_check_block:
        extra_sections += f"\n\n{pre_check_block}"
    return textwrap.dedent(
        f"""
        {review_intro}

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Approved plan:
        {latest_plan}

        Execution tracking state (`finalize.json`):
        {json_dump(finalize_data).strip()}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        {settled_decisions_block}{extra_sections}

        Execution summary:
        {json_dump(execution).strip()}

        {audit_block}

        Git diff summary:
        {diff_summary}

        Requirements:
        - {criteria_guidance}
        - Trust executor evidence by default. Dig deeper only where the git diff, `execution_audit.json`, or vague notes make the claim ambiguous.
        - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
          - `must` criteria are hard gates. A `must` criterion that fails means `needs_rework`.
          - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
          - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
          - If a criterion has `requires` capabilities that are not satisfiable by container workers (e.g., `drive_browser`, `subjective_judgment`), mark it `deferred_human` — NOT `fail` or `waived`. Deferred-human criteria do NOT count toward `needs_rework`.
          - If a criterion (any priority) cannot be verified in this context (e.g., requires manual testing or runtime observation), mark it `waived` with an explanation.
        - Set `review_verdict` to `needs_rework` only when at least one `must` criterion fails or actual implementation work is incomplete. Use `approved` when all `must` criteria pass, even if some `should` criteria are flagged.
        {settled_decisions_instruction}
        - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
        - {task_guidance}
        - {sense_check_guidance}
        - Follow this JSON shape exactly:
        ```json
        {{
          "review_verdict": "approved",
          "criteria": [
            {{
              "name": "All existing tests pass",
              "priority": "must",
              "pass": "pass",
              "evidence": "Test suite ran green — 42 passed, 0 failed."
            }},
            {{
              "name": "File under ~300 lines",
              "priority": "should",
              "pass": "pass",
              "evidence": "File is 375 lines — above the target but reasonable given the component's responsibilities. Spirit met."
            }},
            {{
              "name": "Manual smoke tests pass",
              "priority": "info",
              "pass": "waived",
              "evidence": "Cannot be verified in automated review. Noted for manual QA."
            }}
          ],
          "issues": [],
          "rework_items": [],
          "summary": "Approved. All must criteria pass. The should criterion on line count is close enough given the component scope.",
          "task_verdicts": [
            {{
              "task_id": "T6",
              "reviewer_verdict": "Pass. Claimed handler changes and command evidence match the repo state.",
              "evidence_files": ["megaplan/handlers.py", "megaplan/evaluation.py"]
            }}
          ],
          "sense_check_verdicts": [
            {{
              "sense_check_id": "SC6",
              "verdict": "Confirmed. The execute blocker only fires when both evidence arrays are empty."
            }}
          ]
        }}
        ```
        - `rework_items` must be an array of structured rework directives. When `review_verdict` is `needs_rework`, populate one entry per issue with:
          - `task_id`: which finalize task this issue relates to
          - `issue`: what is wrong
          - `expected`: what correct behavior looks like
          - `actual`: what was observed
          - `evidence_file` (optional): file path supporting the finding
          - `flag_id`: critique/review flag ID when applicable, otherwise `null`
          - `source`: short machine-readable source tag when applicable, otherwise `null`
        - `issues` must still be populated as a flat one-line-per-item summary derived from `rework_items` (for backward compatibility). When approved, both `issues` and `rework_items` should be empty arrays.
        - When the work needs another execute pass, keep the same shape and change only `review_verdict` to `needs_rework`; make `issues`, `rework_items`, `summary`, and task verdicts specific enough for the executor to act on directly.
        """
    ).strip()
