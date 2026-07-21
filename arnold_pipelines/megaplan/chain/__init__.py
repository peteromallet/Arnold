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
        deepseek_provider: direct
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
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    DriverOutcome,
    ESCALATE_ACTIONS,
    drive as auto_drive,
)
from arnold_pipelines.megaplan.feature_flags import supervisor_tier_routing_on
from arnold_pipelines.megaplan.runtime.execution_environment import (
    merge_isolation_evidence,
    resolve_execution_environment,
)
from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    atomic_write_json,
    resolve_plan_dir,
    save_state_merge_meta,
)
from arnold_pipelines.megaplan._core.user_config import VALID_VENDORS
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    _is_explained_noop_completion,
    AuthorityDecision,
    accepted_attempt_execution_projection,
    effective_execute_completed_task_ids,
    load_evidence_nucleus,
)
from arnold_pipelines.megaplan.profiles import (
    VALID_CRITIC_CHOICES,
    VALID_DEEPSEEK_PROVIDER_CHOICES,
    VALID_DEPTH_CHOICES,
    _resolve_default_vendor,
    load_profile_metadata,
)
from arnold_pipelines.megaplan.runtime.process import (
    megaplan_engine_env,
    megaplan_engine_root,
)
from arnold_pipelines.megaplan.anchors import AnchorCaptureRequest, attach_anchor_documents, resolve_anchor_path
from arnold_pipelines.megaplan.resolutions import effective_user_action_resolutions
from arnold_pipelines.megaplan.user_actions import action_resolution_status
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.planning.state import (
    STATE_AWAITING_PR_MERGE,
    STATE_BLOCKED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_PREPPED,
)
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    CHAIN_COMPLETE_ROW_ID,
    CHAIN_MILESTONE_COMPLETION_ROW_ID,
    CHAIN_MILESTONE_START_ROW_ID,
)
from . import spec as chain_spec
from .advancement import policy_for_spec

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


def _automatic_pr_progression_permitted(
    spec: ChainSpec, spec_path: Path
) -> bool:
    """Return the shared effective PR review/merge policy decision."""

    return policy_for_spec(
        spec,
        runtime_overrides=chain_spec.load_runtime_policy(spec_path),
    ).automatic_pr_progression
VALID_FAILURE_ACTIONS = chain_spec.VALID_FAILURE_ACTIONS
VALID_CLEAN_MILESTONE_PR_POLICIES = chain_spec.VALID_CLEAN_MILESTONE_PR_POLICIES
VALID_PREREQUISITE_POLICIES = chain_spec.VALID_PREREQUISITE_POLICIES
VALID_VALIDATION_POLICIES = chain_spec.VALID_VALIDATION_POLICIES
RESUMABLE_RETRY_STATES = frozenset(
    {STATE_FINALIZED, STATE_EXECUTED, "critiqued", "gated"}
)
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
NOOP_COMPLETION_SCHEMA = "megaplan.noop_completion"
NOOP_COMPLETION_SCOPES = frozenset(
    {"docs_only", "already_satisfied_by_base", "planning_only", "infra_only"}
)
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
    from arnold_pipelines.megaplan._core import read_json
    from arnold_pipelines.megaplan._core.state import write_plan_state

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
    try:
        chain_policy["milestone_base_sha"] = _current_head_sha(root)
    except CliError:
        pass

    def _patch_chain_policy(current: dict[str, Any]) -> bool:
        meta = current.setdefault("meta", {})
        if not isinstance(meta, dict):
            current["meta"] = meta = {}
        meta["chain_policy"] = chain_policy
        return True

    write_plan_state(
        plan_dir, mode="patch-many", patch={}, mutation=_patch_chain_policy
    )


def _attach_chain_anchors_to_plan(root: Path, spec_path: Path, plan_name: str, spec: ChainSpec, milestone: MilestoneSpec) -> None:
    from arnold_pipelines.megaplan._core import read_json
    from arnold_pipelines.megaplan._core.state import write_plan_state

    requests: list[AnchorCaptureRequest] = []
    if spec.anchors.north_star:
        requests.append(
            AnchorCaptureRequest(
                anchor_type="north_star",
                scope="epic",
                source_path=resolve_anchor_path(spec_path, spec.anchors.north_star),
                source_kind="chain",
                source_spec_path=spec_path,
            )
        )
    if milestone.anchors.north_star:
        requests.append(
            AnchorCaptureRequest(
                anchor_type="north_star",
                scope="plan",
                source_path=resolve_anchor_path(spec_path, milestone.anchors.north_star),
                source_kind="milestone",
                label=milestone.label,
                source_spec_path=spec_path,
            )
        )
    if not requests:
        return
    plan_dir = resolve_plan_dir(root, plan_name)
    state = read_json(plan_dir / "state.json")
    if not isinstance(state, dict):
        return

    def _patch_anchors(current: dict[str, Any]) -> bool:
        attach_anchor_documents(plan_dir=plan_dir, state=current, documents=requests, project_root=root)
        return True

    write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_patch_anchors)


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
                "-P",
                "-m",
                "arnold_pipelines.megaplan",
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
    _commit_phase,
    _dirty_nested_repos_from_claimed_paths,
    _dirty_worktree_paths,
    _enable_auto_merge,
    _ensure_milestone_pr,
    _fetch_base_branch,
    _is_transient_gh_error,
    _is_worktree_dirty,
    _list_open_pr_for_branch,
    _mark_pr_ready,
    _parse_pr_number_from_url,
    _pr_state,
    _require_git_worktree_root,
    _reconcile_terminal_pr_state,
    _refresh_base_branch,
    _remote_branch_exists,
    _remote_branch_head,
    _reset_staged_paths,
    _run_command,
    _run_git_push_command,
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
    args = [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "init",
        "--project-dir",
        str(root),
    ]
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
        raise CliError(
            "init_failed", f"megaplan init produced non-JSON output: {exc}"
        ) from exc
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
    original_cwd = Path.cwd()
    previous_provider = os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER")
    self_hosted = False
    if not previous_provider:
        try:
            self_hosted = root.resolve() == megaplan_engine_root()
        except Exception:
            self_hosted = False
        if self_hosted:
            os.environ["MEGAPLAN_ENGINE_ISOLATION_PROVIDER"] = "self_hosted_editable"
    try:
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
    finally:
        try:
            os.chdir(original_cwd)
        except FileNotFoundError:
            pass
        if self_hosted:
            if previous_provider is None:
                os.environ.pop("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", None)
            else:
                os.environ["MEGAPLAN_ENGINE_ISOLATION_PROVIDER"] = previous_provider


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


def _completed_records_by_label(chain_state: ChainState) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in chain_state.completed:
        if not isinstance(record, dict):
            continue
        label = record.get("label")
        if isinstance(label, str):
            records[label] = record
    return records


def _plan_dir_for_completed_record(root: Path, record: dict[str, Any]) -> Path | None:
    plan_name = record.get("plan")
    if not isinstance(plan_name, str) or not plan_name.strip():
        return None
    try:
        return resolve_plan_dir(root, plan_name)
    except CliError:
        fallback = root / ".megaplan" / "plans" / plan_name
        return fallback if fallback.exists() else None


def _read_plan_state_payload_from_dir(plan_dir: Path | None) -> dict[str, Any]:
    if plan_dir is None:
        return {}
    try:
        raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _project_dir_from_plan_state(root: Path, state: dict[str, Any]) -> Path:
    config = state.get("config") if isinstance(state.get("config"), dict) else {}
    project_dir_str = config.get("project_dir") if isinstance(config, dict) else None
    if isinstance(project_dir_str, str) and project_dir_str.strip():
        return Path(project_dir_str)
    return root


def _verify_completed_chain(
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    chain_state: ChainState,
) -> dict[str, Any]:
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        CompletionSubject,
        LandedDiffProvider,
        compute_verdict,
        normalize_contract_mode,
    )

    verify_mode = normalize_contract_mode(chain_state.completion_contract_mode)
    completed_records = _completed_records_by_label(chain_state)
    milestones_payload: list[dict[str, Any]] = []
    divergence_count = 0

    for milestone in spec.milestones:
        record = completed_records.get(milestone.label)
        if not isinstance(record, dict):
            continue
        status = record.get("status")
        if status not in {"done", "finalized"}:
            continue
        plan_name = record.get("plan")
        if not isinstance(plan_name, str) or not plan_name.strip():
            continue
        plan_dir = _plan_dir_for_completed_record(root, record)
        state = _read_plan_state_payload_from_dir(plan_dir)
        project_dir = _project_dir_from_plan_state(root, state)
        meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
        policy = (
            meta.get("chain_policy")
            if isinstance(meta.get("chain_policy"), dict)
            else {}
        )
        milestone_base_sha = policy.get("milestone_base_sha")
        verdict = compute_verdict(
            plan_dir=plan_dir or (root / ".megaplan" / "plans" / plan_name),
            project_dir=project_dir,
            state=state,
            subject=CompletionSubject(
                kind="milestone",
                name=milestone.label,
                to_state="done",
                plan_name=plan_name,
                milestone_label=milestone.label,
            ),
            mode=verify_mode,
            providers=(LandedDiffProvider(),),
            git_base_ref=(
                milestone_base_sha if isinstance(milestone_base_sha, str) else None
            ),
        )
        landed_diff = next(
            (ref for ref in verdict.evidence if ref.kind == "landed_diff"), None
        )
        details = landed_diff.details if landed_diff is not None else {}
        if not verdict.accepted:
            divergence_count += 1
        milestones_payload.append(
            {
                "label": milestone.label,
                "plan": plan_name,
                "status": status,
                "accepted": verdict.accepted,
                "would_block": verdict.would_block,
                "failures": list(verdict.failures),
                "files_claimed": list(details.get("files_claimed") or []),
                "files_in_diff": list(details.get("files_in_diff") or []),
                "files_in_committed_range": list(
                    details.get("files_in_committed_range") or []
                ),
                "evidence_window": dict(details.get("evidence_window") or {}),
                "diff_source": details.get("diff_source"),
            }
        )

    return {
        "success": True,
        "spec": str(spec_path),
        "mode": verify_mode,
        "milestone_count": len(spec.milestones),
        "verified_count": len(milestones_payload),
        "divergence_count": divergence_count,
        "milestones": milestones_payload,
    }


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project_relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError as exc:
        raise CliError(
            "invalid_args",
            f"path is outside project root {root}: {path}",
        ) from exc


def _load_manifest_proof_map(path: Path) -> dict[str, list[str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError("invalid_args", f"proof map not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CliError("invalid_args", f"proof map is invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CliError("invalid_args", "proof map must be a JSON object")
    if isinstance(raw.get("milestones"), dict):
        raw = raw["milestones"]
    proof_map: dict[str, list[str]] = {}
    for label, value in raw.items():
        if not isinstance(label, str) or not label:
            raise CliError("invalid_args", "proof map milestone labels must be strings")
        if not isinstance(value, list) or not value:
            raise CliError(
                "invalid_args",
                f"proof map for milestone {label!r} must be a non-empty list",
            )
        paths: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                paths.append(item.strip())
                continue
            if isinstance(item, dict):
                candidate = item.get("path")
                if isinstance(candidate, str) and candidate.strip():
                    paths.append(candidate.strip())
                    continue
            raise CliError(
                "invalid_args",
                f"proof map for milestone {label!r} contains an invalid path entry",
            )
        proof_map[label] = paths
    return proof_map


def _validation_receipt_path(
    spec_path: Path, *, milestone_label: str, validation_kind: str
) -> Path:
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", milestone_label).strip("-")
    safe_kind = re.sub(r"[^A-Za-z0-9_.-]+", "-", validation_kind).strip("-")
    return spec_path.with_name(f"validation-{safe_label}-{safe_kind}.json")


def _validation_receipt_rel_path(
    root: Path, spec_path: Path, *, milestone_label: str, validation_kind: str
) -> str:
    return _project_relative_path(
        root,
        _validation_receipt_path(
            spec_path,
            milestone_label=milestone_label,
            validation_kind=validation_kind,
        ),
    )


def _append_validation_receipt_to_proof_map(
    *,
    root: Path,
    proof_map_path: Path,
    milestone_label: str,
    receipt_path: Path,
) -> None:
    try:
        raw = json.loads(proof_map_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError("validation_failed", f"proof map not found: {proof_map_path}") from exc
    except json.JSONDecodeError as exc:
        raise CliError("validation_failed", f"proof map is invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CliError("validation_failed", "proof map must be a JSON object")
    if isinstance(raw.get("milestones"), dict):
        target = raw["milestones"]
    else:
        target = raw
    existing = target.get(milestone_label)
    if existing is None:
        target[milestone_label] = []
        existing = target[milestone_label]
    if not isinstance(existing, list):
        raise CliError(
            "validation_failed",
            f"proof map for milestone {milestone_label!r} must be a list",
        )
    receipt_rel = _project_relative_path(root, receipt_path)
    existing_paths: set[str] = set()
    for item in existing:
        if isinstance(item, str):
            existing_paths.add(item)
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            existing_paths.add(item["path"])
    if receipt_rel not in existing_paths:
        existing.append(receipt_rel)
        proof_map_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")


def _validation_receipt_artifact(
    *,
    root: Path,
    spec_path: Path,
    milestone: MilestoneSpec,
    validation: Any,
    proof_map: dict[str, list[str]],
) -> tuple[Path, str]:
    receipt_rel = _validation_receipt_rel_path(
        root,
        spec_path,
        milestone_label=milestone.label,
        validation_kind=validation.kind,
    )
    if receipt_rel not in proof_map.get(milestone.label, []):
        raise CliError(
            "invalid_args",
            f"proof map for milestone {milestone.label!r} missing validation receipt {receipt_rel}",
        )
    receipt_path = (root / receipt_rel).resolve()
    if not receipt_path.is_file():
        raise CliError(
            "invalid_args",
            f"validation receipt for milestone {milestone.label!r} not found: {receipt_path}",
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(
            "invalid_args",
            f"validation receipt for milestone {milestone.label!r} is invalid JSON: {exc}",
        ) from exc
    if not isinstance(receipt, dict):
        raise CliError("invalid_args", f"validation receipt {receipt_path} must be an object")
    expected = {
        "schema": "arnold.megaplan.milestone_validation_receipt.v1",
        "milestone": milestone.label,
        "kind": validation.kind,
        "returncode": 0,
        "conformance": validation.conformance,
        "traceability": validation.traceability,
        "proof_map": validation.proof_map,
    }
    for key, expected_value in expected.items():
        if receipt.get(key) != expected_value:
            raise CliError(
                "invalid_args",
                f"validation receipt {receipt_rel} has invalid {key}; expected {expected_value!r}",
            )
    for key, rel_path in (
        ("validator_sha256", validation.validator),
        ("conformance_sha256", validation.conformance),
        ("traceability_sha256", validation.traceability),
    ):
        if not isinstance(rel_path, str):
            raise CliError("invalid_args", f"validation receipt {receipt_rel} missing source path for {key}")
        path = (root / rel_path).resolve()
        if not path.is_file() or receipt.get(key) != _sha256_path(path):
            raise CliError(
                "invalid_args",
                f"validation receipt {receipt_rel} has stale {key}",
            )
    return receipt_path, receipt_rel


def _ensure_validation_receipts_in_proof_map(
    *,
    root: Path,
    spec_path: Path,
    milestone: MilestoneSpec,
    proof_map: dict[str, list[str]],
) -> None:
    for validation in milestone.validate:
        _validation_receipt_artifact(
            root=root,
            spec_path=spec_path,
            milestone=milestone,
            validation=validation,
            proof_map=proof_map,
        )


def _current_git_head(root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _require_validation_checkout_at_ref(
    *,
    root: Path,
    spec: ChainSpec,
    expected_sha: str,
) -> None:
    head = _current_git_head(root)
    if head != expected_sha:
        raise CliError(
            "validation_failed",
            f"validation requires local HEAD to match refreshed origin/{spec.base_branch} "
            f"after merge sync; expected {expected_sha}, got {head or 'unknown'}",
        )


def _run_milestone_validations(
    *,
    root: Path,
    spec_path: Path,
    milestone: MilestoneSpec,
    writer: Callable[[str], None],
) -> None:
    if not milestone.validate:
        return
    for validation in milestone.validate:
        if validation.kind != "final_conformance_gate":
            raise CliError(
                "validation_failed",
                f"unsupported validation kind {validation.kind!r} for {milestone.label}",
            )
        assert validation.validator is not None
        assert validation.conformance is not None
        assert validation.traceability is not None
        assert validation.proof_map is not None
        validator_path = (root / validation.validator).resolve()
        conformance_path = (root / validation.conformance).resolve()
        traceability_path = (root / validation.traceability).resolve()
        proof_map_path = (root / validation.proof_map).resolve()
        for label, path in (
            ("validator", validator_path),
            ("conformance", conformance_path),
            ("traceability", traceability_path),
            ("proof_map", proof_map_path),
        ):
            if not path.is_file():
                raise CliError(
                    "validation_failed",
                    f"{validation.kind} for {milestone.label} missing {label}: {path}",
                )
        receipt_path = _validation_receipt_path(
            spec_path,
            milestone_label=milestone.label,
            validation_kind=validation.kind,
        )
        started_at = datetime.now(timezone.utc).isoformat()
        cmd = [
            sys.executable,
            _project_relative_path(root, validator_path),
            "--conformance",
            _project_relative_path(root, conformance_path),
            "--traceability",
            _project_relative_path(root, traceability_path),
            "--repo-root",
            str(root),
        ]
        writer(f"[chain] validating {milestone.label}: {' '.join(cmd)}\n")
        proc_returncode: int
        stdout = ""
        stderr = ""
        runner_status = "completed"
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
                env=megaplan_engine_env(),
            )
            proc_returncode = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            proc_returncode = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else str(exc)
            runner_status = "timeout"
        except OSError as exc:
            proc_returncode = 127
            stderr = str(exc)
            runner_status = "runner_error"
        finished_at = datetime.now(timezone.utc).isoformat()
        receipt = {
            "schema": "arnold.megaplan.milestone_validation_receipt.v1",
            "milestone": milestone.label,
            "kind": validation.kind,
            "command": cmd,
            "returncode": proc_returncode,
            "runner_status": runner_status,
            "stdout": stdout,
            "stderr": stderr,
            "conformance": _project_relative_path(root, conformance_path),
            "traceability": _project_relative_path(root, traceability_path),
            "proof_map": _project_relative_path(root, proof_map_path),
            "validator": _project_relative_path(root, validator_path),
            "validator_sha256": _sha256_path(validator_path),
            "conformance_sha256": _sha256_path(conformance_path),
            "traceability_sha256": _sha256_path(traceability_path),
            "proof_map_sha256_before": _sha256_path(proof_map_path),
            "git_head": _current_git_head(root),
            "started_at": started_at,
            "finished_at": finished_at,
        }
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        if proc_returncode != 0:
            detail = (stderr or stdout or "").strip()
            raise CliError(
                "validation_failed",
                f"{validation.kind} for {milestone.label} failed; receipt={receipt_path}"
                + (f"; {detail}" if detail else ""),
            )


def _finalize_validation_artifacts_after_done_append(
    *,
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    milestone: MilestoneSpec,
    writer: Callable[[str], None],
) -> str | None:
    if not milestone.validate:
        return None
    proof_map_paths: dict[Path, bytes] = {}
    for validation in milestone.validate:
        if validation.proof_map is None:
            continue
        proof_map_path = (root / validation.proof_map).resolve()
        if proof_map_path not in proof_map_paths:
            proof_map_paths[proof_map_path] = proof_map_path.read_bytes()
    rolled_back_record: dict[str, Any] | None = None
    try:
        for validation in milestone.validate:
            if validation.proof_map is None:
                continue
            receipt_path = _validation_receipt_path(
                spec_path,
                milestone_label=milestone.label,
                validation_kind=validation.kind,
            )
            _append_validation_receipt_to_proof_map(
                root=root,
                proof_map_path=(root / validation.proof_map).resolve(),
                milestone_label=milestone.label,
                receipt_path=receipt_path,
            )
        if state.current_milestone_index >= len(spec.milestones):
            proof_map = milestone.validate[-1].proof_map
            if proof_map is not None:
                proof_map_path = (root / proof_map).resolve()
                writer(
                    "[chain] writing completion manifest after validated final milestone "
                    f"{milestone.label}\n"
                )
                result = _write_completion_manifest(
                    root=root,
                    spec_path=spec_path,
                    spec=spec,
                    state=state,
                    proof_map_path=proof_map_path,
                    output_path=None,
                )
                writer(
                    "[chain] completion manifest written "
                    f"{result['manifest']} sha256={result['manifest_sha256']}\n"
                )
    except CliError as exc:
        for proof_map_path, original in proof_map_paths.items():
            proof_map_path.write_bytes(original)
        kept: list[dict[str, Any]] = []
        for record in state.completed:
            if isinstance(record, dict) and record.get("label") == milestone.label:
                rolled_back_record = record
                continue
            kept.append(record)
        state.completed = kept
        state.current_milestone_index = max(len(spec.milestones) - 1, 0)
        if rolled_back_record is not None:
            plan = rolled_back_record.get("plan")
            state.current_plan_name = plan if isinstance(plan, str) else None
            pr_number = rolled_back_record.get("pr_number")
            state.pr_number = pr_number if isinstance(pr_number, int) else None
            pr_state = rolled_back_record.get("pr_state")
            state.pr_state = pr_state if isinstance(pr_state, str) else None
        state.last_state = "validation_failed"
        chain_spec.save_chain_state(spec_path, state)
        return (
            f"milestone {milestone.label} validation finalization failed: "
            f"{exc.message}"
        )
    state.metadata.pop("pending_validation", None)
    chain_spec.save_chain_state(spec_path, state)
    return None


def _run_milestone_validations_blocking(
    *,
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    milestone: MilestoneSpec,
    writer: Callable[[str], None],
    refresh_base: bool,
    no_git_refresh: bool,
) -> str | None:
    if not milestone.validate:
        return None
    try:
        if refresh_base:
            refreshed = _refresh_base_branch(
                root,
                spec.base_branch,
                writer=writer,
                no_git_refresh=no_git_refresh,
                expected_sha=None,
            )
            if isinstance(refreshed, str) and refreshed:
                state.target_base_ref = refreshed
                chain_spec.save_chain_state(spec_path, state)
            if not no_git_refresh:
                expected_sha = refreshed or _remote_branch_head(root, spec.base_branch)
                if expected_sha:
                    _require_validation_checkout_at_ref(
                        root=root,
                        spec=spec,
                        expected_sha=expected_sha,
                    )
                    state.target_base_ref = expected_sha
                    chain_spec.save_chain_state(spec_path, state)
        _run_milestone_validations(
            root=root,
            spec_path=spec_path,
            milestone=milestone,
            writer=writer,
        )
    except CliError as exc:
        state.last_state = "validation_failed"
        state.metadata["pending_validation"] = {
            "milestone": milestone.label,
            "phase": "validator_failed",
            "reason": exc.message,
        }
        chain_spec.save_chain_state(spec_path, state)
        return f"milestone {milestone.label} validation failed: {exc.message}"
    return None


def _completion_records_by_label_strict(state: ChainState) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for record in state.completed:
        if not isinstance(record, dict):
            continue
        label = record.get("label")
        if not isinstance(label, str) or not label:
            continue
        if label in records:
            duplicates.add(label)
        records[label] = record
    if duplicates:
        raise CliError(
            "invalid_chain_state",
            f"chain state has duplicate completed records for {sorted(duplicates)}",
        )
    return records


def _record_pr_merge_sha(root: Path, record: dict[str, Any]) -> str:
    merge_sha, source = _published_pr_target_from_record(record)
    if merge_sha:
        return merge_sha
    pr_number = record.get("pr_number")
    if not isinstance(pr_number, int):
        raise CliError(
            "invalid_chain_state",
            f"completed record {record.get('label')!r} is missing PR number",
        )
    merge_sha, reason = _published_pr_target_from_gh(root, pr_number)
    if merge_sha:
        return merge_sha
    raise CliError(
        "invalid_chain_state",
        f"completed record {record.get('label')!r} has no merge SHA ({source}; {reason})",
    )


def _build_completion_manifest(
    *,
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    proof_map: dict[str, list[str]],
) -> dict[str, Any]:
    if state.current_plan_name is not None:
        raise CliError(
            "invalid_chain_state",
            f"chain still has active plan {state.current_plan_name!r}",
        )
    if state.current_milestone_index < len(spec.milestones):
        raise CliError(
            "invalid_chain_state",
            "chain has not advanced past all milestones",
        )
    records_by_label = _completion_records_by_label_strict(state)
    manifest: dict[str, Any] = {
        "schema": "arnold.megaplan.chain_completion_manifest.v1",
        "chain": {
            "path": _project_relative_path(root, spec_path),
            "sha256": _sha256_path(spec_path),
        },
        "milestones": [],
    }
    if spec.anchors.north_star:
        north_star_path = resolve_anchor_path(spec_path, spec.anchors.north_star)
        if not north_star_path.is_file():
            raise CliError(
                "invalid_spec",
                f"chain North Star not found: {north_star_path}",
            )
        manifest["north_star"] = {
            "path": _project_relative_path(root, north_star_path),
            "sha256": _sha256_path(north_star_path),
        }
    for milestone in spec.milestones:
        record = records_by_label.get(milestone.label)
        if not record:
            raise CliError(
                "invalid_chain_state",
                f"chain state missing completed record for {milestone.label!r}",
            )
        if record.get("status") != "done":
            raise CliError(
                "invalid_chain_state",
                f"completed record {milestone.label!r} status must be 'done'",
            )
        plan = record.get("plan")
        if not isinstance(plan, str) or not plan.strip():
            raise CliError(
                "invalid_chain_state",
                f"completed record {milestone.label!r} missing plan name",
            )
        brief_path = (root / milestone.idea).resolve()
        if not brief_path.is_file():
            raise CliError(
                "invalid_spec",
                f"milestone {milestone.label!r} brief not found: {brief_path}",
            )
        proof_entries: list[dict[str, str]] = []
        for proof in proof_map.get(milestone.label, []):
            proof_path = (root / proof).resolve()
            if not proof_path.is_file():
                raise CliError(
                    "invalid_args",
                    f"proof artifact for milestone {milestone.label!r} not found: {proof_path}",
                )
            proof_entries.append(
                {
                    "path": _project_relative_path(root, proof_path),
                    "sha256": _sha256_path(proof_path),
                }
            )
        _ensure_validation_receipts_in_proof_map(
            root=root,
            spec_path=spec_path,
            milestone=milestone,
            proof_map=proof_map,
        )
        if not proof_entries:
            raise CliError(
                "invalid_args",
                f"proof map missing proof artifacts for milestone {milestone.label!r}",
            )
        milestone_entry: dict[str, Any] = {
            "label": milestone.label,
            "brief_path": _project_relative_path(root, brief_path),
            "brief_sha256": _sha256_path(brief_path),
            "status": "done",
            "plan": plan,
            "proof_artifacts": proof_entries,
        }
        if spec.merge_policy == "review":
            pr_number = record.get("pr_number")
            pr_state = record.get("pr_state")
            local_commit_sha = record.get("local_commit_sha")
            publication_evidence = record.get("publication_evidence")
            if isinstance(pr_number, int) and pr_state == "merged":
                milestone_entry["pr_number"] = pr_number
                milestone_entry["pr_state"] = "merged"
                milestone_entry["pr_merge_sha"] = _record_pr_merge_sha(root, record)
            elif isinstance(local_commit_sha, str) and local_commit_sha.strip():
                milestone_entry["local_commit_sha"] = local_commit_sha
            elif publication_evidence == "chain_state_only":
                milestone_entry["publication_evidence"] = "chain_state_only"
            else:
                raise CliError(
                    "invalid_chain_state",
                    f"completed record {milestone.label!r} missing merged PR or explicit publication evidence",
                )
        manifest["milestones"].append(milestone_entry)
    return manifest


def _write_completion_manifest(
    *,
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    proof_map_path: Path,
    output_path: Path | None,
) -> dict[str, Any]:
    proof_map = _load_manifest_proof_map(proof_map_path)
    manifest = _build_completion_manifest(
        root=root,
        spec_path=spec_path,
        spec=spec,
        state=state,
        proof_map=proof_map,
    )
    out_path = output_path or spec_path.with_name("completion-manifest.json")
    out_path = out_path.expanduser().resolve()
    if out_path.parent != spec_path.parent.resolve():
        raise CliError(
            "invalid_args",
            "completion manifest output must live beside the chain spec",
        )
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_hash = _sha256_path(out_path)
    metadata = dict(state.metadata)
    metadata["completion_manifest"] = {
        "path": _project_relative_path(root, out_path),
        "sha256": manifest_hash,
        "schema": "arnold.megaplan.chain_completion_manifest.v1",
    }
    state.metadata = metadata
    chain_spec.save_chain_state(spec_path, state)
    return {
        "success": True,
        "spec": str(spec_path),
        "manifest": str(out_path),
        "manifest_sha256": manifest_hash,
        "milestone_count": len(spec.milestones),
    }


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
        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            CONTRACT_MODE_ENFORCE,
            CONTRACT_MODE_OFF,
            CONTRACT_MODE_SHADOW,
            CONTRACT_MODE_WARN,
            CompletionSubject,
            compute_verdict,
            extract_green_suite_info,
            normalize_contract_mode,
        )
        from arnold_pipelines.megaplan.orchestration.completion_io import (
            write_completion_verdict,
        )

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
        project_dir_str = (
            config.get("project_dir") if isinstance(config, dict) else None
        )
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
                newly_failing = (
                    (delta_dict or {}).get("newly_failing", [])
                    if delta_dict
                    else list(verdict.failures)
                )
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
            if not newly_failing and not deleted_tests and not verdict.would_block:
                return False
            failing_refs: list[dict[str, str]] = []
            for ref in verdict.evidence:
                ev_status = getattr(ref.status, "value", str(ref.status))
                if ev_status in ("unsatisfied", "blocked"):
                    failing_refs.append({"kind": ref.kind, "summary": ref.summary})
            log.warning(
                "completion_contract_mode=enforce: blocking milestone %r; "
                "newly_failing=%r deleted_tests=%r would_block=%r "
                "failures=%r failing_evidence=%r",
                milestone_label,
                list(newly_failing),
                list(deleted_tests),
                verdict.would_block,
                list(verdict.failures),
                failing_refs,
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


def _full_suite_backstop_completed_summary(
    result: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    failing_tests = result.get("failing_tests")
    if not isinstance(failing_tests, list):
        failing_tests = []
    newly_failing = result.get("newly_failing")
    if not isinstance(newly_failing, list):
        newly_failing = []
    deleted_tests = result.get("deleted_tests")
    if not isinstance(deleted_tests, list):
        deleted_tests = []
    return {
        "mode": evaluation.get("mode"),
        "status": result.get("status"),
        "blocks": bool(evaluation.get("blocks")),
        "reason": evaluation.get("reason"),
        "passed": result.get("passed"),
        "failed": result.get("failed"),
        "failing_tests": list(failing_tests),
        "newly_failing": list(newly_failing),
        "deleted_tests": list(deleted_tests),
        "baseline_failing_count": result.get("baseline_failing_count", 0),
        "current_failing_count": result.get("current_failing_count", 0),
        "delta_computed": bool(result.get("delta_computed")),
        "command": result.get("command", ""),
        "duration_s": result.get("duration_s"),
        "ran": bool(result.get("ran")),
        "artifact": "full_suite_backstop.json",
    }


def _full_suite_backstop_baseline_path_for(spec_path: Path) -> Path:
    return _state_path_for(spec_path).parent / "full_suite_baseline.json"


def _current_head_sha(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha or None


def _persist_full_suite_backstop_baseline(
    spec_path: Path,
    result: dict[str, Any],
    *,
    captured_at_sha: str | None,
    milestone_label: str,
    captured_at: str | None = None,
) -> bool:
    from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
        build_full_suite_baseline,
    )

    baseline = build_full_suite_baseline(
        result,
        captured_at_sha=captured_at_sha,
        milestone=milestone_label,
        captured_at=captured_at,
    )
    if baseline is None:
        return False
    path = _full_suite_backstop_baseline_path_for(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, baseline)
    return True


def _full_suite_backstop_uncertain(result: dict[str, Any] | None) -> bool:
    return not isinstance(result, dict) or result.get("delta_computed") is not True


def _run_full_suite_backstop_gate(
    root: Path,
    spec_path: Path,
    plan_name: str,
    milestone_label: str,
    mode: str,
    *,
    log_fn: Callable[[str], None],
) -> dict[str, Any]:
    """Run the full-suite backstop gate for a completed milestone."""
    from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
        FULL_SUITE_BACKSTOP_MODE_ENFORCE,
        FULL_SUITE_BACKSTOP_MODE_OFF,
        evaluate_full_suite_backstop,
        normalize_full_suite_backstop_mode,
        run_full_suite_backstop,
    )

    normalized_mode = normalize_full_suite_backstop_mode(mode)
    if normalized_mode == FULL_SUITE_BACKSTOP_MODE_OFF:
        return {
            "blocks": False,
            "reason": "full_suite_backstop_mode=off: backstop disabled",
            "summary": None,
            "result": None,
        }

    try:
        plan_dir = resolve_plan_dir(root, plan_name)
        if plan_dir is None:
            raise FileNotFoundError(f"plan directory not found for {plan_name!r}")

        try:
            raw_state = json.loads(
                (plan_dir / "state.json").read_text(encoding="utf-8")
            )
        except Exception:
            raw_state = {}
        config = raw_state.get("config", {}) if isinstance(raw_state, dict) else {}
        if not isinstance(config, dict):
            config = {}
        project_dir_value = config.get("project_dir")
        project_dir = (
            Path(project_dir_value)
            if isinstance(project_dir_value, str) and project_dir_value
            else root
        )
        baseline_path = _full_suite_backstop_baseline_path_for(spec_path)

        result = run_full_suite_backstop(
            plan_dir,
            project_dir,
            config,
            baseline=baseline_path,
            writer=log_fn,
        )
        atomic_write_json(plan_dir / "full_suite_backstop.json", result)
        evaluation = evaluate_full_suite_backstop(result, normalized_mode)
        if (
            normalized_mode == FULL_SUITE_BACKSTOP_MODE_ENFORCE
            and evaluation.get("blocks")
            and _full_suite_backstop_uncertain(result)
        ):
            log_fn("full_suite_backstop enforce uncertainty; retrying full suite once")
            result = run_full_suite_backstop(
                plan_dir,
                project_dir,
                config,
                baseline=baseline_path,
                writer=log_fn,
            )
            atomic_write_json(plan_dir / "full_suite_backstop.json", result)
            evaluation = evaluate_full_suite_backstop(result, normalized_mode)
        summary = _full_suite_backstop_completed_summary(result, evaluation)

        newly_failing = summary["newly_failing"]
        deleted_tests = summary["deleted_tests"]
        failure_suffix = (
            f"; newly_failing={newly_failing[:5]}"
            if newly_failing
            else f"; deleted_tests={deleted_tests[:5]}" if deleted_tests else ""
        )
        log_fn(
            "full_suite_backstop "
            f"mode={normalized_mode} status={summary['status']} "
            f"blocks={summary['blocks']} artifact=full_suite_backstop.json"
            f"{failure_suffix}"
        )
        return {
            "blocks": bool(evaluation.get("blocks")),
            "reason": str(evaluation.get("reason") or ""),
            "summary": summary,
            "result": result,
        }
    except Exception as exc:
        log.warning(
            "full_suite_backstop failed open for milestone %r: %s",
            milestone_label,
            exc,
        )
        result = {
            "status": "error",
            "passed": None,
            "failed": None,
            "failing_tests": None,
            "command": "",
            "duration_s": None,
            "ran": False,
            "note": f"fail-open: {type(exc).__name__}: {exc}",
        }
        try:
            log_fn(
                "full_suite_backstop "
                f"mode={normalized_mode} status=error blocks=False "
                f"note={result['note']}"
            )
        except Exception:
            pass
        return {
            "blocks": False,
            "reason": (
                "full_suite_backstop failed open after unexpected error; not blocking"
            ),
            "summary": None,
            "result": result,
        }


def _latest_execution_batch_all_tasks_done(
    plan_dir: Path,
    *,
    chain_state: ChainState | None = None,
    completion_record: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    try:
        state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        state_payload = {}
    config = state_payload.get("config") if isinstance(state_payload, dict) else {}
    meta = state_payload.get("meta") if isinstance(state_payload, dict) else {}
    raw_project_dir = config.get("project_dir") if isinstance(config, dict) else None
    project_dir = Path(raw_project_dir) if isinstance(raw_project_dir, str) and raw_project_dir else None
    execution_baseline = (
        meta.get("execution_baseline")
        if isinstance(meta, dict) and isinstance(meta.get("execution_baseline"), dict)
        else {}
    )
    baseline_head = execution_baseline.get("head")
    current_head = _resolve_authority_current_head(
        plan_dir,
        project_dir=project_dir,
        baseline_head=baseline_head if isinstance(baseline_head, str) and baseline_head.strip() else None,
    )
    # Whether the live git HEAD was observable. When it is NOT (e.g. rev-parse
    # failed), there is no execution window to defer finalize authority to, so
    # finalize.json must be evaluated directly even if it contains pending rows.
    actual_git_head = _best_effort_git_head(project_dir) if project_dir is not None else None
    execution_window_available = actual_git_head is not None
    evidence_nucleus = load_evidence_nucleus(plan_dir, default_head=current_head)

    def _authoritative_batch_task_overrides() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        overrides: dict[str, dict[str, Any]] = {}
        sources: dict[str, str] = {}
        for batch_path in sorted(
            list_batch_artifacts(plan_dir),
            key=_execution_batch_sort_key,
        ):
            try:
                batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                continue
            if not isinstance(batch_payload, dict):
                continue
            batch_records = [
                item
                for item in (batch_payload.get("task_updates") or [])
                if isinstance(item, dict)
            ]
            if not batch_records:
                continue
            batch_decisions: dict[str, AuthorityDecision] = {}
            batch_completed = effective_execute_completed_task_ids(
                batch_records,
                plan_dir=plan_dir,
                project_dir=project_dir,
                state=state_payload,
                evidence_nucleus=evidence_nucleus,
                current_head=current_head,
                decisions=batch_decisions,
            )
            for record in batch_records:
                task_id = str(record.get("task_id") or record.get("id") or "")
                if task_id and task_id in batch_completed:
                    if not _task_record_can_override_finalize(record):
                        continue
                    overrides[task_id] = dict(record)
                    sources[task_id] = _plan_relative_source(plan_dir, batch_path)
        return overrides, sources

    authoritative_batch_overrides, authoritative_batch_override_sources = (
        _authoritative_batch_task_overrides()
    )
    batches = sorted(
        list_batch_artifacts(plan_dir),
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

    finalize_path = plan_dir / "finalize.json"
    finalize_payload: dict[str, Any] | None = None
    authoritative_finalize_records: list[dict[str, Any]] | None = None
    baseline_unavailable_task_ids: set[str] = set()
    if finalize_path.exists():
        try:
            loaded_finalize_payload = json.loads(
                finalize_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            return False, f"finalize.json could not be read: {error}"
        if isinstance(loaded_finalize_payload, dict):
            finalize_payload = loaded_finalize_payload
            finalize_tasks = finalize_payload.get("tasks")
            if isinstance(finalize_tasks, list) and finalize_tasks:
                finalize_records = [
                    task for task in finalize_tasks if isinstance(task, dict)
                ]
                from arnold_pipelines.megaplan.execute.batch import (
                    baseline_unavailable_checkpoint_ids,
                )

                finalize_ids = {
                    str(task.get("id"))
                    for task in finalize_records
                    if isinstance(task.get("id"), str)
                }
                baseline_unavailable_task_ids = baseline_unavailable_checkpoint_ids(
                    finalize_payload, finalize_ids
                )
                authoritative_finalize_records = [
                    task
                    for task in finalize_records
                    if str(task.get("id") or "") not in baseline_unavailable_task_ids
                ]
                if authoritative_batch_overrides:
                    overlaid_finalize_records: list[dict[str, Any]] = []
                    for task in authoritative_finalize_records:
                        task_id = str(task.get("id") or "")
                        override = authoritative_batch_overrides.get(task_id)
                        if override is None:
                            overlaid_finalize_records.append(task)
                            continue
                        from arnold_pipelines.megaplan.orchestration.authority_readers import (
                            has_durable_terminal_task_evidence,
                        )
                        if has_durable_terminal_task_evidence(task):
                            # A replayed/partial batch may omit outputs already
                            # reconciled into finalize.json. Never let that erase
                            # terminal corroboration at chain completion.
                            overlaid_finalize_records.append(task)
                            continue
                        merged = dict(task)
                        for field in (
                            "files_changed",
                            "commands_run",
                            "evidence_files",
                            "sections_written",
                            "evidence",
                        ):
                            if field not in override:
                                merged.pop(field, None)
                        for key, value in override.items():
                            if key == "task_id":
                                continue
                            merged[key] = value
                        overlaid_finalize_records.append(merged)
                    authoritative_finalize_records = overlaid_finalize_records

    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        has_durable_terminal_task_evidence,
    )

    # A branch replay changes commit IDs while retaining the milestone diff.
    # Re-anchor terminal finalize evidence only when every claimed file is
    # present in the declared milestone range; arbitrary stale claims stay
    # non-authoritative.
    if authoritative_finalize_records and project_dir is not None and current_head:
        chain_policy = meta.get("chain_policy") if isinstance(meta, dict) else None
        base_ref = chain_policy.get("milestone_base_sha") if isinstance(chain_policy, dict) else None
        if isinstance(base_ref, str) and base_ref.strip():
            try:
                from arnold_pipelines.megaplan.loop.git import _collect_committed_range_paths
                from arnold_pipelines.megaplan.orchestration.authority_readers import (
                    _evidence_from_task_record,
                )
                committed_paths = _collect_committed_range_paths(project_dir, base_ref=base_ref)
                reanchored_refs = []
                reanchored_records: list[dict[str, Any]] = []
                for task in authoritative_finalize_records:
                    files = {
                        str(path).lstrip("./")
                        for path in task.get("files_changed", [])
                        if isinstance(path, str) and path.strip()
                    }
                    if (
                        has_durable_terminal_task_evidence(task)
                        and files
                        and files.issubset(committed_paths)
                    ):
                        task = dict(task)
                        task["head_sha"] = current_head
                        reanchored_refs.extend(
                            _evidence_from_task_record(
                                task, finalize_path, root=plan_dir, default_head=current_head
                            )
                        )
                    reanchored_records.append(task)
                authoritative_finalize_records = reanchored_records
                evidence_nucleus = (*evidence_nucleus, *reanchored_refs)
            except Exception:
                pass

    # finalize.json defines the required task universe. A later execution batch
    # may override stale finalize rows for individual tasks, but it may not
    # shrink the universe to just the latest touched task. This is the incident
    # class where T1/T2/T6 completed, T3+ stayed pending, and the chain accepted
    # the latest execution_batch_N.json anyway.
    if authoritative_finalize_records and batches and execution_window_available:
        pending_without_batch_override = [
            str(task.get("id") or "")
            for task in authoritative_finalize_records
            if _optional_finalize_status(task) == "pending"
            and str(task.get("id") or "") not in authoritative_batch_overrides
        ]
        if pending_without_batch_override:
            return (
                False,
                "finalize.json has pending tasks without authoritative execution "
                f"updates: {', '.join(pending_without_batch_override)}",
            )

    if authoritative_finalize_records:
        finalize_decisions: dict[str, AuthorityDecision] = {}
        finalize_completed = effective_execute_completed_task_ids(
            authoritative_finalize_records,
            plan_dir=plan_dir,
            project_dir=project_dir,
            state=state_payload,
            evidence_nucleus=evidence_nucleus,
            current_head=current_head,
            decisions=finalize_decisions,
        )
        pending = _non_authoritative_task_reasons(
            authoritative_finalize_records,
            finalize_completed,
            finalize_decisions,
            source_by_task=authoritative_batch_override_sources,
        )
        pending.extend(
            _chain_completion_shadow_disagreements(
                authoritative_finalize_records,
                finalize_completed,
                finalize_decisions,
                source_by_task=authoritative_batch_override_sources,
                plan_dir=plan_dir,
                chain_state=chain_state,
                completion_record=completion_record,
                default_source="finalize.json",
                default_source_kind="finalize data",
            )
        )
        pending.extend(
            _finalize_records_missing_authority_fields(
                authoritative_finalize_records
            )
        )
        if pending:
            return (
                False,
                f"finalize.json has non-authoritative tasks: {', '.join(pending)}",
            )
        return True, "finalize.json"

    task_records: list[dict[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw_records = payload.get(key)
        if isinstance(raw_records, list):
            task_records.extend(item for item in raw_records if isinstance(item, dict))
    if not task_records:
        return False, f"{latest.name} has no task records"

    authoritative_task_records = [
        task
        for task in task_records
        if str(task.get("task_id") or task.get("id") or "")
        not in baseline_unavailable_task_ids
    ]
    if authoritative_task_records:
        batch_decisions: dict[str, AuthorityDecision] = {}
        completed = effective_execute_completed_task_ids(
            authoritative_task_records,
            plan_dir=plan_dir,
            project_dir=project_dir,
            state=state_payload,
            evidence_nucleus=evidence_nucleus,
            current_head=current_head,
            decisions=batch_decisions,
        )
        if not completed:
            return False, f"{latest.name} has no corroborated completed task IDs"
        incomplete = _non_authoritative_task_reasons(
            authoritative_task_records, completed, batch_decisions
        )
        incomplete.extend(
            _chain_completion_shadow_disagreements(
                authoritative_task_records,
                completed,
                batch_decisions,
                source_by_task={},
                plan_dir=plan_dir,
                chain_state=chain_state,
                completion_record=completion_record,
                default_source=_plan_relative_source(plan_dir, latest),
                default_source_kind="execution batch",
            )
        )
        if incomplete:
            return (
                False,
                f"{latest.name} has non-authoritative tasks: {', '.join(incomplete)}",
            )
    return True, latest.name


def _resolve_authority_current_head(
    plan_dir: Path,
    *,
    project_dir: Path | None,
    baseline_head: str | None,
) -> str | None:
    actual_head = _best_effort_git_head(project_dir) if project_dir is not None else None
    recorded_head = _latest_recorded_execution_head(plan_dir)
    if actual_head and recorded_head:
        if actual_head == recorded_head:
            return actual_head
        if project_dir is not None:
            if _git_is_ancestor(project_dir, recorded_head, actual_head):
                return actual_head
            if _git_is_ancestor(project_dir, actual_head, recorded_head):
                return recorded_head
    return actual_head or recorded_head or baseline_head


def _best_effort_git_head(project_dir: Path) -> str | None:
    try:
        actual_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return actual_head or None


def _latest_recorded_execution_head(plan_dir: Path) -> str | None:
    for path in sorted(
        list_batch_artifacts(plan_dir),
        key=_execution_batch_sort_key,
        reverse=True,
    ):
        head = _latest_head_in_artifact(path)
        if head:
            return head
    return _latest_head_in_artifact(plan_dir / "finalize.json")


def _latest_head_in_artifact(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    latest_head: str | None = None
    for key in ("task_updates", "tasks"):
        raw_records = payload.get(key)
        if not isinstance(raw_records, list):
            continue
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            observed = record.get("head_sha") or record.get("head")
            if isinstance(observed, str) and observed.strip():
                latest_head = observed.strip()
    return latest_head


def _git_is_ancestor(project_dir: Path, ancestor: str, descendant: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=project_dir,
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _plan_terminal_completion_is_authoritative(
    root: Path, plan_name: str
) -> tuple[bool, str]:
    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        return (
            True,
            f"plan {plan_name} directory unavailable; no chain artifacts to inspect",
        )
    return _latest_execution_batch_all_tasks_done(plan_dir)


def _finalized_plan_has_successful_review(plan_state: dict[str, Any]) -> bool:
    """Return true when a finalized plan has already completed review successfully."""

    if plan_state.get("current_state") != STATE_FINALIZED:
        return False
    if plan_state.get("latest_failure"):
        return False
    if plan_state.get("active_step"):
        return False
    history = plan_state.get("history")
    if not isinstance(history, list):
        return False
    saw_execute = False
    for entry in history:
        if not isinstance(entry, dict):
            continue
        step = str(entry.get("step") or "").strip().lower()
        result = str(entry.get("result") or "").strip().lower()
        if step == "execute":
            saw_execute = True
        if saw_execute and step == "review" and result == "success":
            return True
    return False


def _read_typed_noop_completion_waiver(
    plan_dir: Path,
    *,
    expected_base_sha: str | None = None,
    expected_plan: str | None = None,
    expected_milestone: str | None = None,
) -> tuple[bool, str]:
    """Return whether an explicit typed no-op completion waiver is valid."""

    candidates = (
        plan_dir / "completion_noop.json",
        plan_dir / "no_op_completion.json",
    )
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return False, f"{candidate.name} could not be read: {error}"
        if not isinstance(payload, dict):
            return False, f"{candidate.name} payload is not an object"
        if payload.get("schema") != NOOP_COMPLETION_SCHEMA:
            return False, f"{candidate.name} schema must be {NOOP_COMPLETION_SCHEMA!r}"
        plan = payload.get("plan")
        if expected_plan and plan != expected_plan:
            return (
                False,
                f"{candidate.name} plan {plan!r} does not match {expected_plan!r}",
            )
        milestone = payload.get("milestone_label")
        if expected_milestone and milestone != expected_milestone:
            return (
                False,
                f"{candidate.name} milestone_label {milestone!r} does not match "
                f"{expected_milestone!r}",
            )
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return False, f"{candidate.name} requires a non-empty reason"
        scope = payload.get("scope")
        if scope not in NOOP_COMPLETION_SCOPES:
            allowed = ", ".join(sorted(NOOP_COMPLETION_SCOPES))
            return False, f"{candidate.name} scope must be one of: {allowed}"
        base_sha = payload.get("base_sha")
        if not isinstance(base_sha, str) or not base_sha.strip():
            return False, f"{candidate.name} requires a non-empty base_sha"
        if expected_base_sha and base_sha != expected_base_sha:
            return (
                False,
                f"{candidate.name} base_sha {base_sha!r} does not match "
                f"milestone_base_sha {expected_base_sha!r}",
            )
        return True, f"{candidate.name} scope={scope} reason={reason.strip()}"
    return False, "no typed no-op completion waiver found"


def _finalize_payload_has_empty_tasks(plan_dir: Path) -> tuple[bool, str]:
    candidates = (
        ("finalize.json", plan_dir / "finalize.json"),
        ("finalize_output.json", plan_dir / "finalize_output.json"),
    )
    for label, path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return True, f"{label} could not be read: {error}"
        if not isinstance(payload, dict):
            return True, f"{label} payload is not an object"
        tasks = payload.get("tasks")
        if isinstance(tasks, list) and not tasks:
            return True, f"{label} tasks is empty"
        return False, f"{label} tasks is non-empty or absent"
    return False, "no finalize artifact present"


def _milestone_base_sha_from_plan_state(state: dict[str, Any]) -> str | None:
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    policy = (
        meta.get("chain_policy") if isinstance(meta.get("chain_policy"), dict) else {}
    )
    base_sha = policy.get("milestone_base_sha")
    return base_sha if isinstance(base_sha, str) and base_sha.strip() else None


def _semantic_diff_nonempty_between_refs(
    root: Path, base_sha: str | None, target_ref: str, *, target_label: str
) -> tuple[bool, str]:
    if not base_sha:
        return False, "milestone_base_sha unavailable"
    target_ref = target_ref.strip()
    if not target_ref:
        return False, f"{target_label} unavailable"
    proc = _diff_name_only_between_refs(root, base_sha, target_ref)
    if proc.returncode != 0:
        return (
            False,
            f"git diff from milestone_base_sha to {target_label} failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}",
        )
    changed = [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip()
        and line.strip() != ".megaplan"
        and not line.strip().startswith(".megaplan/")
    ]
    if not changed:
        return (
            False,
            f"no semantic diff from milestone_base_sha {base_sha} to {target_label}",
        )
    return True, f"{target_label} semantic diff files: {', '.join(changed[:10])}"


def _raw_diff_nonempty_between_refs(
    root: Path, base_sha: str | None, target_ref: str, *, target_label: str
) -> tuple[bool | None, str]:
    if not base_sha:
        return None, "milestone_base_sha unavailable"
    target_ref = target_ref.strip()
    if not target_ref:
        return None, f"{target_label} unavailable"
    proc = _diff_name_only_between_refs(root, base_sha, target_ref)
    if proc.returncode != 0:
        return (
            None,
            f"git diff from milestone_base_sha to {target_label} failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}",
        )
    changed = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not changed:
        return False, f"no raw diff from milestone_base_sha {base_sha} to {target_label}"
    return True, f"{target_label} raw diff files: {', '.join(changed[:10])}"


def _semantic_diff_nonempty_from_base(
    root: Path, base_sha: str | None
) -> tuple[bool, str]:
    return _semantic_diff_nonempty_between_refs(
        root, base_sha, "HEAD", target_label="local HEAD"
    )


def _diff_name_only_between_refs(
    root: Path, base_sha: str, target_ref: str
) -> subprocess.CompletedProcess[str]:
    """Run ``git diff --name-only`` between two refs with one fetch-and-retry.

    If the initial diff fails with a ref-resolution error (bad object, unknown
    revision, bad revision, could not resolve, etc.), ``git fetch origin
    --prune`` is executed once and the diff is retried.  If the retry still
    fails, the real error is surfaced unchanged — there is no silent swallowing
    or second fetch attempt.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", base_sha, target_ref, "--"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if proc.returncode == 0:
        return proc
    combined = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()
    if not _is_git_ref_resolution_error(combined):
        return proc
    subprocess.run(
        ["git", "fetch", "origin", "--prune"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return subprocess.run(
        ["git", "diff", "--name-only", base_sha, target_ref, "--"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _is_git_ref_resolution_error(combined_lower: str) -> bool:
    """Return *True* when *combined_lower* matches a known ref-resolution error.

    These are fatal errors that ``git fetch origin --prune`` can potentially
    resolve (stale remote-tracking branches, missing objects, race conditions
    after upstream force-pushes, etc.).
    """
    _REF_RESOLUTION_ERROR_PATTERNS: tuple[str, ...] = (
        "bad object",
        "unknown revision",
        "bad revision",
        "could not resolve",
        "does not point to a valid object",
        "not a valid object name",
        "not our ref",
        "could not read",
        "fatal: ambiguous argument",
        "fatal: not a commit",
        "fatal: not a tree",
    )
    return any(pattern in combined_lower for pattern in _REF_RESOLUTION_ERROR_PATTERNS)


def _string_value(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _sha_from_payload_value(value: Any) -> str | None:
    direct = _string_value(value)
    if direct:
        return direct
    if isinstance(value, dict):
        for key in ("oid", "sha", "id"):
            nested = _string_value(value.get(key))
            if nested:
                return nested
    return None


def _published_pr_target_from_record(
    record: dict[str, Any],
    chain_state: ChainState | None = None,
) -> tuple[str | None, str]:
    merge_sha_keys = (
        "pr_merge_sha",
        "merge_commit_sha",
        "merge_commit",
        "mergeCommit",
        "published_merge_sha",
    )
    head_sha_keys = (
        "pr_head_sha",
        "pr_head",
        "head_ref_oid",
        "headRefOid",
        "published_head_sha",
        "published_commit_sha",
    )
    for key in merge_sha_keys:
        sha = _sha_from_payload_value(record.get(key))
        if sha:
            return sha, f"record.{key}"
    pr_payload = record.get("pr")
    if isinstance(pr_payload, dict):
        for key in merge_sha_keys:
            sha = _sha_from_payload_value(pr_payload.get(key))
            if sha:
                return sha, f"record.pr.{key}"
    for key in head_sha_keys:
        sha = _sha_from_payload_value(record.get(key))
        if sha:
            return sha, f"record.{key}"
    if isinstance(pr_payload, dict):
        for key in head_sha_keys:
            sha = _sha_from_payload_value(pr_payload.get(key))
            if sha:
                return sha, f"record.pr.{key}"
    if chain_state is not None:
        sha = _string_value(chain_state.pr_head)
        if sha:
            return sha, "chain_state.pr_head"
    return None, "record/chain_state"


def _published_pr_target_from_gh(
    root: Path, pr_number: int
) -> tuple[str | None, str]:
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                "state,mergedAt,mergeCommit,headRefOid",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"gh pr view #{pr_number} failed: {error}"
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "gh pr view failed"
        return None, f"gh pr view #{pr_number} failed: {detail}"
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as error:
        return None, f"gh pr view #{pr_number} produced non-JSON output: {error}"
    if not isinstance(payload, dict):
        return None, f"gh pr view #{pr_number} payload is not an object"
    state = _string_value(payload.get("state"))
    if not state or state.lower() != "merged":
        return None, f"gh pr view #{pr_number} state={state!r} is not merged"
    merged_at = _string_value(payload.get("mergedAt"))
    if not merged_at:
        return None, f"gh pr view #{pr_number} has no mergedAt timestamp"
    merge_sha = _sha_from_payload_value(payload.get("mergeCommit"))
    if merge_sha:
        return merge_sha, f"gh.pr#{pr_number}.mergeCommit"
    head_sha = _sha_from_payload_value(payload.get("headRefOid"))
    if head_sha:
        return head_sha, f"gh.pr#{pr_number}.headRefOid"
    return None, f"gh pr view #{pr_number} did not return a mergeCommit/headRefOid"


def _completion_record_is_merged_pr(record: dict[str, Any]) -> bool:
    pr_state = _string_value(record.get("pr_state"))
    return bool(pr_state and pr_state.lower() == "merged")


def _published_target_is_in_chain_target(
    root: Path,
    target: str,
    chain_state: ChainState | None,
) -> tuple[bool | None, str]:
    if chain_state is None:
        return None, "chain target unavailable"
    target_ref = _string_value(chain_state.target_base_ref)
    if not target_ref:
        return None, "chain target ref unavailable"
    # ``target_base_ref`` is the chain's launch-time base.  A valid merged PR
    # advances beyond that snapshot, so the snapshot must be an ancestor of the
    # published merge target (not the other way around).
    if _git_is_ancestor(root, target_ref, target):
        return True, f"chain target {target_ref[:12]} is contained in published PR target {target[:12]}"
    return (
        False,
        f"published PR target {target[:12]} is not contained in chain target {target_ref}",
    )


def _published_pr_semantic_diff_nonempty_from_base(
    root: Path,
    base_sha: str | None,
    record: dict[str, Any],
    *,
    chain_state: ChainState | None = None,
) -> tuple[bool | None, str]:
    target, source = _published_pr_target_from_record(record)
    if target is None:
        pr_number = record.get("pr_number")
        if isinstance(pr_number, int):
            target, source = _published_pr_target_from_gh(root, pr_number)
        elif isinstance(pr_number, str) and pr_number.strip().isdigit():
            target, source = _published_pr_target_from_gh(root, int(pr_number.strip()))
    if target is None and chain_state is not None:
        target, source = _published_pr_target_from_record(record, chain_state)
    if target is None:
        return None, f"published PR target unavailable: {source}"
    landed_ok, landed_reason = _published_target_is_in_chain_target(
        root,
        target,
        chain_state,
    )
    if landed_ok is False:
        return False, landed_reason
    return _semantic_diff_nonempty_between_refs(
        root,
        base_sha,
        target,
        target_label=f"published PR target {target[:12]} ({source})",
    )


def _chain_completion_guard(
    root: Path,
    record: dict[str, Any],
    *,
    implementation_milestone: bool,
    chain_state: ChainState | None = None,
) -> tuple[bool, str]:
    plan_name = record.get("plan")
    if not isinstance(plan_name, str) or not plan_name.strip():
        return False, "completion record has no plan name"
    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError as error:
        return False, f"plan {plan_name} directory unavailable: {error.message}"

    plan_state = _read_plan_state_payload_from_dir(plan_dir)
    current_state = plan_state.get("current_state")
    current_state_note = ""
    is_merged_pr = _completion_record_is_merged_pr(record)
    if is_merged_pr and not implementation_milestone:
        return True, "merged PR milestone accepted without implementation checks"
    merged_pr_internal_state_bypass = is_merged_pr and current_state in {
        STATE_BLOCKED,
        STATE_EXECUTED,
        STATE_FINALIZED,
    }
    merged_pr_state_bypass_reason = ""
    if (
        implementation_milestone
        and current_state != STATE_DONE
        and not merged_pr_internal_state_bypass
    ):
        return (
            False,
            f"plan {plan_name} current_state={current_state!r} is not terminal-success "
            f"{STATE_DONE!r}",
        )
    if implementation_milestone and current_state != STATE_DONE and merged_pr_internal_state_bypass:
        merged_pr_state_bypass_reason = (
            f"merged PR milestone; internal plan state {current_state!r} bypassed "
            "because PR is merged"
        )
        if current_state_note:
            merged_pr_state_bypass_reason = (
                f"{current_state_note}; {merged_pr_state_bypass_reason}"
            )

    if not implementation_milestone:
        return True, "non-implementation completion guard passed"

    milestone_base_sha = _milestone_base_sha_from_plan_state(plan_state)
    waiver_ok, waiver_reason = _read_typed_noop_completion_waiver(
        plan_dir,
        expected_base_sha=milestone_base_sha,
        expected_plan=plan_name,
        expected_milestone=(
            record.get("label") if isinstance(record.get("label"), str) else None
        ),
    )

    if is_merged_pr:
        published_diff_ok, published_diff_reason = (
            _published_pr_semantic_diff_nonempty_from_base(
                root,
                milestone_base_sha,
                record,
                chain_state=chain_state,
            )
        )
        if (
            published_diff_ok is False
            and "not contained in chain target" in published_diff_reason
        ):
            return False, published_diff_reason
        local_diff_ok = False
        local_diff_reason = ""
        local_raw_diff_ok: bool | None = None
        local_raw_diff_reason = ""
        if published_diff_ok is not True:
            local_diff_ok, local_diff_reason = _semantic_diff_nonempty_from_base(
                root, milestone_base_sha
            )
            local_raw_diff_ok, local_raw_diff_reason = _raw_diff_nonempty_between_refs(
                root,
                milestone_base_sha,
                "HEAD",
                target_label="local HEAD",
            )
        if published_diff_ok is True:
            if waiver_ok:
                return True, f"typed no-op waiver accepted: {waiver_reason}"
            reason_parts: list[str] = []
            if merged_pr_state_bypass_reason:
                reason_parts.append(merged_pr_state_bypass_reason)
            if local_diff_reason:
                if local_diff_ok:
                    reason_parts.append(local_diff_reason)
                else:
                    reason_parts.append(f"local HEAD advisory: {local_diff_reason}")
            reason_parts.append(published_diff_reason)
            return True, f"completion guard passed: {'; '.join(reason_parts)}"
        if published_diff_ok is None:
            if not local_diff_ok and not waiver_ok:
                return False, f"{local_diff_reason}; {published_diff_reason}; {waiver_reason}"
            if waiver_ok:
                return True, f"typed no-op waiver accepted: {waiver_reason}"
            return True, f"completion guard passed: {local_diff_reason}; {published_diff_reason}"
        if (
            published_diff_ok is False
            and not local_diff_ok
            and local_raw_diff_ok is False
        ):
            authoritative, authority_reason = _latest_execution_batch_all_tasks_done(
                plan_dir,
                chain_state=chain_state,
                completion_record=record,
            )
            empty_finalize_tasks, finalize_reason = _finalize_payload_has_empty_tasks(
                plan_dir
            )
            if authoritative and not empty_finalize_tasks:
                if waiver_ok:
                    return True, f"typed no-op waiver accepted: {waiver_reason}"
                reason_parts = []
                if merged_pr_state_bypass_reason:
                    reason_parts.append(merged_pr_state_bypass_reason)
                reason_parts.extend(
                    [
                        authority_reason,
                        finalize_reason,
                        "merged PR accepted with authoritative execution and true no-op diff",
                        local_diff_reason,
                        published_diff_reason,
                    ]
                )
                return True, f"completion guard passed: {'; '.join(reason_parts)}"
        if not waiver_ok:
            return False, f"{published_diff_reason}; {waiver_reason}"
        if waiver_ok:
            return True, f"typed no-op waiver accepted: {waiver_reason}"
        return True, f"completion guard passed: {published_diff_reason}"

    authoritative, reason = _latest_execution_batch_all_tasks_done(
        plan_dir,
        chain_state=chain_state,
        completion_record=record,
    )
    if not authoritative and not waiver_ok:
        return (
            False,
            f"execution evidence blocked completion: {reason}; {waiver_reason}",
        )

    empty_finalize_tasks, finalize_reason = _finalize_payload_has_empty_tasks(plan_dir)
    if empty_finalize_tasks and not waiver_ok:
        return False, f"{finalize_reason}; {waiver_reason}"

    diff_ok, diff_reason = _semantic_diff_nonempty_from_base(root, milestone_base_sha)
    if not diff_ok and not waiver_ok:
        return False, f"{diff_reason}; {waiver_reason}"

    published_diff_reason: str | None = None
    if is_merged_pr:
        published_diff_ok, published_diff_reason = (
            _published_pr_semantic_diff_nonempty_from_base(
                root,
                milestone_base_sha,
                record,
                chain_state=chain_state,
            )
        )
        if not published_diff_ok and not waiver_ok:
            return False, f"{published_diff_reason}; {waiver_reason}"

    if waiver_ok:
        return True, f"typed no-op waiver accepted: {waiver_reason}"
    reason_parts = [reason, finalize_reason, diff_reason]
    if current_state_note:
        reason_parts.insert(0, current_state_note)
    if published_diff_reason is not None:
        reason_parts.append(published_diff_reason)
    return True, f"completion guard passed: {'; '.join(reason_parts)}"


def _is_failed_no_next_step_blocked_execute(plan_state: dict[str, Any]) -> bool:
    current_state = plan_state.get("current_state")
    if current_state != "failed":
        return False
    latest_failure = plan_state.get("latest_failure")
    if not isinstance(latest_failure, dict):
        return False
    if latest_failure.get("kind") != "no_next_step":
        return False
    history = plan_state.get("history")
    if not isinstance(history, list):
        return False
    return any(
        isinstance(entry, dict)
        and entry.get("step") == "execute"
        and entry.get("result") == "blocked"
        for entry in history
    )


def _finalize_has_only_terminal_status_rows(plan_dir: Path) -> tuple[bool, str]:
    try:
        payload = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "finalize.json unavailable"
    if not isinstance(payload, dict):
        return False, "finalize.json is not an object"
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return False, "finalize.json has no tasks"
    saw_terminal = False
    for task in tasks:
        if not isinstance(task, dict):
            return False, "finalize.json contains non-object task rows"
        status = _optional_finalize_status(task)
        if status not in {"done", "skipped", "waived", "not_applicable"}:
            return False, f"finalize.json has non-terminal task status {status!r}"
        if _task_record_has_authority_payload(task):
            return False, "finalize.json terminal rows still carry authority payload"
        saw_terminal = True
    if not saw_terminal:
        return False, "finalize.json has no terminal task rows"
    return True, "terminal finalize task statuses"


def _is_chain_control_path(path: str) -> bool:
    return path in {"chain.yaml", "idea.md", "NORTHSTAR.md"}


def _current_branch_name(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    branch = proc.stdout.strip()
    return branch or None


def _root_relative_dirty_paths(root: Path) -> list[str]:
    root_abs = root.resolve()
    dirty_paths: list[str] = []
    for path in _dirty_worktree_paths(root):
        try:
            rel = path.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            continue
        dirty_paths.append(rel)
    return dirty_paths


def _ensure_published_claimed_changes_for_pr_progression(
    root: Path,
    spec_path: Path,
    state: ChainState,
    milestone: MilestoneSpec,
    *,
    writer,
    allow_publish: bool,
) -> tuple[bool, str]:
    """Publish (or refuse to advance past) unpublished claimed milestone work.

    A previously buggy chain could leave a finalized/done plan with claimed
    local changes that never made it onto the milestone branch before the PR
    merged (or before auto-merge is enabled). Refusing to advance here prevents
    a false-completion drop of unfinished work. When ``allow_publish`` is set
    and we are on the milestone branch, the changes are pushed under the
    ``resume-publish`` phase so the normal awaiting-merge path can continue.
    """

    plan_name = state.current_plan_name
    if not plan_name or not milestone.branch or state.pr_number is None:
        return True, "no active milestone PR publish guard needed"

    plan_state = _plan_state_payload_from_name(root, plan_name)
    current_state = plan_state.get("current_state")
    if current_state not in {STATE_FINALIZED, STATE_DONE}:
        return True, f"plan {plan_name} current_state={current_state!r} does not require PR publish guard"

    claimed_root_paths = _claimed_root_paths(root, plan_name)
    if not claimed_root_paths:
        return True, f"plan {plan_name} has no claimed root paths to publish"

    dirty_paths = _root_relative_dirty_paths(root)
    dirty_claimed = sorted(path for path in dirty_paths if path in claimed_root_paths)
    if not dirty_claimed:
        return True, f"plan {plan_name} has no unpublished claimed changes"

    unrelated_dirty = sorted(
        path
        for path in dirty_paths
        if path not in claimed_root_paths
        and not _is_chain_control_path(path)
        and path != ".megaplan"
        and not path.startswith(".megaplan/")
    )
    claimed_sample = ", ".join(dirty_claimed[:5])
    if unrelated_dirty:
        unrelated_sample = ", ".join(unrelated_dirty[:5])
        return (
            False,
            f"plan {plan_name} has unpublished claimed changes ({claimed_sample}) plus "
            f"unrelated dirty paths ({unrelated_sample}); refusing PR progression",
        )

    current_branch = _current_branch_name(root)
    if not allow_publish:
        return (
            False,
            f"plan {plan_name} has unpublished claimed changes after PR merged: "
            f"{claimed_sample}; current branch={current_branch or 'detached HEAD'} "
            f"milestone branch={milestone.branch}",
        )
    if current_branch != milestone.branch:
        return (
            False,
            f"plan {plan_name} has unpublished claimed changes on "
            f"{current_branch or 'detached HEAD'}, not milestone branch "
            f"{milestone.branch}: {claimed_sample}",
        )

    _commit_and_push_phase(
        root,
        milestone.branch,
        plan_name,
        "resume-publish",
        writer=writer,
        preexisting_dirty_paths=[],
    )
    _capture_sync_state(
        root, spec_path, branch=milestone.branch, pr_number=state.pr_number
    )
    remaining_dirty = _root_relative_dirty_paths(root)
    remaining_claimed = sorted(path for path in remaining_dirty if path in claimed_root_paths)
    if remaining_claimed:
        return (
            False,
            f"claimed milestone changes remain dirty after resume-publish: "
            f"{', '.join(remaining_claimed[:5])}",
        )
    return (
        True,
        f"published {len(dirty_claimed)} claimed milestone change(s) before PR progression: "
        f"{claimed_sample}",
    )


def _validate_pr_progression_wbc(
    *,
    root: Path,
    spec_path: Path,
    state: ChainState,
    milestone: MilestoneSpec,
    plan_name: str,
    pr_number: int,
    transition_name: str,
) -> dict[str, Any]:
    from arnold_pipelines.megaplan.chain.execution_binding import (
        execution_binding_report,
    )
    from arnold_pipelines.megaplan.chain.wbc import (
        GIT_PR_READY_SURFACE,
        GIT_PR_READY_WRITER_ID,
        ChainWbcRule,
        finalize_artifact_candidates,
        finalize_receipt_candidates,
        record_chain_wbc_evidence,
        validate_chain_wbc_transition,
    )

    plan_dir = resolve_plan_dir(root, plan_name)
    plan_state = _plan_state_payload_from_name(root, plan_name)
    current_state = plan_state.get("current_state")
    binding = execution_binding_report(spec_path, state)
    finalize_receipts = finalize_receipt_candidates(plan_dir)
    finalize_artifacts = finalize_artifact_candidates(plan_dir)
    binding_ok = (
        binding.get("status") in {"match", "reconcile_required"}
        if binding.get("required")
        else True
    )
    evidence = validate_chain_wbc_transition(
        writer_id=GIT_PR_READY_WRITER_ID,
        surface_name=GIT_PR_READY_SURFACE,
        transition_name=transition_name,
        subject=f"{milestone.label}:pr#{pr_number}",
        source_path=spec_path,
        project_dir=root,
        rules=(
            ChainWbcRule(
                "plan_state_terminal",
                f"{STATE_FINALIZED}|{STATE_DONE}|{STATE_AWAITING_PR_MERGE}",
                current_state,
                current_state in {STATE_FINALIZED, STATE_DONE, STATE_AWAITING_PR_MERGE},
            ),
            ChainWbcRule(
                "finalize_receipt_present",
                True,
                bool(finalize_receipts),
                bool(finalize_receipts),
                "finalize promotion must persist a durable receipt before PR actions",
            ),
            ChainWbcRule(
                "finalize_artifacts_present",
                True,
                bool(finalize_artifacts),
                bool(finalize_artifacts),
                "finalize promotion must leave canonical artifacts behind",
            ),
            ChainWbcRule(
                "execution_binding_current",
                True,
                binding.get("status"),
                binding_ok,
                "chain execution binding must still match before PR progression",
            ),
            ChainWbcRule(
                "pr_number_bound",
                pr_number,
                state.pr_number,
                state.pr_number == pr_number,
            ),
        ),
        extra={
            "milestone_label": milestone.label,
            "plan_name": plan_name,
            "plan_dir": str(plan_dir),
            "finalize_receipts": finalize_receipts,
            "finalize_artifacts": finalize_artifacts,
            "execution_binding_status": binding.get("status"),
        },
    )
    record_chain_wbc_evidence(
        state.metadata,
        entry_key=f"{transition_name}:{milestone.label}:{pr_number}",
        evidence=evidence,
    )
    return evidence


def _recover_stale_merged_pr_for_unfinished_plan(
    root: Path,
    spec_path: Path,
    state: ChainState,
    milestone: MilestoneSpec,
    plan_state: dict[str, Any],
    *,
    writer,
) -> tuple[ChainState | None, str]:
    """Retire a merged PR cursor that points at a plan that still must run.

    A previously buggy chain could squash-merge a draft PR while execute output
    was still local-only. On restart, live GitHub says "merged" but state.json
    still says finalized/executing. Advancing would drop unfinished tasks; a
    plain resume would clean the dirty worktree during branch checkout. Preserve
    claimed local output on the milestone branch first, then clear the stale PR
    cursor so the normal resume path can continue and create a fresh PR.
    """

    plan_name = state.current_plan_name
    if not plan_name or not milestone.branch:
        return None, "missing active plan or milestone branch for stale merged PR recovery"

    current_state = plan_state.get("current_state")
    canonical_current_state = current_state
    if current_state == STATE_DONE:
        return None, f"plan {plan_name} is already {STATE_DONE!r}"
    if not isinstance(canonical_current_state, str) or not canonical_current_state:
        return None, f"plan {plan_name} has no usable current_state for stale merged PR recovery"
    if canonical_current_state not in {STATE_PREPPED, STATE_FINALIZED, STATE_EXECUTED}:
        return (
            None,
            f"plan {plan_name} current_state={current_state!r} is not recoverable "
            f"before terminal-success {STATE_DONE!r}; stale merged PR cannot advance",
        )

    claimed_root_paths = _claimed_root_paths(root, plan_name)
    dirty_paths = _root_relative_dirty_paths(root)
    dirty_claimed = sorted(path for path in dirty_paths if path in claimed_root_paths)
    unrelated_dirty = sorted(
        path
        for path in dirty_paths
        if path not in claimed_root_paths
        and not _is_chain_control_path(path)
        and path != ".megaplan"
        and not path.startswith(".megaplan/")
    )
    active_step = plan_state.get("active_step")
    active_phase = (
        active_step.get("phase")
        if isinstance(active_step, dict) and isinstance(active_step.get("phase"), str)
        else None
    )
    if unrelated_dirty:
        if active_phase != "execute":
            sample = ", ".join(unrelated_dirty[:5])
            return (
                None,
                f"plan {plan_name} has stale merged PR #{state.pr_number} but unrelated "
                f"dirty paths prevent recovery: {sample}",
            )
        writer(
            f"[chain] stale merged PR recovery for {plan_name} will preserve "
            f"{len(unrelated_dirty)} unclaimed dirty path(s) from active execute: "
            f"{', '.join(unrelated_dirty[:5])}\n"
        )

    old_pr_number = state.pr_number
    dirty_recovery_paths = sorted({*dirty_claimed, *unrelated_dirty})
    if dirty_recovery_paths:
        current_branch = _current_branch_name(root)
        if current_branch != milestone.branch:
            _run_command(
                root,
                ["git", "checkout", "-B", milestone.branch, "HEAD"],
                writer=writer,
                error_code="git_branch_failed",
            )
        _commit_and_push_phase(
            root,
            milestone.branch,
            plan_name,
            "stale-merged-pr-recovery",
            writer=writer,
            preexisting_dirty_paths=[],
        )
        _capture_sync_state(root, spec_path, branch=milestone.branch, pr_number=None)
        state = chain_spec.load_chain_state(spec_path)

    plan_dir = resolve_plan_dir(root, plan_name)
    authoritative, authority_reason = _latest_execution_batch_all_tasks_done(plan_dir)
    empty_finalize_tasks, finalize_reason = _finalize_payload_has_empty_tasks(plan_dir)
    terminal_finalize_only, terminal_finalize_reason = _finalize_has_only_terminal_status_rows(
        plan_dir
    )
    if (
        canonical_current_state == STATE_EXECUTED
        and terminal_finalize_only
    ):
        _mark_plan_completed_by_chain(
            root,
            plan_name,
            milestone_label=milestone.label,
            completion_reason=(
                "stale merged PR recovery accepted terminal finalize task statuses: "
                f"{terminal_finalize_reason}"
            ),
            writer=writer,
            state=state,
        )
        state.last_state = STATE_DONE
        state.metadata["stale_merged_pr_recovery"] = {
            "recovered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "milestone": milestone.label,
            "plan": plan_name,
            "stale_pr_number": old_pr_number,
            "plan_current_state": current_state,
            "canonical_plan_current_state": canonical_current_state,
            "dirty_claimed_paths": dirty_claimed,
            "unclaimed_execute_dirty_paths": unrelated_dirty,
        }
        chain_spec.save_chain_state(spec_path, state)
        return (
            state,
            "recovered stale merged PR with terminal finalize task statuses; "
            f"{terminal_finalize_reason}",
        )

    state.pr_number = None
    state.pr_state = None
    state.last_state = canonical_current_state
    state.metadata["stale_merged_pr_recovery"] = {
        "recovered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "milestone": milestone.label,
        "plan": plan_name,
        "stale_pr_number": old_pr_number,
        "plan_current_state": current_state,
        "canonical_plan_current_state": canonical_current_state,
        "dirty_claimed_paths": dirty_claimed,
        "unclaimed_execute_dirty_paths": unrelated_dirty,
    }
    chain_spec.save_chain_state(spec_path, state)

    if dirty_recovery_paths:
        return (
            state,
            f"recovered stale merged PR #{old_pr_number} for unfinished plan {plan_name}; "
            f"published {len(dirty_recovery_paths)} local change(s) to {milestone.branch} "
            f"({len(dirty_claimed)} claimed, {len(unrelated_dirty)} unclaimed active-execute)",
        )
    return (
        state,
        f"recovered stale merged PR #{old_pr_number} for unfinished plan {plan_name}; "
        "cleared stale PR cursor with no claimed local changes to publish",
    )


def _block_pr_progression_guard_failure(
    *,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    milestone: MilestoneSpec,
    reason: str,
    events: list[dict[str, Any]],
    writer,
) -> dict[str, Any]:
    writer(f"[chain] PR progression blocked {milestone.label}: {reason}\n")
    state.last_state = "authority_divergence"
    chain_spec.save_chain_state(spec_path, state)
    return _result(
        "blocked",
        state,
        events,
        spec=spec,
        reason=reason,
    )


def _apply_committed_acceptance_state(
    state: ChainState, new_state: dict[str, Any]
) -> None:
    """Mirror a durably-committed acceptance state into the in-memory state.

    :func:`prepare_acceptance_commit` / :func:`commit_acceptance_commit`
    atomically wrote *new_state* (completed record, cursor advance, and
    milestone-boundary evidence) under the CAS guard.  Reflect only the fields
    the acceptance commit owns into the live state object so subsequent
    in-memory work (further mutations plus a final ``save_chain_state``) stays
    consistent with the committed durable state.  All other state attributes
    are left exactly as the caller set them.
    """
    completed_raw = new_state.get("completed")
    if isinstance(completed_raw, list):
        state.completed = [
            dict(r) if isinstance(r, dict) else r for r in completed_raw
        ]
    idx_raw = new_state.get("current_milestone_index")
    if isinstance(idx_raw, int):
        state.current_milestone_index = idx_raw
    evidence_raw = new_state.get("milestone_boundary_evidence")
    if isinstance(evidence_raw, dict):
        state.milestone_boundary_evidence = {
            key: dict(val) if isinstance(val, dict) else val
            for key, val in evidence_raw.items()
        }


def _append_completed_with_guard(
    root: Path,
    state: ChainState,
    record: dict[str, Any],
    *,
    implementation_milestone: bool,
    writer,
    # T16 — atomic/enforce-mode acceptance-commit wiring.  Every parameter
    # below is optional; when they are absent (all legacy callers today) the
    # function falls back to the original shadow-mode behavior exactly.
    acceptance_result: Any = None,
    spec_path: "Path | None" = None,
    plan_dir: "Path | None" = None,
    milestone_index: "int | None" = None,
    predicate_failures: "list[dict[str, Any]] | None" = None,
    acceptance_transaction_id: str = "",
    acceptance_snapshot_hash: str = "",
) -> tuple[bool, str]:
    ok, reason = _chain_completion_guard(
        root,
        record,
        implementation_milestone=implementation_milestone,
        chain_state=state,
    )
    label = record.get("label") or "unknown"

    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        PREDICATE_KIND_DIVERGENT,
        PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
        is_fail_closed_mode,
        normalize_contract_mode,
    )

    fail_closed = is_fail_closed_mode(
        normalize_contract_mode(state.completion_contract_mode)
    )

    if not fail_closed:
        # ── Shadow / warn / off: preserve legacy behavior exactly ─────────
        if not ok:
            state.last_state = "authority_divergence"
            writer(f"[chain] completion guard blocked {label}: {reason}\n")
            return False, reason
        if spec_path is not None and plan_dir is not None:
            from arnold_pipelines.megaplan.chain.wbc import (
                CHAIN_ADVANCE_SURFACE,
                CHAIN_ADVANCE_WRITER_ID,
                ChainWbcRule,
                record_chain_wbc_evidence,
                validate_chain_wbc_transition,
            )

            validation_evidence = validate_chain_wbc_transition(
                writer_id=CHAIN_ADVANCE_WRITER_ID,
                surface_name=CHAIN_ADVANCE_SURFACE,
                transition_name="chain_milestone_advance",
                subject=label,
                source_path=Path(spec_path),
                project_dir=root,
                rules=(
                    ChainWbcRule("completion_guard", True, ok, ok),
                    ChainWbcRule(
                        "plan_name_bound",
                        True,
                        bool(record.get("plan")),
                        bool(record.get("plan")),
                    ),
                    ChainWbcRule(
                        "milestone_index_known",
                        True,
                        milestone_index is not None,
                        milestone_index is not None,
                    ),
                ),
                extra={
                    "plan_name": str(record.get("plan") or ""),
                    "milestone_index": milestone_index,
                    "guard_reason": reason,
                },
            )
            record_chain_wbc_evidence(
                state.metadata,
                entry_key=f"chain_advance:{label}:{milestone_index}",
                evidence=validation_evidence,
            )
        state.completed.append(record)
        return True, reason

    # ── Atomic / enforce (fail-closed) mode ──────────────────────────────
    def _record_repair_target(
        kind: str,
        summary: str,
        *,
        details: "dict[str, Any] | None" = None,
        evidence_kind: str = "completion_guard",
    ) -> None:
        """Record a typed acceptance repair target without mutating completion
        or cursor state (prior state stays unchanged on failure)."""
        targets = list(state.metadata.get("completion_guard_repair_targets") or [])
        target: dict[str, Any] = {
            "kind": str(kind),
            "evidence_kind": str(evidence_kind),
            "summary": str(summary),
            "details": dict(details or {}),
        }
        if acceptance_transaction_id:
            target["acceptance_transaction_id"] = acceptance_transaction_id
        if acceptance_snapshot_hash:
            target["acceptance_snapshot_hash"] = acceptance_snapshot_hash
        targets.append(target)
        state.metadata["completion_guard_repair_targets"] = targets

    # (1) Predicate failure -> fail closed; prior state unchanged.
    if not ok:
        writer(f"[chain] completion guard blocked {label} (atomic): {reason}\n")
        if predicate_failures:
            for pf in predicate_failures:
                if not isinstance(pf, dict):
                    continue
                _record_repair_target(
                    str(pf.get("kind") or PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE),
                    str(pf.get("summary") or reason),
                    details=dict(pf.get("details") or {}),
                    evidence_kind=str(pf.get("evidence_kind") or "completion_guard"),
                )
        else:
            _record_repair_target(
                PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
                reason,
                details={
                    "legacy": True,
                    "plan_name": str(record.get("plan") or ""),
                    "milestone_label": label,
                    "predicate_reason": reason,
                },
            )
        return False, reason

    # (2) Predicate passed.  Atomic completion requires a durably committed
    #     accepted boundary to advance the completion cursor.  Without one the
    #     cursor must never advance (fail-closed: never complete without
    #     accepted acceptance evidence).
    if acceptance_result is None or spec_path is None or plan_dir is None:
        block_reason = (
            f"atomic completion for {label} requires an accepted acceptance "
            "boundary; none provided (fail-closed)"
        )
        writer(f"[chain] {block_reason}\n")
        _record_repair_target(
            PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
            block_reason,
            details={
                "legacy": True,
                "plan_name": str(record.get("plan") or ""),
                "milestone_label": label,
                "missing_acceptance_evidence": True,
            },
        )
        return False, block_reason

    # (3) Stage the acceptance commit as one CAS-backed journal transaction.
    from arnold_pipelines.megaplan.orchestration.completion_io import (
        commit_acceptance_commit,
        discard_acceptance_commit,
        prepare_acceptance_commit,
    )

    try:
        commit_plan = prepare_acceptance_commit(
            plan_dir=Path(plan_dir),
            spec_path=Path(spec_path),
            result=acceptance_result,
            state=state,
            milestone_index=milestone_index,
        )
    except ValueError as exc:
        # Boundary precondition rejected (not accepted, unbound identity, ...).
        prep_reason = f"acceptance commit prepare rejected for {label}: {exc}"
        writer(f"[chain] {prep_reason}\n")
        _record_repair_target(
            PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
            prep_reason,
            details={
                "plan_name": str(record.get("plan") or ""),
                "milestone_label": label,
                "prepare_error": str(exc),
            },
        )
        return False, prep_reason

    # (4) Apply durably under the CAS guard.
    cas_result = commit_acceptance_commit(commit_plan)
    if not getattr(cas_result, "committed", False):
        # CAS violation -> prior durable state unchanged (the journal already
        # discarded the staged transaction).  Discard any remaining staged
        # prepare and emit a typed divergent repair target.
        discard_acceptance_commit(commit_plan)
        violations = getattr(cas_result, "violations", ()) or ()
        viol_summary = (
            "; ".join(
                f"{v.guard}@{Path(v.target_path).name}" for v in violations
            )
            or "cas guard mismatch"
        )
        cas_reason = (
            f"acceptance commit CAS violation for {label} (prior state "
            f"unchanged): {viol_summary}"
        )
        writer(f"[chain] {cas_reason}\n")
        _record_repair_target(
            PREDICATE_KIND_DIVERGENT,
            cas_reason,
            details={
                "plan_name": str(record.get("plan") or ""),
                "milestone_label": label,
                "cas_violations": [v.to_dict() for v in violations],
            },
            evidence_kind="acceptance_commit",
        )
        return False, cas_reason

    # (5) Commit succeeded.  Mirror the durably-committed completion fields
    #     into the in-memory state so downstream callers observe the same
    #     state that was just written under the CAS guard.
    from arnold_pipelines.megaplan.chain.wbc import (
        CHAIN_ADVANCE_SURFACE,
        CHAIN_ADVANCE_WRITER_ID,
        ChainWbcRule,
        record_chain_wbc_evidence,
        validate_chain_wbc_transition,
    )

    validation_evidence = validate_chain_wbc_transition(
        writer_id=CHAIN_ADVANCE_WRITER_ID,
        surface_name=CHAIN_ADVANCE_SURFACE,
        transition_name="chain_milestone_advance",
        subject=label,
        source_path=Path(spec_path),
        project_dir=root,
        rules=(
            ChainWbcRule("completion_guard", True, ok, ok),
            ChainWbcRule(
                "acceptance_commit_committed",
                True,
                bool(getattr(cas_result, "committed", False)),
                bool(getattr(cas_result, "committed", False)),
            ),
            ChainWbcRule(
                "accepted_boundary_present",
                True,
                acceptance_result is not None,
                acceptance_result is not None,
            ),
            ChainWbcRule(
                "milestone_index_known",
                True,
                milestone_index is not None,
                milestone_index is not None,
            ),
        ),
        extra={
            "plan_name": str(record.get("plan") or ""),
            "milestone_index": milestone_index,
            "acceptance_transaction_id": acceptance_transaction_id,
            "acceptance_snapshot_hash": acceptance_snapshot_hash,
            "guard_reason": reason,
        },
    )
    record_chain_wbc_evidence(
        state.metadata,
        entry_key=f"chain_advance:{label}:{milestone_index}",
        evidence=validation_evidence,
    )
    _apply_committed_acceptance_state(state, commit_plan.new_state)
    return True, reason


def _emit_milestone_start_evidence(
    state: ChainState,
    *,
    milestone_label: str,
    milestone_index: int,
    plan_name: str,
) -> None:
    """Record durable milestone-start boundary evidence in chain state."""
    evidence = chain_spec.build_milestone_boundary_evidence(
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name=plan_name,
        contract_id=CHAIN_MILESTONE_START_ROW_ID,
        contract_boundary_id="chain_milestone_start",
        state=state,
    )
    state.set_milestone_evidence(evidence)


def _emit_milestone_completion_evidence(
    state: ChainState,
    *,
    milestone_label: str,
    milestone_index: int,
    plan_name: str,
) -> None:
    """Record durable milestone-completion boundary evidence in chain state."""
    evidence = chain_spec.build_milestone_boundary_evidence(
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name=plan_name,
        contract_id=CHAIN_MILESTONE_COMPLETION_ROW_ID,
        contract_boundary_id="chain_milestone_completion",
        state=state,
    )
    state.set_milestone_evidence(evidence)


def _emit_chain_complete_evidence(
    state: ChainState,
    *,
    spec: ChainSpec,
) -> None:
    """Record durable chain-complete boundary evidence in chain state."""
    plan_name = "chain_complete"
    evidence = chain_spec.build_milestone_boundary_evidence(
        milestone_label="chain_complete",
        milestone_index=len(spec.milestones),
        plan_name=plan_name,
        contract_id=CHAIN_COMPLETE_ROW_ID,
        contract_boundary_id="chain_complete",
        state=state,
    )
    state.set_milestone_evidence(evidence)


def _reconciliation_fail_closed(state: ChainState) -> tuple[bool, str]:
    """Return ``(True, reason)`` when reconciliation operates in fail-closed mode.

    In atomic/enforce mode, reconciliation must never grant completion
    authority from a ground-truth projection (terminal plan state, merged PR
    state, reviewed finalized state, or any other derived observation).  Only
    an accepted acceptance transaction recorded through the CAS-backed commit
    helper can advance the completion cursor.  This helper lets the
    reconciliation append primitives short-circuit before mutating
    ``state.completed`` so projections cannot masquerade as acceptance
    authority.
    """
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        is_fail_closed_mode,
        normalize_contract_mode,
    )

    mode = normalize_contract_mode(state.completion_contract_mode)
    if is_fail_closed_mode(mode):
        return True, (
            "reconciliation cannot grant atomic-mode completion authority "
            "from a ground-truth projection without an accepted acceptance "
            "transaction (fail-closed)"
        )
    return False, ""


def _append_reconciled_completed_record(
    root: Path,
    state: ChainState,
    *,
    plan_name: str,
    milestone: MilestoneSpec,
    pr_number: int | None,
    pr_state: str | None,
    completion_reason: str,
    writer,
) -> bool:
    # T17 — reconciliation cannot grant atomic-mode completion authority from
    # ground-truth projections without an accepted acceptance transaction.
    fail_closed, reason = _reconciliation_fail_closed(state)
    if fail_closed:
        writer(
            f"[chain] reconciliation blocked completed record for "
            f"{milestone.label} in atomic mode: {reason}\n"
        )
        return False
    state.completed.append(
        {
            "label": milestone.label,
            "plan": plan_name,
            "status": STATE_DONE,
            "pr_number": pr_number,
            "pr_state": pr_state,
        }
    )
    _mark_plan_completed_by_chain(
        root,
        plan_name,
        milestone_label=milestone.label,
        completion_reason=completion_reason,
        writer=writer,
        state=state,
    )
    # Emit milestone completion boundary evidence for the reconciled record.
    _emit_milestone_completion_evidence(
        state,
        milestone_label=milestone.label,
        milestone_index=-1,  # caller is responsible for setting the right index
        plan_name=plan_name,
    )
    return True


def _reconcile_chain_from_ground_truth(
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    *,
    writer,
    push_enabled: bool = True,
) -> ChainState:
    """Derive the chain cursor from plan state.json and live GitHub PR state."""

    # T17 — In atomic/enforce mode reconciliation must NEVER derive completion
    # authority from a ground-truth projection. Only an accepted acceptance
    # transaction committed through the CAS-backed helper can advance the
    # completion cursor. Short-circuit before any projection-derived logic.
    fail_closed, fc_reason = _reconciliation_fail_closed(state)
    if fail_closed:
        writer(
            f"[chain] reconciliation skipped in atomic mode for "
            f"{state.current_plan_name or 'current milestone'}: {fc_reason}\n"
        )
        chain_spec.save_chain_state(spec_path, state)
        return state

    labels_to_index = {
        milestone.label: index for index, milestone in enumerate(spec.milestones)
    }
    completed_by_label = _completed_records_by_label(state)
    reconciled_completed: list[dict[str, Any]] = []
    removed_completed: dict[str, dict[str, Any]] = {}

    for milestone in spec.milestones:
        record = completed_by_label.get(milestone.label)
        if not isinstance(record, dict):
            continue
        record = dict(record)
        pr_number = _record_pr_number(record)
        if push_enabled and milestone.branch and pr_number is not None:
            live_pr_state = _pr_state(root, pr_number, writer=writer)
            if record.get("pr_state") != live_pr_state:
                writer(
                    f"[chain] reconciled completed PR state for {milestone.label} "
                    f"#{pr_number}: {record.get('pr_state') or 'unknown'} -> "
                    f"{live_pr_state}\n"
                )
            record["pr_state"] = live_pr_state
            if live_pr_state != "merged":
                writer(
                    f"[chain] completed record for {milestone.label} is not "
                    f"authoritative yet: PR #{pr_number} state={live_pr_state}\n"
                )
                removed = dict(record)
                removed["pr_state"] = live_pr_state
                removed_completed[milestone.label] = removed
                continue
        reconciled_completed.append(record)

    if reconciled_completed != state.completed:
        state.completed = reconciled_completed

    completed_labels = {
        record.get("label")
        for record in state.completed
        if isinstance(record, dict) and isinstance(record.get("label"), str)
    }
    first_incomplete = _completed_prefix_index(spec, completed_labels)
    if state.current_milestone_index < first_incomplete:
        writer(
            f"[chain] reconciled cursor index: {state.current_milestone_index} "
            f"-> {first_incomplete} from completed milestones\n"
        )
        state.current_milestone_index = first_incomplete
        if first_incomplete >= len(spec.milestones):
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None
            state.last_state = "done"
    elif state.current_milestone_index > first_incomplete:
        writer(
            f"[chain] reconciled cursor index: {state.current_milestone_index} "
            f"-> {first_incomplete} from completed milestones\n"
        )
        state.current_milestone_index = first_incomplete
        if first_incomplete < len(spec.milestones):
            milestone = spec.milestones[first_incomplete]
            removed = removed_completed.get(milestone.label)
            plan = removed.get("plan") if isinstance(removed, dict) else None
            state.current_plan_name = plan if isinstance(plan, str) and plan else None
            state.pr_number = _record_pr_number(removed)
            pr_state = removed.get("pr_state") if isinstance(removed, dict) else None
            state.pr_state = pr_state if isinstance(pr_state, str) else None
            state.last_state = "authority_divergence"
        else:
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None

    plan_name = state.current_plan_name
    plan_state = _plan_state_payload_from_name(root, plan_name)
    if plan_state:
        label = _chain_policy_milestone_label(plan_state)
        plan_index = labels_to_index.get(label) if label is not None else None
        if plan_index is not None and state.current_milestone_index != plan_index:
            writer(
                f"[chain] reconciled cursor index from plan {plan_name}: "
                f"{state.current_milestone_index} -> {plan_index}\n"
            )
            state.current_milestone_index = plan_index
        current_state = plan_state.get("current_state")
        preserve_pr_cursor = (
            state.last_state in {STATE_AWAITING_PR_MERGE, "pr_closed"}
            and state.pr_number is not None
        )
        if (
            isinstance(current_state, str)
            and state.last_state != current_state
            and not preserve_pr_cursor
        ):
            writer(
                f"[chain] synced last_state for {plan_name}: "
                f"{state.last_state or 'unknown'} -> {current_state}\n"
            )
            state.last_state = current_state

    active_index = state.current_milestone_index
    active_milestone = (
        spec.milestones[active_index]
        if 0 <= active_index < len(spec.milestones)
        else None
    )
    active_uses_pr = bool(
        push_enabled and active_milestone is not None and active_milestone.branch
    )
    live_active_pr_state: str | None = None
    if (
        active_uses_pr
        and state.pr_number is not None
        and state.last_state != "pr_closed"
    ):
        live_active_pr_state = _pr_state(root, state.pr_number, writer=writer)
        if state.pr_state == "merged" and live_active_pr_state != "merged":
            writer(
                f"[chain] preserved recorded merged PR state for "
                f"{active_milestone.label if active_milestone else 'milestone'} "
                f"#{state.pr_number} despite live state {live_active_pr_state}\n"
            )
            live_active_pr_state = "merged"
        elif state.pr_state != live_active_pr_state:
            writer(
                f"[chain] reconciled live PR state for "
                f"{active_milestone.label if active_milestone else 'milestone'} "
                f"#{state.pr_number}: {state.pr_state or 'unknown'} -> "
                f"{live_active_pr_state}\n"
            )
        state.pr_state = live_active_pr_state

    current_plan_state = plan_state.get("current_state") if plan_state else None
    if (
        bool(plan_name)
        and active_milestone is not None
        and current_plan_state == STATE_DONE
        and active_milestone.label not in completed_labels
        and (
            not active_uses_pr
            or (state.pr_number is not None and live_active_pr_state == "merged")
        )
    ):
        if _append_reconciled_completed_record(
            root,
            state,
            plan_name=plan_name,
            milestone=active_milestone,
            pr_number=state.pr_number if active_uses_pr else None,
            pr_state="merged" if active_uses_pr else None,
            completion_reason="terminal plan state reconciled from ground truth",
            writer=writer,
        ):
            completed_labels.add(active_milestone.label)

    reviewed_finalized_plan = (
        bool(plan_name)
        and bool(plan_state)
        and _finalized_plan_has_successful_review(plan_state)
    )
    if reviewed_finalized_plan and active_milestone is not None:
        if active_uses_pr and state.pr_number is not None:
            if live_active_pr_state == "open" and state.last_state != STATE_AWAITING_PR_MERGE:
                writer(
                    f"[chain] plan {plan_name} is finalized with successful review but PR "
                    f"#{state.pr_number} is open; waiting for merge\n"
                )
                state.last_state = STATE_AWAITING_PR_MERGE
            elif (
                live_active_pr_state == "merged"
                and active_milestone.label not in completed_labels
            ):
                if _append_reconciled_completed_record(
                    root,
                    state,
                    plan_name=plan_name,
                    milestone=active_milestone,
                    pr_number=state.pr_number,
                    pr_state="merged",
                    completion_reason="reviewed finalized plan with merged PR",
                    writer=writer,
                ):
                    completed_labels.add(active_milestone.label)
        elif not active_uses_pr and active_milestone.label not in completed_labels:
            if _append_reconciled_completed_record(
                root,
                state,
                plan_name=plan_name,
                milestone=active_milestone,
                pr_number=None,
                pr_state=None,
                completion_reason="reviewed finalized local plan",
                writer=writer,
            ):
                completed_labels.add(active_milestone.label)
    if (
        active_uses_pr
        and state.pr_number is not None
        and current_plan_state == STATE_DONE
        and live_active_pr_state == "open"
        and state.last_state != STATE_AWAITING_PR_MERGE
    ):
        writer(
            f"[chain] plan {plan_name} is {current_plan_state} but PR "
            f"#{state.pr_number} is open; waiting for merge\n"
        )
        state.last_state = STATE_AWAITING_PR_MERGE

    if active_milestone is not None and active_milestone.label in completed_labels:
        next_index = _completed_prefix_index(spec, completed_labels)
        if next_index != state.current_milestone_index:
            writer(
                f"[chain] reconciled cursor past completed milestone "
                f"{active_milestone.label}: {state.current_milestone_index} "
                f"-> {next_index}\n"
            )
            state.current_milestone_index = next_index
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None
            if next_index >= len(spec.milestones):
                state.last_state = "done"

    _append_reconciliation_audit(
        state,
        plan_name=plan_name,
        plan_state=plan_state,
        pr_number=state.pr_number,
        pr_state=state.pr_state,
    )
    chain_spec.save_chain_state(spec_path, state)
    return state


def _append_reconciled_completed_record_with_guard(
    root: Path,
    state: ChainState,
    *,
    plan_name: str,
    milestone: MilestoneSpec,
    pr_number: int | None,
    pr_state: str | None,
    completion_reason: str,
    writer,
) -> tuple[bool, str]:
    # T17 — reconciliation cannot grant atomic-mode completion authority from
    # ground-truth projections without an accepted acceptance transaction.
    # Short-circuit before delegating to _append_completed_with_guard so the
    # projection is never turned into completion authority and no spurious
    # repair target is recorded for an expected reconciliation block.
    fail_closed, fail_reason = _reconciliation_fail_closed(state)
    if fail_closed:
        writer(
            f"[chain] reconciliation blocked completed record for "
            f"{milestone.label} in atomic mode: {fail_reason}\n"
        )
        return False, fail_reason
    record = {
        "label": milestone.label,
        "plan": plan_name,
        "status": STATE_DONE,
        "pr_number": pr_number,
        "pr_state": pr_state,
    }
    if pr_number is None:
        local_commit_sha = _current_git_head(root)
        if local_commit_sha is not None:
            record["local_commit_sha"] = local_commit_sha
            record["publication_evidence"] = "local_no_push_reconciliation"
    appended, reason = _append_completed_with_guard(
        root,
        state,
        record,
        implementation_milestone=True,
        writer=writer,
    )
    if not appended:
        return False, reason
    _mark_plan_completed_by_chain(
        root,
        plan_name,
        milestone_label=milestone.label,
        completion_reason=completion_reason if completion_reason else reason,
        writer=writer,
        state=state,
    )
    writer(
        f"[chain] reconciled terminal plan {plan_name} into completed "
        f"milestone {milestone.label}\n"
    )
    return True, reason


def _handle_completion_guard_failure(
    *,
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    milestone: MilestoneSpec,
    plan_name: str,
    outcome_status: str,
    reason: str,
    events: list[dict[str, Any]],
    writer,
    predicate_failures: list[dict[str, Any]] | None = None,
    acceptance_transaction_id: str = "",
    acceptance_snapshot_hash: str = "",
) -> dict[str, Any]:
    writer(
        f"[chain] milestone {milestone.label} completion guard rejected terminal "
        f"claim for {plan_name}: {reason}\n"
    )

    # ── Build typed acceptance repair targets ──────────────────────────
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
    )

    repair_targets: list[dict[str, Any]] = []
    if predicate_failures:
        # Caller provided typed V2 context — use it directly.
        for pf in predicate_failures:
            if not isinstance(pf, dict):
                continue
            target: dict[str, Any] = {
                "kind": str(pf.get("kind") or PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE),
                "evidence_kind": str(pf.get("evidence_kind") or "completion_guard"),
                "summary": str(pf.get("summary") or reason),
                "details": dict(pf.get("details") or {}),
            }
            if acceptance_transaction_id:
                target["acceptance_transaction_id"] = acceptance_transaction_id
            if acceptance_snapshot_hash:
                target["acceptance_snapshot_hash"] = acceptance_snapshot_hash
            repair_targets.append(target)
    else:
        # Legacy caller — no V2 context available.  Emit a fail-closed
        # unknown acceptance failure so downstream repair tooling knows
        # the guard blocked but cannot yet attribute it to a specific
        # predicate.
        legacy_target: dict[str, Any] = {
            "kind": PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
            "evidence_kind": "completion_guard",
            "summary": reason,
            "details": {
                "legacy": True,
                "plan_name": plan_name,
                "milestone_label": milestone.label,
                "outcome_status": outcome_status,
            },
        }
        if acceptance_transaction_id:
            legacy_target["acceptance_transaction_id"] = acceptance_transaction_id
        if acceptance_snapshot_hash:
            legacy_target["acceptance_snapshot_hash"] = acceptance_snapshot_hash
        repair_targets.append(legacy_target)

    state.metadata["completion_guard_repair_targets"] = repair_targets

    # ── T14 — invalidate prior acceptance candidates ───────────────────
    # After a completion guard blocks, any prior uncommitted acceptance
    # candidate is stale.  The caller must produce a new snapshot and run
    # the full acceptance boundary before committing.
    try:
        plan_path = resolve_plan_dir(root, plan_name) if plan_name else None
    except Exception:
        plan_path = None
    if plan_path is not None and plan_path.is_dir():
        now_iso = datetime.now(timezone.utc).isoformat()
        state.invalidate_candidate(
            milestone.label,
            transaction_id=acceptance_transaction_id or "",
            reason=reason or "completion guard blocked",
            superseded_by="",
            invalidated_at=now_iso,
        )
        # Also call the cloud-level candidate invalidation to discard
        # any uncommitted candidate files on disk.
        try:
            from arnold_pipelines.megaplan.cloud.repair_revalidation import (
                invalidate_acceptance_candidates_after_repair,
            )
            invalidate_acceptance_candidates_after_repair(
                plan_path,
                milestone_label=milestone.label,
                repair_reason=f"completion guard blocked: {reason}",
            )
        except Exception:
            pass

    synthetic = DriverOutcome(
        plan=plan_name,
        status="blocked",
        final_state=outcome_status,
        iterations=0,
        reason=f"completion guard rejected terminal claim: {reason}",
        last_phase="completion_guard",
    )
    decision = _handle_outcome(
        synthetic,
        spec=spec,
        writer=writer,
        milestone=milestone,
        state=state,
        root=root,
    )
    if decision == "retry":
        resumable_state = _resumable_retry_state(root, state.current_plan_name)
        if resumable_state is not None:
            writer(
                f"[chain] retrying milestone {milestone.label} by resuming plan "
                f"{state.current_plan_name} from {resumable_state}\n"
            )
        else:
            writer(f"[chain] retrying milestone {milestone.label}\n")
            state.current_plan_name = None
        state.last_state = "blocked"
        state.pr_number = None
        state.pr_state = None
        chain_spec.save_chain_state(spec_path, state)
        return _result(
            "stopped",
            state,
            events,
            spec=spec,
            reason=f"milestone {milestone.label} completion guard retrying: {reason}",
        )
    if decision == "stop":
        state.last_state = "blocked"
        _maybe_file_ladder_ticket(
            root,
            spec_path,
            milestone,
            synthetic,
            state,
            writer=writer,
        )
        chain_spec.save_chain_state(spec_path, state)
        return _result(
            "stopped",
            state,
            events,
            spec=spec,
            reason=f"milestone {milestone.label} completion guard blocked append: {reason}",
        )
    state.last_state = "authority_divergence"
    chain_spec.save_chain_state(spec_path, state)
    return _result(
        "blocked",
        state,
        events,
        spec=spec,
        reason=f"milestone {milestone.label} completion guard blocked append: {reason}",
    )


def _finalize_records_missing_authority_fields(
    task_records: list[dict[str, Any]],
) -> list[str]:
    from arnold_pipelines.megaplan.orchestration.rubber_stamp import is_rubber_stamp

    missing: list[str] = []
    for task in task_records:
        task_id = str(task.get("task_id") or task.get("id") or "?")
        if any(
            task.get(field)
            for field in (
                "files_changed",
                "commands_run",
                "evidence_files",
                "sections_written",
                "evidence",
            )
        ):
            continue
        kind = task.get("kind")
        notes = task.get("executor_notes")
        reviewer_verdict = task.get("reviewer_verdict")
        if (
            task.get("status") == "skipped"
            and isinstance(notes, str)
            and notes.strip()
            and not is_rubber_stamp(notes, strict=True)
        ):
            continue
        if _is_explained_noop_completion(task):
            continue
        if reviewer_verdict == "deferred_baseline_unavailable":
            continue
        if (
            kind in {"audit", "research"}
            and isinstance(notes, str)
            and len(notes.strip()) >= 100
            and not is_rubber_stamp(notes, strict=True)
        ):
            continue
        if task.get("status") in {"waived", "not_applicable"}:
            continue
        missing.append(f"{task_id}='unknown':missing_finalize_authority_fields")
    return missing


def _optional_finalize_status(task: dict[str, Any]) -> str:
    raw = task.get("status")
    return str(raw).strip().lower() if isinstance(raw, str) else ""


def _task_record_has_authority_payload(task: dict[str, Any]) -> bool:
    return any(
        task.get(field)
        for field in (
            "files_changed",
            "commands_run",
            "evidence_files",
            "sections_written",
            "evidence",
        )
    )


def _task_record_can_override_finalize(task: dict[str, Any]) -> bool:
    status = str(task.get("status") or "").strip().lower()
    if status in {"done", "waived", "not_applicable", "skipped"}:
        return True
    return _task_record_has_authority_payload(task)


_CHAIN_SHADOW_TERMINAL_STATUSES = frozenset(
    {"done", "completed", "skipped", "waived", "not_applicable"}
)


def _plan_relative_source(plan_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(plan_dir))
    except ValueError:
        return str(path)


def _decision_shadow_reason(decision: AuthorityDecision | None) -> str:
    if decision is None:
        return "no compatibility-adapter decision"
    reason = next(iter(decision.would_block_reasons), "")
    if reason:
        return reason
    raw = decision.diagnostics.get("reason")
    if isinstance(raw, str) and raw:
        return raw
    return decision.status.value


def _decision_shadow_sources(
    decision: AuthorityDecision | None,
    *,
    projection_sources: tuple[str, ...],
) -> str:
    sources: set[str] = set(projection_sources)
    if decision is not None:
        diagnostics = decision.diagnostics
        for key in ("source_path", "source"):
            value = diagnostics.get(key)
            if isinstance(value, str) and value:
                sources.add(value)
        raw_source_paths = diagnostics.get("source_paths")
        if isinstance(raw_source_paths, list):
            sources.update(str(item) for item in raw_source_paths if str(item))
        validation = diagnostics.get("authority_validation")
        if isinstance(validation, Mapping):
            value = validation.get("source_path")
            if isinstance(value, str) and value:
                sources.add(value)
        raw_projection_diagnostics = diagnostics.get("projection_diagnostics")
        if isinstance(raw_projection_diagnostics, list):
            for item in raw_projection_diagnostics:
                if not isinstance(item, Mapping):
                    continue
                value = item.get("source")
                if isinstance(value, str) and value:
                    sources.add(value)
    return ", ".join(sorted(sources)) or "accepted-attempt projection unavailable"


def _chain_completion_shadow_disagreements(
    task_records: list[dict[str, Any]],
    completed: set[str],
    decisions: Mapping[str, AuthorityDecision],
    *,
    source_by_task: Mapping[str, str],
    plan_dir: Path,
    chain_state: ChainState | None,
    completion_record: Mapping[str, Any] | None,
    default_source: str,
    default_source_kind: str,
) -> list[str]:
    """Name legacy/projection disagreement sources without granting authority."""

    projection = accepted_attempt_execution_projection(task_records, plan_dir=plan_dir)
    projection_sources = projection.source_paths if projection is not None else ()
    diagnostics: list[str] = []
    incomplete_task_sources: list[str] = []
    for task in task_records:
        task_id = str(task.get("task_id") or task.get("id") or "")
        if not task_id:
            continue
        status = _optional_finalize_status(task)
        if not status:
            continue
        label_source = source_by_task.get(task_id, default_source)
        label_kind = "batch overlay" if task_id in source_by_task else default_source_kind
        accepted = task_id in completed
        if not accepted:
            incomplete_task_sources.append(f"{task_id} from {label_source}")
        decision = decisions.get(task_id)
        authority_sources = _decision_shadow_sources(
            decision,
            projection_sources=projection_sources,
        )
        reason = _decision_shadow_reason(decision)
        if status in _CHAIN_SHADOW_TERMINAL_STATUSES and not accepted:
            diagnostics.append(
                f"chain_authority_shadow[{task_id}]: {label_kind} source "
                f"{label_source} status={status!r} disagrees with "
                "dispatch-grant/accepted-attempt authority "
                f"({authority_sources}): {reason}"
            )
        elif status not in _CHAIN_SHADOW_TERMINAL_STATUSES and accepted:
            diagnostics.append(
                f"chain_authority_shadow[{task_id}]: {label_kind} source "
                f"{label_source} status={status!r} disagrees with "
                "dispatch-grant/accepted-attempt authority "
                f"({authority_sources}): accepted dependency-closed attempt"
            )

    if completion_record is not None and incomplete_task_sources:
        label = str(completion_record.get("label") or "unknown")
        record_status = str(completion_record.get("status") or "").strip().lower()
        if record_status in _CHAIN_SHADOW_TERMINAL_STATUSES:
            source = f"chain_state.completed[{label}]"
            if chain_state is not None:
                source = f"{source}@current_milestone_index={chain_state.current_milestone_index}"
            diagnostics.append(
                f"chain_authority_shadow[{label}]: chain state source {source} "
                f"status={record_status!r} disagrees with task authority; "
                f"incomplete sources: {', '.join(sorted(incomplete_task_sources))}"
            )

    return sorted(set(diagnostics))


def _non_authoritative_task_reasons(
    task_records: list[dict[str, Any]],
    completed: set[str],
    decisions: dict[str, AuthorityDecision],
    *,
    source_by_task: Mapping[str, str] | None = None,
) -> list[str]:
    incomplete: list[str] = []
    for task in task_records:
        task_id = str(task.get("task_id") or task.get("id") or "?")
        if task_id in completed:
            continue
        source = (
            source_by_task.get(task_id, "finalize.json")
            if source_by_task is not None
            else None
        )
        decision = decisions.get(task_id)
        if decision is None:
            suffix = f":source={source}" if source else ""
            incomplete.append(f"{task_id}={task.get('status')!r}{suffix}")
            continue
        reason = next(iter(decision.would_block_reasons), decision.status.value)
        suffix = f":source={source}" if source else ""
        incomplete.append(f"{task_id}={decision.status.value!r}:{reason}{suffix}")
    return incomplete


def _mark_blocked_execute_as_executed(plan_dir: Path) -> None:
    from arnold_pipelines.megaplan._core.state import write_plan_state

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


def _has_unresolved_execute_user_actions(plan_dir: Path) -> tuple[bool, str | None]:
    try:
        finalize_payload = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False, None
    if not isinstance(finalize_payload, dict):
        return False, None
    user_actions = finalize_payload.get("user_actions")
    if not isinstance(user_actions, list) or not user_actions:
        return False, None

    try:
        state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        state_payload = {}
    if not isinstance(state_payload, dict):
        state_payload = {}

    resolutions = effective_user_action_resolutions(plan_dir, state_payload)
    for action in user_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id:
            continue
        status = action_resolution_status(action, resolutions)
        if status.get("resolution") in {"satisfied", "accepted_blocked", "waived"}:
            continue
        return True, action_id
    return False, None


def _mark_plan_completed_by_chain(
    root: Path,
    plan_name: str,
    *,
    milestone_label: str,
    completion_reason: str,
    writer,
    state: "ChainState | None" = None,
) -> None:
    """Mirror an authoritative chain-level milestone completion into plan state.

    T18 — In atomic/enforce (fail-closed) mode the plan-done projection
    requires an accepted acceptance transaction for this milestone.  Without
    one the projection is never written (fail-closed: plan state must not
    signal completion authority that was not accepted).
    """

    from arnold_pipelines.megaplan._core.state import write_plan_state
    from arnold_pipelines.megaplan.observability.events import EventKind, emit as emit_event
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        is_fail_closed_mode,
        normalize_contract_mode,
    )

    # ── T18: atomic/enforce gate ─────────────────────────────────────────
    if state is not None:
        mode = normalize_contract_mode(state.completion_contract_mode)
        if is_fail_closed_mode(mode):
            if not state.has_acceptance_receipt(milestone_label):
                writer(
                    f"[chain] plan-done marker blocked for {plan_name} "
                    f"milestone={milestone_label} in atomic mode: "
                    f"no accepted acceptance transaction for this milestone "
                    f"(fail-closed — plan-done projection requires accepted evidence)\n"
                )
                return

    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        return

    def _patch_completed(current: dict[str, Any]) -> bool:
        current["current_state"] = STATE_DONE
        current.pop("active_step", None)
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        meta = current.setdefault("meta", {})
        if not isinstance(meta, dict):
            current["meta"] = meta = {}
        meta["chain_completion"] = {
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "milestone_label": milestone_label,
            "reason": completion_reason,
        }
        return True

    try:
        written_state = write_plan_state(
            plan_dir,
            mode="patch-many",
            patch={},
            mutation=_patch_completed,
        )
    except Exception as error:
        writer(
            f"[chain] warning: failed to reconcile completed plan {plan_name}: {error}\n"
        )
        return
    try:
        emit_event(
            EventKind.PLAN_FINISHED,
            plan_dir=plan_dir,
            payload={
                "state": written_state,
                "source": "chain_completion",
                "milestone_label": milestone_label,
                "reason": completion_reason,
            },
        )
    except Exception as error:
        writer(
            f"[chain] warning: failed to emit plan_finished for {plan_name}: {error}\n"
        )


def _mark_plan_missing_base_ref(root: Path, plan_name: str | None, *, failure: dict[str, Any]) -> None:
    if not plan_name:
        return
    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        return
    state_path = plan_dir / "state.json"
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return
    if not isinstance(raw, dict):
        return
    resume_cursor = raw.get("resume_cursor")
    if not isinstance(resume_cursor, dict):
        resume_cursor = {}
    resume_cursor["phase"] = "recover-base-branch"
    resume_cursor["retry_strategy"] = "manual_review"
    raw["resume_cursor"] = resume_cursor
    raw["current_state"] = "manual_review"
    raw["latest_failure"] = {
        "kind": "missing_base_ref",
        "message": str(failure.get("message") or ""),
        "phase": "chain",
        "recorded_at": str(failure.get("recorded_at") or ""),
    }
    atomic_write_json(state_path, raw)


def _handle_missing_base_ref(
    root: Path,
    spec_path: Path,
    state: ChainState,
    *,
    spec: ChainSpec,
    events: list[dict[str, Any]],
    milestone_label: str | None,
    error: CliError,
) -> dict[str, Any]:
    last_known_sha = None
    if isinstance(error.extra, dict):
        raw_sha = error.extra.get("last_known_sha")
        if isinstance(raw_sha, str) and raw_sha:
            last_known_sha = raw_sha
    if not last_known_sha:
        last_known_sha = state.target_base_ref
    failure = {
        "base_branch": spec.base_branch,
        "last_known_sha": last_known_sha,
        "message": error.message,
        "milestone": milestone_label,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "retry_strategy": "manual_review",
    }
    state.last_state = "missing_base_ref"
    state.metadata["missing_base_ref"] = failure
    _mark_plan_missing_base_ref(root, state.current_plan_name, failure=failure)
    chain_spec.save_chain_state(spec_path, state)
    events.append({"msg": error.message, "state": "missing_base_ref", "base_branch": spec.base_branch})
    return _result(
        "stopped",
        state,
        events,
        spec=spec,
        reason=error.message,
    )


def _recover_blocked_execute_if_tasks_done(
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
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
    has_unresolved_user_actions, action_id = _has_unresolved_execute_user_actions(plan_dir)
    if has_unresolved_user_actions:
        reason = (
            f"unresolved user action {action_id}"
            if action_id
            else "unresolved execute user action"
        )
        writer(
            f"[chain] execute result=blocked for {outcome.plan}; treating as real block: {reason}\n"
        )
        return False

    all_done, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    if not all_done:
        if _recover_stale_prerequisite_block(
            root,
            spec_path,
            spec,
            outcome,
            plan_dir=plan_dir,
            reason=reason,
            writer=writer,
        ):
            return True
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


_PREREQUISITE_BLOCK_TOKENS = (
    "blocked_by_prereq",
    "prerequisite",
    "launch gate",
    "launch precondition",
    "completion manifest",
    "proof-map",
    "proof map",
    "chain_completed",
)


def _looks_like_prerequisite_block(
    outcome: DriverOutcome,
    *,
    extra_text: str = "",
) -> bool:
    if outcome.status not in {
        "blocked",
        "worker_blocked",
        "awaiting_human",
        "human_required",
    }:
        return False
    text = " ".join(
        str(part)
        for part in [
            outcome.reason,
            outcome.last_phase,
            *outcome.blocking_reasons,
            extra_text,
        ]
        if part
    ).lower()
    return any(token in text for token in _PREREQUISITE_BLOCK_TOKENS)


def _plan_latest_failure_text(plan_dir: Path) -> str:
    try:
        raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(raw, dict):
        return ""
    latest_failure = raw.get("latest_failure")
    parts: list[str] = []
    if isinstance(latest_failure, dict):
        for key in ("kind", "message", "suggested_action", "phase"):
            value = latest_failure.get(key)
            if isinstance(value, str):
                parts.append(value)
        metadata = latest_failure.get("metadata")
        if isinstance(metadata, dict):
            blocking_reasons = metadata.get("blocking_reasons")
            if isinstance(blocking_reasons, list):
                parts.extend(str(item) for item in blocking_reasons if item)
    resume_cursor = raw.get("resume_cursor")
    if isinstance(resume_cursor, dict):
        parts.extend(str(value) for value in resume_cursor.values() if value)
    return " ".join(parts)


def _clear_execute_task_attempt_fields(task: dict[str, Any]) -> None:
    task["status"] = "pending"
    task["executor_notes"] = ""
    task["files_changed"] = []
    task["commands_run"] = []
    task["evidence_files"] = []
    task["reviewer_verdict"] = ""
    task.pop("recorded_invocation_id", None)


def _reset_stale_prerequisite_blocked_tasks(
    plan_dir: Path,
    outcome: DriverOutcome,
) -> list[str]:
    finalize_path = plan_dir / "finalize.json"
    try:
        finalize_data = json.loads(finalize_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(finalize_data, dict):
        return []
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        return []
    outcome_text = " ".join([outcome.reason, *outcome.blocking_reasons]).lower()
    reset_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("status") != "blocked":
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        task_text = " ".join(
            str(task.get(key) or "")
            for key in ("id", "description", "executor_notes", "reviewer_verdict")
        ).lower()
        if task_id.lower() not in outcome_text and not any(
            token in task_text for token in _PREREQUISITE_BLOCK_TOKENS
        ):
            continue
        _clear_execute_task_attempt_fields(task)
        reset_ids.append(task_id)
    if reset_ids:
        atomic_write_json(finalize_path, finalize_data)
    return sorted(reset_ids)


def _recover_stale_prerequisite_block(
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    outcome: DriverOutcome,
    *,
    plan_dir: Path,
    reason: str,
    writer,
) -> bool:
    """Retry a blocked execute when current chain preconditions now pass.

    Executor workers can block from stale prerequisite evidence captured in an
    earlier plan/gate/audit artifact. The chain has stronger current authority:
    its launch preconditions and completion manifests. If those pass now, clear
    the stale blocked attempt and let execute re-run with an explicit audit note.
    """

    latest_failure_text = _plan_latest_failure_text(plan_dir)
    if not _looks_like_prerequisite_block(outcome, extra_text=latest_failure_text):
        return False
    if not spec.launch_preconditions:
        return False
    try:
        chain_spec.validate_launch_preconditions(spec, root, spec_path)
    except CliError as exc:
        writer(
            "[chain] prerequisite block revalidation did not pass; "
            f"keeping real block: {exc}\n"
        )
        return False

    reset_ids = _reset_stale_prerequisite_blocked_tasks(plan_dir, outcome)
    audit = {
        "schema": "arnold.megaplan.chain_precondition_revalidation.v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "plan": outcome.plan,
        "outcome_status": outcome.status,
        "outcome_reason": outcome.reason,
        "blocking_reasons": list(outcome.blocking_reasons),
        "chain_spec_path": str(spec_path),
        "reset_task_ids": reset_ids,
        "result": "launch_preconditions_satisfied_retrying_execute",
    }
    atomic_write_json(plan_dir / "chain_precondition_revalidation.json", audit)
    state_path = plan_dir / "state.json"
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        state_payload = {}
    if not isinstance(state_payload, dict):
        state_payload = {}
    state_payload["current_state"] = STATE_FINALIZED
    state_payload.pop("latest_failure", None)
    state_payload.pop("resume_cursor", None)
    state_payload.pop("active_step", None)
    meta = state_payload.setdefault("meta", {})
    if isinstance(meta, dict):
        entries = meta.setdefault("chain_precondition_revalidations", [])
        if isinstance(entries, list):
            entries.append(audit)
    from arnold_pipelines.megaplan._core.state import write_plan_state

    def _patch_revalidated_block(current: dict[str, Any]) -> bool:
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        current.pop("active_step", None)
        meta = current.setdefault("meta", {})
        if isinstance(meta, dict):
            entries = meta.setdefault("chain_precondition_revalidations", [])
            if isinstance(entries, list):
                entries.append(audit)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_FINALIZED},
        mutation=_patch_revalidated_block,
    )
    writer(
        f"[chain] execute result=blocked for {outcome.plan}, but current launch "
        "preconditions now pass; cleared stale prerequisite block"
    )
    if reset_ids:
        writer(f" for tasks {', '.join(reset_ids)}")
    writer(f" ({reason}); retrying execute\n")
    return True


def _rearm_stale_execute_authority_divergence(
    plan_dir: Path,
    *,
    writer,
) -> bool:
    """Rearm a stale execute-authority block only after current corroboration.

    This is admission recovery for a repaired evidence reader, not a bypass:
    a live completion guard must now corroborate the whole finalized task
    universe before the old authority-divergence marker is cleared.
    """
    state_path = plan_dir / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("current_state") != STATE_BLOCKED or payload.get("active_step"):
        return False
    failure = payload.get("latest_failure")
    if not isinstance(failure, dict):
        return False
    if failure.get("kind") != "authority_divergence" or failure.get("phase") not in {None, "execute"}:
        return False
    message = failure.get("message")
    if not isinstance(message, str) or "execute terminal success lacks corroborated task completion" not in message:
        return False
    authoritative, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    if not authoritative:
        return False

    from arnold_pipelines.megaplan._core.state import write_plan_state

    audit = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reason": "chain admission revalidated stale execute terminal authority divergence",
        "authority_reason": reason,
    }

    def _patch_rearmed_authority_block(current: dict[str, Any]) -> bool:
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        current.pop("active_step", None)
        meta = current.setdefault("meta", {})
        if isinstance(meta, dict):
            entries = meta.setdefault("authority_divergence_recoveries", [])
            if isinstance(entries, list):
                entries.append(audit)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_EXECUTED},
        mutation=_patch_rearmed_authority_block,
    )
    writer(
        "[chain] current execute authority now corroborates terminal finalize "
        "evidence; cleared stale authority-divergence block\n"
    )
    return True


def _rearm_fresh_session_execute_block(
    plan_dir: Path,
    *,
    writer,
) -> bool:
    """Reset a blocked execute plan back to finalized for a fresh-session retry.

    ``megaplan auto`` records execute quality/session failures as
    ``current_state=blocked`` with ``resume_cursor={phase: execute,
    retry_strategy: fresh_session}``. A later chain relaunch is the explicit
    signal to honor that cursor and try execute again, not to preserve the
    stale blocked state forever.
    """

    state_path = plan_dir / "state.json"
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(state_payload, dict):
        return False
    if state_payload.get("current_state") != STATE_BLOCKED:
        return False
    if state_payload.get("active_step"):
        return False
    resume_cursor = state_payload.get("resume_cursor")
    if not isinstance(resume_cursor, dict):
        return False
    if resume_cursor.get("phase") != "execute":
        return False
    if resume_cursor.get("retry_strategy") != "fresh_session":
        return False
    latest_failure = state_payload.get("latest_failure")
    if isinstance(latest_failure, dict):
        failure_phase = latest_failure.get("phase")
        failure_kind = latest_failure.get("kind")
        if isinstance(failure_phase, str) and failure_phase and failure_phase != "execute":
            return False
        if isinstance(failure_kind, str) and failure_kind not in {
            "execution_blocked",
            "tasks_blocked",
            "external_error",
        }:
            return False
    from arnold_pipelines.megaplan._core.state import write_plan_state

    recovery_event = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reason": "chain relaunch honored execute fresh_session resume cursor",
    }

    def _patch_blocked_execute(current: dict[str, Any]) -> bool:
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        current.pop("active_step", None)
        meta = current.setdefault("meta", {})
        if isinstance(meta, dict):
            entries = meta.setdefault("fresh_session_execute_recoveries", [])
            if isinstance(entries, list):
                entries.append(recovery_event)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_FINALIZED},
        mutation=_patch_blocked_execute,
    )
    writer(
        "[chain] execute block recorded a fresh-session retry; reset blocked plan "
        "back to finalized so execute can re-run\n"
    )
    return True


def _rearm_stale_terminal_execute_cursor_mismatch(
    plan_dir: Path,
    *,
    writer,
) -> bool:
    """Clear only a stale execute->review cursor wrapper after live authority."""
    state_path = plan_dir / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("current_state") != STATE_BLOCKED or payload.get("active_step"):
        return False
    failure = payload.get("latest_failure")
    if not isinstance(failure, dict):
        return False
    if failure.get("kind") != "workflow_cursor_mismatch" or failure.get("phase") != "execute":
        return False
    message = failure.get("message")
    if not isinstance(message, str) or (
        "workflow cursor from last_step expects one of [review]" not in message
        or "control projection offered [execute]" not in message
    ):
        return False
    authoritative, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    if not authoritative:
        return False

    from arnold_pipelines.megaplan._core.state import write_plan_state

    audit = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reason": "chain admission cleared stale execute-to-review cursor mismatch",
        "authority_reason": reason,
    }

    def _patch_rearmed_cursor(current: dict[str, Any]) -> bool:
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        current.pop("active_step", None)
        meta = current.setdefault("meta", {})
        if isinstance(meta, dict):
            entries = meta.setdefault("terminal_cursor_recoveries", [])
            if isinstance(entries, list):
                entries.append(audit)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_EXECUTED},
        mutation=_patch_rearmed_cursor,
    )
    writer(
        "[chain] terminal execute authority now passes; cleared stale "
        "execute-to-review cursor mismatch\n"
    )
    return True


def _rearm_stale_incomplete_execute_cursor_mismatch(
    plan_dir: Path,
    *,
    writer,
) -> bool:
    """Reopen the specific cursor failure invalidated by current projection rules.

    A partial or blocked execute intentionally leaves the plan in ``finalized``
    so pending batches can be dispatched again.  Older workflow-backed drivers
    incorrectly promoted that incomplete history record into an execute->review
    cursor and then persisted ``workflow_cursor_mismatch``.  Once that record
    is present, ordinary chain admission stops before the corrected driver can
    observe it.  Reopen only the mechanically identifiable stale shape; a
    genuine cursor mismatch (a different cursor source, route, or outcome)
    remains blocked for repair.
    """

    state_path = plan_dir / "state.json"
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(state_payload, dict):
        return False
    if state_payload.get("current_state") != STATE_BLOCKED or state_payload.get("active_step"):
        return False
    latest_failure = state_payload.get("latest_failure")
    resume_cursor = state_payload.get("resume_cursor")
    if not isinstance(latest_failure, dict) or not isinstance(resume_cursor, dict):
        return False
    if latest_failure.get("kind") != "workflow_cursor_mismatch":
        return False
    if latest_failure.get("phase") != "execute":
        return False
    if resume_cursor.get("phase") != "execute":
        return False
    if resume_cursor.get("retry_strategy") != "repair_workflow_projection":
        return False
    metadata = latest_failure.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("observed_phase_source") != "last_step":
        return False
    message = latest_failure.get("message")
    if not isinstance(message, str) or "expects one of [review]" not in message or "offered [execute]" not in message:
        return False
    history = state_payload.get("history")
    last_entry = history[-1] if isinstance(history, list) and history else None
    if not isinstance(last_entry, dict):
        return False
    if last_entry.get("step") != "execute" or last_entry.get("result") not in {"blocked", "partial"}:
        return False

    from arnold_pipelines.megaplan._core.state import write_plan_state

    recovery_event = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reason": "chain relaunch cleared stale incomplete-execute workflow cursor mismatch",
        "history_result": last_entry.get("result"),
    }

    def _patch_stale_cursor(current: dict[str, Any]) -> bool:
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        current.pop("active_step", None)
        meta = current.setdefault("meta", {})
        if isinstance(meta, dict):
            entries = meta.setdefault("workflow_cursor_recoveries", [])
            if isinstance(entries, list):
                entries.append(recovery_event)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_FINALIZED},
        mutation=_patch_stale_cursor,
    )
    writer(
        "[chain] cleared stale incomplete-execute workflow cursor mismatch; "
        "reset plan to finalized so pending execute work can resume\n"
    )
    return True


def _drive_plan_with_blocked_execute_recovery(
    root: Path,
    spec_path: Path,
    plan: str,
    spec: ChainSpec,
    *,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    writer,
) -> DriverOutcome:
    _recover_failed_plan_before_drive(root, plan, writer=writer)
    outcome = _drive_plan(
        root,
        plan,
        spec,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )
    if not _recover_blocked_execute_if_tasks_done(
        root,
        spec_path,
        spec,
        outcome,
        writer=writer,
    ):
        return outcome
    return _drive_plan(
        root,
        plan,
        spec,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )


def _recover_failed_plan_before_drive(root: Path, plan: str, *, writer) -> None:
    """Let the plan recovery entrypoint clear failed state before chain auto-drive."""

    if _plan_current_state_from_payload(root, plan) != "failed":
        return
    writer(f"[chain] plan {plan} is failed; invoking resume before auto-drive\n")
    _run_command(
        root,
        [
            sys.executable,
            "-P",
            "-m",
            "arnold_pipelines.megaplan",
            "resume",
            "--plan",
            plan,
        ],
        writer=writer,
        error_code="plan_resume_failed",
    )


def _milestone_retry_cap(milestone: "MilestoneSpec | None", spec: ChainSpec) -> int:
    """Per-milestone FRESH-reinit cap.

    Default ``DEFAULT_MILESTONE_RETRY_CAP`` (2); CAPPED at
    ``APEX_EXTREME_RETRY_CAP`` (1) for apex profile or extreme robustness
    milestones to bound the cost of the most-expensive nodes.
    """
    profile = (milestone.profile if milestone else None) or None
    robustness = (
        milestone.robustness if milestone and milestone.robustness else spec.robustness
    ) or "standard"
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
    except (
        CliError,
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
    ):
        return None
    if not isinstance(raw, dict):
        return None
    current_state = raw.get("current_state")
    if isinstance(current_state, str) and current_state in RESUMABLE_RETRY_STATES:
        return current_state
    return None


def _awaiting_human_can_retry(root: Path, plan: str | None) -> bool:
    """Return True when an awaiting-human plan is stale and should retry."""

    if not plan:
        return False
    try:
        plan_dir = resolve_plan_dir(root, plan)
        raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        finalize = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    except (
        CliError,
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
    ):
        return False
    if not isinstance(raw, dict):
        return False
    current_state = raw.get("current_state")
    if current_state not in {"awaiting_human", "finalized"}:
        return False
    if not isinstance(finalize, dict):
        return False
    user_actions = finalize.get("user_actions")
    if not isinstance(user_actions, list) or not user_actions:
        return False
    resolutions = effective_user_action_resolutions(plan_dir, raw)
    saw_retryable = False
    for action in user_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id:
            continue
        resolution = resolutions.get(action_id)
        if not isinstance(resolution, dict):
            return False
        state = resolution.get("state") or resolution.get("resolution")
        if state == "satisfied":
            saw_retryable = True
            continue
        if state in {"accepted_blocked", "waived"}:
            saw_retryable = True
            continue
        return False
    return saw_retryable


def _plan_current_state_from_payload(root: Path, plan: str | None) -> str | None:
    raw = _plan_state_payload_from_name(root, plan)
    current_state = raw.get("current_state")
    if not isinstance(current_state, str):
        return None
    if current_state in {STATE_FINALIZED, STATE_EXECUTED, STATE_DONE} and _plan_has_live_active_step(raw):
        active_step = raw.get("active_step")
        active_phase = (
            active_step.get("phase") or active_step.get("step")
            if isinstance(active_step, Mapping)
            else None
        )
        if isinstance(active_phase, str) and active_phase.strip():
            return active_phase.strip()
    return current_state


def _plan_state_payload_from_name(root: Path, plan: str | None) -> dict[str, Any]:
    if not plan:
        return {}
    try:
        plan_dir = resolve_plan_dir(root, plan)
        from arnold_pipelines.megaplan._core.state import load_plan_from_dir

        _, raw = load_plan_from_dir(plan_dir)
    except (
        CliError,
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
    ):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _plan_has_live_active_step(plan_state: Mapping[str, Any]) -> bool:
    active_step = plan_state.get("active_step")
    if not isinstance(active_step, Mapping):
        return False
    return bool(
        active_step.get("phase")
        or active_step.get("worker_pid")
        or active_step.get("pid")
        or active_step.get("session_id")
    )


def _blocked_plan_replay_would_be_redundant(
    state: ChainState,
    *,
    plan_state: Mapping[str, Any],
) -> bool:
    current_state = plan_state.get("current_state")
    if not isinstance(current_state, str):
        return False
    return (
        state.last_state == STATE_BLOCKED
        and current_state == STATE_BLOCKED
        and not _plan_has_live_active_step(plan_state)
    )


def _chain_policy_milestone_label(plan_state: dict[str, Any]) -> str | None:
    meta = plan_state.get("meta")
    if not isinstance(meta, dict):
        return None
    policy = meta.get("chain_policy")
    if not isinstance(policy, dict):
        return None
    label = policy.get("milestone_label")
    return label if isinstance(label, str) and label else None


def _record_pr_number(record: dict[str, Any] | None) -> int | None:
    if not isinstance(record, dict):
        return None
    raw = record.get("pr_number")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _completed_prefix_index(spec: ChainSpec, completed_labels: set[str]) -> int:
    for index, milestone in enumerate(spec.milestones):
        if milestone.label not in completed_labels:
            return index
    return len(spec.milestones)


def _append_reconciliation_audit(
    state: ChainState,
    *,
    plan_name: str | None,
    plan_state: dict[str, Any],
    pr_number: int | None,
    pr_state: str | None,
) -> None:
    current_state = plan_state.get("current_state")
    if not isinstance(current_state, str):
        current_state = None
    state.metadata["ground_truth_reconciliation"] = {
        "reconciled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plan": plan_name,
        "current_state": current_state,
        "latest_failure": plan_state.get("latest_failure"),
        "last_gate": plan_state.get("last_gate"),
        "active_step": plan_state.get("active_step"),
        "pr_number": pr_number,
        "pr_state": pr_state,
    }


def _clear_impossible_terminal_last_state(
    state: ChainState,
    *,
    writer,
    reason: str,
) -> None:
    """Clear a terminal-looking chain state when an active plan still exists."""

    if state.last_state not in {"done", "complete"}:
        return
    if not state.current_plan_name:
        return
    writer(
        f"[chain] cleared stale terminal last_state for {state.current_plan_name}: "
        f"{state.last_state} -> unknown ({reason})\n"
    )
    state.last_state = "unknown"


def _mark_chain_after_milestone_advance(
    spec: ChainSpec,
    state: ChainState,
    *,
    next_index: int,
) -> None:
    state.current_milestone_index = next_index
    state.current_plan_name = None
    state.last_state = "done" if next_index >= len(spec.milestones) else "between_milestones"
    state.pr_number = None
    state.pr_state = None


def _reconcile_chain_from_ground_truth(
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    *,
    writer,
    push_enabled: bool = True,
) -> ChainState:
    """Derive the chain cursor from plan state.json and live GitHub PR state."""

    from arnold_pipelines.megaplan.chain.execution_binding import (
        assert_execution_binding,
    )

    assert_execution_binding(
        spec_path,
        state,
        operation="chain reconciliation",
        allow_unbound_new=True,
    )

    # T17 — In atomic/enforce mode reconciliation must NEVER derive completion
    # authority (cursor advancement, ``last_state = "done"``, completed-record
    # rebuild from live PR state, cursor/last_state sync from plan state.json)
    # from a ground-truth projection. Only an accepted acceptance transaction
    # committed through the CAS-backed helper can advance the completion cursor.
    # We short-circuit here so the projection cannot masquerade as authority,
    # while still persisting an audit trail of the reconciliation attempt.
    fail_closed, fc_reason = _reconciliation_fail_closed(state)
    if fail_closed:
        writer(
            f"[chain] reconciliation skipped in atomic mode for "
            f"{state.current_plan_name or 'current milestone'}: {fc_reason}\n"
        )
        _append_reconciliation_audit(
            state,
            plan_name=state.current_plan_name,
            plan_state={},
            pr_number=state.pr_number,
            pr_state=state.pr_state,
        )
        chain_spec.save_chain_state(spec_path, state)
        return state

    labels_to_index = {
        milestone.label: index for index, milestone in enumerate(spec.milestones)
    }
    completed_by_label = _completed_records_by_label(state)
    reconciled_completed: list[dict[str, Any]] = []
    removed_completed: dict[str, dict[str, Any]] = {}
    current_plan_from_removed_completion = False

    for milestone in spec.milestones:
        record = completed_by_label.get(milestone.label)
        if not isinstance(record, dict):
            continue
        record = dict(record)
        pr_number = _record_pr_number(record)
        if push_enabled and milestone.branch:
            if pr_number is None:
                writer(
                    f"[chain] completed record for {milestone.label} is not "
                    "authoritative yet: branch milestone is missing PR context\n"
                )
                removed_completed[milestone.label] = dict(record)
                continue
            live_pr_state = _pr_state(root, pr_number, writer=writer)
            if record.get("pr_state") != live_pr_state:
                writer(
                    f"[chain] reconciled completed PR state for {milestone.label} "
                    f"#{pr_number}: {record.get('pr_state') or 'unknown'} -> "
                    f"{live_pr_state}\n"
                )
            record["pr_state"] = live_pr_state
            if live_pr_state != "merged":
                writer(
                    f"[chain] completed record for {milestone.label} is not "
                    f"authoritative yet: PR #{pr_number} state={live_pr_state}\n"
                )
                removed = dict(record)
                removed["pr_state"] = live_pr_state
                removed_completed[milestone.label] = removed
                continue
        reconciled_completed.append(record)

    if reconciled_completed != state.completed:
        state.completed = reconciled_completed

    completed_labels = {
        record.get("label")
        for record in state.completed
        if isinstance(record, dict) and isinstance(record.get("label"), str)
    }
    first_incomplete = _completed_prefix_index(spec, completed_labels)
    if state.current_milestone_index < first_incomplete:
        writer(
            f"[chain] reconciled cursor index: {state.current_milestone_index} "
            f"-> {first_incomplete} from completed milestones\n"
        )
        state.current_milestone_index = first_incomplete
        if first_incomplete >= len(spec.milestones):
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None
            state.last_state = "done"
    elif state.current_milestone_index > first_incomplete:
        writer(
            f"[chain] reconciled cursor index: {state.current_milestone_index} "
            f"-> {first_incomplete} from completed milestones\n"
        )
        state.current_milestone_index = first_incomplete
        if first_incomplete < len(spec.milestones):
            milestone = spec.milestones[first_incomplete]
            removed = removed_completed.get(milestone.label)
            plan = removed.get("plan") if isinstance(removed, dict) else None
            state.current_plan_name = plan if isinstance(plan, str) and plan else None
            state.pr_number = _record_pr_number(removed)
            pr_state = removed.get("pr_state") if isinstance(removed, dict) else None
            state.pr_state = pr_state if isinstance(pr_state, str) else None
            state.last_state = "authority_divergence"
            current_plan_from_removed_completion = state.current_plan_name is not None
        else:
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None

    plan_name = state.current_plan_name
    plan_state = _plan_state_payload_from_name(root, plan_name)
    if plan_state:
        label = _chain_policy_milestone_label(plan_state)
        plan_index = labels_to_index.get(label) if label is not None else None
        if plan_index is not None and state.current_milestone_index != plan_index:
            writer(
                f"[chain] reconciled cursor index from plan {plan_name}: "
                f"{state.current_milestone_index} -> {plan_index}\n"
            )
            state.current_milestone_index = plan_index
        current_state = plan_state.get("current_state")
        preserve_pr_cursor = (
            state.last_state in {STATE_AWAITING_PR_MERGE, "pr_closed"}
            and state.pr_number is not None
        )
        if (
            isinstance(current_state, str)
            and state.last_state != current_state
            and not current_plan_from_removed_completion
            and not preserve_pr_cursor
        ):
            writer(
                f"[chain] synced last_state for {plan_name}: "
                f"{state.last_state or 'unknown'} -> {current_state}\n"
            )
            state.last_state = current_state
    elif plan_name:
        _clear_impossible_terminal_last_state(
            state,
            writer=writer,
            reason="active plan state unavailable during ground-truth reconciliation",
        )

    active_index = state.current_milestone_index
    active_milestone = (
        spec.milestones[active_index]
        if 0 <= active_index < len(spec.milestones)
        else None
    )
    active_uses_pr = bool(
        push_enabled and active_milestone is not None and active_milestone.branch
    )
    live_active_pr_state: str | None = None
    if (
        active_uses_pr
        and state.pr_number is not None
        and state.last_state != "pr_closed"
    ):
        live_active_pr_state = _pr_state(root, state.pr_number, writer=writer)
        if state.pr_state == "merged" and live_active_pr_state != "merged":
            writer(
                f"[chain] preserved recorded merged PR state for "
                f"{active_milestone.label if active_milestone else 'milestone'} "
                f"#{state.pr_number} despite live state {live_active_pr_state}\n"
            )
            live_active_pr_state = "merged"
        elif state.pr_state != live_active_pr_state:
            writer(
                f"[chain] reconciled live PR state for "
                f"{active_milestone.label if active_milestone else 'milestone'} "
                f"#{state.pr_number}: {state.pr_state or 'unknown'} -> "
                f"{live_active_pr_state}\n"
            )
        state.pr_state = live_active_pr_state

    current_plan_state = plan_state.get("current_state") if plan_state else None
    if (
        bool(plan_name)
        and active_milestone is not None
        and current_plan_state == STATE_DONE
        and active_milestone.label not in completed_labels
        and (
            not active_uses_pr
            or (state.pr_number is not None and live_active_pr_state == "merged")
        )
    ):
        appended, reason = _append_reconciled_completed_record_with_guard(
            root,
            state,
            plan_name=plan_name,
            milestone=active_milestone,
            pr_number=state.pr_number if active_uses_pr else None,
            pr_state="merged" if active_uses_pr else None,
            completion_reason="terminal plan state reconciled from ground truth",
            writer=writer,
        )
        if appended:
            completed_labels.add(active_milestone.label)
        else:
            writer(
                f"[chain] reconciliation completion guard blocked "
                f"{active_milestone.label}: {reason}\n"
            )

    reviewed_finalized_plan = (
        bool(plan_name)
        and bool(plan_state)
        and _finalized_plan_has_successful_review(plan_state)
    )
    if reviewed_finalized_plan and active_milestone is not None:
        if active_uses_pr and state.pr_number is not None:
            if live_active_pr_state == "open" and state.last_state != STATE_AWAITING_PR_MERGE:
                writer(
                    f"[chain] plan {plan_name} is finalized with successful review but PR "
                    f"#{state.pr_number} is open; waiting for merge\n"
                )
                state.last_state = STATE_AWAITING_PR_MERGE
            elif (
                live_active_pr_state == "merged"
                and active_milestone.label not in completed_labels
            ):
                appended, reason = _append_reconciled_completed_record_with_guard(
                    root,
                    state,
                    plan_name=plan_name,
                    milestone=active_milestone,
                    pr_number=state.pr_number,
                    pr_state="merged",
                    completion_reason="reviewed finalized plan with merged PR",
                    writer=writer,
                )
                if appended:
                    completed_labels.add(active_milestone.label)
                else:
                    writer(
                        f"[chain] reconciliation completion guard blocked "
                        f"{active_milestone.label}: {reason}\n"
                    )
        elif not active_uses_pr and active_milestone.label not in completed_labels:
            appended, reason = _append_reconciled_completed_record_with_guard(
                root,
                state,
                plan_name=plan_name,
                milestone=active_milestone,
                pr_number=None,
                pr_state=None,
                completion_reason="reviewed finalized local plan",
                writer=writer,
            )
            if appended:
                completed_labels.add(active_milestone.label)
            else:
                writer(
                    f"[chain] reconciliation completion guard blocked "
                    f"{active_milestone.label}: {reason}\n"
                )
    if (
        active_uses_pr
        and state.pr_number is not None
        and current_plan_state == STATE_DONE
        and live_active_pr_state == "open"
        and state.last_state != STATE_AWAITING_PR_MERGE
    ):
        writer(
            f"[chain] plan {plan_name} is {current_plan_state} but PR "
            f"#{state.pr_number} is open; waiting for merge\n"
        )
        state.last_state = STATE_AWAITING_PR_MERGE

    if active_milestone is not None and active_milestone.label in completed_labels:
        next_index = _completed_prefix_index(spec, completed_labels)
        if next_index != state.current_milestone_index:
            writer(
                f"[chain] reconciled cursor past completed milestone "
                f"{active_milestone.label}: {state.current_milestone_index} "
                f"-> {next_index}\n"
            )
            state.current_milestone_index = next_index
            state.current_plan_name = None
            state.pr_number = None
            state.pr_state = None
            if next_index >= len(spec.milestones):
                state.last_state = "done"

    _append_reconciliation_audit(
        state,
        plan_name=plan_name,
        plan_state=plan_state,
        pr_number=state.pr_number,
        pr_state=state.pr_state,
    )
    chain_spec.save_chain_state(spec_path, state)
    return state


def _sync_chain_last_state_from_plan(
    root: Path,
    spec_path: Path,
    state: ChainState,
    *,
    writer,
) -> ChainState:
    """Refresh chain.last_state from the current plan's authoritative state.json."""

    plan_name = state.current_plan_name
    if not plan_name:
        return state
    plan_state = _plan_current_state_from_payload(root, plan_name)
    if not plan_state:
        previous = state.last_state
        _clear_impossible_terminal_last_state(
            state,
            writer=writer,
            reason="active plan state unavailable while syncing chain last_state",
        )
        if state.last_state != previous:
            chain_spec.save_chain_state(spec_path, state)
        return state
    if plan_state == state.last_state:
        return state
    previous = state.last_state
    state.last_state = plan_state
    writer(
        f"[chain] synced last_state for {plan_name}: "
        f"{previous or 'unknown'} -> {plan_state}\n"
    )
    chain_spec.save_chain_state(spec_path, state)
    return state


def _record_chain_last_state_after_plan_run(
    root: Path,
    spec_path: Path,
    state: ChainState,
    outcome: DriverOutcome,
    *,
    writer,
) -> ChainState:
    """Persist the chain cursor, then reconcile it from live plan state.json."""

    state.last_state = outcome.status
    chain_spec.save_chain_state(spec_path, state)
    return _sync_chain_last_state_from_plan(root, spec_path, state, writer=writer)


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

    from arnold_pipelines.megaplan.workers import _is_agent_available

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
        current = state.profile_bumps.get(label) or (
            milestone.profile if milestone else None
        )
        nxt, bumped = chain_spec._bump_one_tier(current, PROFILE_BUMP_ORDER)
        if not bumped:
            writer(
                f"[chain] {label}: bump_profile requested but already at top tier "
                f"({current or 'apex'}); no tier above apex — stopping\n"
            )
            return "stop"
        state.profile_bumps[label] = nxt or ""
        # Couple a depth bump so a harder retry also thinks deeper.
        cur_depth = state.depth_bumps.get(label) or (
            milestone.depth if milestone else None
        )
        d_next, d_bumped = chain_spec._bump_one_tier(cur_depth, DEPTH_BUMP_ORDER)
        if d_bumped and d_next:
            state.depth_bumps[label] = d_next
        writer(f"[chain] {label}: bumping profile → {nxt}; retrying once\n")
        return "retry"
    if action == "bump_robustness":
        current = state.robustness_bumps.get(label) or (
            (
                milestone.robustness
                if milestone and milestone.robustness
                else spec.robustness
            )
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
    if status == "finalized":
        writer(
            f"[chain] plan {outcome.plan} is finalized but not executed; "
            "stopping before PR progression\n"
        )
        return "stop"
    if status == "done":
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
        if root is not None and _awaiting_human_can_retry(root, outcome.plan):
            writer(
                f"[chain] plan {outcome.plan} reported awaiting_human, but all user-action "
                "resolutions allow resume; retrying milestone\n"
            )
            policy = spec.on_failure_policy
        else:
            writer(
                f"[chain] plan {outcome.plan} paused awaiting human action: "
                f"{outcome.reason}\n"
            )
            return "stop"
    if status == "infrastructure_error":
        writer(
            f"[chain] plan {outcome.plan} stopped on infrastructure error: "
            f"{outcome.reason}\n"
        )
        return "stop"
    outcome_reason_lower = outcome.reason.lower()
    if (
        status == "blocked"
        and "prerequisite-blocked" in outcome_reason_lower
        and (
            "not satisfied" in outcome_reason_lower
            or "settled" in outcome_reason_lower
        )
    ):
        writer(
            f"[chain] plan {outcome.plan} stopped on unresolved explicit blocker: "
            f"{outcome.reason}\n"
        )
        return "stop"
    if status in ("aborted", "escalated"):
        if status == "aborted":
            writer(f"[chain] plan {outcome.plan} ended aborted\n")
        else:
            writer(
                f"[chain] plan {outcome.plan} escalated — applying on_escalate policy\n"
            )
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
            writer(f"[chain] {label}: retry {spent + 1}/{cap}\n")
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
            [
                "git",
                "stash",
                "push",
                "--include-untracked",
                "-m",
                f"megaplan-chain require_clean_base {milestone.label}",
            ],
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


def _preserve_carried_wip_before_retry(
    root: Path,
    spec_path: Path,
    state: ChainState,
    milestone: "MilestoneSpec",
    plan_name: str | None,
    *,
    writer,
) -> None:
    """Stash abandoned attempt WIP before re-initializing a milestone retry.

    This runs only when the chain has decided the current plan is not resumable
    and will force a fresh init. Without preserving the failed attempt's working
    tree, the next ``require_clean_base`` check reports the abandoned WIP as the
    root failure and hides the original blocker.
    """
    carried = _carried_wip_paths(root)
    if not carried:
        return

    sample = ", ".join(p.name for p in carried[:5])
    message = (
        f"megaplan-chain retry-preserve {milestone.label}"
        + (f" plan={plan_name}" if plan_name else "")
    )
    writer(
        f"[chain] retry for {milestone.label} would re-init over carried WIP "
        f"({sample}); preserving via git stash before retry\n"
    )
    proc = subprocess.run(
        ["git", "stash", "push", "--include-untracked", "-m", message],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if proc.returncode != 0:
        raise CliError(
            "retry_preserve_failed",
            "retry could not preserve carried WIP before re-init for "
            f"{milestone.label}: {proc.stderr.strip() or proc.stdout.strip()}",
        )

    stash_proc = subprocess.run(
        ["git", "stash", "list", "--format=%gd", "-n", "1"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if stash_proc.returncode != 0:
        raise CliError(
            "retry_preserve_failed",
            "retry preserved carried WIP but could not resolve the stash ref: "
            f"{stash_proc.stderr.strip() or stash_proc.stdout.strip()}",
        )
    stash_ref = stash_proc.stdout.strip()
    metadata = state.metadata.setdefault("retry_preserved_wip", [])
    if isinstance(metadata, list):
        metadata.append(
            {
                "milestone": milestone.label,
                "plan": plan_name,
                "stash_ref": stash_ref,
                "sample_paths": [p.as_posix() for p in carried[:20]],
            }
        )
    chain_spec.save_chain_state(spec_path, state)


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
    mode: str = "start",
    full_suite_backstop_mode: str | None = None,
    fresh: bool = False,
    require_anchor_override: bool | None = None,
    missing_anchor_ack_override: str | None = None,
) -> dict[str, Any]:
    """Drive the full chain. Returns a structured JSON-serializable result."""
    root = root.resolve(strict=False)
    spec_path = spec_path.resolve(strict=False)
    _require_git_worktree_root(root, operation="chain start")
    spec = chain_spec.load_spec(spec_path)
    anchor_requirement = chain_spec.validate_anchor_requirement(
        spec,
        spec_path,
        require_anchor_override=require_anchor_override,
        missing_anchor_ack_override=missing_anchor_ack_override,
    )
    if anchor_requirement.warning:
        writer(f"[chain] WARNING: {anchor_requirement.warning}\n")
    chain_spec.validate_paths(spec, root, spec_path=spec_path)
    _preflight_agent_backends(spec, writer=writer)
    state = chain_spec.load_chain_state(spec_path)
    from arnold_pipelines.megaplan.chain.execution_binding import (
        bind_execution_identity,
    )

    # Bind before the first state save or milestone initialization. Existing
    # progressed state without a launch binding is refused by the loader.
    bind_execution_identity(spec_path, state)
    from arnold_pipelines.megaplan.chain.operator_pause import is_paused

    if is_paused(state):
        return _result(
            "paused",
            state,
            [],
            spec=spec,
            reason="durable operator pause is active; explicit chain resume required",
        )
    env = resolve_execution_environment(
        root=root,
        state={"config": {"project_dir": str(root), "base_branch": spec.base_branch}},
    )
    state.metadata = merge_isolation_evidence(state.metadata, env, phase="chain_start")
    if state.current_milestone_index < 0 and not state.completed:
        from arnold_pipelines.megaplan._core.io import get_effective
        from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
            normalize_full_suite_backstop_mode,
        )

        state.full_suite_backstop_mode = normalize_full_suite_backstop_mode(
            full_suite_backstop_mode
            if full_suite_backstop_mode is not None
            else get_effective("execution", "full_suite_backstop_mode")
        )
    chain_spec.save_chain_state(spec_path, state)
    preexisting_dirty_paths = _dirty_worktree_paths(root)
    push_enabled = not no_push and os.environ.get("MEGAPLAN_CHAIN_NO_PUSH") not in {
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    }
    completed_before_reconciliation = len(state.completed)
    state = _reconcile_chain_from_ground_truth(
        root,
        spec_path,
        spec,
        state,
        writer=writer,
        push_enabled=push_enabled,
    )

    events: list[dict[str, Any]] = []

    if one and len(state.completed) > completed_before_reconciliation:
        return _result(
            "done",
            state,
            events,
            spec=spec,
            reason="one-milestone limit reached during ground-truth reconciliation",
        )

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
                spec_path,
                spec.seed_plan,
                spec,
                writer=writer,
            )
            state = _record_chain_last_state_after_plan_run(
                root,
                spec_path,
                state,
                outcome,
                writer=writer,
            )
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
                return _result(
                    "stopped",
                    state,
                    events,
                    spec=spec,
                    reason=f"seed plan {outcome.status}",
                )
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan_with_blocked_execute_recovery(
                    root,
                    spec_path,
                    spec.seed_plan,
                    spec,
                    writer=writer,
                )
                state = _record_chain_last_state_after_plan_run(
                    root,
                    spec_path,
                    state,
                    outcome,
                    writer=writer,
                )
                if outcome.status != "done":
                    return _result(
                        "stopped", state, events, spec=spec, reason="seed retry failed"
                    )
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
        appended, reason = _append_completed_with_guard(
            root,
            state,
            {
                "label": "seed",
                "plan": spec.seed_plan,
                "status": state.last_state or seed_state,
            },
            implementation_milestone=False,
            writer=writer,
        )
        if not appended:
            chain_spec.save_chain_state(spec_path, state)
            return _result(
                "blocked",
                state,
                events,
                spec=spec,
                reason=f"seed completion guard blocked append: {reason}",
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
        state = chain_spec.load_chain_state(spec_path)
        if is_paused(state):
            return _result(
                "paused",
                state,
                events,
                spec=spec,
                reason="durable operator pause is active; explicit chain resume required",
            )
        state = _reconcile_chain_from_ground_truth(
            root,
            spec_path,
            spec,
            state,
            writer=writer,
            push_enabled=push_enabled,
        )
        idx = max(state.current_milestone_index, 0)
        if idx >= len(spec.milestones):
            break
        milestone = spec.milestones[idx]
        log(f"milestone {milestone.label} starting")
        use_pr = push_enabled and bool(milestone.branch)

        if (
            use_pr
            and state.current_milestone_index == idx
            and state.last_state == "pr_closed"
        ):
            state = _clear_stale_closed_pr_state(
                spec_path=spec_path,
                state=state,
                milestone_label=milestone.label,
                log_fn=log,
            )

        if state.current_milestone_index == idx and state.pr_number is not None and use_pr:
            pr_state = _pr_state(root, state.pr_number, writer=writer)
            if pr_state == "closed" and state.last_state == "blocked":
                log(
                    f"clearing stale closed PR context for {milestone.label} while "
                    "resuming blocked plan"
                )
                state.last_state = "pr_closed"
                state.pr_state = "closed"
                chain_spec.save_chain_state(spec_path, state)
                state = _clear_stale_closed_pr_state(
                    spec_path=spec_path,
                    state=state,
                    milestone_label=milestone.label,
                    log_fn=log,
                )
                continue
            if pr_state == "merged":
                state.pr_state = "merged"
                chain_spec.save_chain_state(spec_path, state)
                merged_pr_plan_state = _plan_state_payload_from_name(
                    root, state.current_plan_name
                )
                if merged_pr_plan_state.get("current_state") != STATE_DONE:
                    recovered_state, recovery_reason = (
                        _recover_stale_merged_pr_for_unfinished_plan(
                            root,
                            spec_path,
                            state,
                            milestone,
                            merged_pr_plan_state,
                            writer=writer,
                        )
                    )
                    if recovered_state is None:
                        return _block_pr_progression_guard_failure(
                            spec_path=spec_path,
                            spec=spec,
                            state=state,
                            milestone=milestone,
                            reason=recovery_reason,
                            events=events,
                            writer=writer,
                        )
                    state = recovered_state
                    log(recovery_reason)
                    continue
                publish_ok, publish_reason = _ensure_published_claimed_changes_for_pr_progression(
                    root,
                    spec_path,
                    state,
                    milestone,
                    writer=writer,
                    allow_publish=False,
                )
                if not publish_ok:
                    return _block_pr_progression_guard_failure(
                        spec_path=spec_path,
                        spec=spec,
                        state=state,
                        milestone=milestone,
                        reason=publish_reason,
                        events=events,
                        writer=writer,
                    )
                log(f"PR #{state.pr_number} merged; advancing past {milestone.label}")
                validation_reason = _run_milestone_validations_blocking(
                    root=root,
                    spec_path=spec_path,
                    spec=spec,
                    state=state,
                    milestone=milestone,
                    writer=writer,
                    refresh_base=True,
                    no_git_refresh=no_git_refresh,
                )
                if validation_reason is not None:
                    return _result(
                        "blocked",
                        state,
                        events,
                        spec=spec,
                        reason=validation_reason,
                    )
                appended, reason = _append_completed_with_guard(
                    root,
                    state,
                    {
                        "label": milestone.label,
                        "plan": state.current_plan_name,
                        "status": "done",
                        "pr_number": state.pr_number,
                        "pr_state": "merged",
                    },
                    implementation_milestone=True,
                    writer=writer,
                )
                if not appended:
                    authoritative, _authority_reason = _plan_terminal_completion_is_authoritative(
                        root, state.current_plan_name
                    )
                    if not authoritative:
                        chain_spec.save_chain_state(spec_path, state)
                        return _result(
                            "blocked",
                            state,
                            events,
                            spec=spec,
                            reason=f"milestone {milestone.label} completion guard blocked append: {reason}",
                        )
                    return _handle_completion_guard_failure(
                        root=root,
                        spec_path=spec_path,
                        spec=spec,
                        state=state,
                        milestone=milestone,
                        plan_name=state.current_plan_name or "",
                        outcome_status="done",
                        reason=reason,
                        events=events,
                        writer=writer,
                    )
                if state.current_plan_name:
                    _mark_plan_completed_by_chain(
                        root,
                        state.current_plan_name,
                        milestone_label=milestone.label,
                        completion_reason=reason,
                        writer=writer,
                        state=state,
                    )
                _emit_milestone_completion_evidence(
                    state,
                    milestone_label=milestone.label,
                    milestone_index=idx,
                    plan_name=state.current_plan_name or "",
                )
                idx += 1
                _mark_chain_after_milestone_advance(spec, state, next_index=idx)
                if idx >= len(spec.milestones):
                    _emit_chain_complete_evidence(state, spec=spec)
                chain_spec.save_chain_state(spec_path, state)
                manifest_reason = _finalize_validation_artifacts_after_done_append(
                    root=root,
                    spec_path=spec_path,
                    spec=spec,
                    state=state,
                    milestone=milestone,
                    writer=writer,
                )
                if manifest_reason is not None:
                    return _result(
                        "blocked",
                        state,
                        events,
                        spec=spec,
                        reason=manifest_reason,
                    )
                continue

        if (
            state.last_state == STATE_AWAITING_PR_MERGE
            and state.current_milestone_index == idx
        ):
            local_publication_sha: str | None = None
            if not use_pr or state.pr_number is None:
                log(
                    f"review merge wait for {milestone.label} has no PR context; advancing"
                )
                if not use_pr and state.pr_number is not None:
                    local_publication_sha = _current_git_head(root)
                    if local_publication_sha is None:
                        return _result(
                            "blocked",
                            state,
                            events,
                            spec=spec,
                            reason=(
                                f"milestone {milestone.label} cannot reconcile its open PR "
                                "to a local-only run without a readable local HEAD"
                            ),
                        )
                    state.metadata["local_pr_reconciliation"] = {
                        "milestone": milestone.label,
                        "pr_number": state.pr_number,
                        "observed_pr_state": state.pr_state,
                        "local_commit_sha": local_publication_sha,
                    }
                    state.pr_number = None
                state.pr_state = None
                chain_spec.save_chain_state(spec_path, state)
            else:
                pr_state = _pr_state(root, state.pr_number, writer=writer)
                if pr_state == "closed":
                    log(f"PR #{state.pr_number} closed while awaiting merge; stopping chain")
                    return _stop_for_closed_pr(
                        spec_path=spec_path,
                        state=state,
                        events=events,
                        spec=spec,
                        milestone_label=milestone.label,
                        pr_number=state.pr_number,
                    )
                state.pr_state = pr_state
                chain_spec.save_chain_state(spec_path, state)
                if pr_state != "merged":
                    publish_ok, publish_reason = _ensure_published_claimed_changes_for_pr_progression(
                        root,
                        spec_path,
                        state,
                        milestone,
                        writer=writer,
                        allow_publish=True,
                    )
                    if not publish_ok:
                        return _block_pr_progression_guard_failure(
                            spec_path=spec_path,
                            spec=spec,
                            state=state,
                            milestone=milestone,
                            reason=publish_reason,
                            events=events,
                            writer=writer,
                        )
                    if publish_reason.startswith("published "):
                        state = chain_spec.load_chain_state(spec_path)
                    if _automatic_pr_progression_permitted(spec, spec_path):
                        validation_evidence = _validate_pr_progression_wbc(
                            root=root,
                            spec_path=spec_path,
                            state=state,
                            milestone=milestone,
                            plan_name=state.current_plan_name or "",
                            pr_number=state.pr_number,
                            transition_name="chain_pr_ready",
                        )
                        _pr_ready_evidence = _capture_pr_ready_evidence(
                            root,
                            state.pr_number,
                            writer=writer,
                            ci_readiness_state="ready",
                            validation_evidence=validation_evidence,
                        )
                        _mark_pr_ready(root, state.pr_number, writer=writer)
                        state.pr_state = _enable_auto_merge(
                            root, state.pr_number, writer=writer
                        )
                        _pr_merged_evidence = _capture_pr_merged_evidence(
                            root,
                            state.pr_number,
                            writer=writer,
                            validation_evidence=validation_evidence,
                        )
                        chain_spec.save_chain_state(spec_path, state)
                        pr_state = _pr_state(root, state.pr_number, writer=writer)
                        state.pr_state = pr_state
                        chain_spec.save_chain_state(spec_path, state)
                        if pr_state == "closed":
                            log(
                                f"PR #{state.pr_number} closed while awaiting merge; "
                                "stopping chain"
                            )
                            return _stop_for_closed_pr(
                                spec_path=spec_path,
                                state=state,
                                events=events,
                                spec=spec,
                                milestone_label=milestone.label,
                                pr_number=state.pr_number,
                            )
                        if pr_state == "merged":
                            log(
                                f"PR #{state.pr_number} merged; advancing past "
                                f"{milestone.label}"
                            )
                        else:
                            log(
                                f"PR #{state.pr_number} auto-merge enabled; "
                                f"state={pr_state}; awaiting merge"
                            )
                            return _result(
                                STATE_AWAITING_PR_MERGE,
                                state,
                                events,
                                spec=spec,
                                reason=(
                                    f"milestone {milestone.label} PR "
                                    f"#{state.pr_number} is {pr_state}"
                                ),
                            )
                    else:
                        policy = policy_for_spec(
                            spec,
                            runtime_overrides=chain_spec.load_runtime_policy(spec_path),
                        )
                        log(
                            f"PR #{state.pr_number} state={pr_state}; awaiting human "
                            f"review/merge (merge_policy={policy.merge_policy}, "
                            f"clean_milestone_pr={policy.clean_milestone_pr})"
                        )
                        return _result(
                            STATE_AWAITING_PR_MERGE,
                            state,
                            events,
                            spec=spec,
                            reason=f"milestone {milestone.label} PR #{state.pr_number} is {pr_state}",
                        )
                if pr_state != "merged":
                    log(f"PR #{state.pr_number} state={pr_state}; awaiting merge")
                    return _result(
                        STATE_AWAITING_PR_MERGE,
                        state,
                        events,
                        spec=spec,
                        reason=f"milestone {milestone.label} PR #{state.pr_number} is {pr_state}",
                    )
                merged_pr_plan_state = _plan_state_payload_from_name(
                    root, state.current_plan_name
                )
                if merged_pr_plan_state.get("current_state") != STATE_DONE:
                    recovered_state, recovery_reason = (
                        _recover_stale_merged_pr_for_unfinished_plan(
                            root,
                            spec_path,
                            state,
                            milestone,
                            merged_pr_plan_state,
                            writer=writer,
                        )
                    )
                    if recovered_state is None:
                        return _block_pr_progression_guard_failure(
                            spec_path=spec_path,
                            spec=spec,
                            state=state,
                            milestone=milestone,
                            reason=recovery_reason,
                            events=events,
                            writer=writer,
                        )
                    state = recovered_state
                    log(recovery_reason)
                    continue
                publish_ok, publish_reason = _ensure_published_claimed_changes_for_pr_progression(
                    root,
                    spec_path,
                    state,
                    milestone,
                    writer=writer,
                    allow_publish=False,
                )
                if not publish_ok:
                    return _block_pr_progression_guard_failure(
                        spec_path=spec_path,
                        spec=spec,
                        state=state,
                        milestone=milestone,
                        reason=publish_reason,
                        events=events,
                        writer=writer,
                    )
                log(f"PR #{state.pr_number} merged; advancing past {milestone.label}")
            validation_reason = _run_milestone_validations_blocking(
                root=root,
                spec_path=spec_path,
                spec=spec,
                state=state,
                milestone=milestone,
                writer=writer,
                refresh_base=True,
                no_git_refresh=no_git_refresh,
            )
            if validation_reason is not None:
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=validation_reason,
                )
            completion_record = {
                "label": milestone.label,
                "plan": state.current_plan_name,
                "status": "done",
                "pr_number": state.pr_number,
                "pr_state": "merged" if state.pr_number is not None else None,
            }
            if local_publication_sha is not None:
                completion_record["local_commit_sha"] = local_publication_sha
                completion_record["publication_evidence"] = "local_no_push_reconciliation"
            appended, reason = _append_completed_with_guard(
                root,
                state,
                completion_record,
                implementation_milestone=True,
                writer=writer,
            )
            if not appended:
                authoritative, _authority_reason = _plan_terminal_completion_is_authoritative(
                    root, state.current_plan_name
                )
                if not authoritative:
                    chain_spec.save_chain_state(spec_path, state)
                    return _result(
                        "blocked",
                        state,
                        events,
                        spec=spec,
                        reason=f"milestone {milestone.label} completion guard blocked append: {reason}",
                    )
                return _handle_completion_guard_failure(
                    root=root,
                    spec_path=spec_path,
                    spec=spec,
                    state=state,
                    milestone=milestone,
                    plan_name=state.current_plan_name or "",
                    outcome_status="done",
                    reason=reason,
                    events=events,
                    writer=writer,
                )
            if state.current_plan_name:
                _mark_plan_completed_by_chain(
                    root,
                    state.current_plan_name,
                    milestone_label=milestone.label,
                    completion_reason=reason,
                    writer=writer,
                    state=state,
                )
            _emit_milestone_completion_evidence(
                state,
                milestone_label=milestone.label,
                milestone_index=idx,
                plan_name=state.current_plan_name or "",
            )
            idx += 1
            _mark_chain_after_milestone_advance(spec, state, next_index=idx)
            if idx >= len(spec.milestones):
                _emit_chain_complete_evidence(state, spec=spec)
            chain_spec.save_chain_state(spec_path, state)
            manifest_reason = _finalize_validation_artifacts_after_done_append(
                root=root,
                spec_path=spec_path,
                spec=spec,
                state=state,
                milestone=milestone,
                writer=writer,
            )
            if manifest_reason is not None:
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=manifest_reason,
                )
            continue

        # Resume mid-milestone if we already have a plan name recorded.
        try:
            if (
                state.current_plan_name
                and state.current_milestone_index == idx
                and _plan_state(root, state.current_plan_name, timeout=spec.status_timeout)
                not in ("missing",)
            ):
                plan_name = state.current_plan_name
                try:
                    plan_dir = resolve_plan_dir(root, plan_name)
                except CliError:
                    plan_dir = None
                if plan_dir is not None:
                    _rearm_stale_terminal_execute_cursor_mismatch(plan_dir, writer=writer)
                    _rearm_stale_incomplete_execute_cursor_mismatch(plan_dir, writer=writer)
                    _rearm_stale_execute_authority_divergence(plan_dir, writer=writer)
                    _rearm_fresh_session_execute_block(plan_dir, writer=writer)
                plan_state = _plan_state_payload_from_name(root, plan_name)
                if _blocked_plan_replay_would_be_redundant(state, plan_state=plan_state):
                    _append_reconciliation_audit(
                        state,
                        plan_name=plan_name,
                        plan_state=dict(plan_state),
                        pr_number=state.pr_number,
                        pr_state=state.pr_state,
                    )
                    chain_spec.save_chain_state(spec_path, state)
                    writer(
                        f"[chain] plan {plan_name} is already durably blocked with no "
                        "active step; preserving the stop without replaying the plan\n"
                    )
                    return _result(
                        "stopped",
                        state,
                        events,
                        spec=spec,
                        reason=f"milestone {milestone.label} remains blocked",
                    )
                state = _sync_chain_last_state_from_plan(
                    root,
                    spec_path,
                    state,
                    writer=writer,
                )
                log(f"resuming existing plan {plan_name} for {milestone.label}")
                _emit_milestone_start_evidence(
                    state,
                    milestone_label=milestone.label,
                    milestone_index=idx,
                    plan_name=plan_name,
                )
                if use_pr and milestone.branch:
                    base_ref = _checkout_milestone_branch(
                        root,
                        milestone.branch or "",
                        base_branch=spec.base_branch,
                        writer=writer,
                        from_origin=push_enabled and not no_git_refresh,
                        expected_base_ref=state.target_base_ref,
                    )
                    if isinstance(base_ref, str) and base_ref:
                        state.target_base_ref = base_ref
                        chain_spec.save_chain_state(spec_path, state)
                    _capture_sync_state(
                        root, spec_path, branch=milestone.branch, pr_number=state.pr_number
                    )
                    if state.pr_number is None:
                        state = chain_spec.load_chain_state(spec_path)
                        state.pr_number = _ensure_milestone_pr(
                            root,
                            milestone,
                            base_branch=spec.base_branch,
                            writer=writer,
                        )
                        state.pr_state = "open" if state.pr_number is not None else None
                        chain_spec.save_chain_state(spec_path, state)
            else:
                base_ref = _refresh_base_branch(
                    root,
                    spec.base_branch,
                    writer=writer,
                    no_git_refresh=no_git_refresh,
                    expected_sha=state.target_base_ref,
                )
                if isinstance(base_ref, str) and base_ref:
                    state.target_base_ref = base_ref
                    chain_spec.save_chain_state(spec_path, state)
                if spec.require_clean_base:
                    _assert_clean_base(
                        root,
                        milestone,
                        no_push=not push_enabled,
                        writer=writer,
                    )
                if use_pr:
                    base_ref = _checkout_milestone_branch(
                        root,
                        milestone.branch or "",
                        base_branch=spec.base_branch,
                        writer=writer,
                        from_origin=push_enabled and not no_git_refresh,
                        expected_base_ref=state.target_base_ref,
                    )
                    if isinstance(base_ref, str) and base_ref:
                        state.target_base_ref = base_ref
                        chain_spec.save_chain_state(spec_path, state)
                    _capture_sync_state(
                        root, spec_path, branch=milestone.branch, pr_number=None
                    )
                    state = chain_spec.load_chain_state(spec_path)
                from arnold_pipelines.megaplan.chain.source_admission import (
                    admit_milestone_source,
                )

                admit_milestone_source(
                    root=root,
                    spec_path=spec_path,
                    spec=spec,
                    state=state,
                    milestone=milestone,
                    milestone_index=idx,
                )
                eff_profile = state.profile_bumps.get(milestone.label) or milestone.profile
                eff_robustness = (
                    state.robustness_bumps.get(milestone.label)
                    or milestone.robustness
                    or spec.robustness
                )
                eff_depth = state.depth_bumps.get(milestone.label) or milestone.depth
                if (
                    eff_profile != milestone.profile
                    or eff_robustness != (milestone.robustness or spec.robustness)
                    or eff_depth != milestone.depth
                ):
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
                _attach_chain_anchors_to_plan(root, spec_path, plan_name, spec, milestone)
                state.current_milestone_index = idx
                state.current_plan_name = plan_name
                _emit_milestone_start_evidence(
                    state,
                    milestone_label=milestone.label,
                    milestone_index=idx,
                    plan_name=plan_name,
                )
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
                    state = chain_spec.load_chain_state(spec_path)
                    state.pr_number = _ensure_milestone_pr(
                        root,
                        milestone,
                        base_branch=spec.base_branch,
                        writer=writer,
                    )
                    state.pr_state = "open"
                    chain_spec.save_chain_state(spec_path, state)
        except CliError as exc:
            if exc.code == "missing_base_ref":
                return _handle_missing_base_ref(
                    root,
                    spec_path,
                    state,
                    spec=spec,
                    events=events,
                    milestone_label=milestone.label,
                    error=exc,
                )
            raise

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
            spec_path,
            plan_name,
            spec,
            on_phase_complete=phase_callback if use_pr else None,
            writer=writer,
        )
        if outcome.status == "stalled":
            reconciled_state = _plan_current_state_from_payload(root, plan_name)
            terminal_good = {"done", STATE_FINALIZED}
            if reconciled_state in terminal_good:
                writer(
                    f"[chain] driver reported {outcome.status!r} for {plan_name}, "
                    f"but plan state.json is {reconciled_state!r}; reconciling "
                    "to advance\n"
                )
                outcome.reason = (
                    f"reconciled from {outcome.status} via plan "
                    f"state.json={reconciled_state}"
                )
                outcome.status = "done"
        state = _record_chain_last_state_after_plan_run(
            root,
            spec_path,
            state,
            outcome,
            writer=writer,
        )
        decision = _handle_outcome(
            outcome,
            spec=spec,
            writer=writer,
            milestone=milestone,
            state=state,
            root=root,
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
            authoritative, reason = _plan_terminal_completion_is_authoritative(
                root, plan_name
            )
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
                _preserve_carried_wip_before_retry(
                    root,
                    spec_path,
                    state,
                    milestone,
                    state.current_plan_name,
                    writer=writer,
                )
                state.current_plan_name = None  # force re-init next loop
            state.pr_number = None
            state.pr_state = None
            chain_spec.save_chain_state(spec_path, state)
            continue
        full_suite_backstop_gate: dict[str, Any] | None = None
        full_suite_backstop_summary: dict[str, Any] | None = None
        if decision == "advance" and outcome.status == "done":
            full_suite_backstop_gate = _run_full_suite_backstop_gate(
                root,
                spec_path,
                plan_name,
                milestone.label,
                state.full_suite_backstop_mode,
                log_fn=log,
            )
            full_suite_backstop_summary = full_suite_backstop_gate.get("summary")
            if full_suite_backstop_gate.get("blocks"):
                result = full_suite_backstop_gate.get("result")
                newly_failing = []
                deleted_tests = []
                if isinstance(result, dict):
                    if isinstance(result.get("newly_failing"), list):
                        newly_failing = result["newly_failing"]
                    if isinstance(result.get("deleted_tests"), list):
                        deleted_tests = result["deleted_tests"]
                failing_suffix = (
                    f"; newly_failing={newly_failing[:10]}"
                    if newly_failing
                    else (
                        f"; deleted_tests={deleted_tests[:10]}" if deleted_tests else ""
                    )
                )
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=(
                        f"full_suite_backstop_mode=enforce: milestone "
                        f"{milestone.label!r} blocked before advance; see "
                        f"{plan_name}/full_suite_backstop.json{failing_suffix}"
                    ),
                )
        local_commit_sha: str | None = None
        if (
            decision == "advance"
            and outcome.status == "done"
            and not use_pr
            and mode != "plan"
        ):
            local_commit_sha = _commit_phase(
                root,
                plan_name,
                "done",
                writer=writer,
                preexisting_dirty_paths=preexisting_dirty_paths,
            )
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
            state = chain_spec.load_chain_state(spec_path)
            current_pr_state = _pr_state(root, state.pr_number, writer=writer)
            if current_pr_state == "merged":
                state.pr_state = "merged"
                chain_spec.save_chain_state(spec_path, state)
            elif current_pr_state == "closed":
                log(f"PR #{state.pr_number} closed during milestone completion; stopping chain")
                return _stop_for_closed_pr(
                    spec_path=spec_path,
                    state=state,
                    events=events,
                    spec=spec,
                    milestone_label=milestone.label,
                    pr_number=state.pr_number,
                )
            else:
                pending_merge_record = {
                    "label": milestone.label,
                    "plan": plan_name,
                    "status": outcome.status,
                    "pr_number": state.pr_number,
                    "pr_state": current_pr_state,
                }
                premerge_ok, premerge_reason = _chain_completion_guard(
                    root,
                    pending_merge_record,
                    implementation_milestone=True,
                    chain_state=state,
                )
                if not premerge_ok:
                    # Auto-merge can complete between the first PR observation
                    # and this (potentially expensive) authority check.  A
                    # merged PR has stronger publication evidence than an open
                    # one, so re-read external truth before persisting a stale
                    # blocked cursor.  The normal completed-record guard below
                    # still validates the merged publication; no authority
                    # requirement is weakened here.
                    latest_pr_state = _pr_state(
                        root, state.pr_number, writer=writer
                    )
                    if latest_pr_state == "merged":
                        state.pr_state = "merged"
                        chain_spec.save_chain_state(spec_path, state)
                        log(
                            f"PR #{state.pr_number} merged while completion guard "
                            f"was evaluating; reconciling {milestone.label} from "
                            "published evidence"
                        )
                    else:
                        writer(
                            f"[chain] completion guard blocked {milestone.label} before "
                            f"PR merge: {premerge_reason}\n"
                        )
                        state.last_state = STATE_BLOCKED
                        state.pr_state = latest_pr_state
                        chain_spec.save_chain_state(spec_path, state)
                        return _result(
                            "stopped",
                            state,
                            events,
                            spec=spec,
                            reason=(
                                f"milestone {milestone.label} completion guard blocked "
                                f"before PR merge: {premerge_reason}"
                            ),
                        )
                else:
                    validation_evidence = _validate_pr_progression_wbc(
                        root=root,
                        spec_path=spec_path,
                        state=state,
                        milestone=milestone,
                        plan_name=plan_name,
                        pr_number=state.pr_number,
                        transition_name="chain_pr_ready",
                    )
                    _pr_ready_evidence = _capture_pr_ready_evidence(
                        root,
                        state.pr_number,
                        writer=writer,
                        ci_readiness_state="ready",
                        validation_evidence=validation_evidence,
                    )
                    _mark_pr_ready(root, state.pr_number, writer=writer)
                    if not _automatic_pr_progression_permitted(spec, spec_path):
                        state.last_state = STATE_AWAITING_PR_MERGE
                        state.pr_state = current_pr_state
                        chain_spec.save_chain_state(spec_path, state)
                        policy = policy_for_spec(
                            spec,
                            runtime_overrides=chain_spec.load_runtime_policy(spec_path),
                        )
                        log(
                            f"PR #{state.pr_number} ready; awaiting human review/merge "
                            f"(merge_policy={policy.merge_policy}, "
                            f"clean_milestone_pr={policy.clean_milestone_pr})"
                        )
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
                    state.pr_state = _enable_auto_merge(
                        root, state.pr_number, writer=writer
                    )
                    _pr_merged_evidence = _capture_pr_merged_evidence(
                        root,
                        state.pr_number,
                        writer=writer,
                        validation_evidence=validation_evidence,
                    )
                    chain_spec.save_chain_state(spec_path, state)
                    if state.pr_state != "merged":
                        # Enabling auto-merge is not publication evidence. GitHub
                        # may leave the PR open while checks or the merge queue
                        # run, so never append completion until external truth
                        # reports the PR as merged.
                        latest_pr_state = _pr_state(
                            root, state.pr_number, writer=writer
                        )
                        if latest_pr_state == "merged":
                            state.pr_state = "merged"
                            chain_spec.save_chain_state(spec_path, state)
                        else:
                            state.last_state = STATE_AWAITING_PR_MERGE
                            state.pr_state = latest_pr_state
                            chain_spec.save_chain_state(spec_path, state)
                            return _result(
                                STATE_AWAITING_PR_MERGE,
                                state,
                                events,
                                spec=spec,
                                reason=(
                                    f"milestone {milestone.label} PR "
                                    f"#{state.pr_number} auto-merge pending"
                                ),
                            )
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
                raw_state = json.loads(
                    (plan_dir / "state.json").read_text(encoding="utf-8")
                )
                if isinstance(raw_state, dict):
                    cfg = (
                        raw_state.get("config", {})
                        if isinstance(raw_state.get("config"), dict)
                        else {}
                    )
                    max_retries = int(cfg.get("enforce_revise_max_retries", 2))
            except Exception:
                pass

            milestone_retry_count = int(
                state.enforce_revise_counts.get(milestone.label, 0)
            )
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
        if (
            decision == "advance"
            and full_suite_backstop_gate is not None
            and not full_suite_backstop_gate.get("blocks")
        ):
            result = full_suite_backstop_gate.get("result")
            if isinstance(result, dict):
                if _persist_full_suite_backstop_baseline(
                    spec_path,
                    result,
                    captured_at_sha=_current_head_sha(root),
                    milestone_label=milestone.label,
                ):
                    log(
                        "full_suite_backstop baseline updated "
                        f"milestone={milestone.label}"
                    )
        # advance or skip
        completed_record = {
            "label": milestone.label,
            "plan": plan_name,
            "status": outcome.status,
            "pr_number": state.pr_number,
            "pr_state": state.pr_state,
        }
        if local_commit_sha is not None:
            completed_record["local_commit_sha"] = local_commit_sha
            completed_record["plan_branch"] = spec.base_branch
        if full_suite_backstop_summary is not None:
            completed_record["full_suite_backstop"] = full_suite_backstop_summary
        validation_reason = _run_milestone_validations_blocking(
            root=root,
            spec_path=spec_path,
            spec=spec,
            state=state,
            milestone=milestone,
            writer=writer,
            refresh_base=False,
            no_git_refresh=no_git_refresh,
        )
        if validation_reason is not None:
            return _result(
                "blocked",
                state,
                events,
                spec=spec,
                reason=validation_reason,
            )
        appended, reason = _append_completed_with_guard(
            root,
            state,
            completed_record,
            implementation_milestone=True,
            writer=writer,
        )
        if not appended:
            return _handle_completion_guard_failure(
                root=root,
                spec_path=spec_path,
                spec=spec,
                state=state,
                milestone=milestone,
                plan_name=plan_name,
                outcome_status=outcome.status,
                reason=reason,
                events=events,
                writer=writer,
            )
        _mark_plan_completed_by_chain(
            root,
            plan_name,
            milestone_label=milestone.label,
            completion_reason=reason,
            writer=writer,
            state=state,
        )
        idx += 1
        _mark_chain_after_milestone_advance(spec, state, next_index=idx)
        chain_spec.save_chain_state(spec_path, state)
        manifest_reason = _finalize_validation_artifacts_after_done_append(
            root=root,
            spec_path=spec_path,
            spec=spec,
            state=state,
            milestone=milestone,
            writer=writer,
        )
        if manifest_reason is not None:
            return _result(
                "blocked",
                state,
                events,
                spec=spec,
                reason=manifest_reason,
            )
        _emit_milestone_completion_evidence(
            state,
            milestone_label=milestone.label,
            milestone_index=idx - 1,
            plan_name=plan_name,
        )
        if idx >= len(spec.milestones):
            _emit_chain_complete_evidence(state, spec=spec)
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
    # ── Successor gate check ──────────────────────────────────────────
    # In fail-closed (atomic/enforce) mode a completed chain must carry a
    # validated acceptance receipt for its final milestone before any
    # declared successor may be initialised.  The gate is generic – it
    # reads SuccessorSpec declarations from the chain YAML rather than
    # hardcoding initiative names (M5→M5A→M6 is the first consumer).
    successor_block = _check_successor_gate_at_chain_completion(
        state, spec, spec_path, events, writer=writer
    )
    if successor_block is not None:
        return successor_block
    return _result("done", state, events, spec=spec)


def _check_successor_gate_at_chain_completion(
    state: ChainState,
    spec: ChainSpec,
    spec_path: Path,
    events: list[dict[str, Any]],
    *,
    writer,
) -> dict[str, Any] | None:
    """Check the successor gate when a chain completes all milestones.

    Returns a blocked result dict when the gate is closed (successor
    requires an accepted transaction but none is present), or ``None``
    when the gate is open / not applicable / not in fail-closed mode.

    The gate is generic: it reads ``SuccessorSpec`` declarations from
    the chain YAML rather than hardcoding initiative names.
    """
    successors = getattr(spec, "successors", None) or []
    if not successors:
        return None

    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        is_fail_closed_mode,
        normalize_contract_mode,
    )

    mode = normalize_contract_mode(state.completion_contract_mode)
    if not is_fail_closed_mode(mode):
        return None  # shadow / warn / off — gate is always open

    any_require = any(
        getattr(s, "require_accepted_transaction", True) for s in successors
    )
    if not any_require:
        return None

    if not spec.milestones:
        return None

    final_milestone = spec.milestones[-1]
    has_receipt = state.has_acceptance_receipt(final_milestone.label)

    if has_receipt:
        # Gate is open — chain may advertise completion to successor init.
        return None

    writer(
        f"[chain] successor gate closed: chain is complete but no validated "
        f"acceptance receipt for final milestone {final_milestone.label!r}; "
        f"declared successors require acceptance evidence before initialisation\n"
    )
    return _result(
        "blocked",
        state,
        events,
        spec=spec,
        reason=(
            f"successor gate closed: chain complete but no acceptance receipt "
            f"for final milestone {final_milestone.label!r}"
        ),
    )


def _result(
    status: str,
    state: ChainState,
    events: list[dict[str, Any]],
    *,
    spec: ChainSpec | None = None,
    reason: str = "",
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


def _stop_for_closed_pr(
    *,
    spec_path: Path,
    state: ChainState,
    events: list[dict[str, Any]],
    spec: ChainSpec,
    milestone_label: str,
    pr_number: int,
) -> dict[str, Any]:
    state.last_state = "pr_closed"
    state.pr_state = "closed"
    chain_spec.save_chain_state(spec_path, state)
    return _result(
        "stopped",
        state,
        events,
        spec=spec,
        reason=f"milestone {milestone_label} PR #{pr_number} is closed",
    )


def _clear_stale_closed_pr_state(
    *,
    spec_path: Path,
    state: ChainState,
    milestone_label: str,
    log_fn: Callable[[str], None],
) -> ChainState:
    """Drop persisted PR context after a restart if the prior PR was closed.

    A closed milestone PR is a valid stop signal for the live run that observed
    it, but persisting that state as terminal wedges every later restart on the
    same milestone. Clearing the stale PR binding lets the chain resume the
    existing plan and recreate PR context if needed.
    """

    if state.last_state != "pr_closed":
        return state
    if state.pr_number is None and state.pr_state not in {None, "closed"}:
        return state
    log_fn(
        f"clearing stale closed PR context for {milestone_label}; "
        "resuming milestone with a fresh PR binding"
    )
    state.last_state = None
    state.pr_number = None
    state.pr_state = None
    chain_spec.save_chain_state(spec_path, state)
    return state


def format_chain_status(
    spec: ChainSpec,
    state: ChainState,
    *,
    spec_path: Path | None = None,
) -> dict[str, Any]:
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
    milestone_boundary_evidence: dict[str, Any] = {}
    if state.milestone_boundary_evidence:
        milestone_boundary_evidence = {
            label: {
                "milestone_label": entry.get("milestone_label"),
                "milestone_index": entry.get("milestone_index"),
                "plan_name": entry.get("plan_name"),
                "contract_id": entry.get("contract_id"),
                "contract_boundary_id": entry.get("contract_boundary_id"),
                "commit_ref": entry.get("commit_ref"),
                "tip_ref": entry.get("tip_ref"),
                "pr_head": entry.get("pr_head"),
                "pr_number": entry.get("pr_number"),
                "pr_state": entry.get("pr_state"),
            }
            for label, entry in state.milestone_boundary_evidence.items()
            if isinstance(entry, dict)
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
        "milestone_boundary_evidence": milestone_boundary_evidence,
        "policy": {
            "prerequisite_policy": spec.prerequisite_policy,
            "validation_policy": spec.validation_policy,
            "review_policy": dict(spec.review_policy or {}),
        },
    }
    if state.pr_number is not None:
        summary["pr_number"] = state.pr_number
        summary["pr_state"] = state.pr_state
    if spec_path is not None:
        from arnold_pipelines.megaplan.chain.execution_binding import (
            execution_binding_report,
        )

        summary["execution_binding"] = execution_binding_report(spec_path, state)
    return summary


def _write_chain_status_pretty(summary: dict[str, Any], *, writer) -> None:
    current = summary.get("current_milestone")
    current_label = "none"
    if isinstance(current, dict):
        current_label = f"{current['label']} (index {current['index']})"
    completed = summary.get("completed") or []
    remaining = summary.get("remaining") or []
    completed_labels = (
        ", ".join(item["label"] for item in completed) if completed else "none"
    )
    remaining_labels = (
        ", ".join(item["label"] for item in remaining) if remaining else "none"
    )
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
        writer(
            f"Current PR: #{summary['pr_number']} ({summary.get('pr_state') or 'unknown'})\n"
        )
    binding = summary.get("execution_binding")
    if isinstance(binding, dict) and binding.get("required"):
        expected = binding.get("expected") or {}
        active = binding.get("active") or {}
        writer(
            "Execution binding: "
            f"{binding.get('status')} "
            f"expected={str(expected.get('bundle_sha256') or 'missing')[:12]} "
            f"active={str(active.get('bundle_sha256') or 'missing')[:12]}\n"
        )
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
        writer(
            f"  Review (clean_milestone_pr): {review_policy.get('clean_milestone_pr', 'auto')}\n"
        )
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
    _add_chain_anchor_args(chain_parser)

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    start_parser.add_argument(
        "--spec", required=True, help="Path to the chain spec YAML"
    )
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
    _add_chain_anchor_args(start_parser)

    status_parser = chain_sub.add_parser(
        "status", help="Show persisted chain progress without driving"
    )
    status_parser.add_argument(
        "--spec", required=True, help="Path to the chain spec YAML"
    )
    status_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read chain state from this project directory instead of discovering from CWD.",
    )

    reconcile_source_parser = chain_sub.add_parser(
        "reconcile-source",
        help="Register a content-addressed canonical source update for a future milestone",
    )
    reconcile_source_parser.add_argument("--spec", required=True)
    reconcile_source_parser.add_argument("--project-dir", required=False)
    reconcile_source_parser.add_argument("--milestone", required=True)
    reconcile_source_parser.add_argument("--authoritative-source", required=True)
    reconcile_source_parser.add_argument("--reason", required=True)

    rebind_parser = chain_sub.add_parser(
        "rebind",
        help="Guardedly adopt a content-addressed successor chain without moving its cursor",
    )
    rebind_parser.add_argument("--spec", required=True)
    rebind_parser.add_argument("--project-dir", required=False)
    rebind_parser.add_argument("--from-bundle-sha256", required=True)
    rebind_parser.add_argument("--to-bundle-sha256", required=True)
    rebind_parser.add_argument("--expected-current-milestone", required=True)
    rebind_parser.add_argument(
        "--expected-current-plan",
        required=True,
        help="Exact current plan name, or @none when the cursor has no plan yet.",
    )
    rebind_parser.add_argument("--expected-next-milestone", required=True)
    rebind_parser.add_argument("--reason", required=True)
    rebind_parser.add_argument("--actor", default="operator")

    pause_parser = chain_sub.add_parser(
        "pause", help="Durably pause a chain and disable automatic recovery"
    )
    pause_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    pause_parser.add_argument("--project-dir", required=False)
    pause_parser.add_argument("--reason", required=True)
    pause_parser.add_argument("--actor", default="operator")

    resume_chain_parser = chain_sub.add_parser(
        "resume", help="Explicitly clear a durable operator pause"
    )
    resume_chain_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    resume_chain_parser.add_argument("--project-dir", required=False)
    resume_chain_parser.add_argument("--actor", default="operator")

    verify_parser = chain_sub.add_parser(
        "verify", help="Replay landed-diff completion evidence for completed milestones"
    )
    verify_parser.add_argument(
        "--spec", required=True, help="Path to the chain spec YAML"
    )
    verify_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read chain plans from this project directory instead of discovering from CWD.",
    )

    manifest_parser = chain_sub.add_parser(
        "manifest", help="Write a content-addressed completion manifest"
    )
    manifest_parser.add_argument(
        "--spec", required=True, help="Path to the completed chain spec YAML"
    )
    manifest_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read chain state from this project directory instead of discovering from CWD.",
    )
    manifest_parser.add_argument(
        "--proof-map",
        required=True,
        help=(
            "JSON mapping milestone labels to proof artifact paths. "
            "May also be an object with a top-level `milestones` mapping."
        ),
    )
    manifest_parser.add_argument(
        "--output",
        required=False,
        help=(
            "Output path for completion-manifest.json. Defaults beside chain.yaml; "
            "custom paths must stay in the chain spec directory."
        ),
    )

    override_parser = chain_sub.add_parser(
        "override", help="Set runtime policy overrides without editing chain.yaml"
    )
    override_parser.add_argument(
        "--spec", required=True, help="Path to the chain spec YAML"
    )
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
        "--fresh",
        action="store_true",
        default=False,
        help=(
            "With --in-worktree: remove an existing registered worktree/branch "
            "for this name before creating the new chain worktree."
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


def _add_chain_anchor_args(parser: Any) -> None:
    anchor_group = parser.add_mutually_exclusive_group()
    anchor_group.add_argument(
        "--require-anchor",
        dest="require_anchor",
        action="store_true",
        default=None,
        help="Require top-level anchors.north_star for this chain run (default unless spec opts out).",
    )
    anchor_group.add_argument(
        "--no-require-anchor",
        dest="require_anchor",
        action="store_false",
        default=None,
        help="Opt out of the default top-level anchors.north_star requirement for this chain run.",
    )
    parser.add_argument(
        "--missing-anchor-ack",
        default=None,
        help="Acknowledgement reason required when opting out and no top-level anchors.north_star is declared.",
    )


def run_chain_cli(
    root: Path, args: argparse.Namespace, *, writer=sys.stderr.write
) -> int:
    action = getattr(args, "chain_action", None)
    spec_arg = getattr(args, "spec", None)
    if not spec_arg:
        sys.stderr.write("megaplan chain: --spec is required\n")
        return 64
    spec_path = Path(spec_arg).expanduser().resolve()

    if action in {None, "start", "resume"}:
        from arnold_pipelines.megaplan.layout import retired_chain_marker

        retirement_marker = retired_chain_marker(spec_path, root)
        if retirement_marker is not None:
            return _emit_error(
                CliError(
                    "initiative_retired",
                    f"Refusing to start or resume retired initiative chain: {retirement_marker}",
                )
            )

    if action in {"pause", "resume"}:
        from arnold_pipelines.megaplan.chain.operator_pause import pause_chain, resume_chain

        project_root = root
        project_dir_arg = getattr(args, "project_dir", None)
        if isinstance(project_dir_arg, str) and project_dir_arg.strip():
            project_root = Path(project_dir_arg).expanduser().resolve()
        try:
            if action == "pause":
                payload = pause_chain(
                    spec_path,
                    project_root,
                    reason=args.reason,
                    actor=args.actor,
                )
            else:
                payload = resume_chain(spec_path, project_root, actor=args.actor)
        except CliError as exc:
            return _emit_error(exc)
        sys.stdout.write(
            json.dumps({"success": True, "spec": str(spec_path), **payload}, indent=2) + "\n"
        )
        return 0

    if action == "reconcile-source":
        try:
            spec = chain_spec.load_spec(spec_path)
            chain_state = chain_spec.load_chain_state(
                spec_path,
                verify_execution_binding=False,
            )
            from arnold_pipelines.megaplan.chain.source_admission import (
                require_milestone_source_update,
            )

            requirement = require_milestone_source_update(
                spec_path=spec_path,
                state=chain_state,
                spec=spec,
                milestone_label=args.milestone,
                authoritative_source=Path(args.authoritative_source).expanduser().resolve(),
                reason=args.reason,
            )
            chain_spec.save_chain_state(spec_path, chain_state)
        except CliError as exc:
            return _emit_error(exc)
        sys.stdout.write(
            json.dumps(
                {
                    "success": True,
                    "spec": str(spec_path),
                    "action": "reconcile-source",
                    "requirement": requirement,
                },
                indent=2,
            )
            + "\n"
        )
        return 0

    if action == "rebind":
        try:
            chain_state = chain_spec.load_chain_state(
                spec_path,
                verify_execution_binding=False,
            )
            before = chain_state.to_dict()
            from arnold_pipelines.megaplan.chain.execution_binding import (
                rebind_execution_identity,
            )

            result = rebind_execution_identity(
                spec_path,
                chain_state,
                expected_previous_bundle_sha256=args.from_bundle_sha256,
                expected_active_bundle_sha256=args.to_bundle_sha256,
                expected_current_milestone=args.expected_current_milestone,
                expected_current_plan=args.expected_current_plan,
                expected_next_milestone=args.expected_next_milestone,
                reason=args.reason,
                actor=args.actor,
            )
            after = chain_state.to_dict()
            for field in before:
                if field != "metadata" and before[field] != after[field]:
                    raise CliError(
                        "chain_execution_binding_drift",
                        f"chain rebind refused: operational field {field!r} changed",
                    )
            chain_spec.save_chain_state(spec_path, chain_state)
        except CliError as exc:
            return _emit_error(exc)
        sys.stdout.write(
            json.dumps(
                {
                    "success": True,
                    "spec": str(spec_path),
                    "action": "rebind",
                    **result,
                },
                indent=2,
            )
            + "\n"
        )
        return 0

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
            anchor_requirement = chain_spec.validate_anchor_requirement(
                spec,
                spec_path,
                require_anchor_override=getattr(args, "require_anchor", None),
                missing_anchor_ack_override=getattr(args, "missing_anchor_ack", None),
            )
            chain_spec.validate_paths(spec, root, spec_path=spec_path)
            # Status must remain observable during drift. It reports expected
            # versus active identity without normalizing or adopting either.
            chain_state = chain_spec.load_chain_state(
                spec_path,
                verify_execution_binding=False,
            )
        except CliError as exc:
            return _emit_error(exc)
        if anchor_requirement.warning:
            writer(f"[chain] WARNING: {anchor_requirement.warning}\n")
        runtime_overrides = chain_spec.load_runtime_policy(spec_path)
        effective_policy = chain_spec.effective_chain_policy(spec, runtime_overrides)
        summary = format_chain_status(spec, chain_state, spec_path=spec_path)
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
            "anchor_requirement": {
                "require_anchor": anchor_requirement.require_anchor,
                "missing_anchor_ack": anchor_requirement.missing_anchor_ack,
                "warning": anchor_requirement.warning,
            },
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if action == "verify":
        project_root = root
        project_dir_arg = getattr(args, "project_dir", None)
        if isinstance(project_dir_arg, str) and project_dir_arg.strip():
            project_root = Path(project_dir_arg).expanduser().resolve()
        try:
            spec = chain_spec.load_spec(spec_path)
            chain_spec.validate_paths(spec, project_root, spec_path=spec_path)
            chain_state = chain_spec.load_chain_state(spec_path)
        except CliError as exc:
            return _emit_error(exc)
        sys.stdout.write(
            json.dumps(
                _verify_completed_chain(project_root, spec_path, spec, chain_state),
                indent=2,
            )
            + "\n"
        )
        return 0

    if action == "manifest":
        project_root = root
        project_dir_arg = getattr(args, "project_dir", None)
        if isinstance(project_dir_arg, str) and project_dir_arg.strip():
            project_root = Path(project_dir_arg).expanduser().resolve()
        proof_map_arg = getattr(args, "proof_map", None)
        if not isinstance(proof_map_arg, str) or not proof_map_arg.strip():
            return _emit_error(CliError("invalid_args", "--proof-map is required"))
        proof_map_path = Path(proof_map_arg).expanduser()
        if not proof_map_path.is_absolute():
            proof_map_path = (project_root / proof_map_path).resolve()
        output_arg = getattr(args, "output", None)
        output_path: Path | None = None
        if isinstance(output_arg, str) and output_arg.strip():
            output_path = Path(output_arg).expanduser()
            if not output_path.is_absolute():
                output_path = (project_root / output_path).resolve()
        try:
            spec = chain_spec.load_spec(spec_path)
            chain_spec.validate_paths(spec, project_root, spec_path=spec_path)
            chain_state = chain_spec.load_chain_state(spec_path)
            payload = _write_completion_manifest(
                root=project_root,
                spec_path=spec_path,
                spec=spec,
                state=chain_state,
                proof_map_path=proof_map_path,
                output_path=output_path,
            )
        except CliError as exc:
            return _emit_error(exc)
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if action not in (None, "start"):
        return _emit_error(CliError("invalid_args", f"Unknown chain action: {action}"))

    no_git_refresh = bool(getattr(args, "no_git_refresh", False))
    no_push = bool(getattr(args, "no_push", False))
    one = bool(getattr(args, "one", False))
    fresh = bool(getattr(args, "fresh", False))
    require_anchor_override = getattr(args, "require_anchor", None)
    missing_anchor_ack_override = getattr(args, "missing_anchor_ack", None)
    try:
        spec_for_anchor_check = chain_spec.load_spec(spec_path)
        chain_spec.validate_anchor_requirement(
            spec_for_anchor_check,
            spec_path,
            require_anchor_override=require_anchor_override,
            missing_anchor_ack_override=missing_anchor_ack_override,
        )
        if supervisor_tier_routing_on():
            from arnold_pipelines.megaplan.supervisor.chain_runner import (
                run_chain as supervisor_run_chain,
            )

            result = supervisor_run_chain(
                spec_path,
                root,
                writer=writer,
                one=one,
                require_anchor_override=require_anchor_override,
                missing_anchor_ack_override=missing_anchor_ack_override,
            )
        else:
            result = run_chain(
                spec_path,
                root,
                no_git_refresh=no_git_refresh,
                no_push=no_push,
                one=one,
                fresh=fresh,
                require_anchor_override=require_anchor_override,
                missing_anchor_ack_override=missing_anchor_ack_override,
            )
    except CliError as exc:
        return _emit_error(exc)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if result["status"] in {"done", "paused", "awaiting_pr_merge"}:
        return 0
    return 1


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
