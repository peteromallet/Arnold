"""Chain driver — run a pipeline of milestone plans with state kept in megaplan.

This replaces ad-hoc bash orchestration (`chain.sh`). A YAML spec declares an
optional seed plan and an ordered list of milestones; each milestone is
initialized from an idea file, then driven to `done` via the same auto-loop
entry point used by `megaplan auto`.

Plan state stays in megaplan. Bash is no longer responsible for polling or
deciding the next step — only for process/container liveness.

Spec format (YAML)::

    base_branch: main
    seed:
      plan: milestone-m0-from-docs-state-20260415-0217
    milestones:
      - label: m1
        idea: /workspace/ideas/M1-foundation-store.txt
        branch: megaplan/m1-foundation-store   # optional, currently informational
        profile: thoughtful                     # optional init rubric knobs
        robustness: standard
        vendor: claude
        depth: high
        critic: kimi
        with_prep: true
        with_feedback: true
        prep_direction: |               # optional steering for the prep phase
          focus on the worker shutdown path and how cancel signals propagate
          to inflight tasks; skip CLI plumbing.
        deepseek_provider: fireworks
      - label: m1a
        idea: /workspace/ideas/M1a-settings-store.txt
    on_failure:
      abort: stop_chain          # stop_chain | skip_milestone | retry_milestone
    on_escalate:
      abort: stop_chain          # stop_chain | skip_milestone | retry_milestone

Progress is persisted under ``.megaplan/plans/.chains/`` so a relaunched
process can resume where the previous run left off without dirtying milestone
branches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from arnold.pipelines.megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    DriverOutcome,
    ESCALATE_ACTIONS,
    drive as auto_drive,
)
from arnold.pipelines.megaplan._pipeline.flags import supervisor_tier_routing_on
from arnold.pipelines.megaplan.runtime.execution_environment import (
    merge_isolation_evidence,
    resolve_execution_environment,
)
from arnold.pipelines.megaplan._core import resolve_plan_dir
from arnold.pipelines.megaplan._core.user_config import VALID_VENDORS
from arnold.pipelines.megaplan.orchestration.authority_readers import (
    AuthorityDecision,
    corroborated_completed_task_ids,
)
from arnold.pipelines.megaplan.profiles import (
    VALID_CRITIC_CHOICES,
    VALID_DEEPSEEK_PROVIDER_CHOICES,
    VALID_DEPTH_CHOICES,
    _resolve_default_vendor,
    load_profile_metadata,
)
from arnold.pipelines.megaplan.runtime.process import megaplan_engine_env, megaplan_engine_root
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.planning.state import STATE_AWAITING_PR_MERGE, STATE_EXECUTED, STATE_FINALIZED
from . import spec as chain_spec

APEX_EXTREME_RETRY_CAP = chain_spec.APEX_EXTREME_RETRY_CAP
BLOCKED_EXECUTE_OUTCOME_STATUSES = chain_spec.BLOCKED_EXECUTE_OUTCOME_STATUSES
ChainSpec = chain_spec.ChainSpec
ChainState = chain_spec.ChainState
DEFAULT_MILESTONE_RETRY_CAP = chain_spec.DEFAULT_MILESTONE_RETRY_CAP
DEPTH_BUMP_ORDER = chain_spec.DEPTH_BUMP_ORDER
FailurePolicy = chain_spec.FailurePolicy
MilestoneSpec = chain_spec.MilestoneSpec
PROFILE_BUMP_ORDER = chain_spec.PROFILE_BUMP_ORDER
ROBUSTNESS_BUMP_ORDER = chain_spec.ROBUSTNESS_BUMP_ORDER
VALID_FAILURE_ACTIONS = chain_spec.VALID_FAILURE_ACTIONS
VALID_CLEAN_MILESTONE_PR_POLICIES = chain_spec.VALID_CLEAN_MILESTONE_PR_POLICIES
VALID_PREREQUISITE_POLICIES = chain_spec.VALID_PREREQUISITE_POLICIES
VALID_VALIDATION_POLICIES = chain_spec.VALID_VALIDATION_POLICIES
RESUMABLE_RETRY_STATES = frozenset({STATE_FINALIZED, STATE_EXECUTED, "critiqued", "gated"})
_bump_one_tier = chain_spec._bump_one_tier
_legacy_state_path_for = chain_spec._legacy_state_path_for
_optional_bool = chain_spec._optional_bool
_optional_choice = chain_spec._optional_choice
_runtime_policy_path_for = chain_spec._runtime_policy_path_for
_state_path_for = chain_spec._state_path_for
_warn_chain_fallback = chain_spec._warn_chain_fallback
effective_chain_policy = chain_spec.effective_chain_policy
load_chain_state = chain_spec.load_chain_state
load_runtime_policy = chain_spec.load_runtime_policy
load_spec = chain_spec.load_spec
save_chain_state = chain_spec.save_chain_state
save_runtime_policy = chain_spec.save_runtime_policy
validate_paths = chain_spec.validate_paths

log = logging.getLogger("megaplan")


TERMINAL_SKIP_STATES = ("done", "aborted", "failed")
GH_TRANSIENT_ERROR_PATTERNS = (
    " 500",
    " 502",
    " 503",
    " 504",
    "deadline exceeded",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "gateway timeout",
    "i/o timeout",
    "net/http:",
    "service unavailable",
    "bad gateway",
    "graphql: timeout",
    "graphql timeout",
    "temporary failure",
    "temporarily unavailable",
    "timed out",
    "try again",
)
GH_PR_STATE_ATTEMPTS = 3
def _write_chain_policy_into_plan_meta(
    root: Path,
    plan_name: str,
    spec: ChainSpec,
    spec_path: Path,
    milestone_label: str,
) -> None:
    """Record effective chain policy in the plan's ``state.json`` metadata.

    Reads the plan's state.json, merges ``meta.chain_policy``, and writes
    back atomically.  Does nothing if the plan directory cannot be resolved
    (best-effort, non-critical).
    """
    from arnold.pipelines.megaplan._core import read_json
    from arnold.pipelines.megaplan._core.state import write_plan_state

    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        _warn_chain_fallback(
            "M3A_WARN_CHAIN_POLICY_WRITE",
            reason="plan_dir_unavailable",
            context={"plan": plan_name},
        )
        return
    state_path = plan_dir / "state.json"
    if not state_path.exists():
        return
    try:
        state = read_json(state_path)
    except FileNotFoundError:
        return
    except json.JSONDecodeError:
        _warn_chain_fallback(
            "M3A_WARN_CHAIN_META_WRITE",
            reason="corrupt_json",
            path=state_path,
        )
        return
    except (OSError, UnicodeDecodeError):
        _warn_chain_fallback(
            "M3A_WARN_CHAIN_META_WRITE",
            reason="unreadable",
            path=state_path,
        )
        return
    if not isinstance(state, dict):
        return
    runtime_overrides = chain_spec.load_runtime_policy(spec_path)
    effective = chain_spec.effective_chain_policy(spec, runtime_overrides)
    chain_policy = {
        "prerequisite_policy": effective["prerequisite_policy"],
        "validation_policy": effective["validation_policy"],
        "review_policy": effective["review_policy"],
        "source": effective["source"],
        "milestone_label": milestone_label,
    }

    def _patch_chain_policy(current: dict[str, Any]) -> bool:
        meta = current.setdefault("meta", {})
        if not isinstance(meta, dict):
            current["meta"] = meta = {}
        meta["chain_policy"] = chain_policy
        return True

    write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_patch_chain_policy)


# ---------------------------------------------------------------------------
# Driving
# ---------------------------------------------------------------------------


def _plan_state(root: Path, plan: str, *, timeout: float) -> str:
    """Read just the `state` field of a plan via `megaplan status`.

    Returns "missing" if the plan is not found. Used to decide whether to skip
    driving (plan already terminal) vs. run the full auto loop.
    """
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "arnold.pipelines.megaplan",
                "status",
                "--project-dir",
                str(root),
                "--plan",
                plan,
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=megaplan_engine_env(),
        )
    except subprocess.TimeoutExpired:
        return "unknown"
    if proc.returncode != 0:
        return "missing"
    try:
        return json.loads(proc.stdout).get("state", "unknown")
    except json.JSONDecodeError:
        return "unknown"


from .git_ops import (
    _branch_head,
    _capture_sync_state,
    _checkout_milestone_branch,
    _claimed_nested_repo_paths,
    _claimed_nested_repos,
    _claimed_paths,
    _claimed_root_paths,
    _classify_sync_state,
    _command_env,
    _commit_and_push_phase,
    _dirty_nested_repos_from_claimed_paths,
    _dirty_worktree_paths,
    _enable_auto_merge,
    _ensure_milestone_pr,
    _is_transient_gh_error,
    _is_worktree_dirty,
    _list_open_pr_for_branch,
    _mark_pr_ready,
    _parse_pr_number_from_url,
    _pr_state,
    _reconcile_terminal_pr_state,
    _refresh_base_branch,
    _remote_branch_exists,
    _remote_branch_head,
    _reset_staged_paths,
    _run_command,
    _should_retry_gh_without_env,
)


def _init_plan(
    root: Path,
    idea_path: str,
    *,
    robustness: str,
    auto_approve: bool,
    profile: str | None = None,
    vendor: str | None = None,
    depth: str | None = None,
    critic: str | None = None,
    deepseek_provider: str | None = None,
    with_prep: bool = False,
    with_feedback: bool = False,
    prep_clarify: bool = True,
    prep_direction: str | None = None,
    phase_model: list[str] | None = None,
    writer,
) -> str:
    """Run `megaplan init --idea-file ...` and return the plan name."""
    # The init subprocess does not run from the engine root, but a spec-relative
    # idea path must be resolved against the project root here — otherwise init
    # depends on caller cwd and can fail with a misleading BRIEF_MISSING.
    root = root.resolve(strict=False)
    idea_path = str(_resolve_idea_path(root, idea_path))
    _warn_vendor_ignored_for_locked_profile(
        root,
        profile=profile,
        vendor=vendor,
        writer=writer,
    )
    args = [sys.executable, "-m", "arnold.pipelines.megaplan", "init", "--project-dir", str(root)]
    if auto_approve:
        args.append("--auto-approve")
    args.extend(["--robustness", robustness])
    if profile:
        args.extend(["--profile", profile])
    if vendor:
        args.extend(["--vendor", vendor])
    if depth:
        args.extend(["--depth", depth])
    if critic:
        args.extend(["--critic", critic])
    if deepseek_provider:
        args.extend(["--deepseek-provider", deepseek_provider])
    if with_prep:
        args.append("--with-prep")
    if with_feedback:
        args.append("--with-feedback")
    if not prep_clarify:
        args.append("--no-prep-clarify")
    if prep_direction:
        args.extend(["--prep-direction", prep_direction])
    for override in phase_model or []:
        args.extend(["--phase-model", override])
    args.extend(["--idea-file", str(idea_path)])
    writer(f"[chain] initializing plan from {idea_path}\n")
    proc = subprocess.run(
        args,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env=megaplan_engine_env(),
    )
    if proc.returncode != 0:
        raise CliError(
            "init_failed",
            f"megaplan init failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()[-400:]}",
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CliError("init_failed", f"megaplan init produced non-JSON output: {exc}") from exc
    plan = payload.get("plan")
    if not isinstance(plan, str) or not plan:
        raise CliError("init_failed", "megaplan init did not return a plan name")
    writer(f"[chain] launched plan={plan}\n")
    return plan


def _warn_vendor_ignored_for_locked_profile(
    root: Path,
    *,
    profile: str | None,
    vendor: str | None,
    writer,
) -> None:
    if not profile:
        return
    try:
        metadata = load_profile_metadata(project_dir=root)
    except Exception as exc:
        raise CliError(
            "vendor_lock_profile_load",
            "M3B_HALT_VENDOR_LOCK_PROFILE_LOAD: "
            f"failed to load profile metadata while evaluating vendor lock for profile {profile}: {exc}",
            extra={"profile": profile},
        ) from exc
    if not bool((metadata.get(profile) or {}).get("vendor_locked", False)):
        return
    effective_vendor = vendor
    inherited = False
    if effective_vendor is None:
        try:
            effective_vendor = _resolve_default_vendor()
            inherited = True
        except Exception as exc:
            raise CliError(
                "vendor_lock_resolve",
                "M3B_HALT_VENDOR_LOCK_RESOLVE: "
                f"failed to resolve the default vendor while evaluating vendor lock for profile {profile}: {exc}",
                extra={"profile": profile},
            ) from exc
    if effective_vendor not in VALID_VENDORS:
        return
    source = "inherited " if inherited else ""
    writer(
        f"[chain] WARNING: profile {profile} is vendor-locked; "
        f"{source}vendor={effective_vendor} is ignored.\n"
    )


def _drive_plan(
    root: Path,
    plan: str,
    spec: ChainSpec,
    *,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    writer,
) -> DriverOutcome:
    """Run the auto driver for a single plan."""
    return auto_drive(
        plan,
        cwd=root,
        stall_threshold=spec.stall_threshold,
        max_iterations=spec.max_iterations,
        on_escalate=spec.escalate_action,
        poll_sleep=spec.poll_sleep,
        phase_timeout=spec.phase_timeout,
        status_timeout=spec.status_timeout,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )


def _execution_batch_sort_key(path: Path) -> tuple[int, str]:
    match = re.fullmatch(r"execution_batch_(\d+)\.json", path.name)
    if match:
        return (int(match.group(1)), path.name)
    return (-1, path.name)


def _latest_execute_result(plan_dir: Path) -> str | None:
    try:
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        chain_spec._warn_chain_fallback(
            "M3A_WARN_EXECUTE_RESULT_READ",
            reason="corrupt_json",
            path=plan_dir / "state.json",
        )
        return None
    except (OSError, UnicodeDecodeError):
        chain_spec._warn_chain_fallback(
            "M3A_WARN_EXECUTE_RESULT_READ",
            reason="unreadable",
            path=plan_dir / "state.json",
        )
        return None
    history = state.get("history")
    if not isinstance(history, list):
        return None
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("step") == "execute":
            result = entry.get("result")
            return result if isinstance(result, str) else None
    return None


def _shadow_milestone_completion_verdict(
    root: Path,
    plan_name: str,
    milestone_label: str,
    outcome_status: str,
    contract_mode: str,
    *,
    log_fn: Callable[[str], None],
) -> bool:
    """Compute + persist + log a milestone-level completion verdict.

    FAIL-OPEN. Returns True only when enforce mode should block the milestone.
    """
    try:
        from arnold.pipelines.megaplan.orchestration.completion_contract import (
            CONTRACT_MODE_ENFORCE,
            CONTRACT_MODE_OFF,
            CONTRACT_MODE_SHADOW,
            CONTRACT_MODE_WARN,
            CompletionSubject,
            compute_verdict,
            extract_green_suite_info,
            normalize_contract_mode,
        )
        from arnold.pipelines.megaplan.orchestration.completion_io import write_completion_verdict

        mode = normalize_contract_mode(contract_mode)
        if mode == CONTRACT_MODE_OFF:
            return False
        # Only compute a milestone verdict for an accepted/done milestone — a
        # stopped/blocked milestone already failed loudly through normal paths.
        if outcome_status != "done":
            return False

        plan_dir = resolve_plan_dir(root, plan_name)
        if plan_dir is None:
                return False

        state: dict[str, Any] = {}
        try:
            raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                state = raw
        except Exception:
            state = {}

        config = state.get("config") if isinstance(state.get("config"), dict) else {}
        project_dir_str = config.get("project_dir") if isinstance(config, dict) else None
        if isinstance(project_dir_str, str) and project_dir_str:
            project_dir = Path(project_dir_str)
        else:
            project_dir = root

        subject = CompletionSubject(
            kind="milestone",
            name=milestone_label,
            to_state="done",
            plan_name=plan_name,
            milestone_label=milestone_label,
        )
        verdict = compute_verdict(
            plan_dir=plan_dir,
            project_dir=project_dir,
            state=state,
            subject=subject,
            mode=mode,
        )
        try:
            write_completion_verdict(plan_dir, verdict)
        except Exception:
            pass

        try:
            log_fn(verdict.one_line())
        except Exception:
            pass
        if mode in ("warn", "enforce") and verdict.would_block:
            pass
        if mode == CONTRACT_MODE_SHADOW:
            return False
        if mode == CONTRACT_MODE_WARN:
            if verdict.would_block:
                delta_dict, _ = extract_green_suite_info(verdict)
                newly_failing = (delta_dict or {}).get("newly_failing", []) if delta_dict else list(verdict.failures)
                log.warning(
                    "completion_contract_mode=warn: advisory — verdict would block "
                    "milestone %r; newly_failing=%r failures=%r",
                    milestone_label,
                    newly_failing,
                    list(verdict.failures),
                )
            return False
        if mode == CONTRACT_MODE_ENFORCE:
            delta_dict, result_status = extract_green_suite_info(verdict)
            if result_status in {"runner_error", "timeout", "not_applicable"}:
                log.warning(
                    "completion_contract_mode=enforce: milestone %r verification "
                    "status=%r — not blocking (non-deterministic result); would_block=%r",
                    milestone_label,
                    result_status,
                    verdict.would_block,
                )
                return False
            if delta_dict is None or not delta_dict.get("computable", False):
                log.warning(
                    "completion_contract_mode=enforce: milestone %r delta not "
                    "computable — not blocking; would_block=%r",
                    milestone_label,
                    verdict.would_block,
                )
                return False
            newly_failing = delta_dict.get("newly_failing") or []
            deleted_tests = delta_dict.get("deleted_tests") or []
            if not newly_failing and not deleted_tests:
                return False
            log.warning(
                "completion_contract_mode=enforce: blocking milestone %r; "
                "newly_failing=%r deleted_tests=%r",
                milestone_label,
                list(newly_failing),
                list(deleted_tests),
            )
            return True
        return False
    except Exception as exc:  # fail-open: never break a chain
        log.debug(
            "shadow milestone completion verdict failed for %r: %s",
            milestone_label,
            exc,
        )
        return False


def _latest_execution_batch_all_tasks_done(plan_dir: Path) -> tuple[bool, str]:
    batches = sorted(
        plan_dir.glob("execution_batch_*.json"),
        key=_execution_batch_sort_key,
    )
    if not batches:
        return False, "no execution_batch_*.json artifact found"
    latest = batches[-1]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, f"{latest.name} could not be read: {error}"
    if not isinstance(payload, dict):
        return False, f"{latest.name} payload is not an object"

    task_records: list[dict[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw_records = payload.get(key)
        if isinstance(raw_records, list):
            task_records.extend(item for item in raw_records if isinstance(item, dict))
    if not task_records:
        return False, f"{latest.name} has no task records"

    batch_decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids(
        task_records,
        plan_dir=plan_dir,
        decisions=batch_decisions,
    )
    incomplete = _non_authoritative_task_reasons(task_records, completed, batch_decisions)
    if incomplete:
        return False, f"{latest.name} has non-authoritative tasks: {', '.join(incomplete)}"
    finalize_path = plan_dir / "finalize.json"
    if finalize_path.exists():
        try:
            finalize_payload = json.loads(finalize_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return False, f"finalize.json could not be read: {error}"
        finalize_tasks = (
            finalize_payload.get("tasks") if isinstance(finalize_payload, dict) else None
        )
        if isinstance(finalize_tasks, list) and finalize_tasks:
            finalize_records = [task for task in finalize_tasks if isinstance(task, dict)]
            finalize_decisions: dict[str, AuthorityDecision] = {}
            finalize_completed = corroborated_completed_task_ids(
                finalize_records,
                plan_dir=plan_dir,
                decisions=finalize_decisions,
            )
            pending = _non_authoritative_task_reasons(
                finalize_records,
                finalize_completed,
                finalize_decisions,
            )
            pending.extend(_finalize_records_missing_authority_fields(finalize_records))
            if pending:
                return False, f"finalize.json has non-authoritative tasks: {', '.join(pending)}"
    return True, latest.name


def _plan_terminal_completion_is_authoritative(root: Path, plan_name: str) -> tuple[bool, str]:
    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        return True, f"plan {plan_name} directory unavailable; no chain artifacts to inspect"
    return _latest_execution_batch_all_tasks_done(plan_dir)


def _finalize_records_missing_authority_fields(
    task_records: list[dict[str, Any]],
) -> list[str]:
    missing: list[str] = []
    for task in task_records:
        task_id = str(task.get("task_id") or task.get("id") or "?")
        if any(task.get(field) for field in ("files_changed", "commands_run", "evidence_files", "sections_written", "evidence")):
            continue
        if task.get("status") in {"waived", "not_applicable"}:
            continue
        missing.append(f"{task_id}='unknown':missing_finalize_authority_fields")
    return missing


def _non_authoritative_task_reasons(
    task_records: list[dict[str, Any]],
    completed: set[str],
    decisions: dict[str, AuthorityDecision],
) -> list[str]:
    incomplete: list[str] = []
    for task in task_records:
        task_id = str(task.get("task_id") or task.get("id") or "?")
        if task_id in completed:
            continue
        decision = decisions.get(task_id)
        if decision is None:
            incomplete.append(f"{task_id}={task.get('status')!r}")
            continue
        reason = next(iter(decision.would_block_reasons), decision.status.value)
        incomplete.append(f"{task_id}={decision.status.value!r}:{reason}")
    return incomplete


def _mark_blocked_execute_as_executed(plan_dir: Path) -> None:
    from arnold.pipelines.megaplan._core.state import write_plan_state

    def _patch_blocked_execute(current: dict[str, Any]) -> bool:
        current.pop("active_step", None)
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_EXECUTED},
        mutation=_patch_blocked_execute,
    )


def _recover_blocked_execute_if_tasks_done(
    root: Path,
    outcome: DriverOutcome,
    *,
    writer,
) -> bool:
    if outcome.status not in BLOCKED_EXECUTE_OUTCOME_STATUSES:
        return False
    try:
        plan_dir = resolve_plan_dir(root, outcome.plan)
    except CliError:
        chain_spec._warn_chain_fallback(
            "M3A_WARN_BLOCKED_EXECUTE_RECOVERY",
            reason="plan_dir_unavailable",
            context={"plan": outcome.plan},
        )
        return False
    if _latest_execute_result(plan_dir) != "blocked":
        return False

    all_done, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    if not all_done:
        writer(
            f"[chain] execute result=blocked for {outcome.plan}; treating as real block: {reason}\n"
        )
        return False

    _mark_blocked_execute_as_executed(plan_dir)
    writer(
        f"[chain] execute result=blocked for {outcome.plan}, but {reason} has all tasks done; "
        "continuing from executed state\n"
    )
    return True


def _drive_plan_with_blocked_execute_recovery(
    root: Path,
    plan: str,
    spec: ChainSpec,
    *,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    writer,
) -> DriverOutcome:
    outcome = _drive_plan(
        root,
        plan,
        spec,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )
    if not _recover_blocked_execute_if_tasks_done(root, outcome, writer=writer):
        return outcome
    return _drive_plan(
        root,
        plan,
        spec,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )


def _milestone_retry_cap(milestone: "MilestoneSpec | None", spec: ChainSpec) -> int:
    """Per-milestone FRESH-reinit cap.

    Default ``DEFAULT_MILESTONE_RETRY_CAP`` (2); CAPPED at
    ``APEX_EXTREME_RETRY_CAP`` (1) for apex profile or extreme robustness
    milestones to bound the cost of the most-expensive nodes.
    """
    profile = (milestone.profile if milestone else None) or None
    robustness = (
        (milestone.robustness if milestone and milestone.robustness else spec.robustness)
        or "standard"
    )
    if profile == "apex" or robustness == "extreme":
        return APEX_EXTREME_RETRY_CAP
    return DEFAULT_MILESTONE_RETRY_CAP


def _resumable_retry_state(root: Path, plan: str | None) -> str | None:
    """Return a current_state that is safe to resume during a milestone retry."""

    if not plan:
        return None
    try:
        plan_dir = resolve_plan_dir(root, plan)
        raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (CliError, FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    current_state = raw.get("current_state")
    if isinstance(current_state, str) and current_state in RESUMABLE_RETRY_STATES:
        return current_state
    return None


def _resolve_idea_path(root: Path, idea: str) -> Path:
    idea_path = Path(idea).expanduser()
    if idea_path.is_absolute():
        return idea_path
    return root / idea_path


def _plan_artifact_paths_for_milestone(
    root: Path,
    plan_name: str,
    milestone: MilestoneSpec,
) -> list[Path]:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    artifacts = [
        plan_dir / "final.md",
        plan_dir / "finalize.json",
        plan_dir / "state.json",
        plan_dir / "contract.json",
    ]
    idea_path = _resolve_idea_path(root, milestone.idea)
    if idea_path.exists():
        resolved_idea = idea_path.resolve()
        root_resolved = root.resolve()
        if resolved_idea.is_relative_to(root_resolved):
            artifacts.append(idea_path)
        else:
            idea_copy = plan_dir / "idea.md"
            idea_copy.parent.mkdir(parents=True, exist_ok=True)
            new_content = resolved_idea.read_bytes()
            if not idea_copy.exists() or idea_copy.read_bytes() != new_content:
                idea_copy.write_bytes(new_content)
            artifacts.append(idea_copy)
    return artifacts


def _milestone_uses_hermes_backend(milestone: "MilestoneSpec") -> str | None:
    for entry in milestone.phase_model or []:
        if "=" not in entry:
            continue
        phase_step, spec = entry.split("=", 1)
        if spec.strip().startswith("hermes:") or spec.strip() == "hermes":
            return phase_step
    if milestone.with_prep:
        return "prep"
    return None


def _preflight_agent_backends(spec: "ChainSpec", *, writer) -> None:
    offenders: list[tuple[str, str]] = []
    for milestone in spec.milestones:
        phase = _milestone_uses_hermes_backend(milestone)
        if phase is not None:
            offenders.append((milestone.label, phase))
    if not offenders:
        return

    from arnold.pipelines.megaplan.workers import _is_agent_available

    if _is_agent_available("hermes"):
        return
    names = ", ".join(f"{label}:{phase}" for label, phase in offenders)
    raise CliError(
        "agent_deps_missing",
        "Chain requires the hermes/agent backend for "
        f"{names}, but it is not importable. Install with `uv pip install -e '.[agent]'`.",
    )


def _apply_ladder_action(
    action: str,
    *,
    milestone: "MilestoneSpec | None",
    state: ChainState,
    spec: ChainSpec,
    writer,
) -> str:
    """Translate a single ladder action into a chain decision.

    Returns one of "advance"/"stop"/"retry"/"skip". For the bump actions the
    escalated tier is persisted into ``state.*_bumps`` keyed by milestone label
    so the next FRESH re-init picks it up, then the milestone is retried once.
    ``bump_profile`` at apex (the top tier) is a no-op + warning that falls
    through to ``stop`` since there is nothing left to escalate.
    """
    label = milestone.label if milestone else "seed"
    if action == "stop_chain":
        return "stop"
    if action == "skip_milestone":
        return "skip"
    if action in ("retry_milestone", "resume_milestone"):
        return "retry"
    if action == "bump_profile":
        current = state.profile_bumps.get(label) or (milestone.profile if milestone else None)
        nxt, bumped = chain_spec._bump_one_tier(current, PROFILE_BUMP_ORDER)
        if not bumped:
            writer(
                f"[chain] {label}: bump_profile requested but already at top tier "
                f"({current or 'apex'}); no tier above apex — stopping\n"
            )
            return "stop"
        state.profile_bumps[label] = nxt or ""
        # Couple a depth bump so a harder retry also thinks deeper.
        cur_depth = state.depth_bumps.get(label) or (milestone.depth if milestone else None)
        d_next, d_bumped = chain_spec._bump_one_tier(cur_depth, DEPTH_BUMP_ORDER)
        if d_bumped and d_next:
            state.depth_bumps[label] = d_next
        writer(f"[chain] {label}: bumping profile → {nxt}; retrying once\n")
        return "retry"
    if action == "bump_robustness":
        current = state.robustness_bumps.get(label) or (
            (milestone.robustness if milestone and milestone.robustness else spec.robustness)
        )
        nxt, bumped = chain_spec._bump_one_tier(current, ROBUSTNESS_BUMP_ORDER)
        if not bumped:
            writer(
                f"[chain] {label}: bump_robustness requested but already at top tier "
                f"({current or 'extreme'}); stopping\n"
            )
            return "stop"
        state.robustness_bumps[label] = nxt or ""
        writer(f"[chain] {label}: bumping robustness → {nxt}; retrying once\n")
        return "retry"
    return "stop"


def _handle_outcome(
    outcome: DriverOutcome,
    *,
    spec: ChainSpec,
    writer,
    milestone: "MilestoneSpec | None" = None,
    state: ChainState | None = None,
    root: Path | None = None,
) -> str:
    """Decide the next action given a DriverOutcome, walking the ladder.

    Returns one of: "advance" (move to next milestone), "stop" (chain halts),
    "retry" (re-run the same milestone FRESH), "skip" (advance without waiting),
    "authority_blocked" (terminal claim was not corroborated).

    On a failure/escalate outcome the structured ladder is walked with a
    BOUNDED, persisted per-milestone retry counter:

      retry_milestone (up to cap; 1 for apex/extreme) →
      bump_profile / bump_robustness (once) →
      abort (stop_chain by default).

    The counter is keyed by milestone label in ``state`` so it survives resume
    and CANNOT loop forever on a deterministic failure.
    """
    status = outcome.status
    if status in {"done", "finalized"}:
        if root is not None:
            authoritative, reason = _plan_terminal_completion_is_authoritative(
                root, outcome.plan
            )
            if not authoritative:
                writer(
                    f"[chain] plan {outcome.plan} outcome={status} lacks task authority: "
                    f"{reason}\n"
                )
                return "authority_blocked"
        return "advance"
    if status == "awaiting_human":
        writer(
            f"[chain] plan {outcome.plan} paused awaiting human action: "
            f"{outcome.reason}\n"
        )
        return "stop"
    if status in ("aborted", "escalated"):
        if status == "aborted":
            writer(f"[chain] plan {outcome.plan} ended aborted\n")
        else:
            writer(f"[chain] plan {outcome.plan} escalated — applying on_escalate policy\n")
        policy = spec.on_escalate_policy
    else:
        # failed, stalled, cap, awaiting_human, blocked, … → treat as failure
        writer(f"[chain] plan {outcome.plan} ended {status}: {outcome.reason}\n")
        policy = spec.on_failure_policy

    # No state to track the counter (e.g. legacy seed path) → honor abort only.
    if state is None:
        action = policy.retry or policy.escalate or policy.abort
        if action in ("retry_milestone", "resume_milestone"):
            # Without a counter a bare retry is unsafe; degrade to abort.
            action = policy.abort
        return _apply_ladder_action(
            action, milestone=milestone, state=ChainState(), spec=spec, writer=writer
        )

    label = milestone.label if milestone else "seed"
    stage = state.ladder_stage.get(label, "retry")

    if stage == "retry" and policy.retry in ("retry_milestone", "resume_milestone"):
        cap = _milestone_retry_cap(milestone, spec)
        spent = state.retry_counts.get(label, 0)
        if spent < cap:
            state.retry_counts[label] = spent + 1
            writer(
                f"[chain] {label}: retry {spent + 1}/{cap}\n"
            )
            return "retry"
        # Retries exhausted → climb to the bump rung.
        writer(f"[chain] {label}: retries exhausted ({spent}/{cap})\n")
        state.ladder_stage[label] = "bump"
        stage = "bump"

    if stage in ("retry", "bump") and policy.escalate:
        # Take the escalate rung once, then mark terminal so the next failure
        # aborts (no infinite bump loop).
        state.ladder_stage[label] = "terminal"
        decision = _apply_ladder_action(
            policy.escalate, milestone=milestone, state=state, spec=spec, writer=writer
        )
        if decision == "retry":
            # Reset the retry counter so the post-bump run gets a fresh re-init
            # but the ladder will not re-enter the retry rung (stage=terminal).
            return "retry"
        return decision

    # No retry/escalate rungs left (or already terminal) → abort action.
    return _apply_ladder_action(
        policy.abort, milestone=milestone, state=state, spec=spec, writer=writer
    )


def _carried_wip_paths(root: Path) -> list[Path]:
    """Dirty worktree paths that are NOT megaplan's own ``.megaplan/`` artifacts.

    These represent carried working-state (the recurring carried-WIP review
    false-positive class). ``.megaplan/`` runtime artifacts are expected to be
    dirty mid-chain and never count as a dirty base.
    """
    carried: list[Path] = []
    for path in _dirty_worktree_paths(root):
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            rel = path.as_posix()
        if rel.startswith(".megaplan/") or rel == ".megaplan":
            continue
        carried.append(path)
    return carried


def _assert_clean_base(
    root: Path,
    milestone: "MilestoneSpec",
    *,
    no_push: bool,
    writer,
) -> None:
    """Assert the working base is a clean fork off main (no carried WIP).

    With ``driver.require_clean_base: true`` this runs before each milestone's
    plan init. Carried WIP (non-``.megaplan/`` dirty paths) is the documented
    source of the review false-positive halt class. We auto-clean by stashing
    when running locally (``--no-push`` / no-network), and fail loud otherwise
    so a CI/orchestrator run never silently discards real work.
    """
    carried = _carried_wip_paths(root)
    if not carried:
        return
    sample = ", ".join(p.name for p in carried[:5])
    if no_push:
        # Local/no-network: auto-clean by stashing the carried WIP.
        writer(
            f"[chain] require_clean_base: {milestone.label} base has carried WIP "
            f"({sample}); auto-stashing before init\n"
        )
        proc = subprocess.run(
            ["git", "stash", "push", "--include-untracked", "-m",
             f"megaplan-chain require_clean_base {milestone.label}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if proc.returncode != 0:
            raise CliError(
                "unclean_base",
                f"require_clean_base: failed to auto-clean carried WIP for "
                f"{milestone.label}: {proc.stderr.strip() or proc.stdout.strip()}",
            )
        remaining = _carried_wip_paths(root)
        if remaining:
            raise CliError(
                "unclean_base",
                f"require_clean_base: carried WIP persists after auto-clean for "
                f"{milestone.label}: {', '.join(p.name for p in remaining[:5])}",
            )
        return
    raise CliError(
        "unclean_base",
        f"require_clean_base: milestone {milestone.label} cannot start — the "
        f"working base carries uncommitted WIP ({sample}). Commit, stash, or run "
        f"off a clean fork of {root.name}.",
    )


def _maybe_file_ladder_ticket(
    root: Path,
    spec_path: Path,
    milestone: "MilestoneSpec",
    outcome: DriverOutcome,
    state: ChainState,
    *,
    writer,
) -> None:
    """Auto-file a megaplan ticket when a milestone halts after exhausting the
    autonomy ladder. Best-effort + fail-open: a ticketing failure never changes
    the chain outcome (the chain is already stopping)."""
    if state.ladder_stage.get(milestone.label) != "terminal":
        # Only file when the ladder was actually walked to exhaustion.
        return
    try:
        ticket = {
            "kind": "chain_ladder_exhaustion",
            "milestone": milestone.label,
            "plan": outcome.plan,
            "status": outcome.status,
            "reason": outcome.reason,
            "retries": state.retry_counts.get(milestone.label, 0),
            "profile_bump": state.profile_bumps.get(milestone.label),
            "robustness_bump": state.robustness_bumps.get(milestone.label),
            "needs": "human attention — milestone halted after retry+bump ladder",
        }
        ticket_dir = chain_spec._state_path_for(spec_path).parent / "tickets"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = ticket_dir / f"{milestone.label}-ladder-exhaustion.json"
        ticket_path.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
        writer(
            f"[chain] filed ladder-exhaustion ticket for {milestone.label} "
            f"at {ticket_path}\n"
        )
    except Exception as exc:  # fail-open
        writer(
            f"[chain] note: could not auto-file ladder ticket for "
            f"{milestone.label}: {exc}\n"
        )


def run_chain(
    spec_path: Path,
    root: Path,
    *,
    writer=sys.stdout.write,
    no_git_refresh: bool = False,
    no_push: bool = False,
    one: bool = False,
) -> dict[str, Any]:
    """Drive the full chain. Returns a structured JSON-serializable result."""
    root = root.resolve(strict=False)
    spec_path = spec_path.resolve(strict=False)
    spec = chain_spec.load_spec(spec_path)
    chain_spec.validate_paths(spec, root)
    _preflight_agent_backends(spec, writer=writer)
    state = chain_spec.load_chain_state(spec_path)
    env = resolve_execution_environment(
        root=root,
        state={"config": {"project_dir": str(root), "base_branch": spec.base_branch}},
    )
    state.metadata = merge_isolation_evidence(state.metadata, env, phase="chain_start")
    chain_spec.save_chain_state(spec_path, state)
    preexisting_dirty_paths = _dirty_worktree_paths(root)
    push_enabled = not no_push and os.environ.get("MEGAPLAN_CHAIN_NO_PUSH") not in {"1", "true", "TRUE", "yes", "YES"}

    events: list[dict[str, Any]] = []

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[chain] {msg}\n")

    # ---- Seed phase ----
    if spec.seed_plan and state.current_milestone_index < 0:
        seed_state = _plan_state(root, spec.seed_plan, timeout=spec.status_timeout)
        log(f"seed plan {spec.seed_plan} state={seed_state}")
        if seed_state not in TERMINAL_SKIP_STATES:
            state.current_plan_name = spec.seed_plan
            chain_spec.save_chain_state(spec_path, state)
            outcome = _drive_plan_with_blocked_execute_recovery(
                root,
                spec.seed_plan,
                spec,
                writer=writer,
            )
            state.last_state = outcome.status
            chain_spec.save_chain_state(spec_path, state)
            decision = _handle_outcome(outcome, spec=spec, writer=writer, root=root)
            if decision == "authority_blocked":
                state.last_state = "authority_divergence"
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=f"seed plan terminal outcome lacks authority",
                )
            if decision == "stop":
                return _result("stopped", state, events, spec=spec, reason=f"seed plan {outcome.status}")
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan_with_blocked_execute_recovery(
                    root,
                    spec.seed_plan,
                    spec,
                    writer=writer,
                )
                state.last_state = outcome.status
                chain_spec.save_chain_state(spec_path, state)
                if outcome.status != "done":
                    return _result("stopped", state, events, spec=spec, reason="seed retry failed")
                authoritative, reason = _plan_terminal_completion_is_authoritative(
                    root, spec.seed_plan
                )
                if not authoritative:
                    writer(
                        f"[chain] seed retry {spec.seed_plan} outcome=done lacks authority; "
                        f"stopping: {reason}\n"
                    )
                    state.last_state = "authority_divergence"
                    chain_spec.save_chain_state(spec_path, state)
                    return _result(
                        "blocked",
                        state,
                        events,
                        spec=spec,
                        reason=f"seed retry terminal outcome lacks authority: {reason}",
                    )
            # skip / advance both proceed to milestones
        else:
            authoritative, reason = _plan_terminal_completion_is_authoritative(
                root, spec.seed_plan
            )
            if not authoritative:
                writer(
                    f"[chain] seed plan {spec.seed_plan} terminal state={seed_state} "
                    f"lacks authority; stopping: {reason}\n"
                )
                state.last_state = "authority_divergence"
                state.current_plan_name = spec.seed_plan
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=f"seed plan terminal state lacks authority: {reason}",
                )
        state.completed.append(
            {"label": "seed", "plan": spec.seed_plan, "status": state.last_state or seed_state}
        )
        state.current_milestone_index = 0
        state.current_plan_name = None
        chain_spec.save_chain_state(spec_path, state)

    elif state.current_milestone_index < 0:
        state.current_milestone_index = 0
        chain_spec.save_chain_state(spec_path, state)

    # ---- Milestones ----
    idx = max(state.current_milestone_index, 0)
    if idx >= len(spec.milestones):
        try:
            state = _reconcile_terminal_pr_state(
                root,
                spec_path,
                state,
                writer=writer,
            )
        except CliError as exc:
            log(f"terminal PR reconciliation skipped: {exc.message}")
    while idx < len(spec.milestones):
        milestone = spec.milestones[idx]
        log(f"milestone {milestone.label} starting")
        use_pr = push_enabled and bool(milestone.branch)

        if state.last_state == STATE_AWAITING_PR_MERGE and state.current_milestone_index == idx:
            if not use_pr or state.pr_number is None:
                log(f"review merge wait for {milestone.label} has no PR context; advancing")
                state.pr_state = None
            else:
                pr_state = _pr_state(root, state.pr_number, writer=writer)
                state.pr_state = "merged" if pr_state == "merged" else "awaiting_merge"
                chain_spec.save_chain_state(spec_path, state)
                if pr_state != "merged":
                    log(f"PR #{state.pr_number} state={pr_state}; awaiting merge")
                    return _result(
                        STATE_AWAITING_PR_MERGE,
                        state,
                        events,
                        spec=spec,
                        reason=f"milestone {milestone.label} PR #{state.pr_number} is {pr_state}",
                    )
                log(f"PR #{state.pr_number} merged; advancing past {milestone.label}")
            state.completed.append(
                {
                    "label": milestone.label,
                    "plan": state.current_plan_name,
                    "status": "done",
                    "pr_number": state.pr_number,
                    "pr_state": "merged" if state.pr_number is not None else None,
                }
            )
            idx += 1
            state.current_milestone_index = idx
            state.current_plan_name = None
            state.last_state = "done"
            state.pr_number = None
            state.pr_state = None
            chain_spec.save_chain_state(spec_path, state)
            continue

        # Resume mid-milestone if we already have a plan name recorded.
        if (
            state.current_plan_name
            and state.current_milestone_index == idx
            and _plan_state(root, state.current_plan_name, timeout=spec.status_timeout)
            not in ("missing",)
        ):
            plan_name = state.current_plan_name
            log(f"resuming existing plan {plan_name} for {milestone.label}")
            if use_pr and state.pr_number is None:
                _checkout_milestone_branch(
                    root,
                    milestone.branch or "",
                    base_branch=spec.base_branch,
                    writer=writer,
                    from_origin=push_enabled and not no_git_refresh,
                )
                _capture_sync_state(
                    root, spec_path, branch=milestone.branch, pr_number=state.pr_number
                )
                state.pr_number = _ensure_milestone_pr(
                    root,
                    milestone,
                    base_branch=spec.base_branch,
                    writer=writer,
                )
                state.pr_state = "open"
                chain_spec.save_chain_state(spec_path, state)
        else:
            _refresh_base_branch(
                root,
                spec.base_branch,
                writer=writer,
                no_git_refresh=no_git_refresh,
            )
            if spec.require_clean_base:
                _assert_clean_base(
                    root,
                    milestone,
                    no_push=not push_enabled,
                    writer=writer,
                )
            if use_pr:
                _checkout_milestone_branch(
                    root,
                    milestone.branch or "",
                    base_branch=spec.base_branch,
                    writer=writer,
                    from_origin=push_enabled and not no_git_refresh,
                )
                _capture_sync_state(
                    root, spec_path, branch=milestone.branch, pr_number=None
                )
            eff_profile = state.profile_bumps.get(milestone.label) or milestone.profile
            eff_robustness = (
                state.robustness_bumps.get(milestone.label)
                or milestone.robustness
                or spec.robustness
            )
            eff_depth = state.depth_bumps.get(milestone.label) or milestone.depth
            if eff_profile != milestone.profile or eff_robustness != (
                milestone.robustness or spec.robustness
            ) or eff_depth != milestone.depth:
                log(
                    f"milestone {milestone.label} using bumped tiers "
                    f"profile={eff_profile} robustness={eff_robustness} depth={eff_depth}"
                )
            plan_name = _init_plan(
                root,
                milestone.idea,
                robustness=eff_robustness,
                auto_approve=spec.auto_approve,
                profile=eff_profile,
                vendor=milestone.vendor,
                depth=eff_depth,
                critic=milestone.critic,
                deepseek_provider=milestone.deepseek_provider,
                with_prep=milestone.with_prep,
                with_feedback=milestone.with_feedback,
                prep_clarify=milestone.prep_clarify,
                prep_direction=milestone.prep_direction,
                phase_model=milestone.phase_model,
                writer=writer,
            )
            # Record effective chain policy in the newly initialized plan's
            # state.json metadata so downstream consumers can introspect it.
            _write_chain_policy_into_plan_meta(
                root, plan_name, spec, spec_path, milestone.label
            )
            state.current_milestone_index = idx
            state.current_plan_name = plan_name
            chain_spec.save_chain_state(spec_path, state)
            if use_pr:
                _commit_and_push_phase(
                    root,
                    milestone.branch or "",
                    plan_name,
                    "init",
                    writer=writer,
                    preexisting_dirty_paths=preexisting_dirty_paths,
                )
                _capture_sync_state(
                    root, spec_path, branch=milestone.branch, pr_number=state.pr_number
                )
                state.pr_number = _ensure_milestone_pr(
                    root,
                    milestone,
                    base_branch=spec.base_branch,
                    writer=writer,
                )
                state.pr_state = "open"
                chain_spec.save_chain_state(spec_path, state)

        def phase_callback(phase: str, _code: int, _out: str, _err: str) -> None:
            if use_pr and milestone.branch:
                _commit_and_push_phase(
                    root,
                    milestone.branch,
                    plan_name,
                    phase,
                    writer=writer,
                    preexisting_dirty_paths=preexisting_dirty_paths,
                )
                _capture_sync_state(
                    root, spec_path, branch=milestone.branch, pr_number=state.pr_number
                )

        outcome = _drive_plan_with_blocked_execute_recovery(
            root,
            plan_name,
            spec,
            on_phase_complete=phase_callback if use_pr else None,
            writer=writer,
        )
        state.last_state = outcome.status
        chain_spec.save_chain_state(spec_path, state)
        decision = _handle_outcome(
            outcome, spec=spec, writer=writer, milestone=milestone, state=state, root=root
        )
        if decision == "authority_blocked":
            state.last_state = "authority_divergence"
            chain_spec.save_chain_state(spec_path, state)
            return _result(
                "blocked",
                state,
                events,
                spec=spec,
                reason=f"milestone {milestone.label} terminal outcome lacks authority",
            )
        if decision in {"advance", "skip"}:
            authoritative, reason = _plan_terminal_completion_is_authoritative(root, plan_name)
            if not authoritative:
                writer(
                    f"[chain] milestone {milestone.label} outcome={outcome.status} "
                    f"lacks task authority; stopping: {reason}\n"
                )
                state.last_state = "authority_divergence"
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=(
                        f"milestone {milestone.label} terminal outcome lacks authority: "
                        f"{reason}"
                    ),
                )

        if decision == "stop":
            _maybe_file_ladder_ticket(
                root, spec_path, milestone, outcome, state, writer=writer
            )
            chain_spec.save_chain_state(spec_path, state)
            return _result(
                "stopped",
                state,
                events,
                spec=spec,
                reason=f"milestone {milestone.label} ended {outcome.status}",
            )
        if decision == "retry":
            resumable_state = _resumable_retry_state(root, state.current_plan_name)
            if resumable_state is not None:
                log(
                    f"retrying milestone {milestone.label} by resuming plan "
                    f"{state.current_plan_name} from {resumable_state}"
                )
            else:
                log(f"retrying milestone {milestone.label}")
                state.current_plan_name = None  # force re-init next loop
            state.pr_number = None
            state.pr_state = None
            chain_spec.save_chain_state(spec_path, state)
            continue
        if decision == "advance" and use_pr and state.pr_number is not None:
            _commit_and_push_phase(
                root,
                milestone.branch or "",
                plan_name,
                "done",
                writer=writer,
                preexisting_dirty_paths=preexisting_dirty_paths,
            )
            _capture_sync_state(
                root, spec_path, branch=milestone.branch, pr_number=state.pr_number
            )
            current_pr_state = _pr_state(root, state.pr_number, writer=writer)
            if current_pr_state == "merged":
                state.pr_state = "merged"
                chain_spec.save_chain_state(spec_path, state)
            else:
                _mark_pr_ready(root, state.pr_number, writer=writer)
                if spec.merge_policy == "review":
                    state.last_state = STATE_AWAITING_PR_MERGE
                    state.pr_state = "awaiting_merge"
                    chain_spec.save_chain_state(spec_path, state)
                    log(f"PR #{state.pr_number} ready; awaiting manual merge")
                    _capture_sync_state(
                        root,
                        spec_path,
                        branch=milestone.branch,
                        pr_number=state.pr_number,
                    )
                    return _result(
                        STATE_AWAITING_PR_MERGE,
                        state,
                        events,
                        spec=spec,
                        reason=f"milestone {milestone.label} PR #{state.pr_number} awaiting merge",
                    )
                state.pr_state = _enable_auto_merge(root, state.pr_number, writer=writer)
                chain_spec.save_chain_state(spec_path, state)
        # Completion-verification contract (SHADOW-MODE, fail-open): compute +
        # persist + log a milestone-level verdict. NEVER alters the append,
        # NEVER blocks the chain, NEVER runs the suite. See
        # megaplan/orchestration/completion_contract.py.
        enforce_blocked = _shadow_milestone_completion_verdict(
            root,
            plan_name,
            milestone.label,
            outcome.status,
            state.completion_contract_mode,
            log_fn=log,
        )
        if enforce_blocked:
            max_retries = 2
            try:
                plan_dir = resolve_plan_dir(root, plan_name)
                raw_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
                if isinstance(raw_state, dict):
                    cfg = raw_state.get("config", {}) if isinstance(raw_state.get("config"), dict) else {}
                    max_retries = int(cfg.get("enforce_revise_max_retries", 2))
            except Exception:
                pass

            milestone_retry_count = int(state.enforce_revise_counts.get(milestone.label, 0))
            if milestone_retry_count >= max_retries:
                log(
                    f"completion_contract_mode=enforce: milestone {milestone.label!r} "
                    f"blocked; retry cap {max_retries} exhausted — operator action required"
                )
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=(
                        f"enforce block: milestone {milestone.label!r} revise retry cap "
                        f"({max_retries}) exhausted — operator action required"
                    ),
                )

            state.enforce_revise_counts[milestone.label] = milestone_retry_count + 1
            log(
                f"completion_contract_mode=enforce: milestone {milestone.label!r} blocked — "
                f"retry {milestone_retry_count + 1}/{max_retries}"
            )
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None
            chain_spec.save_chain_state(spec_path, state)
            continue
        # advance or skip
        state.completed.append(
            {
                "label": milestone.label,
                "plan": plan_name,
                "status": outcome.status,
                "pr_number": state.pr_number,
                "pr_state": state.pr_state,
            }
        )
        idx += 1
        state.current_milestone_index = idx
        state.current_plan_name = None
        state.pr_number = None
        state.pr_state = None
        chain_spec.save_chain_state(spec_path, state)
        if one:
            log(f"paused after milestone {milestone.label}")
            return _result(
                "paused",
                state,
                events,
                spec=spec,
                reason=f"completed one milestone: {milestone.label}",
            )

    log("all milestones complete")
    return _result("done", state, events, spec=spec)


def _result(
    status: str, state: ChainState, events: list[dict[str, Any]], *, spec: ChainSpec | None = None, reason: str = ""
) -> dict[str, Any]:
    result = {
        "status": status,
        "reason": reason,
        "chain_state": state.to_dict(),
        "events": events,
    }
    if spec is not None:
        result["base_branch"] = spec.base_branch
    return result


def format_chain_status(spec: ChainSpec, state: ChainState) -> dict[str, Any]:
    completed_labels = {
        entry.get("label")
        for entry in state.completed
        if isinstance(entry, dict) and isinstance(entry.get("label"), str)
    }
    current_milestone: dict[str, Any] | None = None
    if 0 <= state.current_milestone_index < len(spec.milestones):
        milestone = spec.milestones[state.current_milestone_index]
        current_milestone = {
            "label": milestone.label,
            "index": state.current_milestone_index,
        }
        if milestone.branch:
            current_milestone["branch"] = milestone.branch

    per_milestone: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for index, milestone in enumerate(spec.milestones):
        if milestone.label in completed_labels:
            status = "completed"
        elif index == state.current_milestone_index and state.current_plan_name:
            status = "in_progress"
        else:
            status = "pending"
        entry = {"label": milestone.label, "index": index, "status": status}
        per_milestone.append(entry)
        if status == "completed":
            completed.append({"label": milestone.label, "index": index})
        else:
            remaining.append({"label": milestone.label, "index": index})

    sync: dict[str, Any] = {
        "branch_head": state.branch_head,
        "pr_head": state.pr_head,
        "last_pushed_commit": state.last_pushed_commit,
        "dirty_flag": state.dirty_flag,
        "sync_state": state.sync_state,
    }
    summary = {
        "current_milestone": current_milestone,
        "completed": completed,
        "remaining": remaining,
        "per_milestone": per_milestone,
        "seed_plan": spec.seed_plan,
        "base_branch": spec.base_branch,
        "current_plan_name": state.current_plan_name,
        "last_state": state.last_state,
        "sync": sync,
        "policy": {
            "prerequisite_policy": spec.prerequisite_policy,
            "validation_policy": spec.validation_policy,
            "review_policy": dict(spec.review_policy or {}),
        },
    }
    if state.pr_number is not None:
        summary["pr_number"] = state.pr_number
        summary["pr_state"] = state.pr_state
    return summary


def _write_chain_status_pretty(summary: dict[str, Any], *, writer) -> None:
    current = summary.get("current_milestone")
    current_label = "none"
    if isinstance(current, dict):
        current_label = f"{current['label']} (index {current['index']})"
    completed = summary.get("completed") or []
    remaining = summary.get("remaining") or []
    completed_labels = ", ".join(item["label"] for item in completed) if completed else "none"
    remaining_labels = ", ".join(item["label"] for item in remaining) if remaining else "none"
    writer(f"Current milestone: {current_label}\n")
    writer(f"Completed: {completed_labels}\n")
    writer(f"Remaining: {remaining_labels}\n")
    if summary.get("seed_plan"):
        writer(f"Seed plan: {summary['seed_plan']}\n")
    writer(f"Base branch: {summary.get('base_branch') or 'main'}\n")
    if summary.get("current_plan_name"):
        writer(f"Current plan: {summary['current_plan_name']}\n")
    if summary.get("last_state"):
        writer(f"Last state: {summary['last_state']}\n")
    if summary.get("pr_number"):
        writer(f"Current PR: #{summary['pr_number']} ({summary.get('pr_state') or 'unknown'})\n")
    # Sync section (branch/PR sync state)
    sync = summary.get("sync") or {}
    if any(v is not None for v in sync.values()) or sync.get("dirty_flag"):
        writer("Sync:\n")
        if sync.get("branch_head"):
            writer(f"  Branch head: {sync['branch_head']}\n")
        if sync.get("pr_head"):
            writer(f"  PR head: {sync['pr_head']}\n")
        if sync.get("last_pushed_commit"):
            writer(f"  Last pushed: {sync['last_pushed_commit']}\n")
        if sync.get("dirty_flag"):
            writer("  Dirty: yes\n")
        if sync.get("sync_state"):
            writer(f"  Sync state: {sync['sync_state']}\n")
    # Policy section (chain-level policies)
    policy = summary.get("policy") or {}
    if policy:
        writer("Policy:\n")
        writer(f"  Prerequisite: {policy.get('prerequisite_policy', 'none')}\n")
        writer(f"  Validation: {policy.get('validation_policy', 'none')}\n")
        review_policy = policy.get("review_policy") or {}
        writer(f"  Review (clean_milestone_pr): {review_policy.get('clean_milestone_pr', 'auto')}\n")
    writer("Per-milestone:\n")
    for item in summary.get("per_milestone") or []:
        writer(f"  - [{item['status']}] {item['label']} (index {item['index']})\n")


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def build_chain_parser(subparsers: Any) -> None:
    chain_parser = subparsers.add_parser(
        "chain",
        help="Drive a pipeline of milestone plans described by a YAML spec",
    )
    chain_sub = chain_parser.add_subparsers(dest="chain_action")
    # No action == run. `start` is the explicit spelling, kept in sync with the
    # backcompat top-level alias.
    chain_parser.add_argument(
        "--spec",
        required=False,
        help="Path to the chain spec YAML (required at top-level or on subcommands)",
    )
    chain_parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
    _add_chain_worktree_args(chain_parser)
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone. Use this on developer checkouts where "
            "you do not want chain to stomp on the currently checked-out "
            "branch. Default: refresh enabled (preserves CI/orchestrator "
            "behavior)."
        ),
    )
    chain_parser.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "Disable milestone branch creation, PR creation, commits, and pushes. "
            "Also enabled by MEGAPLAN_CHAIN_NO_PUSH=1; intended for local/no-network tests."
        ),
    )
    chain_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    start_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    start_parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
    _add_chain_worktree_args(start_parser)
    start_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone."
        ),
    )
    start_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Disable branch/PR/push lifecycle for no-network runs.",
    )
    start_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    status_parser = chain_sub.add_parser(
        "status", help="Show persisted chain progress without driving"
    )
    status_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    status_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read chain state from this project directory instead of discovering from CWD.",
    )

    override_parser = chain_sub.add_parser(
        "override", help="Set runtime policy overrides without editing chain.yaml"
    )
    override_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    override_parser.add_argument(
        "--project-dir",
        required=False,
        help="Apply chain overrides against this project directory instead of discovering from CWD.",
    )
    override_parser.add_argument(
        "--set-prerequisite-policy",
        choices=VALID_PREREQUISITE_POLICIES,
        default=None,
        help="Set prerequisite policy at runtime (e.g. none, required)",
    )
    override_parser.add_argument(
        "--set-validation-policy",
        choices=VALID_VALIDATION_POLICIES,
        default=None,
        help="Set validation policy at runtime (e.g. none, required)",
    )
    override_parser.add_argument(
        "--set-review-clean-milestone-pr",
        choices=VALID_CLEAN_MILESTONE_PR_POLICIES,
        default=None,
        help="Set review clean_milestone_pr policy at runtime (e.g. auto, manual)",
    )


def _add_chain_worktree_args(parser: Any) -> None:
    parser.add_argument(
        "--in-worktree",
        default=None,
        metavar="NAME",
        help=(
            "Create a new git worktree at ~/Documents/.megaplan-worktrees/<name>/ "
            "on a new branch and run the whole chain inside it. Name must match "
            "^[a-z0-9][a-z0-9._-]{0,63}$. Substitutes for --project-dir."
        ),
    )
    parser.add_argument(
        "--worktree-from",
        default=None,
        metavar="GITREF",
        help=(
            "Base ref for the new worktree (default: current HEAD of the repo "
            "where `megaplan chain` was invoked). Only valid with --in-worktree."
        ),
    )
    parser.add_argument(
        "--clean-worktree",
        action="store_true",
        default=False,
        help=(
            "With --in-worktree: fork from a clean base ref and leave any "
            "uncommitted state behind in the source repo (no carry)."
        ),
    )
    parser.add_argument(
        "--carry-dirty",
        action="store_true",
        default=False,
        help=(
            "With --in-worktree: explicitly opt into carrying uncommitted state "
            "from the source repo into the new worktree. Mutually exclusive "
            "with --clean-worktree."
        ),
    )


def run_chain_cli(root: Path, args: argparse.Namespace, *, writer=sys.stderr.write) -> int:
    action = getattr(args, "chain_action", None)
    spec_arg = getattr(args, "spec", None)
    if not spec_arg:
        sys.stderr.write("megaplan chain: --spec is required\n")
        return 64
    spec_path = Path(spec_arg).expanduser().resolve()

    if action == "override":
        set_prereq = getattr(args, "set_prerequisite_policy", None)
        set_valid = getattr(args, "set_validation_policy", None)
        set_clean = getattr(args, "set_review_clean_milestone_pr", None)
        if set_prereq is None and set_valid is None and set_clean is None:
            return _emit_error(
                CliError(
                    "invalid_spec",
                    "At least one --set-* flag is required for chain override. "
                    "Use --set-prerequisite-policy, --set-validation-policy, "
                    "or --set-review-clean-milestone-pr.",
                )
            )
        try:
            spec = chain_spec.load_spec(spec_path)
        except CliError as exc:
            return _emit_error(exc)
        overrides: dict[str, Any] = chain_spec.load_runtime_policy(spec_path)
        if set_prereq is not None:
            overrides["prerequisite_policy"] = set_prereq
        if set_valid is not None:
            overrides["validation_policy"] = set_valid
        if set_clean is not None:
            review_from_overrides = overrides.get("review_policy") or {}
            review_from_overrides["clean_milestone_pr"] = set_clean
            overrides["review_policy"] = review_from_overrides
        chain_spec.save_runtime_policy(spec_path, overrides)
        effective = chain_spec.effective_chain_policy(spec, overrides)
        payload = {
            "success": True,
            "spec": str(spec_path),
            "effective_policy": effective,
            "runtime_overrides": overrides,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if action == "status":
        try:
            spec = chain_spec.load_spec(spec_path)
            chain_state = chain_spec.load_chain_state(spec_path)
        except CliError as exc:
            return _emit_error(exc)
        runtime_overrides = chain_spec.load_runtime_policy(spec_path)
        effective_policy = chain_spec.effective_chain_policy(spec, runtime_overrides)
        summary = format_chain_status(spec, chain_state)
        _write_chain_status_pretty(summary, writer=writer)
        payload = {
            "success": True,
            "spec": str(spec_path),
            "milestone_count": len(spec.milestones),
            "seed_plan": spec.seed_plan,
            "base_branch": spec.base_branch,
            "chain_state": chain_state.to_dict(),
            "summary": summary,
            "policy": effective_policy,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if action not in (None, "start"):
        return _emit_error(CliError("invalid_args", f"Unknown chain action: {action}"))

    no_git_refresh = bool(getattr(args, "no_git_refresh", False))
    no_push = bool(getattr(args, "no_push", False))
    one = bool(getattr(args, "one", False))
    try:
        if supervisor_tier_routing_on():
            from arnold.pipelines.megaplan.supervisor.chain_runner import run_chain as supervisor_run_chain

            result = supervisor_run_chain(
                spec_path,
                root,
                writer=writer,
                one=one,
            )
        else:
            result = run_chain(
                spec_path,
                root,
                no_git_refresh=no_git_refresh,
                no_push=no_push,
                one=one,
            )
    except CliError as exc:
        return _emit_error(exc)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if result["status"] in {"done", "paused"}:
        return 0
    return 1


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
