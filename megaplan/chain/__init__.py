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
        idea: .megaplan/briefs/foundation-store/M1-foundation-store.txt
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
        idea: .megaplan/briefs/foundation-store/M1a-settings-store.txt
    on_failure:
      abort: stop_chain          # stop_chain | skip_milestone | resume_milestone | retry_milestone
    on_escalate:
      abort: stop_chain          # stop_chain | skip_milestone | resume_milestone | retry_milestone

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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan chain requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    DriverOutcome,
    ESCALATE_ACTIONS,
    drive as auto_drive,
)
from megaplan._core import resolve_plan_dir
from megaplan._core.user_config import VALID_VENDORS
from megaplan.profiles import (
    VALID_CRITIC_CHOICES,
    VALID_DEEPSEEK_PROVIDER_CHOICES,
    VALID_DEPTH_CHOICES,
    _resolve_default_vendor,
    load_profile_metadata,
)
from megaplan.runtime.process import megaplan_engine_env, megaplan_engine_root
from megaplan.types import CliError, STATE_AWAITING_PR_MERGE, STATE_EXECUTED, STATE_FINALIZED

log = logging.getLogger("megaplan")


VALID_FAILURE_ACTIONS = (
    "stop_chain",
    "skip_milestone",
    "resume_milestone",
    "retry_milestone",
    "bump_profile",
    "bump_robustness",
)
VALID_MERGE_POLICIES = ("auto", "review")
VALID_CHAIN_SPEC_KEYS = frozenset(
    {
        "base_branch",
        "seed",
        "milestones",
        "on_failure",
        "on_escalate",
        "merge_policy",
        "prerequisite_policy",
        "validation_policy",
        "review_policy",
        "driver",
    }
)

# Autonomy-ladder bump ordering. These are the *one-tier-up* escalation maps
# the chain applies when a milestone exhausts its retry budget. There is no
# tier above ``apex`` (apex.toml is the top premium profile) — a bump_profile
# at apex is a no-op + warning, never an error.
PROFILE_BUMP_ORDER = ("premium", "apex")
ROBUSTNESS_BUMP_ORDER = ("thorough", "extreme")
DEPTH_BUMP_ORDER = ("high", "max")

# Default per-milestone retry budget before the ladder bumps.
# Capped at 1 for apex profile / extreme robustness milestones to bound cost.
DEFAULT_MILESTONE_RETRY_CAP = 2
APEX_EXTREME_RETRY_CAP = 1
RESUMABLE_RETRY_STATES = frozenset({"finalized", "executed", "critiqued", "gated"})


def _bump_one_tier(current: str | None, order: tuple[str, ...]) -> tuple[str | None, bool]:
    """Return (next_tier, bumped). At/above the top tier this is a no-op.

    *current* of ``None`` (unset) is treated as the bottom of the ladder so a
    bump moves to the second rung — the first explicit escalation tier.
    """
    if current is None:
        return order[1] if len(order) > 1 else order[0], len(order) > 1
    try:
        idx = order.index(current)
    except ValueError:
        # Unknown/custom tier — leave it alone rather than guess.
        return current, False
    if idx >= len(order) - 1:
        return current, False
    return order[idx + 1], True


@dataclass(frozen=True)
class FailurePolicy:
    """Structured autonomy ladder for ``on_failure`` / ``on_escalate``.

    YAML may declare either a plain string (abort-only, back-compat)::

        on_failure: stop_chain

    or a structured ladder mapping::

        on_failure:
          retry: retry_milestone     # or resume_milestone; walked first, bounded by a counter
          escalate: bump_profile     # walked once after retries exhaust
          abort: stop_chain          # terminal action

    ``retry`` / ``escalate`` are optional; ``abort`` defaults to ``stop_chain``.
    """

    abort: str = "stop_chain"
    retry: str | None = None
    escalate: str | None = None

    @classmethod
    def from_yaml(cls, value: Any, section: str, default_abort: str = "stop_chain") -> "FailurePolicy":
        # Plain string (or absent) → abort-only, back-compat.
        if value is None:
            return cls(abort=default_abort)
        if isinstance(value, str):
            if value not in VALID_FAILURE_ACTIONS:
                raise CliError(
                    "invalid_spec",
                    f"{section} must be one of {VALID_FAILURE_ACTIONS}; got {value!r}",
                )
            return cls(abort=value)
        if not isinstance(value, dict):
            raise CliError(
                "invalid_spec",
                f"`{section}` must be a string or a mapping of retry/escalate/abort",
            )

        def _check(key: str, fallback: str | None) -> str | None:
            raw = value.get(key, fallback)
            if raw is None:
                return None
            if raw not in VALID_FAILURE_ACTIONS:
                raise CliError(
                    "invalid_spec",
                    f"{section}.{key} must be one of {VALID_FAILURE_ACTIONS}; got {raw!r}",
                )
            return raw

        abort = _check("abort", default_abort) or default_abort
        retry = _check("retry", None)
        escalate = _check("escalate", None)
        return cls(abort=abort, retry=retry, escalate=escalate)

# Chain-level policy enums — conservative values following the
# VALID_MERGE_POLICIES module-level tuple pattern.  These are
# operator-facing contracts; renaming later is a breaking change.
# Validated in ChainSpec.from_dict() with CliError("invalid_spec", ...).
VALID_PREREQUISITE_POLICIES = ("none", "required")
VALID_VALIDATION_POLICIES = ("none", "required")
# review_policy.clean_milestone_pr
VALID_CLEAN_MILESTONE_PR_POLICIES = ("auto", "manual")
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


def _warn_chain_fallback(
    token: str,
    *,
    reason: str,
    path: Path | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    details = [f"reason={reason}"]
    if path is not None:
        details.append(f"path={path}")
    if context:
        for key in sorted(context):
            details.append(f"{key}={context[key]!r}")
    log.warning("%s chain fallback (%s)", token, ", ".join(details), exc_info=True)
BLOCKED_EXECUTE_OUTCOME_STATUSES = {"blocked", "worker_blocked"}


def _optional_choice(
    raw: dict[str, Any],
    key: str,
    choices: tuple[str, ...],
    *,
    index: int,
) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CliError("invalid_spec", f"milestones[{index}].{key} must be a string")
    if value not in choices:
        raise CliError(
            "invalid_spec",
            f"milestones[{index}].{key} must be one of {choices}; got {value!r}",
        )
    return value


def _optional_bool(raw: dict[str, Any], key: str, *, index: int) -> bool:
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise CliError("invalid_spec", f"milestones[{index}].{key} must be a boolean")
    return value


@dataclass
class MilestoneSpec:
    label: str
    idea: str
    branch: str | None = None
    profile: str | None = None
    robustness: str | None = None
    vendor: str | None = None
    depth: str | None = None
    critic: str | None = None
    deepseek_provider: str | None = None
    with_prep: bool = False
    with_feedback: bool = False
    prep_clarify: bool = True
    prep_direction: str | None = None
    phase_model: list[str] = field(default_factory=list)
    bakeoff: dict[str, Any] | None = None
    notes: str | None = None
    # Validation-only dependency edges (labels of milestones that MUST appear
    # earlier in the list). The chain runs strictly serial-in-listed-order — a
    # single cursor — so ``depends_on`` does NOT reorder or parallelize
    # execution. It is a topological-sort ASSERTION: ``ChainSpec.from_dict``
    # fails loud if a milestone declares a dependency that is not listed before
    # it, so the non-negotiable edges (e.g. m5-eval → m5-cal) cannot silently
    # drift out of order in a hand-edited chain.yaml. ``∥`` parallel tracks stay
    # prose — concurrency is never introduced here.
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "MilestoneSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", f"milestones[{index}] must be a mapping")
        label = raw.get("label")
        idea = raw.get("idea")
        if not isinstance(label, str) or not label.strip():
            raise CliError("invalid_spec", f"milestones[{index}].label is required")
        if not isinstance(idea, str) or not idea.strip():
            raise CliError("invalid_spec", f"milestones[{index}].idea is required")
        branch = raw.get("branch")
        if branch is not None and not isinstance(branch, str):
            raise CliError("invalid_spec", f"milestones[{index}].branch must be a string")
        profile = raw.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise CliError("invalid_spec", f"milestones[{index}].profile must be a string")
        robustness = raw.get("robustness")
        if robustness is not None and not isinstance(robustness, str):
            raise CliError("invalid_spec", f"milestones[{index}].robustness must be a string")
        vendor = _optional_choice(
            raw,
            "vendor",
            VALID_VENDORS,
            index=index,
        )
        depth = _optional_choice(
            raw,
            "depth",
            VALID_DEPTH_CHOICES,
            index=index,
        )
        critic = _optional_choice(
            raw,
            "critic",
            VALID_CRITIC_CHOICES,
            index=index,
        )
        deepseek_provider = _optional_choice(
            raw,
            "deepseek_provider",
            VALID_DEEPSEEK_PROVIDER_CHOICES,
            index=index,
        )
        with_prep = _optional_bool(raw, "with_prep", index=index)
        with_feedback = _optional_bool(raw, "with_feedback", index=index)
        prep_clarify_raw = raw.get("prep_clarify")
        if prep_clarify_raw is None:
            prep_clarify = True
        elif isinstance(prep_clarify_raw, bool):
            prep_clarify = prep_clarify_raw
        else:
            raise CliError("invalid_spec", f"milestones[{index}].prep_clarify must be a boolean")
        prep_direction_raw = raw.get("prep_direction")
        if prep_direction_raw is None:
            prep_direction = None
        elif isinstance(prep_direction_raw, str):
            stripped = prep_direction_raw.strip()
            if not stripped:
                raise CliError(
                    "invalid_spec",
                    f"milestones[{index}].prep_direction must be non-empty when provided",
                )
            prep_direction = stripped
        else:
            raise CliError(
                "invalid_spec",
                f"milestones[{index}].prep_direction must be a string",
            )
        phase_model_raw = raw.get("phase_model") or []
        if isinstance(phase_model_raw, str):
            phase_model = [phase_model_raw]
        elif isinstance(phase_model_raw, list) and all(isinstance(item, str) for item in phase_model_raw):
            phase_model = list(phase_model_raw)
        else:
            raise CliError("invalid_spec", f"milestones[{index}].phase_model must be a string or list of strings")
        bakeoff = raw.get("bakeoff")
        if bakeoff is not None and not isinstance(bakeoff, dict):
            raise CliError("invalid_spec", f"milestones[{index}].bakeoff must be a mapping")
        notes = raw.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise CliError("invalid_spec", f"milestones[{index}].notes must be a string")
        depends_on_raw = raw.get("depends_on") or []
        if isinstance(depends_on_raw, str):
            depends_on = [depends_on_raw]
        elif isinstance(depends_on_raw, list) and all(
            isinstance(item, str) and item.strip() for item in depends_on_raw
        ):
            depends_on = [item.strip() for item in depends_on_raw]
        else:
            raise CliError(
                "invalid_spec",
                f"milestones[{index}].depends_on must be a label or list of non-empty labels",
            )
        return cls(
            label=label,
            idea=idea,
            branch=branch,
            profile=profile,
            robustness=robustness,
            vendor=vendor,
            depth=depth,
            critic=critic,
            deepseek_provider=deepseek_provider,
            with_prep=with_prep,
            with_feedback=with_feedback,
            prep_clarify=prep_clarify,
            prep_direction=prep_direction,
            phase_model=phase_model,
            bakeoff=bakeoff,
            notes=notes,
            depends_on=depends_on,
        )


@dataclass
class ChainSpec:
    milestones: list[MilestoneSpec]
    seed_plan: str | None = None
    base_branch: str = "main"
    on_failure: str = "stop_chain"
    on_escalate: str = "stop_chain"
    # Structured autonomy ladders. ``on_failure``/``on_escalate`` above remain
    # the abort-only string for back-compat; these carry the full ladder.
    on_failure_policy: FailurePolicy = field(default_factory=FailurePolicy)
    on_escalate_policy: FailurePolicy = field(default_factory=FailurePolicy)
    merge_policy: str = "auto"
    # When true, assert each milestone's working base is a clean fork off the
    # base branch before plan init (auto-clean or fail-loud).
    require_clean_base: bool = False
    # Chain-level policies — conservative defaults (see VALID_* tuples above).
    prerequisite_policy: str = "none"
    validation_policy: str = "none"
    review_policy: dict[str, str] = field(default_factory=lambda: {"clean_milestone_pr": "auto"})
    # Driver knobs propagated into auto.drive for each plan.
    stall_threshold: int = DEFAULT_STALL_THRESHOLD
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS
    escalate_action: str = "force-proceed"  # passed to auto.drive on_escalate
    robustness: str = "standard"
    auto_approve: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", "chain spec must be a YAML mapping")
        unknown_keys = sorted(str(key) for key in raw if key not in VALID_CHAIN_SPEC_KEYS)
        if unknown_keys:
            if "base" in unknown_keys:
                raise CliError(
                    "invalid_spec",
                    "unknown top-level chain spec key `base`; did you mean `base_branch`?",
                )
            formatted = ", ".join(f"`{key}`" for key in unknown_keys)
            raise CliError(
                "invalid_spec",
                f"unknown top-level chain spec key(s): {formatted}",
            )
        base_branch = raw.get("base_branch", "main")
        if not isinstance(base_branch, str) or not base_branch.strip():
            raise CliError("invalid_spec", "`base_branch` must be a non-empty string")
        base_branch = base_branch.strip()
        milestones_raw = raw.get("milestones") or []
        if not isinstance(milestones_raw, list):
            raise CliError("invalid_spec", "`milestones` must be a list")
        milestones = [MilestoneSpec.from_dict(m, i) for i, m in enumerate(milestones_raw)]
        # Validation-only topological-order assertion: a milestone's declared
        # ``depends_on`` labels must each be a real milestone listed BEFORE it.
        # The chain executes strictly serial-in-listed-order; this only proves
        # the hand-authored list order respects the declared edges (e.g. the
        # non-negotiable m5-eval → m5-cal edge). It introduces no concurrency.
        seen_labels: set[str] = set()
        all_labels = {m.label for m in milestones}
        for i, m in enumerate(milestones):
            for dep in m.depends_on:
                if dep == m.label:
                    raise CliError(
                        "invalid_spec",
                        f"milestones[{i}] ({m.label!r}) cannot depend on itself",
                    )
                if dep not in all_labels:
                    raise CliError(
                        "invalid_spec",
                        f"milestones[{i}] ({m.label!r}) depends_on unknown milestone {dep!r}",
                    )
                if dep not in seen_labels:
                    raise CliError(
                        "invalid_spec",
                        f"milestones[{i}] ({m.label!r}) depends_on {dep!r} which is not "
                        f"listed before it; the chain runs serial-in-listed-order, so a "
                        f"dependency must appear earlier in `milestones`",
                    )
            seen_labels.add(m.label)
        seed_raw = raw.get("seed") or {}
        seed_plan: str | None = None
        if seed_raw:
            if not isinstance(seed_raw, dict):
                raise CliError("invalid_spec", "`seed` must be a mapping")
            seed_plan = seed_raw.get("plan")
            if seed_plan is not None and not isinstance(seed_plan, str):
                raise CliError("invalid_spec", "`seed.plan` must be a string")
            if isinstance(seed_plan, str) and not seed_plan.strip():
                seed_plan = None

        # Parse the failure/escalate sections as STRUCTURED ladders. A plain
        # string (or absence) is back-compat abort-only; a mapping reads
        # retry:/escalate:/abort: into a FailurePolicy.
        on_failure_policy = FailurePolicy.from_yaml(
            raw.get("on_failure"), "on_failure", "stop_chain"
        )
        on_escalate_policy = FailurePolicy.from_yaml(
            raw.get("on_escalate"), "on_escalate", "stop_chain"
        )
        # Back-compat scalar mirrors (the terminal abort action).
        on_failure = on_failure_policy.abort
        on_escalate = on_escalate_policy.abort
        merge_policy = raw.get("merge_policy", "auto")
        if merge_policy not in VALID_MERGE_POLICIES:
            raise CliError(
                "invalid_spec",
                f"merge_policy must be one of {VALID_MERGE_POLICIES}; got {merge_policy!r}",
            )

        # -- chain-level policies ---------------------------------------------------
        prerequisite_policy = raw.get("prerequisite_policy", "none")
        if prerequisite_policy not in VALID_PREREQUISITE_POLICIES:
            raise CliError(
                "invalid_spec",
                f"prerequisite_policy must be one of {VALID_PREREQUISITE_POLICIES}; got {prerequisite_policy!r}",
            )
        validation_policy = raw.get("validation_policy", "none")
        if validation_policy not in VALID_VALIDATION_POLICIES:
            raise CliError(
                "invalid_spec",
                f"validation_policy must be one of {VALID_VALIDATION_POLICIES}; got {validation_policy!r}",
            )
        # review_policy is a nested mapping: {clean_milestone_pr: auto|manual}
        review_raw = raw.get("review_policy") or {}
        if not isinstance(review_raw, dict):
            raise CliError(
                "invalid_spec",
                "`review_policy` must be a mapping",
            )
        clean_milestone_pr = review_raw.get("clean_milestone_pr", "auto")
        if clean_milestone_pr not in VALID_CLEAN_MILESTONE_PR_POLICIES:
            raise CliError(
                "invalid_spec",
                f"review_policy.clean_milestone_pr must be one of {VALID_CLEAN_MILESTONE_PR_POLICIES}; got {clean_milestone_pr!r}",
            )
        review_policy = {"clean_milestone_pr": clean_milestone_pr}

        driver_raw = raw.get("driver") or {}
        if not isinstance(driver_raw, dict):
            raise CliError("invalid_spec", "`driver` must be a mapping")
        stall = int(
            driver_raw.get(
                "max_stall_iterations",
                driver_raw.get("stall_threshold", DEFAULT_STALL_THRESHOLD),
            )
        )
        max_iter = int(driver_raw.get("max_iterations", DEFAULT_MAX_ITERATIONS))
        poll = float(driver_raw.get("poll_sleep", DEFAULT_POLL_SLEEP_SECONDS))
        phase_to = float(driver_raw.get("phase_timeout", DEFAULT_PHASE_TIMEOUT_SECONDS))
        status_to = float(driver_raw.get("status_timeout", DEFAULT_STATUS_TIMEOUT_SECONDS))
        esc = driver_raw.get("on_escalate", "force-proceed")
        if esc not in ESCALATE_ACTIONS:
            raise CliError(
                "invalid_spec",
                f"driver.on_escalate must be one of {ESCALATE_ACTIONS}; got {esc!r}",
            )
        robustness = driver_raw.get("robustness", "standard")
        if not isinstance(robustness, str):
            raise CliError("invalid_spec", "driver.robustness must be a string")
        auto_approve = bool(driver_raw.get("auto_approve", True))
        require_clean_base_raw = driver_raw.get("require_clean_base", False)
        if not isinstance(require_clean_base_raw, bool):
            raise CliError(
                "invalid_spec", "driver.require_clean_base must be a boolean"
            )
        require_clean_base = require_clean_base_raw

        return cls(
            milestones=milestones,
            seed_plan=seed_plan,
            base_branch=base_branch,
            on_failure=on_failure,
            on_escalate=on_escalate,
            on_failure_policy=on_failure_policy,
            on_escalate_policy=on_escalate_policy,
            require_clean_base=require_clean_base,
            merge_policy=merge_policy,
            prerequisite_policy=prerequisite_policy,
            validation_policy=validation_policy,
            review_policy=review_policy,
            stall_threshold=stall,
            max_iterations=max_iter,
            poll_sleep=poll,
            phase_timeout=phase_to,
            status_timeout=status_to,
            escalate_action=esc,
            robustness=robustness,
            auto_approve=auto_approve,
        )


@dataclass
class ChainState:
    """Persisted progress for a chain run.

    ``current_milestone_index`` is -1 before any milestone starts (seed phase),
    0 for the first milestone, etc. ``current_plan_name`` is the plan currently
    being driven. ``last_state`` is the terminal driver status string from the
    most recently completed plan.
    """

    current_milestone_index: int = -1
    current_plan_name: str | None = None
    current_milestone_base_sha: str | None = None
    last_state: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)
    # PR/branch sync fields (see megaplan.types SYNC_CLEAN / SYNC_STALE / SYNC_DIRTY).
    branch_head: str | None = None
    pr_head: str | None = None
    last_pushed_commit: str | None = None
    dirty_flag: bool = False
    sync_state: str | None = None
    # Slot-first watchdog fields.
    extra_repos: list[str] = field(default_factory=list)
    chain_session: str | None = None
    resolved_workspace: str | None = None
    extra_repo_sync: list[dict[str, Any]] = field(default_factory=list)
    # Completion-verification contract mode pinned for the whole chain
    # (off | shadow | warn | enforce). Default "shadow" = compute + persist +
    # log a milestone verdict, never block, never run the suite.
    completion_contract_mode: str = "shadow"
    # Autonomy-ladder bookkeeping, keyed by milestone label so it survives
    # resume regardless of index drift. ``retry_counts`` is the number of FRESH
    # re-inits already spent on a milestone; ``ladder_stage`` records how far up
    # the bump ladder a milestone has climbed ("retry" → "bump" → terminal);
    # ``profile_bumps`` / ``robustness_bumps`` / ``depth_bumps`` persist the
    # escalated tier overrides applied for the next re-init.
    retry_counts: dict[str, int] = field(default_factory=dict)
    reground_decisions: dict[str, Any] = field(default_factory=dict)
    ladder_stage: dict[str, str] = field(default_factory=dict)
    profile_bumps: dict[str, str] = field(default_factory=dict)
    robustness_bumps: dict[str, str] = field(default_factory=dict)
    depth_bumps: dict[str, str] = field(default_factory=dict)
    # Enforce-block retry counts keyed by milestone label; tracks how many
    # times enforce mode has blocked a milestone and routed it back for retry.
    enforce_revise_counts: dict[str, int] = field(default_factory=dict)
    # Divergence fingerprints and carry-forward manifests, keyed by
    # milestone_label.  Used by the repeated-divergence halt guard to detect
    # when a milestone produces the same changed-file signature across retries.
    #
    # divergence_fingerprints entry schema:
    #   {
    #     "fingerprint": str,           # sorted SHA of changed-file list
    #     "first_seen_at": str,         # ISO-8601 timestamp
    #     "consecutive_count": int,     # runs in a row with this fingerprint
    #   }
    #
    # carry_forward_manifests entry schema:
    #   {
    #     "base_sha": str | None,       # git SHA of milestone base commit
    #     "head_sha": str,              # git SHA of HEAD at review time
    #     "changed_files": list[str],   # files in the milestone diff
    #     "divergences": list[str],     # human-readable divergence notes
    #     "source": str,                # "declared" | "heuristic_merge_base"
    #     "captured_at": str,           # ISO-8601 timestamp
    #     "milestone_label": str,       # label of the originating milestone
    #   }
    divergence_fingerprints: dict[str, Any] = field(default_factory=dict)
    carry_forward_manifests: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_milestone_index": self.current_milestone_index,
            "current_plan_name": self.current_plan_name,
            "current_milestone_base_sha": self.current_milestone_base_sha,
            "last_state": self.last_state,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
            "completed": list(self.completed),
            "branch_head": self.branch_head,
            "pr_head": self.pr_head,
            "last_pushed_commit": self.last_pushed_commit,
            "dirty_flag": self.dirty_flag,
            "sync_state": self.sync_state,
            "extra_repos": list(self.extra_repos),
            "chain_session": self.chain_session,
            "resolved_workspace": self.resolved_workspace,
            "extra_repo_sync": list(self.extra_repo_sync),
            "completion_contract_mode": self.completion_contract_mode,
            "retry_counts": dict(self.retry_counts),
            "reground_decisions": dict(self.reground_decisions),
            "ladder_stage": dict(self.ladder_stage),
            "profile_bumps": dict(self.profile_bumps),
            "robustness_bumps": dict(self.robustness_bumps),
            "depth_bumps": dict(self.depth_bumps),
            "enforce_revise_counts": dict(self.enforce_revise_counts),
            "divergence_fingerprints": dict(self.divergence_fingerprints),
            "carry_forward_manifests": dict(self.carry_forward_manifests),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainState":
        # Shape-validate optional new fields with fallback defaults for
        # backward compatibility with old state JSON.
        extra_repos = raw.get("extra_repos")
        if not isinstance(extra_repos, list) or any(
            not isinstance(item, str) or not item for item in extra_repos
        ):
            extra_repos = []

        chain_session = raw.get("chain_session")
        if chain_session is not None and (
            not isinstance(chain_session, str) or not chain_session.strip()
        ):
            chain_session = None

        resolved_workspace = raw.get("resolved_workspace")
        if resolved_workspace is not None and (
            not isinstance(resolved_workspace, str) or not resolved_workspace.strip()
        ):
            resolved_workspace = None

        extra_repo_sync = raw.get("extra_repo_sync")
        if not isinstance(extra_repo_sync, list):
            extra_repo_sync = []

        from megaplan.orchestration.completion_contract import (
            normalize_contract_mode,
        )

        completion_contract_mode = normalize_contract_mode(
            raw.get("completion_contract_mode")
        )

        def _str_int_map(value: Any) -> dict[str, int]:
            if not isinstance(value, dict):
                return {}
            out: dict[str, int] = {}
            for key, val in value.items():
                if isinstance(key, str):
                    try:
                        out[key] = int(val)
                    except (TypeError, ValueError):
                        continue
            return out

        def _str_str_map(value: Any) -> dict[str, str]:
            if not isinstance(value, dict):
                return {}
            return {
                key: val
                for key, val in value.items()
                if isinstance(key, str) and isinstance(val, str)
            }

        def _str_any_map(value: Any) -> dict[str, Any]:
            if not isinstance(value, dict):
                return {}
            return {key: val for key, val in value.items() if isinstance(key, str)}

        return cls(
            current_milestone_index=int(raw.get("current_milestone_index", -1)),
            current_plan_name=raw.get("current_plan_name"),
            current_milestone_base_sha=raw.get("current_milestone_base_sha"),
            last_state=raw.get("last_state"),
            pr_number=int(raw["pr_number"]) if raw.get("pr_number") is not None else None,
            pr_state=raw.get("pr_state"),
            completed=list(raw.get("completed") or []),
            branch_head=raw.get("branch_head"),
            pr_head=raw.get("pr_head"),
            last_pushed_commit=raw.get("last_pushed_commit"),
            dirty_flag=bool(raw.get("dirty_flag", False)),
            sync_state=raw.get("sync_state"),
            extra_repos=extra_repos,
            chain_session=chain_session,
            resolved_workspace=resolved_workspace,
            extra_repo_sync=extra_repo_sync,
            completion_contract_mode=completion_contract_mode,
            retry_counts=_str_int_map(raw.get("retry_counts")),
            reground_decisions=_str_any_map(raw.get("reground_decisions")),
            ladder_stage=_str_str_map(raw.get("ladder_stage")),
            profile_bumps=_str_str_map(raw.get("profile_bumps")),
            robustness_bumps=_str_str_map(raw.get("robustness_bumps")),
            depth_bumps=_str_str_map(raw.get("depth_bumps")),
            enforce_revise_counts=_str_int_map(raw.get("enforce_revise_counts")),
            divergence_fingerprints=_str_any_map(raw.get("divergence_fingerprints")),
            carry_forward_manifests=_str_any_map(raw.get("carry_forward_manifests")),
        )


def _chain_runtime_dir_for(spec_path: Path) -> Path:
    spec_resolved = spec_path.resolve()
    parts = spec_resolved.parts
    for index, part in enumerate(parts):
        if part == ".megaplan" and index + 1 < len(parts) and parts[index + 1] == "briefs":
            repo_root = Path(*parts[:index])
            return repo_root / ".megaplan" / "plans" / ".chains"
    return spec_resolved.parent / ".megaplan" / "plans" / ".chains"


def _state_path_for(spec_path: Path) -> Path:
    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return _chain_runtime_dir_for(spec_path) / f"{spec_resolved.stem}-{digest}.json"


def _legacy_state_path_for(spec_path: Path) -> Path:
    return spec_path.with_name("chain_state.json")


def load_spec(spec_path: Path) -> ChainSpec:
    if not spec_path.exists():
        raise CliError("invalid_spec", f"spec file not found: {spec_path}")
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CliError("invalid_spec", f"YAML parse error: {exc}") from exc
    return ChainSpec.from_dict(raw or {})


def load_chain_state(spec_path: Path) -> ChainState:
    state_path = _state_path_for(spec_path)
    if not state_path.exists():
        legacy_path = _legacy_state_path_for(spec_path)
        if legacy_path.exists():
            state_path = legacy_path
    if not state_path.exists():
        return ChainState()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("invalid_chain_state", f"chain_state.json is invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CliError("invalid_chain_state", "chain_state.json must be an object")
    return ChainState.from_dict(raw)


def save_chain_state(spec_path: Path, state: ChainState) -> None:
    state_path = _state_path_for(spec_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def _spec_milestone_branches(spec: ChainSpec) -> list[str]:
    branches: list[str] = []
    seen: set[str] = set()
    for milestone in spec.milestones:
        branch = milestone.branch
        if branch and branch not in seen:
            seen.add(branch)
            branches.append(branch)
    return branches


def reset_chain_anchors(
    spec_path: Path,
    root: Path,
    spec: ChainSpec,
    *,
    writer=sys.stdout.write,
    include_remote_branches: bool = True,
) -> dict[str, Any]:
    """Remove resume anchors for one chain spec before an explicit fresh start."""
    removed_state: list[str] = []
    for state_path in (_state_path_for(spec_path), _legacy_state_path_for(spec_path)):
        if state_path.exists():
            state_path.unlink()
            removed_state.append(str(state_path))

    removed_local_branches: list[str] = []
    removed_remote_branches: list[str] = []
    skipped_remote_branches: list[str] = []
    for branch in _spec_milestone_branches(spec):
        local = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if local.returncode == 0:
            _run_command(
                root,
                ["git", "branch", "-D", branch],
                writer=writer,
                error_code="chain_reset_failed",
            )
            removed_local_branches.append(branch)
        elif local.returncode not in (1,):
            raise CliError(
                "chain_reset_failed",
                f"could not inspect local branch {branch!r}: git show-ref exited {local.returncode}",
                extra={"branch": branch, "stdout": local.stdout, "stderr": local.stderr},
            )

        if include_remote_branches:
            if _remote_branch_exists(root, branch, writer=writer):
                _run_command(
                    root,
                    ["git", "push", "origin", "--delete", branch],
                    writer=writer,
                    error_code="chain_reset_failed",
                )
                removed_remote_branches.append(branch)
        else:
            skipped_remote_branches.append(branch)

    return {
        "state_files": removed_state,
        "local_branches": removed_local_branches,
        "remote_branches": removed_remote_branches,
        "skipped_remote_branches": skipped_remote_branches,
    }


def _completed_records_by_label(state: ChainState) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for entry in state.completed:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        if isinstance(label, str) and label:
            records[label] = entry
    return records


def _upsert_completed_record(state: ChainState, record: dict[str, Any]) -> None:
    label = record.get("label")
    if not isinstance(label, str) or not label:
        state.completed.append(record)
        return
    for index in range(len(state.completed) - 1, -1, -1):
        entry = state.completed[index]
        if isinstance(entry, dict) and entry.get("label") == label:
            state.completed[index] = record
            return
    state.completed.append(record)


def _completed_record_for_label(state: ChainState, label: str) -> dict[str, Any] | None:
    return _completed_records_by_label(state).get(label)


def _load_contract_for_completed_record(root: Path, record: dict[str, Any]) -> dict[str, Any] | None:
    """Load the plan contract for a completed record.

    Prefers the current ``contract.json`` in the plan directory. When that
    file is missing, falls back to reading it from the git commit stored in
    ``artifact_commit_sha`` via ``read_plan_artifact_from_commit``.  The
    loaded payload is normalized through ``normalize_contract_payload``.

    Returns ``None`` when the record has no usable plan name or the contract
    cannot be found through either path.
    """
    from megaplan.chain.git_ops import read_plan_artifact_from_commit
    from megaplan.orchestration.plan_contracts import normalize_contract_payload

    plan_name = record.get("plan")
    if not isinstance(plan_name, str) or not plan_name.strip():
        return None

    plan_dir = root / ".megaplan" / "plans" / plan_name
    contract_path = plan_dir / "contract.json"

    # Prefer the current artifact on disk.
    if contract_path.exists():
        try:
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            return normalize_contract_payload(payload)
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to the commit artifact.
    commit_sha = record.get("artifact_commit_sha")
    if isinstance(commit_sha, str) and commit_sha.strip():
        rel_path = f".megaplan/plans/{plan_name}/contract.json"
        try:
            content = read_plan_artifact_from_commit(root, commit_sha.strip(), rel_path)
            if content is not None:
                payload = json.loads(content)
                return normalize_contract_payload(payload)
        except (json.JSONDecodeError, CliError):
            pass

    return None


def _contract_context_for_plan_only_milestone(
    root: Path,
    milestone: MilestoneSpec,
    state: ChainState,
) -> dict[str, Any]:
    from megaplan.orchestration.plan_contracts import provided_paths_by_milestone

    records = _completed_records_by_label(state)
    upstream_contracts: list[dict[str, Any]] = []
    dependency_labels: list[str] = []
    for label in milestone.depends_on:
        record = records.get(label)
        if not isinstance(record, dict) or record.get("status") not in {"finalized", "done"}:
            continue
        contract = _load_contract_for_completed_record(root, record)
        if contract is None:
            continue
        dependency_labels.append(label)
        upstream_contracts.append(
            {
                "milestone_label": label,
                "provides": list(contract.get("provides", [])),
                "assumes": list(contract.get("assumes", [])),
            }
        )
    return {
        "plan_only": True,
        "milestone_label": milestone.label,
        "dependency_labels": dependency_labels,
        "upstream_contracts": upstream_contracts,
        "provided_paths": provided_paths_by_milestone(upstream_contracts),
    }


def _chain_review_path(spec_path: Path) -> Path:
    return _chain_runtime_dir_for(spec_path) / f"{spec_path.stem}.review.md"


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _write_chain_review(
    root: Path,
    spec_path: Path,
    spec: ChainSpec,
    state: ChainState,
    *,
    partial_reason: str | None = None,
) -> Path:
    from megaplan.orchestration.plan_contracts import diff_assumes_against_provides

    records = _completed_records_by_label(state)
    loaded_contracts: dict[str, dict[str, Any]] = {}
    for label, record in records.items():
        if not isinstance(record, dict) or record.get("status") not in {"finalized", "done"}:
            continue
        contract = _load_contract_for_completed_record(root, record)
        if contract is not None:
            loaded_contracts[label] = contract

    rows: list[dict[str, str]] = []
    for milestone in spec.milestones:
        downstream_contract = loaded_contracts.get(milestone.label)
        if downstream_contract is None or not downstream_contract.get("assumes"):
            continue
        upstream_contracts = [
            {
                "milestone_label": label,
                "provides": list(loaded_contracts[label].get("provides", [])),
                "assumes": list(loaded_contracts[label].get("assumes", [])),
            }
            for label in milestone.depends_on
            if label in loaded_contracts
        ]
        rows.extend(
            diff_assumes_against_provides(
                downstream_contract,
                upstream_contracts,
                downstream_label=milestone.label,
            )
        )

    status_counts = {status: 0 for status in ("OK", "MISSING_UPSTREAM", "MISMATCH")}
    for row in rows:
        status = row.get("status")
        if status in status_counts:
            status_counts[status] += 1

    lines = [
        f"# Chain Review: {spec_path.stem}",
        "",
        f"- Status: {'partial' if partial_reason else 'complete'}",
        f"- Partial reason: {partial_reason or ''}",
        f"- Completed records considered: {len(records)}",
        f"- Contracts loaded: {len(loaded_contracts)}",
        f"- OK: {status_counts['OK']}",
        f"- MISSING_UPSTREAM: {status_counts['MISSING_UPSTREAM']}",
        f"- MISMATCH: {status_counts['MISMATCH']}",
        "",
        "| Downstream | Upstream | Symbol | Expected Path | Actual Path | Expected Signature | Actual Signature | Status | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if rows:
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(row.get(key, ""))
                    for key in (
                        "downstream_label",
                        "upstream_label",
                        "symbol",
                        "expected_path",
                        "actual_path",
                        "expected_signature",
                        "actual_signature",
                        "status",
                        "note",
                    )
                )
                + " |"
            )
    else:
        lines.append("|  |  |  |  |  |  |  | OK | No Provides-to-Assumes rows. |")

    path = _chain_review_path(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _read_plan_state_payload(root: Path, plan_name: str) -> dict[str, Any] | None:
    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        plan_dir = root / ".megaplan" / "plans" / plan_name
    state_path = plan_dir / "state.json"
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _plan_current_state_from_payload(root: Path, plan_name: str) -> str | None:
    raw = _read_plan_state_payload(root, plan_name)
    current = raw.get("current_state") if isinstance(raw, dict) else None
    return current if isinstance(current, str) else None


def _apply_reground_replan(
    root: Path,
    plan_name: str,
    decision: dict[str, Any],
) -> None:
    from megaplan.handlers.override import apply_override_replan

    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError:
        plan_dir = root / ".megaplan" / "plans" / plan_name
    raw_state = _read_plan_state_payload(root, plan_name)
    if not isinstance(raw_state, dict):
        raise CliError(
            "missing_reground_plan_state",
            f"cannot apply reground replan: plan {plan_name!r} has no readable state.json",
        )
    summary = _reground_diff_summary(decision)
    apply_override_replan(
        root,
        plan_dir,
        raw_state,
        reason=f"Contract drift detected before execute. {summary}",
        note=summary,
    )


def _reground_skip_decision(milestone: MilestoneSpec, reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "milestone_label": milestone.label,
        "reason": reason,
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def _record_execute_reground_decision(
    root: Path,
    state: ChainState,
    milestone: MilestoneSpec,
    plan_name: str,
    downstream_record: dict[str, Any] | None,
) -> dict[str, Any]:
    from megaplan.orchestration.plan_contracts import (
        MATERIAL_CONTRACT_STATUSES,
        contract_diff_fingerprint,
        diff_assumes_against_provides,
    )

    if not milestone.depends_on:
        decision = _reground_skip_decision(milestone, "no_dependencies")
        state.reground_decisions[milestone.label] = decision
        return decision
    if not isinstance(downstream_record, dict) or downstream_record.get("status") != "finalized":
        decision = _reground_skip_decision(milestone, "downstream_not_finalized")
        state.reground_decisions[milestone.label] = decision
        return decision

    plan_state = _read_plan_state_payload(root, plan_name)
    meta = (plan_state or {}).get("meta")
    chain_policy = meta.get("chain_policy") if isinstance(meta, dict) else None
    contract_context = chain_policy.get("contract_context") if isinstance(chain_policy, dict) else None
    if not isinstance(contract_context, dict) or contract_context.get("plan_only") is not True:
        decision = _reground_skip_decision(milestone, "not_plan_only")
        state.reground_decisions[milestone.label] = decision
        return decision

    downstream_contract = _load_contract_for_completed_record(root, downstream_record)
    if downstream_contract is None:
        decision = _reground_skip_decision(milestone, "downstream_contract_unavailable")
        state.reground_decisions[milestone.label] = decision
        return decision
    if not downstream_contract.get("assumes"):
        decision = _reground_skip_decision(milestone, "downstream_assumes_empty")
        state.reground_decisions[milestone.label] = decision
        return decision

    records = _completed_records_by_label(state)
    upstream_contracts: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for label in milestone.depends_on:
        record = records.get(label)
        contract = _load_contract_for_completed_record(root, record) if isinstance(record, dict) else None
        if contract is None:
            unavailable.append(label)
            continue
        upstream_contracts.append(
            {
                "milestone_label": label,
                "provides": list(contract.get("provides", [])),
                "assumes": list(contract.get("assumes", [])),
            }
        )
    if unavailable:
        decision = _reground_skip_decision(
            milestone,
            "upstream_contract_unavailable:" + ",".join(sorted(unavailable)),
        )
        state.reground_decisions[milestone.label] = decision
        return decision
    if not any(contract.get("provides") for contract in upstream_contracts):
        decision = _reground_skip_decision(milestone, "upstream_provides_empty")
        state.reground_decisions[milestone.label] = decision
        return decision

    diff_rows = diff_assumes_against_provides(
        downstream_contract,
        upstream_contracts,
        downstream_label=milestone.label,
    )
    material_rows = [
        row for row in diff_rows if row.get("status") in MATERIAL_CONTRACT_STATUSES
    ]
    decision = {
        "status": "drift" if material_rows else "pass",
        "milestone_label": milestone.label,
        "dependency_labels": list(milestone.depends_on),
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "diff_row_count": len(diff_rows),
        "material_diff_count": len(material_rows),
        "material_fingerprint": contract_diff_fingerprint(material_rows),
        "material_diffs": material_rows,
    }
    state.reground_decisions[milestone.label] = decision
    return decision


def _reground_diff_summary(decision: dict[str, Any]) -> str:
    rows = decision.get("material_diffs")
    if not isinstance(rows, list) or not rows:
        return "No material contract drift rows."
    parts: list[str] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        upstream = row.get("upstream_label") or "<unknown>"
        symbol = row.get("symbol") or "<unknown>"
        status = row.get("status") or "MISMATCH"
        note = row.get("note") or ""
        parts.append(f"{status} {upstream}:{symbol}" + (f" ({note})" if note else ""))
    suffix = ""
    if len(rows) > len(parts):
        suffix = f"; +{len(rows) - len(parts)} more"
    return "; ".join(parts) + suffix


def _load_finalized_record_state(
    root: Path,
    label: str,
    record: dict[str, Any],
) -> tuple[str, Path, dict[str, Any]]:
    plan_name = record.get("plan")
    if not isinstance(plan_name, str) or not plan_name.strip():
        raise CliError(
            "missing_finalized_plan",
            f"execute mode cannot resume milestone {label!r}: finalized record has no plan name",
        )
    fallback_plan_dir = root / ".megaplan" / "plans" / plan_name
    try:
        plan_dir = resolve_plan_dir(root, plan_name)
    except CliError as exc:
        if fallback_plan_dir.exists() and fallback_plan_dir.is_dir():
            plan_dir = fallback_plan_dir
        else:
            raise CliError(
                "missing_finalized_plan_dir",
                f"execute mode cannot resume milestone {label!r}: plan {plan_name!r} is missing",
            ) from exc
    state_path = plan_dir / "state.json"
    if not state_path.exists():
        raise CliError(
            "missing_finalized_state",
            f"execute mode cannot resume milestone {label!r}: {state_path} is missing",
        )
    try:
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(
            "invalid_finalized_state",
            f"execute mode cannot resume milestone {label!r}: {state_path} is invalid JSON",
        ) from exc
    if not isinstance(raw_state, dict) or raw_state.get("current_state") != STATE_FINALIZED:
        raise CliError(
            "non_resumable_finalized_state",
            f"execute mode cannot resume milestone {label!r}: plan {plan_name!r} is not finalized",
        )
    return plan_name, state_path, raw_state


def _reset_execute_plan_state_for_fresh_approval(
    state_path: Path,
    raw_state: dict[str, Any],
) -> None:
    meta = raw_state.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        raw_state["meta"] = meta
    meta.pop("user_approved_gate", None)

    config = raw_state.get("config")
    if not isinstance(config, dict):
        config = {}
        raw_state["config"] = config
    config["auto_approve"] = False

    state_path.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")


def _completed_record_for_status(
    state: ChainState,
    milestone: MilestoneSpec,
) -> dict[str, Any] | None:
    return _completed_record_for_label(state, milestone.label)


def _completed_record_branch(record: dict[str, Any] | None) -> str | None:
    if not isinstance(record, dict):
        return None
    branch = record.get("plan_branch")
    return branch if isinstance(branch, str) and branch else None


def _prepare_execute_mode_state(root: Path, spec: ChainSpec, state: ChainState) -> bool:
    records = _completed_records_by_label(state)
    if spec.seed_plan:
        seed_record = records.get("seed")
        if seed_record is None:
            raise CliError(
                "missing_finalized_record",
                "execute mode cannot start seed plan: no finalized or done record found",
            )
        seed_status = seed_record.get("status")
        if seed_status == "finalized":
            plan_name, state_path, raw_state = _load_finalized_record_state(
                root,
                "seed",
                seed_record,
            )
            _reset_execute_plan_state_for_fresh_approval(state_path, raw_state)
            state.current_milestone_index = -1
            state.current_plan_name = plan_name
            state.last_state = STATE_FINALIZED
            state.pr_number = None
            state.pr_state = None
            return False
        if seed_status != "done":
            raise CliError(
                "missing_finalized_record",
                f"execute mode cannot start seed plan: record status is {seed_status!r}, expected finalized or done",
            )
    for idx, milestone in enumerate(spec.milestones):
        record = records.get(milestone.label)
        if record is None:
            raise CliError(
                "missing_finalized_record",
                f"execute mode cannot start milestone {milestone.label!r}: no finalized or done record found",
            )
        status = record.get("status")
        if status == "done":
            continue
        if status != "finalized":
            raise CliError(
                "missing_finalized_record",
                f"execute mode cannot start milestone {milestone.label!r}: record status is {status!r}, expected finalized or done",
            )
        if (
            state.last_state == STATE_AWAITING_PR_MERGE
            and state.current_milestone_index == idx
        ):
            plan_name, _state_path, _raw_state = _load_finalized_record_state(
                root,
                milestone.label,
                record,
            )
            state.current_milestone_index = idx
            state.current_plan_name = plan_name
            return False
        plan_name, state_path, raw_state = _load_finalized_record_state(
            root,
            milestone.label,
            record,
        )
        _reset_execute_plan_state_for_fresh_approval(state_path, raw_state)
        state.current_milestone_index = idx
        state.current_plan_name = plan_name
        state.last_state = STATE_FINALIZED
        state.pr_number = None
        state.pr_state = None
        return False
    state.current_milestone_index = len(spec.milestones)
    state.current_plan_name = None
    state.pr_number = None
    state.pr_state = None
    return True


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
        # The idea brief is an immutable artifact. If it lives outside the
        # project repo (e.g. an absolute path to a brief authored elsewhere),
        # git cannot add it. Copy it into the plan dir so the in-repo copy is
        # what gets persisted. When the idea is already inside the repo we add
        # it in place, preserving prior behavior.
        resolved_idea = idea_path.resolve()
        root_resolved = root.resolve()
        if resolved_idea.is_relative_to(root_resolved):
            artifacts.append(idea_path)
        else:
            idea_copy = plan_dir / "idea.md"
            idea_copy.parent.mkdir(parents=True, exist_ok=True)
            # Only copy when content differs to avoid redundant churn.
            new_content = resolved_idea.read_bytes()
            if not idea_copy.exists() or idea_copy.read_bytes() != new_content:
                idea_copy.write_bytes(new_content)
            artifacts.append(idea_copy)
    return artifacts


def _resolve_idea_path(root: Path, idea: str) -> Path:
    idea_path = Path(idea).expanduser()
    if idea_path.is_absolute():
        return idea_path
    return root / idea_path


# ---------------------------------------------------------------------------
# Runtime policy artifact helpers
# ---------------------------------------------------------------------------


def _runtime_policy_path_for(spec_path: Path) -> Path:
    """Return the path for the runtime policy override artifact.

    Placed alongside the chain state file in ``.megaplan/plans/.chains/``
    using the same stem+digest naming convention.
    """
    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return (
        spec_resolved.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{spec_resolved.stem}-{digest}.runtime_policy.json"
    )


def load_runtime_policy(spec_path: Path) -> dict[str, Any]:
    """Load the runtime policy override artifact for *spec_path*.

    Returns an empty dict when no artifact exists so callers never need to
    guard against ``None``.
    """
    path = _runtime_policy_path_for(spec_path)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _warn_chain_fallback(
            "M3A_WARN_CHAIN_POLICY_READ",
            reason="corrupt_json",
            path=path,
        )
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def save_runtime_policy(spec_path: Path, overrides: dict[str, Any]) -> None:
    """Persist *overrides* as the runtime policy override artifact.

    The caller is responsible for validating keys/values before calling this.
    This writes only the override artifact — never touches chain.yaml.
    """
    path = _runtime_policy_path_for(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(overrides, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def effective_chain_policy(
    spec: ChainSpec,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge runtime overrides with spec-level policy defaults.

    Returns a plain dict suitable for serialization in status payloads,
    plan metadata, and cloud preflight output.  Runtime overrides always
    win over the static YAML values.
    """
    overrides = overrides or {}
    prerequisite_policy = overrides.get("prerequisite_policy", spec.prerequisite_policy)
    validation_policy = overrides.get("validation_policy", spec.validation_policy)
    # review_policy is stored as a dict on the spec; keep it as a dict here.
    review_from_spec = spec.review_policy or {}
    review_from_override = overrides.get("review_policy") or {}
    clean_milestone_pr = review_from_override.get(
        "clean_milestone_pr",
        review_from_spec.get("clean_milestone_pr", "auto"),
    )
    return {
        "prerequisite_policy": prerequisite_policy,
        "validation_policy": validation_policy,
        "review_policy": {"clean_milestone_pr": clean_milestone_pr},
        # Record whether any override was active so consumers can trace provenance.
        "source": "runtime_override" if overrides else "chain_yaml",
    }


def _merge_chain_policy_keys(plan_dir: Path, updates: dict[str, Any]) -> None:
    """Merge keys into plan state ``meta.chain_policy``.

    Reads ``plan_dir/state.json``, navigates to ``meta.chain_policy``
    (creating intermediate dicts if missing), then merges *updates* via
    top-level key overwrite — callers supply full sub-key values; there is
    no deep merge. Silently returns when ``state.json`` is absent or
    unreadable. Best-effort mirror, never crashes.
    """
    from megaplan._core import read_json
    from megaplan._core.state import write_plan_state

    state_path = plan_dir / "state.json"
    if not state_path.exists():
        return
    try:
        state = read_json(state_path)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return
    if not isinstance(state, dict):
        return

    def _apply(current: dict[str, Any]) -> bool:
        meta = current.setdefault("meta", {})
        if not isinstance(meta, dict):
            current["meta"] = meta = {}
        chain_policy = meta.setdefault("chain_policy", {})
        if not isinstance(chain_policy, dict):
            meta["chain_policy"] = chain_policy = {}
        chain_policy.update(updates)
        return True

    write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_apply)


def _write_chain_policy_into_plan_meta(
    root: Path,
    plan_name: str,
    spec: ChainSpec,
    spec_path: Path,
    milestone_label: str,
    *,
    milestone_base_sha: str | None = None,
    plan_only: bool = False,
    contract_context: dict[str, Any] | None = None,
) -> None:
    """Record effective chain policy in the plan's ``state.json`` metadata.

    Reads the plan's state.json, merges ``meta.chain_policy``, and writes
    back atomically.  Does nothing if the plan directory cannot be resolved
    (best-effort, non-critical).
    """
    from megaplan._core import read_json
    from megaplan._core.state import write_plan_state

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
    runtime_overrides = load_runtime_policy(spec_path)
    effective = effective_chain_policy(spec, runtime_overrides)
    chain_policy = {
        "prerequisite_policy": effective["prerequisite_policy"],
        "validation_policy": effective["validation_policy"],
        "review_policy": effective["review_policy"],
        "source": effective["source"],
        "milestone_label": milestone_label,
        "plan_only": plan_only,
    }
    if milestone_base_sha:
        chain_policy["milestone_base_sha"] = milestone_base_sha
    if contract_context is not None:
        chain_policy["dependency_labels"] = list(contract_context.get("dependency_labels", []))
        chain_policy["upstream_contracts"] = list(contract_context.get("upstream_contracts", []))
        chain_policy["provided_paths"] = dict(contract_context.get("provided_paths", {}))
        chain_policy["contract_context"] = contract_context

    def _patch_chain_policy(current: dict[str, Any]) -> bool:
        meta = current.setdefault("meta", {})
        if not isinstance(meta, dict):
            current["meta"] = meta = {}
        meta["chain_policy"] = chain_policy
        return True

    write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_patch_chain_policy)


def _current_head_sha(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha or None


def validate_paths(spec: ChainSpec, root: Path, state: ChainState | None = None) -> None:
    """Check that idea files needed by this invocation exist on disk.

    On resume, completed milestones and an already-adopted current plan do not
    need their source idea files. Validating them again makes a durable chain
    fragile when a spec uses absolute paths into a checkout that moved or was
    cleaned after those milestones had already landed.
    """
    current_index = state.current_milestone_index if state is not None else -1
    current_plan_name = state.current_plan_name if state is not None else None
    for index, m in enumerate(spec.milestones):
        if state is not None and index < current_index:
            continue
        if state is not None and index == current_index and current_plan_name:
            continue
        idea_path = _resolve_idea_path(root, m.idea)
        try:
            exists = idea_path.exists()
        except OSError:
            # An inline brief (or any oversized string) accidentally placed in
            # `idea:` cannot be a path — stat() raises ENAMETOOLONG. Surface a
            # clear, actionable error instead of an unhandled OSError traceback.
            preview = m.idea.strip().splitlines()[0][:80] if m.idea.strip() else ""
            raise CliError(
                "invalid_idea_path",
                f"milestone {m.label!r} `idea` must be a PATH to a brief file, "
                f"not inline text (got {preview!r}…). Write the brief to a file "
                f"under .megaplan/briefs/ and set `idea:` to that path.",
            )
        if not exists:
            raise CliError(
                "missing_idea_file",
                f"milestone {m.label!r} idea file not found: {m.idea}",
            )
    if spec.seed_plan:
        try:
            resolve_plan_dir(root, spec.seed_plan)
        except CliError as exc:
            raise CliError(
                "missing_seed_plan",
                f"seed plan {spec.seed_plan!r} not found under {root}: {exc.message}",
            ) from exc


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
                "megaplan",
                "status",
                "--project-dir",
                str(root),
                "--plan",
                plan,
            ],
            cwd=str(megaplan_engine_root()),
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


def _resumable_retry_state(root: Path, plan: str | None) -> str | None:
    """Return the plan's current_state when retry should resume it in place."""
    if not plan:
        return None
    try:
        plan_dir = resolve_plan_dir(root, plan)
    except CliError:
        return None
    try:
        raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    current_state = raw.get("current_state")
    if isinstance(current_state, str) and current_state in RESUMABLE_RETRY_STATES:
        return current_state
    return None


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
    commit_plan_artifacts_to_base,
    _commit_phase,
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
    # The init subprocess runs with cwd=megaplan_engine_root(), so a spec-relative
    # idea path must be resolved against the project root here — otherwise init
    # resolves it against the engine repo and fails with a misleading BRIEF_MISSING.
    idea_path = str(_resolve_idea_path(root, idea_path))
    _warn_vendor_ignored_for_locked_profile(
        root,
        profile=profile,
        vendor=vendor,
        writer=writer,
    )
    args = [sys.executable, "-m", "megaplan", "init", "--project-dir", str(root)]
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
        cwd=str(megaplan_engine_root()),
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
    stop_at_finalized: bool = False,
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
        stop_at_finalized=stop_at_finalized,
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
        _warn_chain_fallback(
            "M3A_WARN_EXECUTE_RESULT_READ",
            reason="corrupt_json",
            path=plan_dir / "state.json",
        )
        return None
    except (OSError, UnicodeDecodeError):
        _warn_chain_fallback(
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
    current_milestone_base_sha: str | None = None,
) -> bool:
    """Compute + persist + log a milestone-level completion verdict.

    Returns ``True`` when enforce mode blocks this milestone (caller must NOT
    append to ``state.completed`` and must handle the retry/halt logic).
    Returns ``False`` in all other cases (shadow/warn/off/fail-open).

    FAIL-OPEN. Mirrors the exact mode-gated logic of
    ``auto._shadow_completion_verdict``: off → no-op; shadow → measure+log;
    warn → advisory WARNING; enforce → block on newly_failing/deleted_tests,
    pass-through on runner_error/timeout/not_applicable/non-computable delta.
    Reads ``completion_contract_mode`` from ``ChainState`` (already
    snapshot-aligned at chain init from CLI > get_effective).
    """
    try:
        from megaplan.orchestration.completion_contract import (
            CONTRACT_MODE_ENFORCE,
            CONTRACT_MODE_OFF,
            CONTRACT_MODE_SHADOW,
            CONTRACT_MODE_WARN,
            CompletionSubject,
            compute_verdict,
            extract_green_suite_info,
            normalize_contract_mode,
        )
        from megaplan.orchestration.completion_io import write_completion_verdict

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

        # Resolve milestone_base_sha: prefer plan state chain_policy,
        # fall back to the caller-supplied kwarg (ChainState).
        milestone_base_sha: str | None = (
            state.get("meta", {}).get("chain_policy", {}).get("milestone_base_sha")
            or current_milestone_base_sha
        )
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
            git_base_ref=milestone_base_sha,
        )
        try:
            write_completion_verdict(plan_dir, verdict)
        except Exception:
            pass

        try:
            log_fn(verdict.one_line())
        except Exception:
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

            # Non-blocking: runner errors — record warning, don't block.
            if result_status in {"runner_error", "timeout", "not_applicable"}:
                log.warning(
                    "completion_contract_mode=enforce: milestone %r verification "
                    "status=%r — not blocking (non-deterministic result); would_block=%r",
                    milestone_label,
                    result_status,
                    verdict.would_block,
                )
                return False

            # Non-blocking: delta not computable — record warning, don't block.
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

            # Blocking: newly_failing or deleted_tests present.
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

    incomplete: list[str] = []
    for task in task_records:
        if task.get("status") == "done":
            continue
        task_id = task.get("task_id") or task.get("id") or "?"
        incomplete.append(f"{task_id}={task.get('status')!r}")
    if incomplete:
        return False, f"{latest.name} has non-done tasks: {', '.join(incomplete)}"
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
            # A "no new failures vs the recorded baseline" checkpoint cannot be
            # evaluated when baseline capture failed (baseline_test_failures is
            # null — e.g. the suite timed out). The execute layer already treats
            # such checkpoints as acknowledged deviations rather than real blocks
            # (batch.py prereq_blocked = active_blocked - baseline_blocked); the
            # chain completion gate must apply the SAME exemption, or a transient
            # baseline-capture failure permanently deadlocks a finished milestone
            # on an unattended (auto_approve) run — there is no operator to clear
            # the "end-of-run signal" the interim-vs-final distinction reserved.
            from megaplan.execute.batch import baseline_unavailable_checkpoint_ids

            all_finalize_ids = {
                task["id"]
                for task in finalize_tasks
                if isinstance(task, dict) and isinstance(task.get("id"), str)
            }
            baseline_unavailable = baseline_unavailable_checkpoint_ids(
                finalize_payload, all_finalize_ids
            )
            pending = [
                f"{(task.get('id') or '?')}={task.get('status')!r}"
                for task in finalize_tasks
                if isinstance(task, dict)
                and task.get("status") not in {"done", "skipped"}
                and task.get("id") not in baseline_unavailable
            ]
            if pending:
                return False, f"finalize.json has incomplete tasks: {', '.join(pending)}"
            if baseline_unavailable:
                print(
                    "[chain] WARNING: no-new-failures checkpoint(s) "
                    f"{', '.join(sorted(baseline_unavailable))} could not be "
                    "verified (baseline capture failed / baseline_test_failures "
                    "is null); milestone completion is NOT blocked on an "
                    "un-capturable baseline. Review the post-execute suite for "
                    "regressions.",
                    file=sys.stderr,
                    flush=True,
                )
    return True, latest.name


def _mark_blocked_execute_as_executed(plan_dir: Path) -> None:
    from megaplan._core.state import write_plan_state

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
        _warn_chain_fallback(
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
    stop_at_finalized: bool = False,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    writer,
) -> DriverOutcome:
    outcome = _drive_plan(
        root,
        plan,
        spec,
        stop_at_finalized=stop_at_finalized,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )
    if not _recover_blocked_execute_if_tasks_done(root, outcome, writer=writer):
        return outcome
    return _drive_plan(
        root,
        plan,
        spec,
        stop_at_finalized=stop_at_finalized,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )


def _milestone_retry_cap(milestone: "MilestoneSpec | None", spec: ChainSpec) -> int:
    """Per-milestone retry cap.

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
        nxt, bumped = _bump_one_tier(current, PROFILE_BUMP_ORDER)
        if not bumped:
            writer(
                f"[chain] {label}: bump_profile requested but already at top tier "
                f"({current or 'apex'}); no tier above apex — stopping\n"
            )
            return "stop"
        state.profile_bumps[label] = nxt or ""
        # Couple a depth bump so a harder retry also thinks deeper.
        cur_depth = state.depth_bumps.get(label) or (milestone.depth if milestone else None)
        d_next, d_bumped = _bump_one_tier(cur_depth, DEPTH_BUMP_ORDER)
        if d_bumped and d_next:
            state.depth_bumps[label] = d_next
        writer(f"[chain] {label}: bumping profile → {nxt}; retrying once\n")
        return "retry"
    if action == "bump_robustness":
        current = state.robustness_bumps.get(label) or (
            (milestone.robustness if milestone and milestone.robustness else spec.robustness)
        )
        nxt, bumped = _bump_one_tier(current, ROBUSTNESS_BUMP_ORDER)
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
) -> str:
    """Decide the next action given a DriverOutcome, walking the ladder.

    Returns one of: "advance" (move to next milestone), "stop" (chain halts),
    "retry" (retry the same milestone), "skip" (advance without waiting).

    On a failure/escalate outcome the structured ladder is walked with a
    BOUNDED, persisted per-milestone retry counter:

      retry_milestone / resume_milestone (up to cap; 1 for apex/extreme) →
      bump_profile / bump_robustness (once) →
      abort (stop_chain by default).

    The counter is keyed by milestone label in ``state`` so it survives resume
    and CANNOT loop forever on a deterministic failure.
    """
    status = outcome.status
    if status in {"done", "finalized"}:
        return "advance"
    if status == "awaiting_human":
        # A human-only block (e.g. a task blocked on an unresolved
        # manual_required / rejected user action). Retrying re-runs execute and
        # re-hits the identical block — its input cannot change without human
        # action — so this must STOP the chain immediately rather than burn the
        # retry/bump ladder on a deterministically-unresolvable state. The plan
        # resumes normally on the next chain run once the action is resolved.
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
        print(
            "[chain] WARNING: require_clean_base is STASHING non-.megaplan WIP "
            f"for milestone {milestone.label} ({sample}).\n"
            "[chain] WARNING: this stashed work will NOT be in this milestone's "
            "base. Under --no-push each completed milestone now commits its own "
            "output locally, so this carried WIP is presumed to be UNRELATED "
            "pre-existing work — confirm it is not a milestone's product before "
            "relying on the stash.",
            file=sys.stderr,
        )
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
        ticket_dir = _state_path_for(spec_path).parent / "tickets"
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


def _milestone_uses_hermes_backend(milestone: "MilestoneSpec") -> str | None:
    """Return a phase name if *milestone* will exercise the hermes/agent backend.

    The canonical prep models (triage/fanout/distill) all route to
    ``hermes:deepseek:...`` (see ``CANONICAL_PREP_MODELS``), so any milestone
    that runs prep WILL import the hermes runtime. Explicit per-phase
    ``hermes:...`` routes (via ``phase_model``) also need the backend. Returns
    the most representative phase name for the error message, or ``None`` if the
    milestone does not need the hermes backend.
    """
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
    """Fail fast (cold path) if a milestone needs the hermes/agent backend but
    it is not importable.

    Without this, a misconfigured install only surfaces the failure deep inside
    the prep phase (e.g. prep research iteration 3) as a confusing
    ``phase 'prep' internal_error`` whose stdout is the raw
    ``agent_deps_missing`` payload. This preflight names the offending
    milestone + phase and the exact remediation BEFORE any milestone is driven.
    """
    offenders: list[tuple[str, str]] = []
    for milestone in spec.milestones:
        phase = _milestone_uses_hermes_backend(milestone)
        if phase is not None:
            offenders.append((milestone.label, phase))
    if not offenders:
        return

    # Probe via the same import check the hot path uses, so a partial install
    # (e.g. hermes_state present but run_agent's deps missing) also fails here.
    from megaplan.workers import _is_agent_available

    if _is_agent_available("hermes"):
        return

    first_label, first_phase = offenders[0]
    detail = ", ".join(f"{label} ({phase})" for label, phase in offenders)
    raise CliError(
        "agent_deps_missing",
        "The hermes/agent backend is required for this chain but is not "
        f"installed. Milestone {first_label!r} phase {first_phase!r} (and: "
        f"{detail}) will route to the hermes runtime. Reinstall the engine so "
        "the agent backend is present, e.g. `uv pip install -e .` (its packages "
        "are core dependencies) or `pip install megaplan-harness` from PyPI. "
        "The legacy `[agent]` extra is only a no-op compatibility alias on "
        "current builds. "
        "Verify with: python -c \"import megaplan.agent; "
        "import sys; sys.path.insert(0, megaplan.agent.__path__[0]); "
        "from run_agent import AIAgent\".",
    )


def run_chain(
    spec_path: Path,
    root: Path,
    *,
    writer=sys.stdout.write,
    no_git_refresh: bool = False,
    no_push: bool = False,
    fresh: bool = False,
    one: bool = False,
    stop_at_finalized: bool = False,
    mode: Literal["start", "plan", "execute"] = "start",
) -> dict[str, Any]:
    """Drive the full chain. Returns a structured JSON-serializable result."""
    if mode not in {"start", "plan", "execute"}:
        raise CliError("invalid_args", f"chain mode must be start, plan, or execute; got {mode!r}")
    planning_pass = mode == "plan"
    execution_pass = mode == "execute"
    effective_stop_at_finalized = planning_pass or (stop_at_finalized and not execution_pass)
    spec = load_spec(spec_path)
    push_enabled = not no_push and os.environ.get("MEGAPLAN_CHAIN_NO_PUSH") not in {"1", "true", "TRUE", "yes", "YES"}
    reset_summary: dict[str, Any] | None = None
    if fresh:
        reset_summary = reset_chain_anchors(
            spec_path,
            root,
            spec,
            writer=writer,
            include_remote_branches=push_enabled,
        )
        writer(
            "[chain] fresh start reset anchors: "
            f"{len(reset_summary['state_files'])} state file(s), "
            f"{len(reset_summary['local_branches'])} local branch(es), "
            f"{len(reset_summary['remote_branches'])} remote branch(es)"
        )
        if reset_summary["skipped_remote_branches"]:
            writer(
                "; skipped remote branch deletion because pushing is disabled"
            )
        writer("\n")
    state = load_chain_state(spec_path)
    validate_paths(spec, root, state)
    _preflight_agent_backends(spec, writer=writer)
    # Snapshot completion_contract_mode at chain init from the same resolved
    # source as plan-level (CLI flag > get_effective) so the two never diverge.
    if state.current_milestone_index < 0 and not state.completed:
        from megaplan._core.io import get_effective
        from megaplan.orchestration.completion_contract import normalize_contract_mode

        state.completion_contract_mode = normalize_contract_mode(
            get_effective("execution", "completion_contract_mode")
        )
    preexisting_dirty_paths = _dirty_worktree_paths(root)

    # ---- Preflight: announce --no-push local-commit integration mode ----
    # Under --no-push each milestone now commits LOCALLY onto the base branch as
    # it completes (see the advance path / _commit_phase), so HEAD advances and
    # milestones build on each other. (Historically --no-push milestones never
    # committed — their output stayed as uncommitted WIP that, with
    # require_clean_base, got stashed away, freezing HEAD and siloing prior work.
    # The local commit closes that data-integrity gap.)
    if not push_enabled and len(spec.milestones) > 1:
        print(
            "\n"
            "============================================================\n"
            "[chain] --no-push: LOCAL-COMMIT integration mode\n"
            "============================================================\n"
            f"This chain has {len(spec.milestones)} milestones and pushing is "
            "disabled.\n"
            "\n"
            "Each milestone is committed LOCALLY onto the base branch\n"
            f"({spec.base_branch}) as it completes — HEAD advances so every\n"
            "milestone builds on the previous one's integrated tree, exactly as a\n"
            "pushed chain would, just without contacting origin. Nothing is pushed\n"
            "and no PRs are opened; publish with a manual `git push` when ready.\n"
            "\n"
            "Notes:\n"
            "  - Per-milestone history is real local commits (one 'megaplan: <plan>\n"
            "    done' commit per milestone), so each milestone has a reviewable\n"
            "    diff and the completion contract can compute per-milestone deltas.\n"
            "  - require_clean_base stays compatible: the worktree is clean between\n"
            "    milestones (work is committed, not stashed), so it no longer silos\n"
            "    output into stashes.\n"
            "  - Unrelated pre-existing WIP present at chain start is NOT swept into\n"
            "    milestone commits.\n"
            "============================================================\n",
            file=sys.stderr,
        )

    events: list[dict[str, Any]] = []
    if reset_summary is not None:
        events.append({"msg": "fresh reset anchors", "reset": reset_summary})

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[chain] {msg}\n")

    if execution_pass:
        all_done = _prepare_execute_mode_state(root, spec, state)
        save_chain_state(spec_path, state)
        if all_done:
            log("all milestones already executed")
            return _result("done", state, events, spec=spec)

    # ---- Seed phase ----
    if spec.seed_plan and state.current_milestone_index < 0:
        seed_state = _plan_state(root, spec.seed_plan, timeout=spec.status_timeout)
        log(f"seed plan {spec.seed_plan} state={seed_state}")
        if seed_state not in TERMINAL_SKIP_STATES:
            state.current_plan_name = spec.seed_plan
            save_chain_state(spec_path, state)
            outcome = _drive_plan_with_blocked_execute_recovery(
                root,
                spec.seed_plan,
                spec,
                stop_at_finalized=effective_stop_at_finalized,
                writer=writer,
            )
            state.last_state = outcome.status
            save_chain_state(spec_path, state)
            decision = _handle_outcome(outcome, spec=spec, writer=writer)
            if decision == "stop":
                if planning_pass:
                    _write_chain_review(
                        root,
                        spec_path,
                        spec,
                        state,
                        partial_reason=f"seed plan {outcome.status}",
                    )
                return _result("stopped", state, events, spec=spec, reason=f"seed plan {outcome.status}")
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan_with_blocked_execute_recovery(
                    root,
                    spec.seed_plan,
                    spec,
                    stop_at_finalized=effective_stop_at_finalized,
                    writer=writer,
                )
                state.last_state = outcome.status
                save_chain_state(spec_path, state)
                if outcome.status != "done":
                    if planning_pass:
                        _write_chain_review(
                            root,
                            spec_path,
                            spec,
                            state,
                            partial_reason="seed retry failed",
                        )
                    return _result("stopped", state, events, spec=spec, reason="seed retry failed")
            # skip / advance both proceed to milestones
        _upsert_completed_record(
            state,
            {
                "label": "seed",
                "plan": spec.seed_plan,
                "status": state.last_state or seed_state,
            },
        )
        state.current_milestone_index = 0
        state.current_plan_name = None
        state.current_milestone_base_sha = None
        save_chain_state(spec_path, state)

    elif state.current_milestone_index < 0:
        state.current_milestone_index = 0
        state.current_milestone_base_sha = None
        save_chain_state(spec_path, state)

    # ---- Milestones ----
    idx = max(state.current_milestone_index, 0)
    if idx >= len(spec.milestones) and not planning_pass:
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
        # Preflight disk guard: a disk that fills mid-milestone corrupts SQLite
        # (WAL can't flush → "database is locked") and crashes the driver at
        # interpreter shutdown (sqlite3.Connection.__del__ raising during GC on a
        # full/locked DB). Halt CLEANLY here instead so a babysit/operator can
        # free space and resume, rather than losing the run to a fatal teardown.
        _min_free_gb = float(os.environ.get("MEGAPLAN_MIN_FREE_DISK_GB", "1.5"))
        try:
            _free_gb = shutil.disk_usage(root).free / 1e9
        except OSError:
            _free_gb = None
        if _free_gb is not None and _free_gb < _min_free_gb:
            log(
                f"disk critically low ({_free_gb:.2f} GB free < {_min_free_gb} GB) "
                f"before milestone {milestone.label}; halting cleanly — free space and resume"
            )
            return _result(
                "stopped",
                state,
                events,
                spec=spec,
                reason=(
                    f"low_disk: {_free_gb:.2f} GB free before milestone "
                    f"{milestone.label} (min {_min_free_gb} GB)"
                ),
            )
        use_pr = push_enabled and bool(milestone.branch)
        effective_use_pr = use_pr and not planning_pass
        if planning_pass and (state.pr_number is not None or state.pr_state is not None):
            state.pr_number = None
            state.pr_state = None
            save_chain_state(spec_path, state)

        if state.last_state == STATE_AWAITING_PR_MERGE and state.current_milestone_index == idx:
            if not effective_use_pr or state.pr_number is None:
                log(f"review merge wait for {milestone.label} has no PR context; advancing")
                state.pr_number = None
                state.pr_state = None
            else:
                pr_state = _pr_state(root, state.pr_number, writer=writer)
                state.pr_state = "merged" if pr_state == "merged" else "awaiting_merge"
                save_chain_state(spec_path, state)
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
            existing_record = _completed_record_for_status(state, milestone) or {}
            _upsert_completed_record(
                state,
                {
                    "label": milestone.label,
                    "plan": state.current_plan_name,
                    "status": "done",
                    "plan_branch": _completed_record_branch(existing_record),
                    "pr_number": state.pr_number,
                    "pr_state": "merged" if state.pr_number is not None else None,
                },
            )
            idx += 1
            state.current_milestone_index = idx
            state.current_plan_name = None
            state.current_milestone_base_sha = None
            state.last_state = "done"
            state.pr_number = None
            state.pr_state = None
            save_chain_state(spec_path, state)
            continue

        if (
            execution_pass
            and state.current_milestone_index == idx
            and not state.current_plan_name
        ):
            existing_record = _completed_record_for_status(state, milestone)
            if existing_record and existing_record.get("status") == "finalized":
                plan_name, state_path, raw_state = _load_finalized_record_state(
                    root,
                    milestone.label,
                    existing_record,
                )
                _reset_execute_plan_state_for_fresh_approval(state_path, raw_state)
                state.current_plan_name = plan_name
                state.last_state = STATE_FINALIZED
                save_chain_state(spec_path, state)

        # Resume mid-milestone if we already have a plan name recorded.
        if (
            state.current_plan_name
            and state.current_milestone_index == idx
            and (
                execution_pass
                or _plan_state(root, state.current_plan_name, timeout=spec.status_timeout)
                not in ("missing",)
            )
        ):
            plan_name = state.current_plan_name
            log(f"resuming existing plan {plan_name} for {milestone.label}")
            if effective_use_pr and state.pr_number is None:
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
                save_chain_state(spec_path, state)
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
            if effective_use_pr:
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
            milestone_base_sha = _current_head_sha(root)
            state.current_milestone_base_sha = milestone_base_sha
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
            contract_context = (
                _contract_context_for_plan_only_milestone(root, milestone, state)
                if planning_pass
                else None
            )
            # Record effective chain policy in the newly initialized plan's
            # state.json metadata so downstream consumers can introspect it.
            _write_chain_policy_into_plan_meta(
                root,
                plan_name,
                spec,
                spec_path,
                milestone.label,
                milestone_base_sha=milestone_base_sha,
                plan_only=planning_pass,
                contract_context=contract_context,
            )
            state.current_milestone_index = idx
            state.current_plan_name = plan_name
            save_chain_state(spec_path, state)
            if effective_use_pr:
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
                save_chain_state(spec_path, state)

        def phase_callback(phase: str, _code: int, _out: str, _err: str) -> None:
            if effective_use_pr and milestone.branch:
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

        if execution_pass:
            previous_reground_decision = state.reground_decisions.get(milestone.label)
            current_plan_state = _plan_current_state_from_payload(root, plan_name)
            if current_plan_state != STATE_FINALIZED:
                reground_decision = _reground_skip_decision(milestone, "plan_not_finalized")
                if not (
                    isinstance(previous_reground_decision, dict)
                    and previous_reground_decision.get("status") == "replanned"
                ):
                    state.reground_decisions[milestone.label] = reground_decision
                    save_chain_state(spec_path, state)
            else:
                reground_decision = _record_execute_reground_decision(
                    root,
                    state,
                    milestone,
                    plan_name,
                    _completed_record_for_status(state, milestone),
                )
                if reground_decision.get("status") == "drift":
                    fingerprint = reground_decision.get("material_fingerprint")
                    if (
                        isinstance(previous_reground_decision, dict)
                        and previous_reground_decision.get("material_fingerprint") == fingerprint
                        and previous_reground_decision.get("status") in {"drift", "replanned"}
                    ):
                        save_chain_state(spec_path, state)
                        summary = _reground_diff_summary(reground_decision)
                        log(f"reground {milestone.label}: repeated drift; stopping")
                        return _result(
                            "stopped",
                            state,
                            events,
                            spec=spec,
                            reason=f"repeated contract drift for {milestone.label}: {summary}",
                        )
                    _apply_reground_replan(root, plan_name, reground_decision)
                    replanned_decision = dict(reground_decision)
                    replanned_decision["status"] = "replanned"
                    replanned_decision["replan_reason"] = _reground_diff_summary(reground_decision)
                    replanned_decision["replanned_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                    state.reground_decisions[milestone.label] = replanned_decision
                    save_chain_state(spec_path, state)
                    log(f"reground {milestone.label}: drift; replanning same milestone")
                    continue
                save_chain_state(spec_path, state)
            log(
                f"reground {milestone.label}: {reground_decision['status']}"
                + (
                    f" ({reground_decision['reason']})"
                    if reground_decision.get("reason")
                    else ""
                )
            )

        outcome = _drive_plan_with_blocked_execute_recovery(
            root,
            plan_name,
            spec,
            stop_at_finalized=effective_stop_at_finalized,
            on_phase_complete=phase_callback if effective_use_pr else None,
            writer=writer,
        )
        # Reconcile a non-terminal driver outcome against the plan's
        # AUTHORITATIVE state.json BEFORE on_failure can abort the chain.
        # The stall watchdog can race a slow reasoning model (e.g.
        # deepseek-v4-pro): it returns "stalled" while the phase worker is
        # still alive, and the plan then reaches a terminal-good state a few
        # polls later. Aborting on that stale view abandons a finished,
        # mergeable milestone (its PR never merges and idx never advances).
        # If the plan actually reached its terminal-good state, treat the
        # milestone as complete so the normal advance/merge path runs.
        if outcome.status not in {"done", "finalized"}:
            reconciled_state = _plan_current_state_from_payload(root, plan_name)
            terminal_good = {"done"}
            if effective_stop_at_finalized:
                terminal_good.add(STATE_FINALIZED)
            if reconciled_state in terminal_good:
                writer(
                    f"[chain] driver reported {outcome.status!r} for "
                    f"{plan_name}, but plan state.json is "
                    f"{reconciled_state!r} (terminal-good) — false stall; "
                    f"reconciling to advance\n"
                )
                outcome.reason = (
                    f"reconciled from {outcome.status} via plan "
                    f"state.json={reconciled_state}"
                )
                outcome.status = "done"
        state.last_state = outcome.status
        save_chain_state(spec_path, state)
        decision = _handle_outcome(
            outcome, spec=spec, writer=writer, milestone=milestone, state=state
        )

        if decision == "stop":
            _maybe_file_ladder_ticket(
                root, spec_path, milestone, outcome, state, writer=writer
            )
            save_chain_state(spec_path, state)
            if planning_pass:
                _write_chain_review(
                    root,
                    spec_path,
                    spec,
                    state,
                    partial_reason=f"milestone {milestone.label} ended {outcome.status}",
                )
            return _result(
                "stopped",
                state,
                events,
                spec=spec,
                reason=f"milestone {milestone.label} ended {outcome.status}",
            )
        if decision == "retry":
            resumable_state = _resumable_retry_state(root, state.current_plan_name)
            if resumable_state:
                log(
                    f"retrying milestone {milestone.label} by resuming plan "
                    f"{state.current_plan_name} from {resumable_state}"
                )
            else:
                log(f"retrying milestone {milestone.label} with a new plan")
                state.current_plan_name = None  # force re-init next loop
                state.current_milestone_base_sha = None
            state.pr_number = None
            state.pr_state = None
            save_chain_state(spec_path, state)
            continue
        if decision == "advance" and effective_use_pr and state.pr_number is not None:
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
                save_chain_state(spec_path, state)
            else:
                _mark_pr_ready(root, state.pr_number, writer=writer)
                if spec.merge_policy == "review":
                    state.last_state = STATE_AWAITING_PR_MERGE
                    state.pr_state = "awaiting_merge"
                    save_chain_state(spec_path, state)
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
                save_chain_state(spec_path, state)
        # Completion-verification contract: compute + persist + log a milestone
        # verdict. Shadow/warn: fail-open, never blocks. Enforce: may block the
        # milestone and route it back for retry (newly_failing/deleted_tests).
        enforce_blocked = _shadow_milestone_completion_verdict(
            root,
            plan_name,
            milestone.label,
            outcome.status,
            state.completion_contract_mode,
            log_fn=log,
            current_milestone_base_sha=state.current_milestone_base_sha,
        )
        if enforce_blocked:
            # Read retry cap from the plan's state.json config (default 2).
            max_retries = 2
            try:
                _plan_dir = resolve_plan_dir(root, plan_name)
                if _plan_dir is not None:
                    _st = json.loads((_plan_dir / "state.json").read_text(encoding="utf-8"))
                    _cfg = _st.get("config", {}) if isinstance(_st, dict) else {}
                    max_retries = int(_cfg.get("enforce_revise_max_retries", 2))
            except Exception:
                pass

            milestone_retry_count = int(state.enforce_revise_counts.get(milestone.label, 0))
            if milestone_retry_count >= max_retries:
                log(
                    f"completion_contract_mode=enforce: milestone {milestone.label!r} "
                    f"blocked; retry cap {max_retries} exhausted — operator action required"
                )
                save_chain_state(spec_path, state)
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
            state.current_plan_name = None  # force re-init on next loop
            state.current_milestone_base_sha = None
            state.pr_number = None
            state.pr_state = None
            save_chain_state(spec_path, state)
            continue

        # --no-push local integration. When we are NOT managing a milestone
        # branch/PR (push disabled, so ``effective_use_pr`` is False), the
        # branch+PR commit path at decision=="advance" above never runs and the
        # milestone's CODE would otherwise be left as uncommitted WIP while HEAD
        # stayed frozen at the chain's start. Commit the milestone's worktree
        # diff locally onto the base branch (HEAD) — no push — so HEAD advances
        # and the next milestone's base (``_current_head_sha``) is this
        # milestone's integrated tree. This is what makes --no-push milestones
        # build on each other instead of all forking the same frozen base.
        local_commit_sha: str | None = None
        if (
            decision == "advance"
            and not planning_pass
            and not effective_use_pr
            # Only integrate where there is real git history to build on. Off a
            # git repo (logic-only tests, degenerate setups) _current_head_sha is
            # None and there is nothing to commit onto.
            and _current_head_sha(root) is not None
        ):
            local_commit_sha = _commit_phase(
                root,
                plan_name,
                "done",
                writer=writer,
                preexisting_dirty_paths=preexisting_dirty_paths,
            )
            if local_commit_sha:
                state.branch_head = local_commit_sha
                log(
                    f"--no-push: integrated milestone {milestone.label} locally as "
                    f"{local_commit_sha[:10]} on {spec.base_branch} (HEAD advanced; not pushed)"
                )

        # advance or skip
        completed_record = _completed_record_for_status(state, milestone) or {}
        if planning_pass and outcome.status == "finalized":
            artifact_result = commit_plan_artifacts_to_base(
                root,
                spec.base_branch,
                plan_name,
                _plan_artifact_paths_for_milestone(root, plan_name, milestone),
                push_enabled,
            )
            completed_record = {
                "label": milestone.label,
                "plan": plan_name,
                "status": "finalized",
                "plan_branch": spec.base_branch,
                "artifact_commit_sha": artifact_result.commit_sha,
                "artifact_pushed": artifact_result.pushed,
                "artifact_audit_notes": list(artifact_result.audit_notes),
                "pr_number": None,
                "pr_state": None,
            }
        else:
            completed_record = {
                "label": milestone.label,
                "plan": plan_name,
                "status": outcome.status,
                "plan_branch": (
                    spec.base_branch
                    if local_commit_sha
                    else _completed_record_branch(completed_record)
                ),
                "local_commit_sha": local_commit_sha,
                "pr_number": state.pr_number,
                "pr_state": state.pr_state,
            }
        _upsert_completed_record(state, completed_record)
        idx += 1
        state.current_milestone_index = idx
        state.current_plan_name = None
        state.current_milestone_base_sha = None
        state.pr_number = None
        state.pr_state = None
        save_chain_state(spec_path, state)
        if one:
            log(f"paused after milestone {milestone.label}")
            if planning_pass:
                _write_chain_review(
                    root,
                    spec_path,
                    spec,
                    state,
                    partial_reason=f"completed one milestone: {milestone.label}",
                )
            return _result(
                "paused",
                state,
                events,
                spec=spec,
                reason=f"completed one milestone: {milestone.label}",
            )

    log("all milestones complete")
    if planning_pass:
        _write_chain_review(root, spec_path, spec, state)
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
    completed_records = _completed_records_by_label(state)
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
        record = completed_records.get(milestone.label)
        plan_status = record.get("status") if isinstance(record, dict) else None
        planned = plan_status in {"finalized", "done"}
        executed = plan_status == "done"
        if executed:
            status = "completed"
        elif planned:
            status = "planned"
        elif index == state.current_milestone_index and state.current_plan_name:
            status = "in_progress"
        else:
            status = "pending"
        entry = {
            "label": milestone.label,
            "index": index,
            "status": status,
            "planned": planned,
            "executed": executed,
            "plan_status": plan_status,
            "plan_branch": _completed_record_branch(record),
        }
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
    per_milestone = summary.get("per_milestone") or []
    completed_labels = ", ".join(item["label"] for item in completed) if completed else "none"
    remaining_labels = ", ".join(item["label"] for item in remaining) if remaining else "none"
    planned_count = sum(1 for item in per_milestone if item.get("planned"))
    executed_count = sum(1 for item in per_milestone if item.get("executed"))
    writer(f"Current milestone: {current_label}\n")
    writer(f"Completed: {completed_labels}\n")
    writer(f"Remaining: {remaining_labels}\n")
    writer(f"Planned: {planned_count}/{len(per_milestone)}\n")
    writer(f"Executed: {executed_count}/{len(per_milestone)}\n")
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
    for item in per_milestone:
        branch_suffix = ""
        if item.get("plan_branch"):
            branch_suffix = f", artifact branch {item['plan_branch']}"
        writer(
            f"  - [{item['status']}] {item['label']} "
            f"(index {item['index']}, planned={int(bool(item.get('planned')))}, "
            f"executed={int(bool(item.get('executed')))}{branch_suffix})\n"
        )


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
            "Disable milestone branch creation, PR creation, and pushes to origin. "
            "Milestones still commit LOCALLY onto the base branch as they complete, "
            "so HEAD advances and each builds on the previous one's integrated tree "
            "(publish later with a manual git push). Also enabled by "
            "MEGAPLAN_CHAIN_NO_PUSH=1; intended for local/no-network runs."
        ),
    )
    chain_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    _add_chain_run_args(start_parser)
    plan_parser = chain_sub.add_parser("plan", help="Drive the planning pass until plans finalize")
    _add_chain_run_args(plan_parser)
    execute_parser = chain_sub.add_parser("execute", help="Drive finalized milestone plans through execute")
    _add_chain_run_args(execute_parser)

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


def _add_chain_run_args(parser: Any) -> None:
    parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
    _add_chain_worktree_args(parser)
    parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone."
        ),
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Disable branch/PR/push lifecycle for no-network runs.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "Discard this spec's persisted chain state and milestone branches "
            "before starting. With --no-push, remote branch deletion is skipped."
        ),
    )
    parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
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
            spec = load_spec(spec_path)
        except CliError as exc:
            return _emit_error(exc)
        overrides: dict[str, Any] = load_runtime_policy(spec_path)
        if set_prereq is not None:
            overrides["prerequisite_policy"] = set_prereq
        if set_valid is not None:
            overrides["validation_policy"] = set_valid
        if set_clean is not None:
            review_from_overrides = overrides.get("review_policy") or {}
            review_from_overrides["clean_milestone_pr"] = set_clean
            overrides["review_policy"] = review_from_overrides
        save_runtime_policy(spec_path, overrides)
        effective = effective_chain_policy(spec, overrides)
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
            spec = load_spec(spec_path)
            chain_state = load_chain_state(spec_path)
        except CliError as exc:
            return _emit_error(exc)
        runtime_overrides = load_runtime_policy(spec_path)
        effective_policy = effective_chain_policy(spec, runtime_overrides)
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

    if action not in (None, "start", "plan", "execute"):
        return _emit_error(CliError("invalid_args", f"Unknown chain action: {action}"))

    no_git_refresh = bool(getattr(args, "no_git_refresh", False))
    no_push = bool(getattr(args, "no_push", False))
    fresh = bool(getattr(args, "fresh", False))
    one = bool(getattr(args, "one", False))
    try:
        result = run_chain(
            spec_path,
            root,
            no_git_refresh=no_git_refresh,
            no_push=no_push,
            fresh=fresh,
            one=one,
            mode=action or "start",
        )
    except CliError as exc:
        return _emit_error(exc)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if result["status"] in {"done", "paused", "finalized"}:
        return 0
    return 1


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
