"""Review-phase prompt builders."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.anchors import render_anchor_context
from arnold_pipelines.megaplan._core import (
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
from arnold_pipelines.megaplan.orchestration.completion_contract import CompletionSubject
from arnold_pipelines.megaplan.orchestration.review_evidence import collect_review_evidence
from arnold_pipelines.megaplan.types import PlanState
from arnold_pipelines.megaplan.schema_projection import schema_template_payload
from arnold_pipelines.megaplan.schemas import SCHEMAS

from ._projection import (
    PromptProjectionCapabilities,
    project_execution_audit_context,
    project_review_context,
)
from ._shared import _gate_summary_or_skipped

log = logging.getLogger(__name__)
REVIEW_EVIDENCE_FILENAME = "review_evidence.json"

LARGE_REVIEW_DIFF_MAX_BYTES = 120 * 1024
LARGE_REVIEW_DIFF_MAX_FILES = 40
COMPACT_REVIEW_PLAN_MAX_CHARS = 20_000
COMPACT_REVIEW_CONTEXT_MAX_CHARS = 60_000
REVIEW_EVIDENCE_PROMPT_MAX_CHARS = 100_000
REVIEW_EVIDENCE_MAX_REFS = 80
REVIEW_EVIDENCE_DETAIL_MAX_CHARS = 1_200
REVIEW_EVIDENCE_ARTIFACT_MAX_REFS = 8


def _with_anchor_block(prompt: str, state: PlanState, plan_dir: Path, *, audience: str) -> str:
    anchor_block = render_anchor_context(state, plan_dir, audience=audience)
    if not anchor_block:
        return prompt
    return f"{anchor_block}\n\n{prompt}"
COMPACT_REVIEW_MAX_CHANGED_FILES = 200


def _review_subject(state: PlanState) -> CompletionSubject:
    config = state.get("config", {})
    plan_name = str(config.get("plan") or config.get("plan_name") or state.get("plan_name") or "plan")
    return CompletionSubject(
        kind="plan",
        name=plan_name,
        to_state="done",
        from_state=str(state.get("current_state") or "executed"),
        phase="review",
        plan_name=plan_name,
    )


def ensure_review_evidence_for_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    """Refresh review-time evidence for explicit review prompt entrypoints."""
    project_dir = root or Path(state["config"]["project_dir"])
    return collect_review_evidence(
        plan_dir=plan_dir,
        project_dir=Path(project_dir),
        state=state,
        subject=_review_subject(state),
        iteration=state.get("iteration") if isinstance(state.get("iteration"), int) else None,
    )


def _read_review_evidence(plan_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = plan_dir / REVIEW_EVIDENCE_FILENAME
    if not path.exists():
        return None, f"`{REVIEW_EVIDENCE_FILENAME}` is absent."
    try:
        payload = read_json(path)
    except (OSError, ValueError) as exc:
        return None, f"`{REVIEW_EVIDENCE_FILENAME}` is malformed or unreadable: {exc}."
    if not isinstance(payload, dict):
        return None, f"`{REVIEW_EVIDENCE_FILENAME}` is malformed: expected a JSON object."
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return payload, f"`{REVIEW_EVIDENCE_FILENAME}` has zero evidence refs."
    return payload, None


def _review_evidence_block(plan_dir: Path) -> str:
    review_evidence, degraded_reason = _read_review_evidence(plan_dir)
    if review_evidence is None:
        return (
            "Fresh review-time evidence (`review_evidence.json`): degraded. "
            f"{degraded_reason} Treat stale execution-time artifacts as advisory and inspect the repository directly."
        )
    evidence_text = json_dump(_project_review_evidence_for_prompt(review_evidence)).strip()
    # Review evidence can enumerate thousands of changed files and long test logs.
    # Keep the prompt bounded; the durable full file remains on disk.
    evidence_text = _truncate_prompt_block(evidence_text, limit=REVIEW_EVIDENCE_PROMPT_MAX_CHARS)
    if degraded_reason:
        return textwrap.dedent(
            f"""
            Fresh review-time evidence (`review_evidence.json`): degraded.
            {degraded_reason}
            {evidence_text}
            """
        ).strip()
    return textwrap.dedent(
        f"""
        Fresh review-time evidence (`review_evidence.json`):
        {evidence_text}
        """
    ).strip()


def _project_review_evidence_for_prompt(review_evidence: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {
        "projection": "bounded_prompt_summary",
        "full_artifact": REVIEW_EVIDENCE_FILENAME,
    }
    for key in (
        "schema",
        "schema_version",
        "evidence_contract_version",
        "mode",
        "subject",
        "accepted",
        "would_block",
        "failures",
        "providers_used",
        "legacy_evidence_count",
        "unknown_evidence_count",
        "would_block_reasons",
        "artifact",
        "generated_at",
        "phase",
        "iteration",
        "base_sha",
        "head_sha",
        "invocation_id",
        "provider_diagnostics",
        "diagnostics",
    ):
        if key in review_evidence:
            projected[key] = _bounded_json_value(review_evidence[key])

    evidence = review_evidence.get("evidence")
    if isinstance(evidence, list):
        projected["evidence"] = [
            _project_evidence_ref_for_prompt(ref)
            for ref in evidence[:REVIEW_EVIDENCE_MAX_REFS]
            if isinstance(ref, dict)
        ]
        projected["evidence_count"] = len(evidence)
        omitted = len(evidence) - len(projected["evidence"])
        if omitted > 0:
            projected["evidence_refs_omitted"] = omitted

    green_suite = review_evidence.get("green_suite")
    if isinstance(green_suite, dict):
        projected["green_suite"] = _project_green_suite_for_prompt(green_suite)
    return projected


def _project_evidence_ref_for_prompt(ref: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in (
        "kind",
        "status",
        "summary",
        "trust_class",
        "provider",
        "provider_version",
        "source",
        "subject",
        "observed_at",
        "code_hash",
    ):
        if key in ref:
            projected[key] = _bounded_json_value(ref[key])
    artifact = ref.get("artifact")
    if isinstance(artifact, dict):
        projected["artifact"] = _project_artifact_ref_for_prompt(artifact)
    artifacts = ref.get("artifacts")
    if isinstance(artifacts, list):
        projected["artifacts"] = [
            _project_artifact_ref_for_prompt(item)
            for item in artifacts[:REVIEW_EVIDENCE_ARTIFACT_MAX_REFS]
            if isinstance(item, dict)
        ]
        omitted = len(artifacts) - len(projected["artifacts"])
        if omitted > 0:
            projected["artifacts_omitted"] = omitted
    if "details" in ref:
        projected["details_preview"] = _bounded_json_value(
            ref["details"], max_chars=REVIEW_EVIDENCE_DETAIL_MAX_CHARS
        )
        projected["details_full_location"] = REVIEW_EVIDENCE_FILENAME
    return projected


def _project_artifact_ref_for_prompt(artifact: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in ("path", "sha256", "artifact_type", "description"):
        if key in artifact:
            projected[key] = _bounded_json_value(artifact[key])
    return projected


def _project_green_suite_for_prompt(green_suite: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key, value in green_suite.items():
        if key == "delta" and isinstance(value, dict):
            projected[key] = {
                delta_key: len(delta_value)
                if isinstance(delta_value, list)
                else _bounded_json_value(delta_value)
                for delta_key, delta_value in value.items()
            }
        else:
            projected[key] = _bounded_json_value(value)
    return projected


def _bounded_json_value(value: Any, *, max_chars: int = REVIEW_EVIDENCE_DETAIL_MAX_CHARS) -> Any:
    if isinstance(value, str):
        return _truncate_prompt_block(value, limit=max_chars)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        preview = [_bounded_json_value(item, max_chars=max_chars) for item in value[:20]]
        if len(value) > len(preview):
            preview.append({"omitted_items": len(value) - len(preview)})
        return preview
    if isinstance(value, dict):
        text = json_dump(value)
        if len(text) > max_chars:
            return {
                "preview": _truncate_prompt_block(text, limit=max_chars),
                "full_location": REVIEW_EVIDENCE_FILENAME,
            }
        return {str(k): _bounded_json_value(v, max_chars=max_chars) for k, v in value.items()}
    return _truncate_prompt_block(str(value), limit=max_chars)


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


def _milestone_diff_base(state: PlanState | None) -> str | None:
    if state is None:
        return None
    meta = state.get("meta", {})
    if not isinstance(meta, dict):
        return None
    chain_policy = meta.get("chain_policy", {})
    if not isinstance(chain_policy, dict):
        return None
    base = chain_policy.get("milestone_base_sha")
    return base if isinstance(base, str) and base.strip() else None


def _truncate_prompt_block(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return (
        f"{text[:limit]}\n\n"
        f"[truncated {omitted:,} characters for review prompt; full data remains in "
        f"`{REVIEW_EVIDENCE_FILENAME}`]"
    )


def _compact_changed_files(files: list[str]) -> list[str]:
    if len(files) <= COMPACT_REVIEW_MAX_CHANGED_FILES:
        return files
    omitted = len(files) - COMPACT_REVIEW_MAX_CHANGED_FILES
    return [
        *files[:COMPACT_REVIEW_MAX_CHANGED_FILES],
        f"... {omitted:,} more changed files omitted from compact prompt",
    ]


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

    template = schema_template_payload(
        SCHEMAS["review.json"],
        contract="review scratch template",
    )
    template.update({
        "review_completion_status": "",
        "criteria": criteria,
        "task_verdicts": task_verdicts,
        "sense_check_verdicts": sense_check_verdicts,
    })
    return template


def _parallel_review_context(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    def _read_optional_json(name: str) -> dict[str, Any]:
        path = plan_dir / name
        if not path.exists():
            return {}
        value = read_json(path)
        return value if isinstance(value, dict) else {}

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
        diff_base = _milestone_diff_base(state)
        git_diff = collect_git_diff_patch(project_dir, base_ref=diff_base)
        changed_files = _changed_files_from_patch(git_diff)
        large_diff = _review_diff_is_large(git_diff, changed_files)
        diff_summary = collect_git_diff_summary(project_dir, base_ref=diff_base) if large_diff else ""
    return {
        "project_dir": project_dir,
        "intent_block": intent_brief_reference(state),
        "approved_plan": latest_plan_path(plan_dir, state).read_text(encoding="utf-8"),
        "git_diff": git_diff,
        "large_diff": large_diff,
        "diff_summary": diff_summary,
        "changed_files": changed_files,
        "prior_unmet_block": _prior_unmet_review_block(plan_dir, state) if large_diff else "",
        "finalize_data": _read_optional_json("finalize.json"),
        "execution_data": _read_optional_json("execution.json"),
        "execution_audit_data": _read_optional_json("execution_audit.json") or None,
        "settled_decisions": settled_decisions,
        "prior_flags": load_flag_registry(plan_dir).get("flags", []),
    }


def compact_review_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    *,
    prompt_size_error: dict[str, Any] | None = None,
    pre_check_flags: list[dict[str, Any]] | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    """Build a bounded review prompt when the normal review prompt is too large.

    The reviewer must inspect the repository directly, because this prompt
    intentionally carries summaries instead of the full patch.
    """
    ensure_review_evidence_for_prompt(state, plan_dir, root=root)
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    finalize_data = read_json(plan_dir / "finalize.json")
    execution_data = read_json(plan_dir / "execution.json")
    execution_audit_data = (
        read_json(plan_dir / "execution_audit.json")
        if (plan_dir / "execution_audit.json").exists()
        else None
    )
    projected_review, _ = _projected_review_blocks(
        finalize_data,
        execution_data,
        execution_audit_data,
        capabilities=projection_capabilities,
    )
    base_ref = _milestone_diff_base(state)
    git_diff = collect_git_diff_patch(project_dir, base_ref=base_ref)
    changed_files = _changed_files_from_patch(git_diff)
    diff_summary = collect_git_diff_summary(project_dir, base_ref=base_ref)
    diff_context = _large_diff_context_block(
        project_dir=project_dir,
        diff_summary=diff_summary,
        changed_files=_compact_changed_files(changed_files),
        prior_unmet_block=_prior_unmet_review_block(plan_dir, state),
    )
    size_note = ""
    if prompt_size_error:
        size_note = textwrap.dedent(
            f"""
            Normal review prompt overflow:
            The first review prompt was {prompt_size_error.get("prompt_size", "unknown")} characters with a limit of {prompt_size_error.get("max_chars", "unknown")}. This compact prompt is the fallback path; still produce a usable `review_verdict`.
            """
        ).strip()
    pre_check_block = ""
    if pre_check_flags:
        pre_check_block = textwrap.dedent(
            f"""
            Advisory mechanical pre-check flags:
            {json_dump(pre_check_flags).strip()}
            """
        ).strip()
    prompt = textwrap.dedent(
        f"""
        Review the execution against the original issue text and finalized criteria.

        {size_note}

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Approved plan (compact excerpt):
        {_truncate_prompt_block(latest_plan, limit=COMPACT_REVIEW_PLAN_MAX_CHARS)}

        {diff_context}

        Review execution context (`finalize.json` + `execution.json`, compact projection):
        {_truncate_prompt_block(json_dump(projected_review).strip(), limit=COMPACT_REVIEW_CONTEXT_MAX_CHARS)}

        {_execution_audit_block(execution_audit_data, capabilities=projection_capabilities)}

        {_review_evidence_block(plan_dir)}

        {_settled_decisions_review_block(_gate_summary_or_skipped(plan_dir).get("settled_decisions", []))}

        {_north_star_closeout_review_block(plan_dir)}

        {pre_check_block}

        Requirements:
        - This is degraded large-review mode. Do not fail because the full diff was too large to paste.
        - Use repository tools in the project directory to inspect the real changed files and run focused checks before writing the verdict.
        - Set `review_verdict` to `needs_rework` only for issue-anchored, deterministic failures that require another execute pass. Use `approved` when all must criteria are satisfied.
        - Set `review_completion_status` to `"incomplete"` only if repository inspection or required verification commands cannot complete; otherwise set it to `"complete"`.
        - Populate `criteria`, `issues`, `rework_items`, `summary`, `task_verdicts`, and `sense_check_verdicts` using the existing review JSON shape.
        - If uncertainty remains because the compact prompt omitted detail, record that as an advisory issue unless a deterministic check demonstrates a blocker.
        """
    ).strip()
    return _with_anchor_block(prompt, state, plan_dir, audience="compact_review")


def _projected_review_blocks(
    finalize_data: dict[str, Any],
    execution_data: dict[str, Any] | None,
    execution_audit_data: dict[str, Any] | None,
    *,
    capabilities: PromptProjectionCapabilities | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    projected_review = project_review_context(
        finalize_data,
        execution_data,
        capabilities=capabilities,
    )
    projected_audit = project_execution_audit_context(execution_audit_data)
    return projected_review, projected_audit


def _execution_audit_block(
    execution_audit_data: dict[str, Any] | None,
    *,
    capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    if execution_audit_data is None:
        return (
            "Historical execution audit context (`execution_audit.json`): not present. "
            "Skip that artifact gracefully and rely on `finalize.json`, `execution.json`, "
            "the approved plan, and the git diff."
        )
    projected_audit = project_execution_audit_context(execution_audit_data)
    return textwrap.dedent(
        f"""
        Historical execution audit context (`execution_audit.json`, prompt projection only):
        {json_dump(projected_audit).strip()}
        """
    ).strip()


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


def _north_star_closeout_review_block(plan_dir: Path) -> str:
    """Render carried blocking North Star actions as reviewer closeout blockers.

    Reviewers must treat any carried blocking North Star action that is not
    concretely resolved in the executed work as a closeout blocker: the
    milestone must not be marked complete. This complements (does not replace)
    the hard pre-check in the review→done transition. Returns an empty string
    when no carried blocking North Star actions are present.
    """
    from arnold_pipelines.megaplan.north_star_actions import (
        blocking_north_star_actions,
        read_carried_north_star_actions,
    )

    carried = read_carried_north_star_actions(plan_dir)
    blocking = blocking_north_star_actions(carried)
    if not blocking:
        return ""

    lines: list[str] = [
        "Carried blocking North Star actions (closeout blockers):",
        "",
        "These blocking plan-level concerns were identified by the gate. Each one is",
        "a closeout blocker: the milestone MUST NOT be marked complete until the action",
        "is concretely resolved in the executed work. Treat any blocking action that is",
        "NOT concretely resolved (omitted, prose-only, missing concrete plan refs, or a",
        "mismatched action type) as a hard `needs_rework` blocker, not an advisory note.",
        "",
        "Carried blocking actions:",
    ]
    for action in blocking:
        aid = action.get("id", "?")
        category = action.get("category", "?")
        action_type = action.get("action_type", "?")
        concern = action.get("concern", "")
        evidence = action.get("evidence", "")
        lines.append(f"  - {aid} | category={category} | type={action_type}")
        if concern:
            lines.append(f"    concern: {concern}")
        if evidence:
            ev = evidence[:300] + ("..." if len(evidence) > 300 else "")
            lines.append(f"    evidence: {ev}")
    lines.append("")
    lines.append(
        "For each action above, verify the executed diff concretely resolves it (a "
        "traceable change with concrete plan refs and the matching action type marker). "
        "If it is not concretely resolved, set `review_verdict` to `needs_rework` and add "
        "a blocking `rework_items` entry citing the unresolved action id. The review→done "
        "transition is independently gated on these actions, so a milestone with any "
        "unresolved blocking North Star action cannot be marked complete."
    )
    return "\n".join(lines)


def single_check_review_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    check: Any,
    output_path: Path,
    pre_check_flags: list[dict[str, Any]],
    prior_flags: list[dict[str, Any]] | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    review_evidence = ensure_review_evidence_for_prompt(state, plan_dir, root=root)
    context = _parallel_review_context(state, plan_dir)
    projected_review, _ = _projected_review_blocks(
        context["finalize_data"],
        context["execution_data"],
        context["execution_audit_data"],
        capabilities=projection_capabilities,
    )
    audit_block = _execution_audit_block(
        context["execution_audit_data"],
        capabilities=projection_capabilities,
    )
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

    def _done(prompt: str) -> str:
        return _with_anchor_block(prompt, state, plan_dir, audience="parallel_review")

    if context["large_diff"]:
        diff_context = _large_diff_context_block(
            project_dir=context["project_dir"],
            diff_summary=context["diff_summary"],
            changed_files=context["changed_files"],
            prior_unmet_block=context["prior_unmet_block"],
        )
        return _done(textwrap.dedent(
            f"""
            You are an independent parallel-review checker. Review one focused dimension of the executed patch against the original issue text.

            Project directory:
            {context["project_dir"]}

            {context["intent_block"]}

            Approved plan:
            {context["approved_plan"]}

            {diff_context}

            Review execution context (`finalize.json` + `execution.json`, prompt projection only):
            {json_dump(projected_review).strip()}

            {audit_block}

            {_review_evidence_block(plan_dir)}

            {_settled_decisions_review_block(context["settled_decisions"])}

            {_north_star_closeout_review_block(plan_dir)}

            Advisory mechanical pre-check flags (copy these verbatim into `pre_check_flags` in the output file):
            {json_dump(pre_check_flags).strip()}

            {prior_flags_block}

            Your output template is at: {output_path}
            Read this file first. It contains exactly one check slot.

            Check ID: {check_id}
            Question: {question}
            Guidance: {guidance}

            Requirements:
            - Anchor your reasoning to the original issue text first, then use the approved plan and projected execution context as supporting context for what the executor committed to deliver.
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
        ).strip())
    return _done(textwrap.dedent(
        f"""
        You are an independent parallel-review checker. Review one focused dimension of the executed patch against the original issue text.

        Project directory:
        {context["project_dir"]}

        {context["intent_block"]}

        Approved plan:
        {context["approved_plan"]}

        Full git diff:
        {context["git_diff"]}

        Review execution context (`finalize.json` + `execution.json`, prompt projection only):
        {json_dump(projected_review).strip()}

        {audit_block}

        {_review_evidence_block(plan_dir)}

        {_settled_decisions_review_block(context["settled_decisions"])}

        {_north_star_closeout_review_block(plan_dir)}

        Advisory mechanical pre-check flags (copy these verbatim into `pre_check_flags` in the output file):
        {json_dump(pre_check_flags).strip()}

        {prior_flags_block}

        Your output template is at: {output_path}
        Read this file first. It contains exactly one check slot.

        Check ID: {check_id}
        Question: {question}
        Guidance: {guidance}

        Requirements:
        - Anchor your reasoning to the original issue text first, then use the approved plan and projected execution context as supporting context for what the executor committed to deliver.
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
    ).strip())


def parallel_criteria_review_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    output_path: Path,
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    """Build the parallel-mode criteria review prompt.

    This intentionally keeps the issue-anchored review contract tighter than
    `_review_prompt()` while still keeping the approved plan inline and
    projecting oversized execution artifacts.
    """
    ensure_review_evidence_for_prompt(state, plan_dir, root=root)
    context = _parallel_review_context(state, plan_dir)
    projected_review, _ = _projected_review_blocks(
        context["finalize_data"],
        context["execution_data"],
        context["execution_audit_data"],
        capabilities=projection_capabilities,
    )
    audit_block = _execution_audit_block(
        context["execution_audit_data"],
        capabilities=projection_capabilities,
    )

    def _done(prompt: str) -> str:
        return _with_anchor_block(prompt, state, plan_dir, audience="parallel_review")

    if context["large_diff"]:
        diff_context = _large_diff_context_block(
            project_dir=context["project_dir"],
            diff_summary=context["diff_summary"],
            changed_files=context["changed_files"],
            prior_unmet_block=context["prior_unmet_block"],
        )
        return _done(textwrap.dedent(
            f"""
            Review the execution against the original issue text and the finalized execution criteria.

            Project directory:
            {context["project_dir"]}

            {context["intent_block"]}

            Approved plan:
            {context["approved_plan"]}

            {diff_context}

            Review execution context (`finalize.json` + `execution.json`, prompt projection only):
            {json_dump(projected_review).strip()}

            {audit_block}

            {_review_evidence_block(plan_dir)}

            {_settled_decisions_review_block(context["settled_decisions"])}

            {_north_star_closeout_review_block(plan_dir)}

            Your output template is at: {output_path}
            Read the file first and write your final answer into that JSON structure.

            Requirements:
            - Stay anchored to the issue text when deciding whether the work solved the problem. Use the approved plan plus the projected finalize/execution/audit context here as supporting evidence, not as substitutes for repository inspection.
            - Do not rely on plan metadata or raw gate/execution dumps that are not present here.
            - Judge against the success criteria from the projected finalize context, but stay anchored to the original issue text when deciding whether the work actually solved the problem.
            - Verify each criterion with file inspection and focused commands where applicable before setting `pass`.
            - Every criterion entry is a per-criterion check: populate `pass` and concrete evidence from the files or commands you inspected.
            - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
              - `must` criteria are hard gates. A `must` criterion that fails means `needs_rework`.
              - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
              - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
              - If a criterion cannot be verified in this context, mark it `waived` with an explanation.
            - Set `review_verdict` to `needs_rework` only when at least one `must` criterion fails or actual implementation work is incomplete. Use `approved` when all `must` criteria pass, even if some `should` criteria are flagged.
            - Set `review_completion_status` to `"incomplete"` when you could not inspect the repository or run verification commands; otherwise set it to `"complete"`.
            - The settled decisions above are already approved. Verify implementation against them, but do not re-litigate them.
            - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
            - `rework_items` must be structured and directly actionable. Populate `evidence_file` for every rework item with the file where the issue was observed. Populate `issues` as one-line summaries derived from `rework_items`.
            - When approved, keep both `issues` and `rework_items` empty arrays.
            """
        ).strip())
    return _done(textwrap.dedent(
        f"""
        Review the execution against the original issue text and the finalized execution criteria.

        Project directory:
        {context["project_dir"]}

        {context["intent_block"]}

        Approved plan:
        {context["approved_plan"]}

        Full git diff:
        {context["git_diff"]}

        Review execution context (`finalize.json` + `execution.json`, prompt projection only):
        {json_dump(projected_review).strip()}

        {audit_block}

        {_review_evidence_block(plan_dir)}

        {_settled_decisions_review_block(context["settled_decisions"])}

        {_north_star_closeout_review_block(plan_dir)}

        Your output template is at: {output_path}
        Read the file first and write your final answer into that JSON structure.

        Requirements:
        - Stay anchored to the issue text when deciding whether the work solved the problem. Use the approved plan plus the projected finalize/execution/audit context here as supporting evidence, not as substitutes for repository inspection.
        - Do not rely on plan metadata or raw gate/execution dumps that are not present here.
        - Judge against the success criteria from the projected finalize context, but stay anchored to the original issue text when deciding whether the work actually solved the problem.
        - Verify each criterion with file inspection and focused commands where applicable before setting `pass`.
        - Every criterion entry is a per-criterion check: populate `pass` and concrete evidence from the files or commands you inspected.
        - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
          - `must` criteria are hard gates only when backed by a deterministic runnable check that failed on the pre-execute baseline and still fails after execution. Ungrounded prose concerns are advisory.
          - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
          - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
          - If a criterion cannot be verified in this context, mark it `waived` with an explanation.
        - Set `review_verdict` to `needs_rework` only for a rework item with `deterministic_check: {{"command": "...", "baseline_status": "failed", "post_status": "failed"}}`. Use `approved` for prose-only concerns; record those as advisory issues instead.
        - Set `review_completion_status` to `"incomplete"` when you could not inspect the repository or run verification commands; otherwise set it to `"complete"`.
        - The settled decisions above are already approved. Verify implementation against them, but do not re-litigate them.
        - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
        - `rework_items` must be structured and directly actionable. Blocking items must include the `deterministic_check` object described above. Populate `issues` as one-line summaries derived from `rework_items`.
        - When approved, keep both `issues` and `rework_items` empty arrays.
        """
    ).strip())


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
    template = _review_template_payload(plan_dir, state)

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
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    execution = read_json(plan_dir / "execution.json")
    gate = _gate_summary_or_skipped(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    projected_review, _ = _projected_review_blocks(
        finalize_data,
        execution,
        read_json(plan_dir / "execution_audit.json")
        if (plan_dir / "execution_audit.json").exists()
        else None,
        capabilities=projection_capabilities,
    )
    settled_decisions_block = _settled_decisions_block(gate)
    settled_decisions_instruction = _settled_decisions_instruction(gate)
    north_star_closeout_block = _north_star_closeout_review_block(plan_dir)
    diff_summary = collect_git_diff_summary(project_dir, base_ref=_milestone_diff_base(state))
    audit_path = plan_dir / "execution_audit.json"
    audit_block = _execution_audit_block(
        read_json(audit_path) if audit_path.exists() else None,
        capabilities=projection_capabilities,
    )
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
            Add flag IDs that are unresolved only by prose judgment, without a deterministic pre/post failing check, to `disputed_flag_ids`.
            For any unresolved flag that is backed by a deterministic pre/post failing check, add a `rework_items` entry with a typed `target`, `issue`, `expected`, `actual`, `evidence_file`, `flag_id`, `source: "review_flag_reverify"`, and `deterministic_check`. Use `target.kind: "task"` with `task_id` for a single finalize task, `target.kind: "bulk"` with `task_ids` for a bulk operation that maps to multiple finalize tasks, or `target.kind: "manifest"` with `task_ids` for manifest-backed routes. Only use legacy `task_id: "REVIEW"` when the finding is a review blocker with no routable finalize target; execute treats that as telemetry/blocker compatibility, not runnable rework.
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
    output_path = _write_review_template(plan_dir, state)

    return textwrap.dedent(
        f"""
        {review_intro}

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Approved plan:
        {latest_plan}

        Review execution context (`finalize.json` + `execution.json`, prompt projection only):
        {json_dump(projected_review).strip()}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        {settled_decisions_block}

        {north_star_closeout_block}

        {extra_sections}

        {audit_block}

        {_review_evidence_block(plan_dir)}

        Your output template is at: {output_path}
        Read this file first — it contains the expected JSON structure with pre-populated `task_verdicts`, `sense_check_verdicts`, and `criteria`.
        Fill the JSON structure with your results and write the file back.
        If you cannot use file tools, return the populated JSON structure inline as your response instead.

        Git diff summary:
        {diff_summary}

        Requirements:
        - {criteria_guidance}
        - Fresh repository inspection and `review_evidence.json` outrank stale execution-time claims from `execution_audit.json`, `finalize.json`, and executor notes.
        - Use repository tools to inspect relevant files and run focused verification commands when behavior or tests are part of a criterion; include concrete repository-backed evidence for every criterion verdict.
        - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
          - `must` criteria are hard gates only when backed by a deterministic runnable check that failed on the pre-execute baseline and still fails after execution. Ungrounded prose concerns are advisory.
          - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
          - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
          - If a criterion has `requires` capabilities that are not satisfiable by container workers (e.g., `drive_browser`, `subjective_judgment`), mark it `deferred_human` — NOT `fail` or `waived`. Deferred-human criteria do NOT count toward `needs_rework`.
          - If a criterion (any priority) cannot be verified in this context (e.g., requires manual testing or runtime observation), mark it `waived` with an explanation.
        - Set `review_verdict` to `needs_rework` only for a rework item with `deterministic_check: {{"command": "...", "baseline_status": "failed", "post_status": "failed"}}`. Use `approved` for prose-only concerns; record those as advisory issues instead.
        - Set `review_completion_status` to `"incomplete"` when you could not inspect the repository or run verification commands; otherwise set it to `"complete"`.
        {settled_decisions_instruction}
        - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
        - {task_guidance}
        - {sense_check_guidance}
        - Follow this JSON shape exactly:
        ```json
        {{
          "review_verdict": "approved",
          "review_completion_status": "complete",
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
          - `target`: typed route for the rework. Use `{{"kind": "task", "task_id": "T6"}}` for one finalize task, `{{"kind": "bulk", "id": "bulk-1", "task_ids": ["T6", "T7"]}}` for bulk-operation findings, or `{{"kind": "manifest", "id": "manifest-path-or-ref", "task_ids": ["T6"]}}` for manifest-backed findings.
          - `task_id`: legacy compatibility only. It may mirror the single task target, or be `"REVIEW"` only for review blockers with no runnable finalize target.
          - `issue`: what is wrong
          - `expected`: what correct behavior looks like
          - `actual`: what was observed
          - `evidence_file`: file path supporting the finding
          - `flag_id`: critique/review flag ID when applicable, otherwise `null`
          - `source`: short machine-readable source tag when applicable, otherwise `null`
          - `deterministic_check` (required for blocking rework): object with `command`, `baseline_status`, and `post_status`
        - `issues` must still be populated as a flat one-line-per-item summary derived from `rework_items` (for backward compatibility). When approved, blocking `rework_items` should be empty; prose-only concerns may be summarized in `issues`.
        - When the work needs another execute pass, keep the same shape and change only `review_verdict` to `needs_rework`; make `issues`, `rework_items`, `summary`, and task verdicts specific enough for the executor to act on directly.
        """
    ).strip()
