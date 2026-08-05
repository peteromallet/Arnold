from __future__ import annotations

import hashlib
import json
import logging
import re
import stat
import subprocess
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan chain requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from arnold_pipelines.megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    ESCALATE_ACTIONS,
)
from arnold_pipelines.megaplan._core import resolve_plan_dir
from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
    ProjectionRecord,
    append_projection_event,
    deterministic_projection_replay,
    latest_projection_cursor,
    load_projection_history,
    now_utc,
    projection_snapshot_path,
    rebuild_projection_atomically,
)
from arnold_pipelines.megaplan._core.user_config import VALID_VENDORS
from arnold_pipelines.megaplan.profiles import (
    VALID_CRITIC_CHOICES,
    VALID_DEPTH_CHOICES,
    normalize_robustness,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.finite_canary_policy import (
    DIRECT_SUCCESS_ROUTE,
    ONE_REVISION_SUCCESS_ROUTE,
    finite_canary_policy_allows_route,
    finite_canary_policy_is_exact,
)
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.anchors import resolve_anchor_path, validate_anchor_source

log = logging.getLogger("megaplan")


VALID_FAILURE_ACTIONS = (
    "stop_chain",
    "skip_milestone",
    "resume_milestone",
    "retry_milestone",
    "bump_profile",
    "bump_robustness",
)
VALID_MERGE_POLICIES = ("auto", "review", "manual")
DEFAULT_MERGE_POLICY = "auto"
VALID_CHAIN_DEEPSEEK_PROVIDER_CHOICES = ("direct", "fireworks")

# Autonomy-ladder bump ordering. These are the *one-tier-up* escalation maps
# the chain applies when a milestone exhausts its retry budget. There is no
# tier above ``apex`` (apex.toml is the top premium profile) — a bump_profile
# at apex is a no-op + warning, never an error.
PROFILE_BUMP_ORDER = ("premium", "apex")
ROBUSTNESS_BUMP_ORDER = ("thorough", "extreme")
DEPTH_BUMP_ORDER = ("high", "max")

# Default per-milestone retry budget (FRESH re-inits) before the ladder bumps.
# Capped at 1 for apex profile / extreme robustness milestones to bound cost.
DEFAULT_MILESTONE_RETRY_CAP = 2
APEX_EXTREME_RETRY_CAP = 1


def _project_root_for_chain_spec(spec_path: Path) -> Path:
    resolved = spec_path.resolve(strict=False)
    for parent in resolved.parents:
        if parent.name == ".megaplan":
            return parent.parent
    return resolved.parent


def _storage_identity_for_chain_spec(spec_path: Path) -> Path:
    resolved = spec_path.resolve(strict=False)
    project_root = _project_root_for_chain_spec(spec_path)
    project_chain = project_root / spec_path.name
    try:
        if project_chain.exists() and project_chain.samefile(resolved):
            return project_chain
    except OSError:
        pass
    return resolved


def _state_path_candidates_for(spec_path: Path) -> list[Path]:
    resolved = spec_path.resolve(strict=False)
    resolved_digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
    resolved_state_path = (
        resolved.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{resolved.stem}-{resolved_digest}.json"
    )
    candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in (
        _state_path_for(spec_path),
        resolved_state_path,
        _legacy_state_path_for(spec_path),
    ):
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


def _load_chain_state_file(path: Path) -> ChainState:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("invalid_chain_state", f"chain_state.json is invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CliError("invalid_chain_state", "chain_state.json must be an object")
    return ChainState.from_dict(raw)


def _normalize_stale_current_plan_reference(state: "ChainState") -> "ChainState":
    plan_name = state.current_plan_name
    if not isinstance(plan_name, str) or not plan_name:
        return state
    for index, completed in enumerate(state.completed):
        if not isinstance(completed, dict):
            continue
        if completed.get("plan") != plan_name:
            continue
        if state.current_milestone_index < index + 1:
            return state
        state.current_plan_name = None
        state.pr_number = None
        state.pr_state = None
        if state.last_state in {"blocked", "authority_divergence"}:
            # In fail-closed (atomic/enforce) mode a completed record does NOT
            # carry authority to clear a blocked/authority_divergence marker
            # unless the record also carries a validated acceptance receipt.
            # Without the receipt the normalization must refuse the rewrite so
            # the blocked marker stays live.
            from arnold_pipelines.megaplan.orchestration.completion_contract import (
                is_fail_closed_mode,
            )
            if is_fail_closed_mode(state.completion_contract_mode):
                if not state.has_acceptance_receipt(str(completed.get("label") or "")):
                    return state
            state.last_state = "done"
        return state
    return state


def _normalize_advanced_completed_cursor(
    state: "ChainState",
    spec: "ChainSpec",
) -> "ChainState":
    # Rewrite a stale blocked/authority_divergence marker ONLY when the cursor
    # has genuinely advanced past a completed milestone AND the chain is NOT
    # actively retrying the current milestone.
    #
    # The original commit 50a8ee92 targeted the case where a chain was blocked,
    # then externally advanced (e.g. by the agentbox handler or a repair script)
    # past a now-completed milestone, leaving a stale "blocked" marker. Its
    # discriminator (``current_milestone_index == completed_prefix``) also fired
    # at the START of any milestone N whose predecessors were complete, which
    # collapsed a fresh completion-guard retry at milestone N into "done" on
    # every load_chain_state — a false-completion regression.
    #
    # The two discriminator guards below make the rewrite safe:
    #   1. The milestone IMMEDIATELY before the cursor must be completed (the
    #      cursor advanced past a finished milestone), which excludes the
    #      common case of a fresh block/retry at milestone 0 or at any milestone
    #      whose predecessor has not yet completed.
    #   2. The current milestone must NOT have an active retry counter — a live
    #      completion-guard retry leaves a non-empty ``retry_counts[label]`` for
    #      the milestone it is retrying, so we must not silently clear its
    #      "blocked" marker. This distinguishes a live retry (blocked stays)
    #      from an externally-advanced cursor with a leftover marker (cleared).
    #
    # ── fail-closed (atomic/enforce) gate ──────────────────────────────
    # In fail-closed modes a completed record does NOT carry authority to
    # clear a blocked/authority_divergence marker unless the record carries a
    # validated acceptance receipt whose identity fields match the record.
    # Without a receipt the normalization refuses the rewrite so the blocked
    # marker is preserved for the acceptance boundary to adjudicate.
    if state.current_plan_name:
        return state
    if state.current_milestone_index <= 0:
        return state
    completed_labels = {
        record.get("label")
        for record in state.completed
        if isinstance(record, dict) and isinstance(record.get("label"), str)
    }
    previous_index = state.current_milestone_index - 1
    if previous_index >= len(spec.milestones):
        return state
    previous_milestone_label = spec.milestones[previous_index].label
    if previous_milestone_label not in completed_labels:
        # Cursor is sitting at a milestone whose predecessor has NOT completed;
        # a blocked/authority_divergence marker here is live, not stale.
        return state
    if state.current_milestone_index >= len(spec.milestones):
        # Cursor is past the final milestone; nothing current to retry-check.
        if state.last_state in {"blocked", "authority_divergence"}:
            if _atomic_acceptance_gate_allows_rewrite(state, previous_milestone_label):
                state.last_state = "done"
        return state
    current_milestone_label = spec.milestones[state.current_milestone_index].label
    if state.retry_counts.get(current_milestone_label, 0) > 0:
        # The chain is actively retrying this milestone (e.g. a live
        # completion-guard retry); the blocked marker is live, not stale.
        return state
    if state.last_state in {"blocked", "authority_divergence"}:
        if _atomic_acceptance_gate_allows_rewrite(state, previous_milestone_label):
            state.last_state = "done"
    return state


def _atomic_acceptance_gate_allows_rewrite(
    state: "ChainState",
    milestone_label: str,
) -> bool:
    """Return ``True`` when the completed record for *milestone_label* carries
    a validated acceptance receipt, or the chain is NOT in fail-closed mode.

    In shadow/warn/off modes this gate is always open (returns ``True``) -
    legacy normalization behaviour is unchanged.  In atomic/enforce mode the
    gate is closed unless the completed record for the given milestone resolves
    to an accepted committed transaction and a matching content-addressed
    snapshot.
    """
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        is_fail_closed_mode,
    )
    if not is_fail_closed_mode(state.completion_contract_mode):
        return True
    # Locate the completed record for this milestone.
    for record in state.completed:
        if not isinstance(record, dict):
            continue
        if record.get("label") != milestone_label:
            continue
        return state.has_acceptance_receipt(milestone_label)
    # No completed record found — the prerequisite check already failed.
    return True


def _state_progress_key(state: "ChainState", *, path: Path) -> tuple[int, int, int, int, float]:
    return (
        int(state.current_milestone_index),
        len(state.completed),
        1 if state.current_plan_name else 0,
        1 if state.last_state else 0,
        path.stat().st_mtime,
    )


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
          retry: retry_milestone     # walked first, bounded by a counter
          escalate: bump_profile     # walked once after retries exhaust
          abort: stop_chain          # terminal action

    ``retry`` / ``escalate`` are optional; ``abort`` defaults to ``stop_chain``.
    """

    abort: str = "stop_chain"
    retry: str | None = None
    escalate: str | None = None

    @classmethod
    def from_yaml(
        cls, value: Any, section: str, default_abort: str = "stop_chain"
    ) -> "FailurePolicy":
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
        unknown = sorted(set(value) - {"retry", "escalate", "abort"})
        if unknown:
            raise CliError(
                "invalid_spec",
                f"`{section}` only supports retry/escalate/abort; unknown key `{unknown[0]}`",
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
# VALID_MERGE_POLICIES module-level tuple pattern. These are
# operator-facing contracts; renaming later is a breaking change.
# Validated in ChainSpec.from_dict() with CliError("invalid_spec", ...).
VALID_PREREQUISITE_POLICIES = ("none", "required")
VALID_VALIDATION_POLICIES = ("none", "required")
VALID_CLEAN_MILESTONE_PR_POLICIES = ("auto", "manual")
BLOCKED_EXECUTE_OUTCOME_STATUSES = {"blocked", "worker_blocked"}


@dataclass(frozen=True)
class AnchorSpec:
    north_star: str | None = None

    @classmethod
    def from_yaml(cls, value: Any, section: str) -> "AnchorSpec":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise CliError("invalid_spec", f"`{section}` must be a mapping")
        unknown = sorted(set(value) - {"north_star"})
        if unknown:
            raise CliError("invalid_spec", f"`{section}` only supports `north_star`; unknown anchor type `{unknown[0]}`")
        north_star = value.get("north_star")
        if north_star is None:
            return cls()
        if not isinstance(north_star, str) or not north_star.strip():
            raise CliError("invalid_spec", f"`{section}.north_star` must be a non-empty string")
        return cls(north_star=north_star.strip())


@dataclass(frozen=True)
class LaunchPreconditionSpec:
    name: str
    kind: str = "artifact"
    path: str | None = None
    chain: str | None = None
    check: str = "exists"
    text: str | None = None
    require_manifest: bool = False

    @classmethod
    def from_yaml(cls, value: Any, index: int) -> "LaunchPreconditionSpec":
        if not isinstance(value, dict):
            raise CliError("invalid_spec", f"launch_preconditions[{index}] must be a mapping")
        allowed = {"name", "kind", "path", "chain", "check", "text", "require_manifest"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}] unknown key `{unknown[0]}`",
            )
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CliError("invalid_spec", f"launch_preconditions[{index}].name is required")
        kind = value.get("kind", "artifact")
        if not isinstance(kind, str) or not kind.strip():
            raise CliError("invalid_spec", f"launch_preconditions[{index}].kind must be a string")
        kind = kind.strip()
        if kind not in {
            "artifact",
            "chain_completed",
            "finite_canary_receipt",
            "git_tracked",
        }:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}].kind must be `artifact`, `chain_completed`, `finite_canary_receipt`, or `git_tracked`; got {kind!r}",
            )
        chain = value.get("chain")
        path = value.get("path")
        if kind == "chain_completed":
            if not isinstance(chain, str) or not chain.strip():
                raise CliError("invalid_spec", f"launch_preconditions[{index}].chain is required")
            if path is not None or value.get("text") is not None:
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] chain_completed does not support `path` or `text`",
                )
            check = value.get("check")
            if check not in (None, "chain_completed"):
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] chain_completed does not support check {check!r}",
                )
            require_manifest = value.get("require_manifest", False)
            if not isinstance(require_manifest, bool):
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}].require_manifest must be a boolean",
                )
            return cls(
                name=name.strip(),
                kind=kind,
                chain=chain.strip(),
                check="chain_completed",
                require_manifest=require_manifest,
            )

        if kind == "finite_canary_receipt":
            if chain is not None or value.get("text") is not None:
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] finite_canary_receipt does not support `chain` or `text`",
                )
            if not isinstance(path, str) or not path.strip():
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}].path is required",
                )
            check = value.get("check")
            if check not in (None, "finite_canary_receipt"):
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] finite_canary_receipt does not support check {check!r}",
                )
            if "require_manifest" in value:
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] finite_canary_receipt does not support `require_manifest`",
                )
            return cls(
                name=name.strip(),
                kind=kind,
                path=path.strip(),
                check="finite_canary_receipt",
            )

        if kind == "git_tracked":
            if chain is not None or value.get("text") is not None:
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] git_tracked does not support `chain` or `text`",
                )
            if not isinstance(path, str) or not path.strip():
                raise CliError("invalid_spec", f"launch_preconditions[{index}].path is required")
            check = value.get("check")
            if check not in (None, "git_tracked"):
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}] git_tracked does not support check {check!r}",
                )
            return cls(
                name=name.strip(),
                kind=kind,
                path=path.strip(),
                check="git_tracked",
            )

        if chain is not None:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}] artifact precondition does not support `chain`",
            )
        if not isinstance(path, str) or not path.strip():
            raise CliError("invalid_spec", f"launch_preconditions[{index}].path is required")
        check = value.get("check", "exists")
        text: str | None = None
        if isinstance(check, dict):
            check_unknown = sorted(set(check) - {"kind", "text"})
            if check_unknown:
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}].check unknown key `{check_unknown[0]}`",
                )
            kind = check.get("kind")
            if not isinstance(kind, str) or not kind.strip():
                raise CliError(
                    "invalid_spec",
                    f"launch_preconditions[{index}].check.kind is required",
                )
            check_name = kind.strip()
            text_raw = check.get("text")
            if text_raw is not None:
                if not isinstance(text_raw, str) or not text_raw:
                    raise CliError(
                        "invalid_spec",
                        f"launch_preconditions[{index}].check.text must be a non-empty string",
                    )
                text = text_raw
        elif isinstance(check, str):
            check_name = check.strip()
            text_raw = value.get("text")
            if text_raw is not None:
                if not isinstance(text_raw, str) or not text_raw:
                    raise CliError(
                        "invalid_spec",
                        f"launch_preconditions[{index}].text must be a non-empty string",
                    )
                text = text_raw
        else:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}].check must be a string or mapping",
            )
        if check_name not in {"exists", "contains_text", "review_log_clean"}:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}].check must be `exists`, `contains_text`, or `review_log_clean`; got {check_name!r}",
            )
        if check_name == "contains_text" and not text:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}] contains_text check requires `text`",
            )
        if check_name in {"exists", "review_log_clean"} and text is not None:
            raise CliError(
                "invalid_spec",
                f"launch_preconditions[{index}] {check_name} check does not support `text`",
            )
        return cls(
            name=name.strip(),
            kind=kind,
            path=path.strip(),
            check=check_name,
            text=text,
        )


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


@dataclass(frozen=True)
class MilestoneValidationSpec:
    kind: str
    traceability: str | None = None
    conformance: str | None = None
    validator: str | None = None
    proof_map: str | None = None

    @classmethod
    def from_yaml(
        cls, value: Any, *, milestone_index: int, validation_index: int
    ) -> "MilestoneValidationSpec":
        section = f"milestones[{milestone_index}].validate[{validation_index}]"
        if not isinstance(value, dict):
            raise CliError("invalid_spec", f"{section} must be a mapping")
        allowed = {"kind", "traceability", "conformance", "validator", "proof_map"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise CliError("invalid_spec", f"{section} unknown key `{unknown[0]}`")
        kind = value.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            raise CliError("invalid_spec", f"{section}.kind is required")
        kind = kind.strip()
        if kind != "final_conformance_gate":
            raise CliError(
                "invalid_spec",
                f"{section}.kind must be `final_conformance_gate`; got {kind!r}",
            )


        def _required_path(key: str) -> str:
            raw = value.get(key)
            if not isinstance(raw, str) or not raw.strip():
                raise CliError("invalid_spec", f"{section}.{key} is required")
            return raw.strip()

        return cls(
            kind=kind,
            traceability=_required_path("traceability"),
            conformance=_required_path("conformance"),
            validator=_required_path("validator"),
            proof_map=_required_path("proof_map"),
        )


@dataclass(frozen=True)
class FreshChildAdmissionSpec:
    """Opt-in owner admission contract for an independent chain child.

    Legacy chain specs do not contain this section and therefore retain their
    existing launch behaviour. When enabled, all three owner paths and the
    explicit operator/lineage fields are required; the launcher never falls
    back to a projection or synthesises approval context.
    """

    enabled: bool = False
    authority_journal_path: str | None = None
    wbc_ledger_path: str | None = None
    custody_lease_dir: str | None = None
    approval_receipt: str | None = None
    approval_actor: str | None = None
    parent_occurrence_digest: str | None = None
    blocker_or_phase_result_hash: str | None = None
    normalized_failure_kind: str | None = None
    chain_identity: str | None = None
    source_revision: str | None = None
    environment: str = "cloud"
    session: str = "megaplan"
    chain: str = "chain"
    phase: str = "plan"
    task: str = "milestone"
    run_revision: str | None = None
    lease_ttl_seconds: int = 1800

    @classmethod
    def from_yaml(cls, value: Any) -> "FreshChildAdmissionSpec | None":
        if value is None:
            return None
        if not isinstance(value, dict):
            raise CliError("invalid_spec", "fresh_child_admission must be a mapping")
        allowed = {
            "enabled", "authority_journal_path", "wbc_ledger_path", "custody_lease_dir",
            "approval_receipt", "approval_actor", "parent_occurrence_digest",
            "blocker_or_phase_result_hash", "normalized_failure_kind", "chain_identity",
            "source_revision", "environment", "session", "chain", "phase", "task",
            "run_revision", "lease_ttl_seconds",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise CliError("invalid_spec", f"fresh_child_admission unknown key `{unknown[0]}`")
        enabled = value.get("enabled", False)
        if not isinstance(enabled, bool):
            raise CliError("invalid_spec", "fresh_child_admission.enabled must be a boolean")

        def _optional_text(key: str) -> str | None:
            raw = value.get(key)
            if raw is None:
                return None
            if not isinstance(raw, str) or not raw.strip():
                raise CliError("invalid_spec", f"fresh_child_admission.{key} must be a non-empty string")
            return raw.strip()

        paths = {key: _optional_text(key) for key in ("authority_journal_path", "wbc_ledger_path", "custody_lease_dir")}
        approval = {key: _optional_text(key) for key in (
            "approval_receipt", "approval_actor", "parent_occurrence_digest",
            "blocker_or_phase_result_hash", "normalized_failure_kind", "chain_identity",
        )}
        source_revision = _optional_text("source_revision")
        run_revision = _optional_text("run_revision")
        text_fields = {
            key: value.get(key, default)
            for key, default in {
                "environment": "cloud", "session": "megaplan", "chain": "chain",
                "phase": "plan", "task": "milestone",
            }.items()
        }
        for key, raw in text_fields.items():
            if not isinstance(raw, str) or not raw.strip():
                raise CliError("invalid_spec", f"fresh_child_admission.{key} must be a non-empty string")
        ttl = value.get("lease_ttl_seconds", 1800)
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 1:
            raise CliError("invalid_spec", "fresh_child_admission.lease_ttl_seconds must be a positive integer")
        if enabled:
            required = {**paths, **approval, "source_revision": source_revision}
            missing = sorted(key for key, raw in required.items() if raw is None)
            if missing:
                raise CliError("invalid_spec", "fresh_child_admission.enabled requires: " + ", ".join(missing))
        return cls(
            enabled=enabled,
            **paths,
            **approval,
            source_revision=source_revision,
            **{key: raw.strip() for key, raw in text_fields.items()},
            run_revision=run_revision,
            lease_ttl_seconds=ttl,
        )


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
    anchors: AnchorSpec = field(default_factory=AnchorSpec)
    # Validation-only dependency edges (labels of milestones that MUST appear
    # earlier in the list). The chain runs strictly serial-in-listed-order — a
    # single cursor — so ``depends_on`` does NOT reorder or parallelize
    # execution. It is a topological-sort ASSERTION: ``ChainSpec.from_dict``
    # fails loud if a milestone declares a dependency that is not listed before
    # it, so the non-negotiable edges cannot silently drift out of order in a
    # hand-edited chain.yaml. ``∥`` parallel tracks stay prose — concurrency is
    # never introduced here.
    depends_on: list[str] = field(default_factory=list)
    validate: list[MilestoneValidationSpec] = field(default_factory=list)
    north_star_critical: bool = False

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
        vendor = _optional_choice(raw, "vendor", VALID_VENDORS, index=index)
        depth = _optional_choice(raw, "depth", VALID_DEPTH_CHOICES, index=index)
        critic = _optional_choice(raw, "critic", VALID_CRITIC_CHOICES, index=index)
        deepseek_provider = _optional_choice(
            raw,
            "deepseek_provider",
            VALID_CHAIN_DEEPSEEK_PROVIDER_CHOICES,
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
        elif isinstance(phase_model_raw, list) and all(
            isinstance(item, str) for item in phase_model_raw
        ):
            phase_model = list(phase_model_raw)
        else:
            raise CliError("invalid_spec", f"milestones[{index}].phase_model must be a string or list of strings")
        bakeoff = raw.get("bakeoff")
        if bakeoff is not None and not isinstance(bakeoff, dict):
            raise CliError("invalid_spec", f"milestones[{index}].bakeoff must be a mapping")
        notes = raw.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise CliError("invalid_spec", f"milestones[{index}].notes must be a string")
        anchors = AnchorSpec.from_yaml(raw.get("anchors"), f"milestones[{index}].anchors")
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
        validate_raw = raw.get("validate") or []
        if isinstance(validate_raw, dict):
            validate_values = [validate_raw]
        elif isinstance(validate_raw, list):
            validate_values = validate_raw
        else:
            raise CliError(
                "invalid_spec",
                f"milestones[{index}].validate must be a mapping or list of mappings",
            )
        validate = [
            MilestoneValidationSpec.from_yaml(
                item, milestone_index=index, validation_index=validation_index
            )
            for validation_index, item in enumerate(validate_values)
        ]
        north_star_critical = _optional_bool(raw, "north_star_critical", index=index)
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
            anchors=anchors,
            depends_on=depends_on,
            validate=validate,
            north_star_critical=north_star_critical,
        )


@dataclass(frozen=True)
class SuccessorSpec:
    """Declares a successor chain that may be initialised after this chain completes.

    The gate in :func:`advancement.check_successor_gate` reads these declarations
    so the relationship is configuration rather than hardcoded policy.  The first
    consumer is M5 → M5A → M6, but the gate itself is generic.
    """

    chain_spec_path: str
    label: str
    require_accepted_transaction: bool = True
    note: str = ""

    @classmethod
    def from_yaml(cls, value: Any, index: int) -> "SuccessorSpec":
        if not isinstance(value, dict):
            raise CliError(
                "invalid_spec",
                f"successors[{index}] must be a mapping",
            )
        allowed = {"chain_spec_path", "label", "require_accepted_transaction", "note"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise CliError(
                "invalid_spec",
                f"successors[{index}] unknown key `{unknown[0]}`",
            )
        chain_spec_path = value.get("chain_spec_path")
        if not isinstance(chain_spec_path, str) or not chain_spec_path.strip():
            raise CliError(
                "invalid_spec",
                f"successors[{index}].chain_spec_path is required",
            )
        label = value.get("label")
        if not isinstance(label, str) or not label.strip():
            raise CliError(
                "invalid_spec",
                f"successors[{index}].label is required",
            )
        require_accepted_transaction = bool(
            value.get("require_accepted_transaction", True)
        )
        note = str(value.get("note") or "")
        return cls(
            chain_spec_path=chain_spec_path.strip(),
            label=label.strip(),
            require_accepted_transaction=require_accepted_transaction,
            note=note,
        )


@dataclass
class ChainSpec:
    milestones: list[MilestoneSpec]
    anchors: AnchorSpec = field(default_factory=AnchorSpec)
    launch_preconditions: list[LaunchPreconditionSpec] = field(default_factory=list)
    fresh_child_admission: FreshChildAdmissionSpec | None = None
    successors: list[SuccessorSpec] = field(default_factory=list)
    seed_plan: str | None = None
    base_branch: str = "main"
    on_failure: str = "stop_chain"
    on_escalate: str = "stop_chain"
    on_failure_policy: FailurePolicy = field(default_factory=FailurePolicy)
    on_escalate_policy: FailurePolicy = field(default_factory=FailurePolicy)
    merge_policy: str = DEFAULT_MERGE_POLICY
    require_clean_base: bool = False
    prerequisite_policy: str = "none"
    validation_policy: str = "none"
    review_policy: dict[str, str] = field(
        default_factory=lambda: {"clean_milestone_pr": "auto"}
    )
    stall_threshold: int = DEFAULT_STALL_THRESHOLD
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS
    escalate_action: str = "force-proceed"
    robustness: str = "standard"
    auto_approve: bool = True
    require_anchor: bool = True
    missing_anchor_ack: str | None = None
    north_star_critical: bool = False
    # Opt-in only; kept at the end so positional construction of legacy
    # ChainSpec instances retains its historical field order.
    fresh_child_admission: FreshChildAdmissionSpec | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", "chain spec must be a YAML mapping")
        allowed_keys = {
            "anchors",
            "base_branch",
            "driver",
            "fresh_child_admission",
            "launch_preconditions",
            "merge_policy",
            "milestones",
            "on_escalate",
            "on_failure",
            "prerequisite_policy",
            "review_policy",
            "seed",
            "successors",
            "validation_policy",
        }
        unknown_keys = sorted(set(raw) - allowed_keys)
        if unknown_keys:
            key = unknown_keys[0]
            hint = "; did you mean `base_branch`" if key == "base" else ""
            raise CliError("invalid_spec", f"Unknown chain spec key `{key}`{hint}")
        base_branch = raw.get("base_branch", "main")
        if not isinstance(base_branch, str) or not base_branch.strip():
            raise CliError("invalid_spec", "`base_branch` must be a non-empty string")
        base_branch = base_branch.strip()
        anchors = AnchorSpec.from_yaml(raw.get("anchors"), "anchors")
        preconditions_raw = raw.get("launch_preconditions") or []
        if not isinstance(preconditions_raw, list):
            raise CliError("invalid_spec", "`launch_preconditions` must be a list")
        launch_preconditions = [
            LaunchPreconditionSpec.from_yaml(item, i)
            for i, item in enumerate(preconditions_raw)
        ]
        fresh_child_admission = FreshChildAdmissionSpec.from_yaml(
            raw.get("fresh_child_admission")
        )
        milestones_raw = raw.get("milestones") or []
        if not isinstance(milestones_raw, list):
            raise CliError("invalid_spec", "`milestones` must be a list")
        milestones = [MilestoneSpec.from_dict(m, i) for i, m in enumerate(milestones_raw)]
        seen_labels: set[str] = set()
        all_labels = {m.label for m in milestones}
        for i, milestone in enumerate(milestones):
            if milestone.validate and i != len(milestones) - 1:
                raise CliError(
                    "invalid_spec",
                    f"milestones[{i}] ({milestone.label!r}) declares final_conformance_gate validation but is not the final milestone",
                )
            for dep in milestone.depends_on:
                if dep == milestone.label:
                    raise CliError(
                        "invalid_spec",
                        f"milestones[{i}] ({milestone.label!r}) cannot depend on itself",
                    )
                if dep not in all_labels:
                    raise CliError(
                        "invalid_spec",
                        f"milestones[{i}] ({milestone.label!r}) depends_on unknown milestone {dep!r}",
                    )
                if dep not in seen_labels:
                    raise CliError(
                        "invalid_spec",
                        f"milestones[{i}] ({milestone.label!r}) depends_on {dep!r} which is not "
                        f"listed before it; the chain runs serial-in-listed-order, so a "
                        f"dependency must appear earlier in `milestones`",
                    )
            seen_labels.add(milestone.label)
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

        successors_raw = raw.get("successors") or []
        if not isinstance(successors_raw, list):
            raise CliError("invalid_spec", "`successors` must be a list")
        successors = [
            SuccessorSpec.from_yaml(item, i)
            for i, item in enumerate(successors_raw)
        ]

        on_failure_policy = FailurePolicy.from_yaml(
            raw.get("on_failure"), "on_failure", "stop_chain"
        )
        on_escalate_policy = FailurePolicy.from_yaml(
            raw.get("on_escalate"), "on_escalate", "stop_chain"
        )
        on_failure = on_failure_policy.abort
        on_escalate = on_escalate_policy.abort

        explicit_merge_policy = "merge_policy" in raw
        merge_policy = raw.get("merge_policy", DEFAULT_MERGE_POLICY)
        if merge_policy not in VALID_MERGE_POLICIES:
            raise CliError(
                "invalid_spec",
                f"merge_policy must be one of {VALID_MERGE_POLICIES}; got {merge_policy!r}",
            )
        if explicit_merge_policy and merge_policy != DEFAULT_MERGE_POLICY:
            warnings.warn(
                "merge_policy should only be set away from `auto` when the user "
                "explicitly requests a human PR merge gate after every milestone; "
                f"`{merge_policy}` will park unattended/cloud chains at awaiting_pr_merge.",
                stacklevel=2,
            )
        # "manual" is an operator-facing synonym for human-reviewed merge.
        if merge_policy == "manual":
            merge_policy = "review"

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
        review_raw = raw.get("review_policy") or {}
        if not isinstance(review_raw, dict):
            raise CliError("invalid_spec", "`review_policy` must be a mapping")
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
        escalate_action = driver_raw.get("on_escalate", "force-proceed")
        if escalate_action not in ESCALATE_ACTIONS:
            raise CliError(
                "invalid_spec",
                f"driver.on_escalate must be one of {ESCALATE_ACTIONS}; got {escalate_action!r}",
            )
        robustness = driver_raw.get("robustness", "standard")
        if not isinstance(robustness, str):
            raise CliError("invalid_spec", "driver.robustness must be a string")
        auto_approve = bool(driver_raw.get("auto_approve", True))
        require_clean_base = driver_raw.get("require_clean_base", False)
        if not isinstance(require_clean_base, bool):
            raise CliError(
                "invalid_spec", "driver.require_clean_base must be a boolean"
            )
        require_anchor = driver_raw.get("require_anchor", True)
        if not isinstance(require_anchor, bool):
            raise CliError("invalid_spec", "driver.require_anchor must be a boolean")
        missing_anchor_ack = driver_raw.get("missing_anchor_ack")
        if missing_anchor_ack is not None:
            if not isinstance(missing_anchor_ack, str) or not missing_anchor_ack.strip():
                raise CliError("invalid_spec", "driver.missing_anchor_ack must be a non-empty string")
            missing_anchor_ack = missing_anchor_ack.strip()
        north_star_critical = bool(driver_raw.get("north_star_critical", False))

        # --- north_star_critical validation ---
        # Reject ``north_star_critical: true`` when the effective robustness
        # is ``bare`` or ``light``.  Use milestone-level robustness when
        # present; fall back to the driver-level robustness otherwise.
        # Never silently upgrade robustness — emit CliError instead.
        driver_robustness_canonical = normalize_robustness(robustness)
        for i, milestone in enumerate(milestones):
            effective_critical = (
                milestone.north_star_critical or north_star_critical
            )
            if not effective_critical:
                continue
            milestone_rb = milestone.robustness
            effective_robustness = (
                normalize_robustness(milestone_rb)
                if milestone_rb is not None
                else driver_robustness_canonical
            )
            if effective_robustness in ("bare", "light"):
                raise CliError(
                    "invalid_spec",
                    f"milestones[{i}] ({milestone.label!r}) has "
                    f"north_star_critical enabled but effective robustness "
                    f"is {effective_robustness!r}.  "
                    f"north_star_critical requires at least `full` robustness.",
                )

        return cls(
            milestones=milestones,
            anchors=anchors,
            launch_preconditions=launch_preconditions,
            fresh_child_admission=fresh_child_admission,
            successors=successors,
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
            escalate_action=escalate_action,
            robustness=robustness,
            auto_approve=auto_approve,
            require_anchor=require_anchor,
            missing_anchor_ack=missing_anchor_ack,
            north_star_critical=north_star_critical,
        )


@dataclass(frozen=True)
class MilestoneBoundaryEvidence:
    """Durable evidence record for a completed chain milestone.

    Carries the contract ID, milestone identity, plan name, state snapshot ref,
    commit/tip refs, and PR refs needed to satisfy chain milestone boundary
    contracts.  This is a structured record — not a loose dict — so consumers
    can rely on stable field names.
    """

    milestone_label: str
    milestone_index: int
    plan_name: str
    contract_id: str
    contract_boundary_id: str
    state_snapshot_ref: str | None = None
    commit_ref: str | None = None
    tip_ref: str | None = None
    branch_head: str | None = None
    pr_head: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "milestone_label": self.milestone_label,
            "milestone_index": self.milestone_index,
            "plan_name": self.plan_name,
            "contract_id": self.contract_id,
            "contract_boundary_id": self.contract_boundary_id,
        }
        if self.state_snapshot_ref is not None:
            payload["state_snapshot_ref"] = self.state_snapshot_ref
        if self.commit_ref is not None:
            payload["commit_ref"] = self.commit_ref
        if self.tip_ref is not None:
            payload["tip_ref"] = self.tip_ref
        if self.branch_head is not None:
            payload["branch_head"] = self.branch_head
        if self.pr_head is not None:
            payload["pr_head"] = self.pr_head
        if self.pr_number is not None:
            payload["pr_number"] = self.pr_number
        if self.pr_state is not None:
            payload["pr_state"] = self.pr_state
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MilestoneBoundaryEvidence":
        return cls(
            milestone_label=raw.get("milestone_label", ""),
            milestone_index=int(raw.get("milestone_index", -1)),
            plan_name=raw.get("plan_name", ""),
            contract_id=raw.get("contract_id", ""),
            contract_boundary_id=raw.get("contract_boundary_id", ""),
            state_snapshot_ref=raw.get("state_snapshot_ref"),
            commit_ref=raw.get("commit_ref"),
            tip_ref=raw.get("tip_ref"),
            branch_head=raw.get("branch_head"),
            pr_head=raw.get("pr_head"),
            pr_number=int(raw["pr_number"]) if raw.get("pr_number") is not None else None,
            pr_state=raw.get("pr_state"),
        )


def build_milestone_boundary_evidence(
    *,
    milestone_label: str,
    milestone_index: int,
    plan_name: str,
    contract_id: str,
    contract_boundary_id: str,
    state: "ChainState | None" = None,
    state_snapshot_ref: str | None = None,
    commit_ref: str | None = None,
    tip_ref: str | None = None,
) -> MilestoneBoundaryEvidence:
    """Construct a milestone boundary evidence record.

    When *state* is provided, commit/tip/PR refs are drawn from the current
    chain state.  Explicit keyword overrides take precedence.
    """
    branch_head: str | None = None
    pr_head: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    if state is not None:
        if commit_ref is None:
            commit_ref = state.current_milestone_base_sha
        if tip_ref is None:
            tip_ref = state.target_base_ref
        branch_head = state.branch_head
        pr_head = state.pr_head
        pr_number = state.pr_number
        pr_state = state.pr_state
    return MilestoneBoundaryEvidence(
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name=plan_name,
        contract_id=contract_id,
        contract_boundary_id=contract_boundary_id,
        state_snapshot_ref=state_snapshot_ref,
        commit_ref=commit_ref,
        tip_ref=tip_ref,
        branch_head=branch_head,
        pr_head=pr_head,
        pr_number=pr_number,
        pr_state=pr_state,
    )


@dataclass
class ChainState:
    """Persisted progress for a chain run.

    Acceptance receipt fields (SD2)
    -------------------------------
    Each completed record MAY carry an ``acceptance_receipt`` sub-dict with
    ``transaction_id``, ``snapshot_hash``, ``milestone_label``,
    ``milestone_index``, and ``plan_name`` — the lightweight pointer defined
    by :class:`AcceptanceReceipt`.  Shadow-mode chains omit this field;
    atomic/enforce mode chains MUST have a valid receipt for every completed
    record and the receipt content must match the completed record's own
    identity fields.

    Candidate invalidation metadata
    -------------------------------
    ``candidate_invalidation`` is a dict keyed by milestone label whose value
    is a list of invalidation records.  Each record is a dict with at minimum
    ``transaction_id`` (the candidate that was invalidated) and ``reason``
    (a short machine-readable reason tag, e.g. ``"stale-evidence"``,
    ``"repair-result"``, ``"content-hash-mismatch"``).  This field is
    informational for audit; it does not gate transitions on its own.
    """

    current_milestone_index: int = -1
    current_plan_name: str | None = None
    current_milestone_base_sha: str | None = None
    target_base_ref: str | None = None
    last_state: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)
    branch_head: str | None = None
    pr_head: str | None = None
    last_pushed_commit: str | None = None
    dirty_flag: bool = False
    sync_state: str | None = None
    extra_repos: list[str] = field(default_factory=list)
    chain_session: str | None = None
    resolved_workspace: str | None = None
    extra_repo_sync: list[dict[str, Any]] = field(default_factory=list)
    completion_contract_mode: str = "shadow"
    full_suite_backstop_mode: str = "shadow"
    retry_counts: dict[str, int] = field(default_factory=dict)
    ladder_stage: dict[str, str] = field(default_factory=dict)
    profile_bumps: dict[str, str] = field(default_factory=dict)
    robustness_bumps: dict[str, str] = field(default_factory=dict)
    depth_bumps: dict[str, str] = field(default_factory=dict)
    enforce_revise_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 0
    milestone_boundary_evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    candidate_invalidation: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_milestone_index": self.current_milestone_index,
            "current_plan_name": self.current_plan_name,
            "current_milestone_base_sha": self.current_milestone_base_sha,
            "target_base_ref": self.target_base_ref,
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
            "full_suite_backstop_mode": self.full_suite_backstop_mode,
            "retry_counts": dict(self.retry_counts),
            "ladder_stage": dict(self.ladder_stage),
            "profile_bumps": dict(self.profile_bumps),
            "robustness_bumps": dict(self.robustness_bumps),
            "depth_bumps": dict(self.depth_bumps),
            "enforce_revise_counts": dict(self.enforce_revise_counts),
            "metadata": dict(self.metadata),
            "milestone_boundary_evidence": dict(self.milestone_boundary_evidence),
            "candidate_invalidation": {
                label: [dict(rec) for rec in recs]
                for label, recs in self.candidate_invalidation.items()
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainState":
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

        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            CONTRACT_MODE_ENFORCE,
            FAIL_CLOSED_CONTRACT_MODES,
            normalize_contract_mode,
        )
        from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
            normalize_full_suite_backstop_mode,
        )

        raw_mode = raw.get("completion_contract_mode")
        completion_contract_mode = normalize_contract_mode(raw_mode)
        full_suite_backstop_mode = normalize_full_suite_backstop_mode(
            raw.get("full_suite_backstop_mode")
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

        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        milestone_boundary_evidence_raw = raw.get("milestone_boundary_evidence")
        if not isinstance(milestone_boundary_evidence_raw, dict):
            milestone_boundary_evidence_raw = {}
        milestone_boundary_evidence: dict[str, dict[str, Any]] = {}
        for key, val in milestone_boundary_evidence_raw.items():
            if isinstance(key, str) and isinstance(val, dict):
                milestone_boundary_evidence[key] = val

        # ── candidate_invalidation ────────────────────────────────────
        candidate_invalidation_raw = raw.get("candidate_invalidation")
        candidate_invalidation: dict[str, list[dict[str, Any]]] = {}
        if isinstance(candidate_invalidation_raw, dict):
            for label, recs in candidate_invalidation_raw.items():
                if isinstance(label, str) and isinstance(recs, list):
                    candidate_invalidation[label] = [
                        dict(r) for r in recs if isinstance(r, dict)
                    ]
        # ──────────────────────────────────────────────────────────────

        # ── atomic-mode completed-record validation ──────────────────
        # In fail-closed modes every completed record MUST carry a valid
        # acceptance_receipt that matches its own identity fields.  Missing
        # or mismatched receipts raise :class:`CliError` so the load is
        # refused rather than silently normalizing invalid evidence.
        completed_raw = list(raw.get("completed") or [])
        if completion_contract_mode in FAIL_CLOSED_CONTRACT_MODES or completion_contract_mode == CONTRACT_MODE_ENFORCE:
            for idx, record in enumerate(completed_raw):
                if not isinstance(record, dict):
                    continue
                receipt = record.get("acceptance_receipt")
                if not isinstance(receipt, dict):
                    raise CliError(
                        "invalid_chain_state",
                        f"completed[{idx}] is missing an acceptance_receipt in "
                        f"atomic/enforce mode (completion_contract_mode={completion_contract_mode!r}). "
                        f"Legacy shadow-mode states cannot be loaded in fail-closed mode.",
                    )
                rec_label = record.get("label")
                rec_plan = record.get("plan")
                rec_mi = record.get("milestone_index")
                for field in (
                    "transaction_id",
                    "snapshot_hash",
                    "source_commit_ref",
                    "runtime_identity",
                ):
                    if not isinstance(record.get(field), str) or not str(record.get(field)).strip():
                        raise CliError(
                            "invalid_chain_state",
                            f"completed[{idx}] is missing required atomic acceptance field "
                            f"{field!r}",
                        )
                if not cls._receipt_identity_matches_record(record, receipt):
                    raise CliError(
                        "invalid_chain_state",
                        f"completed[{idx}] acceptance_receipt identity mismatch: "
                        f"receipt(milestone_label={receipt.get('milestone_label')!r}, "
                        f"plan_name={receipt.get('plan_name')!r}, "
                        f"milestone_index={receipt.get('milestone_index')!r}, "
                        f"transaction_id={receipt.get('transaction_id')!r}, "
                        f"snapshot_hash={receipt.get('snapshot_hash')!r}) vs "
                        f"record(label={rec_label!r}, plan={rec_plan!r}, "
                        f"milestone_index={rec_mi!r}, "
                        f"transaction_id={record.get('transaction_id')!r}, "
                        f"snapshot_hash={record.get('snapshot_hash')!r})",
                    )
        # ──────────────────────────────────────────────────────────────

        return cls(
            current_milestone_index=int(raw.get("current_milestone_index", -1)),
            current_plan_name=raw.get("current_plan_name"),
            current_milestone_base_sha=raw.get("current_milestone_base_sha"),
            target_base_ref=raw.get("target_base_ref"),
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
            full_suite_backstop_mode=full_suite_backstop_mode,
            retry_counts=_str_int_map(raw.get("retry_counts")),
            ladder_stage=_str_str_map(raw.get("ladder_stage")),
            profile_bumps=_str_str_map(raw.get("profile_bumps")),
            robustness_bumps=_str_str_map(raw.get("robustness_bumps")),
            depth_bumps=_str_str_map(raw.get("depth_bumps")),
            enforce_revise_counts=_str_int_map(raw.get("enforce_revise_counts")),
            metadata=dict(metadata),
            milestone_boundary_evidence=milestone_boundary_evidence,
            candidate_invalidation=candidate_invalidation,
        )

    # ── Milestone boundary evidence helpers ──────────────────────────────

    def get_milestone_evidence(
        self, label: str,
    ) -> MilestoneBoundaryEvidence | None:
        """Return the structured evidence record for *label*, or ``None``."""
        raw = self.milestone_boundary_evidence.get(label)
        if not isinstance(raw, dict):
            return None
        try:
            return MilestoneBoundaryEvidence.from_dict(raw)
        except (TypeError, ValueError):
            return None

    def has_milestone_evidence(self, label: str) -> bool:
        """Return ``True`` when durable boundary evidence exists for *label*."""
        return label in self.milestone_boundary_evidence

    def set_milestone_evidence(
        self, evidence: MilestoneBoundaryEvidence,
    ) -> None:
        """Record durable boundary evidence keyed by milestone label."""
        self.milestone_boundary_evidence[evidence.milestone_label] = evidence.to_dict()

    def completed_milestone_contract_ids(self) -> dict[str, str]:
        """Return ``{milestone_label: contract_id}`` for every completed milestone with evidence."""
        result: dict[str, str] = {}
        for label, raw in self.milestone_boundary_evidence.items():
            if isinstance(raw, dict) and isinstance(raw.get("contract_id"), str):
                result[label] = raw["contract_id"]
        return result

    def enrich_completed_record(
        self,
        record: dict[str, Any],
        *,
        contract_id: str,
        contract_boundary_id: str,
    ) -> dict[str, Any]:
        """Return *record* with milestone boundary evidence fields attached.

        The returned dict is a shallow copy of *record* augmented with
        ``milestone_index``, ``contract_id``, ``contract_boundary_id``,
        ``commit_ref``, ``tip_ref``, ``branch_head``, ``pr_head``, and
        ``state_snapshot_ref`` drawn from current chain state.

        This is safe to call on records that already carry evidence fields
        (they will be overwritten with fresh values).
        """
        enriched = dict(record)
        enriched.setdefault("milestone_index", self.current_milestone_index)
        enriched["contract_id"] = contract_id
        enriched["contract_boundary_id"] = contract_boundary_id
        if self.current_milestone_base_sha:
            enriched["commit_ref"] = self.current_milestone_base_sha
        if self.target_base_ref:
            enriched["tip_ref"] = self.target_base_ref
        if self.branch_head:
            enriched["branch_head"] = self.branch_head
        if self.pr_head:
            enriched["pr_head"] = self.pr_head
        if self.pr_number is not None:
            enriched["pr_number"] = self.pr_number
        if self.pr_state:
            enriched["pr_state"] = self.pr_state
        # state_snapshot_ref is intentionally None here — it is filled in
        # by the caller when a plan state snapshot path is available.
        return enriched

    # ── Acceptance receipt helpers ──────────────────────────────────────

    def _completed_record_for_label(self, label: str) -> dict[str, Any] | None:
        for record in self.completed:
            if isinstance(record, dict) and record.get("label") == label:
                return record
        return None

    def _acceptance_plan_dir_for_record(
        self,
        label: str,
        record: dict[str, Any],
        *,
        plan_dir: Path | None = None,
    ) -> Path | None:
        if plan_dir is not None:
            return Path(plan_dir)

        plan_name = record.get("plan")
        if not isinstance(plan_name, str) or not plan_name.strip():
            return None

        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        acceptance_plan_dirs = metadata.get("acceptance_plan_dirs")
        if isinstance(acceptance_plan_dirs, dict):
            for key in (label, plan_name):
                value = acceptance_plan_dirs.get(key)
                if isinstance(value, str) and value.strip():
                    candidate = Path(value)
                    if candidate.exists():
                        return candidate

        for root_value in (
            metadata.get("chain_spec_path"),
            self.resolved_workspace,
            str(Path.cwd()),
        ):
            if not isinstance(root_value, str) or not root_value.strip():
                continue
            root_path = Path(root_value)
            if root_path.is_file() or root_path.suffix:
                root = _project_root_for_chain_spec(root_path)
            else:
                root = root_path
            try:
                candidate = resolve_plan_dir(root, plan_name)
            except CliError:
                candidate = root / ".megaplan" / "plans" / plan_name
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _receipt_identity_matches_record(
        record: dict[str, Any],
        receipt: dict[str, Any],
    ) -> bool:
        if receipt.get("milestone_label") != record.get("label"):
            return False
        if receipt.get("plan_name") != record.get("plan"):
            return False
        try:
            receipt_index = int(receipt.get("milestone_index"))
            record_index = int(record.get("milestone_index"))
        except (TypeError, ValueError):
            return False
        if receipt_index != record_index:
            return False
        for receipt_field in ("transaction_id", "snapshot_hash"):
            value = record.get(receipt_field)
            if (
                isinstance(value, str)
                and value
                and receipt.get(receipt_field) != value
            ):
                return False
        return True

    def validate_acceptance_receipt(
        self,
        label: str,
        *,
        plan_dir: Path | None = None,
        require_committed: bool | None = None,
    ) -> bool:
        """Return ``True`` only for accepted, identity-bound receipt evidence.

        Shadow/warn/off callers keep the legacy lightweight check unless
        ``require_committed`` is explicitly true.  Fail-closed modes require
        the receipt to resolve to a committed acceptance transaction, the
        transaction to be accepted, the content-addressed snapshot to load, and
        transaction/snapshot/record identity to agree on milestone, plan,
        source commit, and runtime identity.
        """
        record = self._completed_record_for_label(label)
        if record is None:
            return False
        receipt = record.get("acceptance_receipt")
        if not isinstance(receipt, dict):
            return False
        try:
            from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
                AcceptanceReceipt,
            )

            AcceptanceReceipt.from_dict(receipt)
        except (TypeError, ValueError):
            return False
        if not self._receipt_identity_matches_record(record, receipt):
            return False

        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            is_fail_closed_mode,
        )

        needs_committed = (
            is_fail_closed_mode(self.completion_contract_mode)
            if require_committed is None
            else bool(require_committed)
        )
        if not needs_committed:
            return True

        source_commit_ref = record.get("source_commit_ref")
        runtime_identity = record.get("runtime_identity")
        if not isinstance(source_commit_ref, str) or not source_commit_ref.strip():
            return False
        if not isinstance(runtime_identity, str) or not runtime_identity.strip():
            return False

        resolved_plan_dir = self._acceptance_plan_dir_for_record(
            label,
            record,
            plan_dir=plan_dir,
        )
        if resolved_plan_dir is None:
            return False

        from arnold_pipelines.megaplan.orchestration.completion_io import (
            list_committed_acceptance_transactions,
            load_acceptance_snapshot,
        )

        snapshot_hash = str(receipt.get("snapshot_hash") or "")
        transaction_id = str(receipt.get("transaction_id") or "")
        snapshot = load_acceptance_snapshot(resolved_plan_dir, snapshot_hash)
        if snapshot is None:
            return False
        if getattr(snapshot, "transaction_id", None) != transaction_id:
            return False
        if getattr(snapshot, "milestone_label", None) != record.get("label"):
            return False
        if getattr(snapshot, "plan_name", None) != record.get("plan"):
            return False
        if getattr(snapshot, "milestone_index", None) != record.get("milestone_index"):
            return False
        if getattr(snapshot, "source_commit_ref", None) != source_commit_ref:
            return False
        if getattr(snapshot, "runtime_identity", None) != runtime_identity:
            return False

        committed = list_committed_acceptance_transactions(resolved_plan_dir)
        for transaction in committed.values():
            if getattr(transaction, "transaction_id", None) != transaction_id:
                continue
            if getattr(transaction, "snapshot_hash", None) != snapshot_hash:
                continue
            if getattr(transaction, "accepted", None) is not True:
                continue
            if getattr(transaction, "tested_commit_ref", None) != source_commit_ref:
                continue
            if getattr(transaction, "tested_runtime_identity", None) != runtime_identity:
                continue
            return True
        return False

    def has_acceptance_receipt(self, label: str) -> bool:
        """Return ``True`` when *label* carries validated acceptance evidence."""
        return self.validate_acceptance_receipt(label)

    def get_acceptance_receipt(self, label: str) -> dict[str, Any] | None:
        """Return the acceptance receipt dict for *label*, or ``None``."""
        record = self._completed_record_for_label(label)
        if record is not None:
            receipt = record.get("acceptance_receipt")
            return dict(receipt) if isinstance(receipt, dict) else None
        return None

    def set_acceptance_receipt(
        self,
        label: str,
        receipt: dict[str, Any],
    ) -> None:
        """Attach or overwrite *receipt* on the completed record for *label*.

        Raises :class:`ValueError` when no completed record matches *label*.
        """
        for record in self.completed:
            if isinstance(record, dict) and record.get("label") == label:
                record["acceptance_receipt"] = dict(receipt)
                record.setdefault("milestone_index", receipt.get("milestone_index", -1))
                return
        raise ValueError(f"No completed record found for milestone {label!r}")

    # ── Candidate invalidation helpers ─────────────────────────────────

    def invalidate_candidate(
        self,
        label: str,
        *,
        transaction_id: str,
        reason: str,
        **extra: Any,
    ) -> None:
        """Record that a candidate acceptance transaction was invalidated.

        Appends an invalidation record to ``candidate_invalidation[label]``.
        """
        rec: dict[str, Any] = {
            "transaction_id": transaction_id,
            "reason": reason,
        }
        rec.update(extra)
        self.candidate_invalidation.setdefault(label, []).append(rec)

    def get_candidate_invalidations(self, label: str) -> list[dict[str, Any]]:
        """Return all invalidation records for *label*, or an empty list."""
        return list(self.candidate_invalidation.get(label, []))


def _state_path_for(spec_path: Path) -> Path:
    identity = _storage_identity_for_chain_spec(spec_path)
    project_root = _project_root_for_chain_spec(spec_path)
    digest = hashlib.sha1(str(identity).encode("utf-8")).hexdigest()[:12]
    return (
        project_root
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{identity.stem}-{digest}.json"
    )


def _legacy_state_path_for(spec_path: Path) -> Path:
    return _storage_identity_for_chain_spec(spec_path).with_name("chain_state.json")


def load_spec(spec_path: Path) -> ChainSpec:
    if not spec_path.exists():
        raise CliError("invalid_spec", f"spec file not found: {spec_path}")
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CliError("invalid_spec", f"YAML parse error: {exc}") from exc
    return ChainSpec.from_dict(raw or {})


def load_chain_state(
    spec_path: Path,
    *,
    verify_execution_binding: bool = True,
) -> ChainState:
    candidates = [path for path in _state_path_candidates_for(spec_path) if path.exists()]
    if not candidates:
        return ChainState()
    spec = load_spec(spec_path)
    loaded: list[tuple[Path, ChainState]] = [
        (path, _load_chain_state_file(path)) for path in candidates
    ]
    best_path, best_state = max(
        loaded,
        key=lambda item: _state_progress_key(item[1], path=item[0]),
    )
    # Refuse drift before compatibility normalization can rewrite the cursor
    # against a newly edited spec and make the stale binding look current.
    if verify_execution_binding:
        from arnold_pipelines.megaplan.chain.execution_binding import (
            assert_execution_binding,
        )

        assert_execution_binding(
            spec_path,
            best_state,
            operation="chain state load/resume",
        )
    else:
        # Observe-only callers must not normalize or save a cursor while
        # presenting a binding mismatch.
        return best_state
    original_state = best_state.to_dict()
    best_state = _normalize_stale_current_plan_reference(best_state)
    best_state = _normalize_advanced_completed_cursor(best_state, spec)
    canonical_path = _state_path_for(spec_path)
    if best_path != canonical_path or best_state.to_dict() != original_state:
        save_chain_state(spec_path, best_state)
    return best_state


# ── Chain state projection constants ────────────────────────────────────────
# M7: Projection adapters for chain state persistence.
# These are cursor-checked append + atomic rebuild adapters that supplement
# (not replace) the legacy full-file save.  Legacy readers consume the
# state.json file directly; new readers should prefer the projection
# snapshot or replay for cursor-validated reads.
#
# OLD-READER / NEW-WRITER METADATA:
#   - Legacy readers (all callers before M7) use load_chain_state() which
#     reads state.json directly.  These readers DO NOT validate projection
#     cursors and accept the file as authority.
#   - New writers (M7+) supplement each save_chain_state() with a
#     cursor-checked projection event appended to the history.
#   - New readers (M7+) can use rebuild_chain_state_projection() or
#     chain_state_projection_cursor() for cursor-validated reads.
#   - UNCERTAINTY: Legacy readers have no cursor validation; divergence
#     between state.json and projection history is only detectable by
#     the new readers.  Production enforcement remains disabled in M7.
#   - The projection history is an append-only ledger; it never erases
#     prior records, even on rebuild.

_CHAIN_PROJECTION_ID = "chain-state"
_CHAIN_PROJECTION_SCHEMA_VERSION = 1


def _chain_projection_dir(spec_path: Path) -> Path:
    """Return the projection storage directory for chain state events.

    Stores under ``<project_root>/.megaplan/plans/.chains/projections/``.
    """
    project_root = _project_root_for_chain_spec(spec_path)
    return project_root / ".megaplan" / "plans" / ".chains" / "projections"


def _record_chain_state_event(
    spec_path: Path,
    state: ChainState,
    *,
    event_type: str = "state_saved",
    flock: bool = True,
) -> ProjectionRecord:
    """Append a cursor-checked projection event recording the chain state save.

    The event carries the full state payload and a cursor derived from the
    current chain state file.  This is a shadow-side-effect — it supplements
    the existing full-file write without replacing it.
    """
    projection_dir = _chain_projection_dir(spec_path)
    state_path = _state_path_for(spec_path)

    # Compute a cursor from the current state file (the accepted-source record)
    source_cursor = None
    if state_path.exists():
        try:
            source_cursor = _cursor_from_path(state_path)
        except (FileNotFoundError, OSError):
            pass

    event_id = _generate_projection_event_id(_CHAIN_PROJECTION_ID, event_type)
    record = ProjectionRecord(
        event_type=event_type,
        event_id=event_id,
        payload={
            "schema_version": _CHAIN_PROJECTION_SCHEMA_VERSION,
            "state": state.to_dict(),
            "spec_path": str(_storage_identity_for_chain_spec(spec_path)),
        },
        occurred_at=now_utc(),
        cursor=source_cursor,
        idempotency_key=f"chain-save-{_storage_identity_for_chain_spec(spec_path)}-{event_id}",
    )
    return append_projection_event(
        projection_dir,
        _CHAIN_PROJECTION_ID,
        record,
        source_path=state_path,
        flock=flock,
        snapshot_dir=projection_dir,
    )


def rebuild_chain_state_projection(
    spec_path: Path,
    *,
    flock: bool = True,
) -> dict[str, Any]:
    """Atomically rebuild the chain state projection from the append-only history.

    Returns a dict with keys:
      - ``status``: ``\"rebuilt\"`` | ``\"no_history\"`` | ``\"error\"``
      - ``snapshot_path``: path to the written snapshot (if rebuilt)
      - ``projection``: the complete projected state (if rebuilt)
      - ``cursor``: the latest source cursor (if available)
      - ``record_count``: number of projection records processed
      - ``diagnostics``: list of diagnostic messages

    The rebuild writes a complete snapshot atomically so consumers see
    either the full previous version or the full new version.
    """
    projection_dir = _chain_projection_dir(spec_path)
    diagnostics: list[str] = []
    records = load_projection_history(projection_dir, _CHAIN_PROJECTION_ID)
    if not records:
        return {
            "status": "no_history",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": 0,
            "diagnostics": ["No projection history found — nothing to rebuild"],
        }

    def _fold_chain_state(
        acc: dict[str, Any], record: ProjectionRecord
    ) -> dict[str, Any]:
        """Fold: last non-empty state payload wins."""
        state_payload = record.payload.get("state")
        if isinstance(state_payload, dict):
            acc.update(state_payload)
        return acc

    try:
        projection_data = deterministic_projection_replay(
            projection_dir, _CHAIN_PROJECTION_ID, fold_fn=_fold_chain_state
        )
    except Exception as exc:
        return {
            "status": "error",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": len(records),
            "diagnostics": [f"Replay failed: {exc}"],
        }

    last_cursor = latest_projection_cursor(projection_dir, _CHAIN_PROJECTION_ID)
    snapshot_path = rebuild_projection_atomically(
        projection_dir,
        _CHAIN_PROJECTION_ID,
        projection_data,
        cursor=last_cursor,
    )
    return {
        "status": "rebuilt",
        "snapshot_path": str(snapshot_path),
        "projection": dict(projection_data),
        "cursor": last_cursor.to_dict() if last_cursor else None,
        "record_count": len(records),
        "diagnostics": diagnostics,
    }


def chain_state_projection_cursor(spec_path: Path) -> ProjectionCursor | None:
    """Return the latest cursor from the chain state projection history."""
    projection_dir = _chain_projection_dir(spec_path)
    return latest_projection_cursor(projection_dir, _CHAIN_PROJECTION_ID)


def chain_state_projection_snapshot(spec_path: Path) -> dict[str, Any] | None:
    """Return the most recent chain state projection snapshot, or None."""
    projection_dir = _chain_projection_dir(spec_path)
    snapshot_path = projection_snapshot_path(projection_dir, _CHAIN_PROJECTION_ID)
    if not snapshot_path.exists():
        return None
    try:
        import json as _json

        return _json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _generate_projection_event_id(projection_id: str, event_type: str) -> str:
    """Generate a deterministic event ID for projection events."""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    seed = f"{projection_id}:{event_type}:{ts}"
    return f"chain-proj-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def _cursor_from_path(path: Path) -> ProjectionCursor:
    """Build a ProjectionCursor from the current state of *path*."""
    resolved = path.resolve()
    record_count = 0
    if resolved.exists():
        try:
            text = resolved.read_text(encoding="utf-8")
            lines = [line for line in text.splitlines() if line.strip()]
            record_count = len(lines)
        except (FileNotFoundError, OSError):
            pass
    from arnold_pipelines.megaplan._core.io import sha256_file

    source_digest = (
        sha256_file(resolved)
        if resolved.exists()
        else "sha256:" + hashlib.sha256(b"").hexdigest()
    )
    return ProjectionCursor(
        source_path=str(resolved),
        source_record_count=record_count,
        source_digest=source_digest,
        computed_at=now_utc(),
    )


def save_chain_state(
    spec_path: Path,
    state: ChainState,
    *,
    _record_projection: bool = True,
) -> None:
    """Persist chain state with atomic JSON replacement.

    M7 (shadow): In addition to the legacy full-file atomic write, this
    function appends a cursor-checked projection event to an append-only
    history.  The projection event is recorded *after* the state file write
    succeeds so the source-of-truth file always reflects the committed state.

    Set ``_record_projection=False`` to skip the projection side-effect
    (used by internal rebuild/repair callers that should not create
    duplicate records).
    """
    state_path = _state_path_for(spec_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    spec_identity = _storage_identity_for_chain_spec(spec_path)
    metadata = dict(state.metadata)
    # A chain launched beneath a Discord-resident delegation retains the same
    # routing-only correlation/custody projection.  Internal workers and repair
    # dispatchers can then be audited without copying user content or secrets.
    from arnold_pipelines.megaplan.resident.provenance import safe_provenance_projection

    resident_delegation = safe_provenance_projection()
    if resident_delegation is not None:
        metadata.setdefault("resident_delegation", resident_delegation)
    metadata["chain_spec_path"] = str(spec_identity)
    if spec_identity.exists():
        metadata["chain_spec_sha256"] = hashlib.sha256(spec_identity.read_bytes()).hexdigest()
    # ── M7 old-reader / new-writer metadata ─────────────────────────────
    # Record the writer identity so that later readers can distinguish
    # legacy full-file writes from projection-supplemented writes.
    metadata["_m7_projection_writer"] = True
    metadata["_m7_projection_id"] = _CHAIN_PROJECTION_ID
    metadata.setdefault("_m7_projection_first_seen_at", now_utc())
    # ─────────────────────────────────────────────────────────────────────
    state.metadata = metadata
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)

    # ── M7 projection side-effect ────────────────────────────────────────
    if _record_projection:
        try:
            _record_chain_state_event(spec_path, state)
        except ProjectionCursorMismatchError as exc:
            # Shadow-mode: projection append failure is logged but never
            # blocks the write.  The state.json file is the authority;
            # the projection is supplemental evidence.
            log.warning(
                "M7 chain-state projection append blocked by cursor mismatch: %s. "
                "State file is intact; projection history may need reconciliation.",
                exc,
            )
        except Exception:
            log.warning(
                "M7 chain-state projection append failed (non-fatal). "
                "State file is intact.",
                exc_info=True,
            )


def _runtime_policy_path_for(spec_path: Path) -> Path:
    identity = _storage_identity_for_chain_spec(spec_path)
    project_root = _project_root_for_chain_spec(spec_path)
    digest = hashlib.sha1(str(identity).encode("utf-8")).hexdigest()[:12]
    return (
        project_root
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{identity.stem}-{digest}.runtime_policy.json"
    )


def load_runtime_policy(spec_path: Path) -> dict[str, Any]:
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
    path = _runtime_policy_path_for(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(overrides, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def effective_chain_policy(
    spec: ChainSpec,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overrides = overrides or {}
    prerequisite_policy = overrides.get("prerequisite_policy", spec.prerequisite_policy)
    validation_policy = overrides.get("validation_policy", spec.validation_policy)
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
        "source": "runtime_override" if overrides else "chain_yaml",
    }


def validate_anchor_paths(spec: ChainSpec, spec_path: Path) -> None:
    if spec.anchors.north_star:
        validate_anchor_source(resolve_anchor_path(spec_path, spec.anchors.north_star), label="chain anchors.north_star")
    for milestone in spec.milestones:
        if milestone.anchors.north_star:
            validate_anchor_source(resolve_anchor_path(spec_path, milestone.anchors.north_star), label=f"milestone {milestone.label!r} anchors.north_star")


def validate_required_anchor(spec: ChainSpec) -> None:
    if not spec.anchors.north_star:
        raise CliError(
            "invalid_spec",
            "this chain requires a North Star anchor. Add:\n\nanchors:\n  north_star: NORTHSTAR.md\n\nPaths resolve relative to the chain.yaml directory.",
        )


@dataclass(frozen=True)
class AnchorRequirement:
    require_anchor: bool
    missing_anchor_ack: str | None
    warning: str | None = None


def resolve_anchor_requirement(
    spec: ChainSpec,
    spec_path: Path,
    *,
    require_anchor_override: bool | None = None,
    missing_anchor_ack_override: str | None = None,
) -> AnchorRequirement:
    require_anchor = spec.require_anchor if require_anchor_override is None else require_anchor_override
    missing_anchor_ack = _clean_missing_anchor_ack(
        missing_anchor_ack_override
        if missing_anchor_ack_override is not None
        else spec.missing_anchor_ack
    )
    if spec.anchors.north_star:
        return AnchorRequirement(require_anchor=require_anchor, missing_anchor_ack=missing_anchor_ack)
    if require_anchor:
        validate_required_anchor(spec)
    if not missing_anchor_ack:
        raise CliError(
            "missing_anchor_ack",
            "this chain is opted out of the default North Star requirement but has no top-level anchors.north_star. "
            "Provide an explicit acknowledgement with `driver.missing_anchor_ack` or `--missing-anchor-ack TEXT`.",
        )
    warning = (
        "North Star requirement explicitly disabled for this chain without top-level anchors.north_star. "
        f"Acknowledgement: {missing_anchor_ack}"
    )
    if undeclared := warn_undeclared_north_star(spec, spec_path):
        warning = f"{warning} {undeclared}"
    return AnchorRequirement(
        require_anchor=False,
        missing_anchor_ack=missing_anchor_ack,
        warning=warning,
    )


def validate_anchor_requirement(
    spec: ChainSpec,
    spec_path: Path,
    *,
    require_anchor_override: bool | None = None,
    missing_anchor_ack_override: str | None = None,
) -> AnchorRequirement:
    return resolve_anchor_requirement(
        spec,
        spec_path,
        require_anchor_override=require_anchor_override,
        missing_anchor_ack_override=missing_anchor_ack_override,
    )


def _clean_missing_anchor_ack(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise CliError("missing_anchor_ack", "`missing_anchor_ack` must be a non-empty string")
    return stripped


def warn_undeclared_north_star(spec: ChainSpec, spec_path: Path) -> str | None:
    if spec.anchors.north_star:
        return None
    candidate = spec_path.parent / "NORTHSTAR.md"
    if candidate.is_file():
        message = (
            f"NORTHSTAR.md exists next to {spec_path} but is not declared. "
            "Add `anchors.north_star: NORTHSTAR.md`; anchors are not auto-discovered."
        )
        log.warning(
            "NORTHSTAR.md exists next to %s but is not declared. Add `anchors: {north_star: NORTHSTAR.md}`; anchors are not auto-discovered.",
            spec_path,
        )
        return message
    return None


def _resolve_launch_precondition_path(raw_path: str, root: Path) -> Path:
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = root / target
    return target.resolve(strict=False)


def _require_inside_root(target: Path, root: Path, label: str) -> None:
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} points outside project root {root}: {target}",
        ) from exc


def _pathspec_for_git(target: Path, root: Path) -> str:
    return target.relative_to(root).as_posix()


def _git_lines(root: Path, args: list[str]) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"unable to run git while validating launch preconditions: {exc}",
        ) from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise CliError(
            "launch_precondition_failed",
            f"git command failed while validating launch preconditions: git {' '.join(args)}; {detail}",
        )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _git_status_porcelain(root: Path, rel: str) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", rel],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"unable to run git while validating launch preconditions: {exc}",
        ) from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise CliError(
            "launch_precondition_failed",
            f"git command failed while validating launch preconditions: git status --porcelain --untracked-files=all -- {rel}; {detail}",
        )
    return [
        line.rstrip()
        for line in proc.stdout.splitlines()
        if line.strip() and not _is_runtime_status_line(line)
    ]


def _is_runtime_status_line(line: str) -> bool:
    # Strip the two-character porcelain status prefix + optional leading
    # space so we match on the raw filesystem path.  ``git status
    # --porcelain`` emits lines like ``?? path`` or `` M path``.
    path = line[3:] if len(line) > 3 else line
    # Suffixes / substrings that always denote runtime scaffolding.
    # Keep in sync with the ``.gitignore`` entries that re-ignore runtime
    # artifacts under committed ``.megaplan/initiatives/`` directories.
    #
    # Notes on the prefix convention: ``/.megaplan/<dir>/`` catches runtime
    # directories that live under a tracked initiative dir (path is
    # ``.megaplan/initiatives/<epic>/.megaplan/<dir>/...``).  For runtime
    # artifacts that sit directly inside an initiative tree *without* a
    # ``.megaplan/`` wrapper — e.g. ``repair-queue/`` or
    # ``chain_state.json`` — the patterns use only the distinguishing
    # suffix so they still match.
    runtime_parts = (
        "/.megaplan/plans/",
        "/.megaplan/epics/",
        "/.megaplan/resident/",
        "/.megaplan/cloud-sessions/",
        "/repair-queue/",
        "/chain_state.json",
    )
    return any(part in path for part in runtime_parts)


def _tracked_paths_in_head(root: Path, rel: str) -> set[str]:
    try:
        return set(_git_lines(root, ["ls-tree", "-r", "--name-only", "HEAD", "--", rel]))
    except CliError as exc:
        if "Not a valid object name HEAD" in exc.message:
            raise CliError(
                "launch_precondition_failed",
                f"required git path is not committed in HEAD: {rel}",
            ) from exc
        raise


def _validate_git_tracked_precondition(
    precondition: LaunchPreconditionSpec,
    root: Path,
    spec_path: Path,
    *,
    index: int,
) -> None:
    label = f"launch_preconditions[{index}] {precondition.name!r}"
    if precondition.path is None:
        raise CliError("invalid_spec", f"{label} missing artifact path")
    target = _resolve_launch_precondition_path(precondition.path, root)
    _require_inside_root(target, root, label)
    if not target.exists():
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: required tracked path missing at {target}",
        )
    rel = _pathspec_for_git(target, root)
    tracked = _git_lines(root, ["ls-files", "--", rel])
    head_tracked = _tracked_paths_in_head(root, rel)
    status_lines = _git_status_porcelain(root, rel)
    if target.is_file():
        if rel not in set(tracked) or rel not in head_tracked:
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: required file is not committed in HEAD: {rel}",
            )
        if status_lines:
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: required file has uncommitted changes: {rel}",
            )
        return
    if not tracked:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: required directory has no tracked files: {rel}",
        )
    if not head_tracked:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: required directory has no files committed in HEAD: {rel}",
        )
    if status_lines:
        sample = ", ".join(status_lines[:8])
        suffix = "" if len(status_lines) <= 8 else f", ... +{len(status_lines) - 8} more"
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: required directory has uncommitted changes under {rel}: {sample}{suffix}",
        )


def _validate_review_log_clean(
    *,
    contents: str,
    target: Path,
    label: str,
    spec_path: Path,
) -> None:
    for line in contents.splitlines():
        stripped = line.strip()
        if re.match(r"^- [HD]\d+\b.*: `BLOCK`", stripped):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: review log contains blocking verdict in {target}: {stripped}",
            )
        if "returned `BLOCK`" in stripped and not stripped.startswith("No "):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: review log contains blocking summary in {target}: {stripped}",
            )

    sections = re.split(r"^## ", contents, flags=re.MULTILINE)
    for section in sections:
        if "`PASS WITH EDIT`" not in section and "PASS WITH\nEDIT" not in section:
            continue
        if "edits were applied" in section.lower():
            continue
        title = section.splitlines()[0] if section.splitlines() else "<untitled>"
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: review log section has unaddressed PASS WITH EDIT verdicts in {target}: {title}",
        )


def _completed_milestone_labels(state: ChainState) -> set[str]:
    labels: set[str] = set()
    for record in state.completed:
        if not isinstance(record, dict):
            continue
        label = record.get("label")
        status = record.get("status")
        if isinstance(label, str) and status == "done":
            labels.add(label)
    return labels


def _completion_record_by_label(state: ChainState) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    duplicate_labels: set[str] = set()
    for record in state.completed:
        if not isinstance(record, dict):
            continue
        label = record.get("label")
        if not isinstance(label, str) or not label:
            continue
        if label in records:
            duplicate_labels.add(label)
        records[label] = record
    if duplicate_labels:
        raise CliError(
            "launch_precondition_failed",
            f"prerequisite chain state has duplicate completed records for {sorted(duplicate_labels)}",
        )
    return records


def _validate_completed_record_evidence(
    record: dict[str, Any],
    *,
    label: str,
    prerequisite_spec: ChainSpec,
    precondition_label: str,
    dependent_spec_path: Path,
    require_manifest: bool,
) -> None:
    status = record.get("status")
    if status != "done":
        raise CliError(
            "launch_precondition_failed",
            f"{precondition_label} failed for {dependent_spec_path}: prerequisite milestone {label!r} status must be 'done'; got {status!r}",
        )
    plan = record.get("plan")
    if not isinstance(plan, str) or not plan.strip():
        raise CliError(
            "launch_precondition_failed",
            f"{precondition_label} failed for {dependent_spec_path}: prerequisite milestone {label!r} has no plan name",
        )
    if prerequisite_spec.merge_policy == "review":
        pr_number = record.get("pr_number")
        pr_state = record.get("pr_state")
        if not isinstance(pr_number, int) or pr_state != "merged":
            local_commit_sha = record.get("local_commit_sha")
            publication_evidence = record.get("publication_evidence")
            if require_manifest and (
                (isinstance(local_commit_sha, str) and local_commit_sha.strip())
                or publication_evidence == "chain_state_only"
            ):
                return
            raise CliError(
                "launch_precondition_failed",
                f"{precondition_label} failed for {dependent_spec_path}: prerequisite milestone {label!r} requires merged PR evidence",
            )


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"unable to hash launch prerequisite file {path}: {exc}",
        ) from exc


def _validation_receipt_rel_path(
    root: Path, chain_path: Path, *, milestone_label: str, validation_kind: str
) -> str:
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", milestone_label).strip("-")
    safe_kind = re.sub(r"[^A-Za-z0-9_.-]+", "-", validation_kind).strip("-")
    return _pathspec_for_git(chain_path.with_name(f"validation-{safe_label}-{safe_kind}.json"), root)


def _validate_manifest_validation_receipt(
    *,
    root: Path,
    chain_path: Path,
    spec_path: Path,
    label: str,
    milestone: MilestoneSpec,
    validation: MilestoneValidationSpec,
    seen_proofs: set[str],
) -> None:
    receipt_rel = _validation_receipt_rel_path(
        root,
        chain_path,
        milestone_label=milestone.label,
        validation_kind=validation.kind,
    )
    if receipt_rel not in seen_proofs:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest missing validation receipt {receipt_rel} for {milestone.label!r}",
        )
    receipt_path = (root / receipt_rel).resolve()
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: validation receipt missing at {receipt_path}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: validation receipt {receipt_rel} is invalid JSON: {exc}",
        ) from exc
    if not isinstance(receipt, dict):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: validation receipt {receipt_rel} must be an object",
        )
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
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: validation receipt {receipt_rel} has invalid {key}; expected {expected_value!r}",
            )
    for key, rel_path in (
        ("validator_sha256", validation.validator),
        ("conformance_sha256", validation.conformance),
        ("traceability_sha256", validation.traceability),
    ):
        if not isinstance(rel_path, str):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: validation receipt {receipt_rel} missing path for {key}",
            )
        target = (root / rel_path).resolve()
        if not target.is_file() or receipt.get(key) != _sha256_file(target):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: validation receipt {receipt_rel} has stale {key}",
            )


def _require_manifest_string(
    obj: dict[str, Any],
    key: str,
    *,
    manifest_path: Path,
    label: str,
    dependent_spec_path: Path,
) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {dependent_spec_path}: completion manifest {manifest_path} missing string field {key!r}",
        )
    return value


def _validate_manifest_file_hash(
    manifest_entry: dict[str, Any],
    *,
    path_key: str,
    hash_key: str,
    root: Path,
    manifest_path: Path,
    label: str,
    dependent_spec_path: Path,
) -> Path:
    rel_path = _require_manifest_string(
        manifest_entry,
        path_key,
        manifest_path=manifest_path,
        label=label,
        dependent_spec_path=dependent_spec_path,
    )
    expected_hash = _require_manifest_string(
        manifest_entry,
        hash_key,
        manifest_path=manifest_path,
        label=label,
        dependent_spec_path=dependent_spec_path,
    )
    target = _resolve_launch_precondition_path(rel_path, root)
    _require_inside_root(target, root, label)
    if not target.is_file():
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {dependent_spec_path}: completion manifest file missing at {target}",
        )
    actual_hash = _sha256_file(target)
    if actual_hash != expected_hash:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {dependent_spec_path}: completion manifest hash mismatch for {rel_path}",
        )
    return target


def _validate_completion_manifest(
    *,
    precondition: LaunchPreconditionSpec,
    root: Path,
    spec_path: Path,
    label: str,
    chain_path: Path,
    prereq_spec: ChainSpec,
    prereq_state: ChainState,
    records_by_label: dict[str, dict[str, Any]],
) -> None:
    manifest_path = chain_path.with_name("completion-manifest.json")
    if not manifest_path.is_file():
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite completion manifest missing at {manifest_path}",
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest is invalid JSON: {exc}",
        ) from exc
    if not isinstance(raw, dict):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest must be an object",
        )
    schema = raw.get("schema")
    if schema != "arnold.megaplan.chain_completion_manifest.v1":
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest has unsupported schema {schema!r}",
        )
    chain_entry = raw.get("chain")
    if not isinstance(chain_entry, dict):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest missing chain object",
        )
    manifest_chain_path = _require_manifest_string(
        chain_entry,
        "path",
        manifest_path=manifest_path,
        label=label,
        dependent_spec_path=spec_path,
    )
    expected_chain_rel = _pathspec_for_git(chain_path, root)
    if manifest_chain_path != expected_chain_rel:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest chain path mismatch; expected {expected_chain_rel}, got {manifest_chain_path!r}",
        )
    manifest_chain_hash = _require_manifest_string(
        chain_entry,
        "sha256",
        manifest_path=manifest_path,
        label=label,
        dependent_spec_path=spec_path,
    )
    actual_chain_hash = _sha256_file(chain_path)
    if manifest_chain_hash != actual_chain_hash:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest chain hash mismatch for {manifest_chain_path}",
        )
    if prereq_spec.anchors.north_star:
        north_star_entry = raw.get("north_star")
        if not isinstance(north_star_entry, dict):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: completion manifest missing north_star object",
            )
        north_star_path = resolve_anchor_path(chain_path, prereq_spec.anchors.north_star)
        manifest_north_star_path = _require_manifest_string(
            north_star_entry,
            "path",
            manifest_path=manifest_path,
            label=label,
            dependent_spec_path=spec_path,
        )
        expected_north_star_rel = _pathspec_for_git(north_star_path, root)
        if manifest_north_star_path != expected_north_star_rel:
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: completion manifest North Star path mismatch; expected {expected_north_star_rel}, got {manifest_north_star_path!r}",
            )
        _validate_manifest_file_hash(
            north_star_entry,
            path_key="path",
            hash_key="sha256",
            root=root,
            manifest_path=manifest_path,
            label=label,
            dependent_spec_path=spec_path,
        )
    milestones = raw.get("milestones")
    if not isinstance(milestones, list) or any(not isinstance(item, dict) for item in milestones):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest milestones must be a list of objects",
        )
    expected_labels = [milestone.label for milestone in prereq_spec.milestones]
    manifest_labels = [item.get("label") for item in milestones]
    if manifest_labels != expected_labels:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest milestone order mismatch; expected {expected_labels}, got {manifest_labels}",
        )
    seen_proofs: set[str] = set()
    for manifest_milestone, spec_milestone in zip(milestones, prereq_spec.milestones):
        record = records_by_label[spec_milestone.label]
        manifest_brief_path = _require_manifest_string(
            manifest_milestone,
            "brief_path",
            manifest_path=manifest_path,
            label=label,
            dependent_spec_path=spec_path,
        )
        expected_brief_path = _pathspec_for_git(
            _resolve_launch_precondition_path(spec_milestone.idea, root),
            root,
        )
        if manifest_brief_path != expected_brief_path:
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: completion manifest brief path mismatch for {spec_milestone.label!r}; expected {expected_brief_path}, got {manifest_brief_path!r}",
            )
        _validate_manifest_file_hash(
            manifest_milestone,
            path_key="brief_path",
            hash_key="brief_sha256",
            root=root,
            manifest_path=manifest_path,
            label=label,
            dependent_spec_path=spec_path,
        )
        if manifest_milestone.get("status") != "done":
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: completion manifest milestone {spec_milestone.label!r} status must be 'done'",
            )
        if manifest_milestone.get("plan") != record.get("plan"):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: completion manifest plan mismatch for {spec_milestone.label!r}",
            )
        if prereq_spec.merge_policy == "review":
            record_pr_number = record.get("pr_number")
            record_pr_state = record.get("pr_state")
            record_local_commit = record.get("local_commit_sha")
            if isinstance(record_pr_number, int) and record_pr_state == "merged":
                if manifest_milestone.get("pr_number") != record_pr_number or manifest_milestone.get("pr_state") != "merged":
                    raise CliError(
                        "launch_precondition_failed",
                        f"{label} failed for {spec_path}: completion manifest merged PR evidence mismatch for {spec_milestone.label!r}",
                    )
                pr_merge_sha = manifest_milestone.get("pr_merge_sha")
                if not isinstance(pr_merge_sha, str) or not pr_merge_sha.strip():
                    raise CliError(
                        "launch_precondition_failed",
                        f"{label} failed for {spec_path}: completion manifest milestone {spec_milestone.label!r} missing pr_merge_sha",
                    )
            elif isinstance(record_local_commit, str) and record_local_commit.strip():
                if manifest_milestone.get("local_commit_sha") != record_local_commit:
                    raise CliError(
                        "launch_precondition_failed",
                        f"{label} failed for {spec_path}: completion manifest local commit evidence mismatch for {spec_milestone.label!r}",
                    )
            else:
                if manifest_milestone.get("publication_evidence") != "chain_state_only":
                    raise CliError(
                        "launch_precondition_failed",
                        f"{label} failed for {spec_path}: completion manifest publication evidence mismatch for {spec_milestone.label!r}",
                    )
        proof_artifacts = manifest_milestone.get("proof_artifacts")
        if not isinstance(proof_artifacts, list):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: completion manifest milestone {spec_milestone.label!r} proof_artifacts must be a list",
            )
        for proof in proof_artifacts:
            if not isinstance(proof, dict):
                raise CliError(
                    "launch_precondition_failed",
                    f"{label} failed for {spec_path}: completion manifest proof artifact for {spec_milestone.label!r} must be an object",
                )
            proof_path = _validate_manifest_file_hash(
                proof,
                path_key="path",
                hash_key="sha256",
                root=root,
                manifest_path=manifest_path,
                label=label,
                dependent_spec_path=spec_path,
            )
            seen_proofs.add(_pathspec_for_git(proof_path, root))
        for validation in spec_milestone.validate:
            _validate_manifest_validation_receipt(
                root=root,
                chain_path=chain_path,
                spec_path=spec_path,
                label=label,
                milestone=spec_milestone,
                validation=validation,
                seen_proofs=seen_proofs,
            )
    if not seen_proofs:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: completion manifest contains no proof artifacts",
        )
    metadata = prereq_state.metadata.get("completion_manifest")
    if isinstance(metadata, dict):
        recorded_hash = metadata.get("sha256")
        if recorded_hash is not None and recorded_hash != _sha256_file(manifest_path):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: prerequisite state completion_manifest hash does not match {manifest_path}",
            )


def _validate_chain_completed_precondition(
    precondition: LaunchPreconditionSpec,
    root: Path,
    spec_path: Path,
    *,
    index: int,
) -> None:
    label = f"launch_preconditions[{index}] {precondition.name!r}"
    raw_chain = precondition.chain
    if not raw_chain:
        raise CliError("invalid_spec", f"{label} missing chain path")
    chain_path = _resolve_launch_precondition_path(raw_chain, root)
    _require_inside_root(chain_path, root, label)
    if not chain_path.is_file():
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain not found at {chain_path}",
        )
    prereq_spec = load_spec(chain_path)
    canonical_state_path = _state_path_for(chain_path)
    legacy_state_path = _legacy_state_path_for(chain_path)
    if not canonical_state_path.exists():
        if legacy_state_path.exists():
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: prerequisite chain state is legacy/ambiguous at {legacy_state_path}; rerun or refresh {chain_path}",
            )
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain state missing at {canonical_state_path}",
        )
    prereq_state = load_chain_state(chain_path)
    metadata = prereq_state.metadata
    expected_path = str(chain_path.resolve(strict=False))
    actual_path = metadata.get("chain_spec_path")
    if actual_path != expected_path:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain state path metadata is stale or missing; expected {expected_path}, got {actual_path!r}",
        )
    expected_hash = hashlib.sha256(chain_path.read_bytes()).hexdigest()
    actual_hash = metadata.get("chain_spec_sha256")
    if actual_hash != expected_hash:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain state hash is stale for {chain_path}",
        )
    if prereq_state.current_plan_name is not None:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain {chain_path} still has active plan {prereq_state.current_plan_name!r}",
        )
    if prereq_state.current_milestone_index < len(prereq_spec.milestones):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain {chain_path} has not advanced past all milestones",
        )
    required_labels = [milestone.label for milestone in prereq_spec.milestones]
    records_by_label = _completion_record_by_label(prereq_state)
    completed = _completed_milestone_labels(prereq_state)
    missing = [label for label in required_labels if label not in completed]
    if missing:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: prerequisite chain {chain_path} incomplete; missing milestones {missing}",
        )
    for required_label in required_labels:
        _validate_completed_record_evidence(
            records_by_label[required_label],
            label=required_label,
            prerequisite_spec=prereq_spec,
            precondition_label=label,
            dependent_spec_path=spec_path,
            require_manifest=precondition.require_manifest,
        )
    if precondition.require_manifest:
        _validate_completion_manifest(
            precondition=precondition,
            root=root,
            spec_path=spec_path,
            label=label,
            chain_path=chain_path,
            prereq_spec=prereq_spec,
            prereq_state=prereq_state,
            records_by_label=records_by_label,
        )


_FINITE_CANARY_SCHEMA = "arnold.megaplan.finite_canary_receipt.v1"
_FINITE_CANARY_PHASES = list(DIRECT_SUCCESS_ROUTE)
_FINITE_CANARY_REVISED_PHASES = list(ONE_REVISION_SUCCESS_ROUTE)
_FINITE_CANARY_ROLES = {
    "canary_spec",
    "proof_map",
    "traceability",
    "run_receipt",
    "independent_conformance_receipt",
    "host_zero_recovery_fence_receipt",
    "host_predeploy_receipt",
    "v2_terminal_fence_receipt",
    "detached_reviewer_source",
    "dispatch_ledger",
    "phase_receipts_manifest",
    "privilege_receipts_manifest",
    "plan_state",
    "gate_result",
    "cloud_spec",
    "custody_manifest",
    "unfinished_work_ledger",
    "supersession_index",
    "finite_canary_operational_route",
}
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OBJECT_RE = re.compile(r"[0-9a-f]{40}\Z")

_FINITE_CANARY_OPERATIONAL_SUBSTRATES = [
    {
        "id": "cloud-observation-preflight-repair-v2",
        "disposition": "CONSUMED_BOUNDED_SUBSTRATE",
    },
    {
        "id": "t1.9-zero-recovery-launcher",
        "disposition": "CONSUMED_ON_SUCCESS",
    },
]
_FINITE_CANARY_DEFERRED_OBLIGATION_IDS = (
    "F1.platform_capacity_storage_hardening",
    "F1.physically_minimal_image",
    "F1.cross_pipeline_model_isolation",
    "F1.t1_5_monotonic_consumed_grant",
    "F1.production_recovery_owner",
    "F1.exact_occurrence_handoff",
    "F1.notification_occurrence_version_custody",
    "F1.t1_5_topology_retirement",
    "F1.t1_7_transactional_storage",
    "F1.t1_10_notification_policy",
    "F2.t1_1_universal_admission",
    "F2.t1_2_attempt_model_handling",
    "F2.provider_attested_model_identity",
    "F2.t1_3_transport_integration",
    "F2.t1_4_t1_6_release_closure",
)
_FINITE_CANARY_DEFERRED_OBLIGATIONS = [
    {
        "id": obligation_id,
        "phase": obligation_id.split(".", 1)[0],
        "status": "DEFERRED_POST_CANARY",
        "operational_disposition": "NOT_CONSUMED_OPERATIONAL_CANARY",
    }
    for obligation_id in _FINITE_CANARY_DEFERRED_OBLIGATION_IDS
]
_FINITE_CANARY_DEFERRED_OWNERS = {
    "F1": "f1-owner-storage-recovery-hardening",
    "F2": "f2-admission-model-effect-release-closure",
}
_FINITE_CANARY_CUSTODY_OBLIGATIONS = [
    {
        **obligation,
        "owner_milestone": _FINITE_CANARY_DEFERRED_OWNERS[obligation["phase"]],
        "acceptance_gate": "INDEPENDENT_COMPLETION_MANIFEST_REQUIRED",
        "evidence_ref": (
            "proof-map.json#/"
            + _FINITE_CANARY_DEFERRED_OWNERS[obligation["phase"]]
        ),
        "required_claim_id": obligation["id"],
    }
    for obligation in _FINITE_CANARY_DEFERRED_OBLIGATIONS
]
_FINITE_CANARY_PRELAUNCH_GATE_OWNERS = (
    (
        "accepted_finite_canary_candidate",
        "finite-canary release operator and independent exact-commit reviewer",
    ),
    ("trusted_host_control_state", "typed SSH zero-recovery provider"),
    ("bounded_fence_reclaim", "typed SSH zero-recovery provider"),
    ("durable_failure_reconciliation", "typed SSH zero-recovery provider"),
    ("built_image_four_phase_smoke", "finite-canary release operator"),
    (
        "live_capacity_and_predeploy",
        "finite-canary release operator through the typed SSH zero-recovery provider",
    ),
    (
        "finite_canary_and_stable_exit",
        "finite-canary runner and independent conformance reviewer",
    ),
    (
        "remote_custody_and_fresh_clone",
        "release custody operator and independent reconstruction reviewer",
    ),
)
_FINITE_CANARY_PENDING_PRELAUNCH_GATES = [
    {
        "id": gate_id,
        "blocking_phase": "T6.2_PRELAUNCH",
        "owner": owner,
        "status": "PENDING",
        "acceptance_gate": "INDEPENDENT_EXACT_EVIDENCE_REQUIRED",
        "evidence": {"path": None, "sha256": None, "status": "PENDING"},
    }
    for gate_id, owner in _FINITE_CANARY_PRELAUNCH_GATE_OWNERS
]
_FINITE_CANARY_HOST_CONTROL_STATE_CONTRACT = {
    "global_containment_marker": {
        "schema": "arnold.cloud.zero_recovery_marker.v2",
        "exact_fields": ["schema", "profile", "scope", "active"],
        "transaction_independent": True,
        "publish_after": [
            "durable_unit_containment_proof",
            "durable_systemd_job_containment_proof",
            "durable_session_containment_proof",
            "durable_process_containment_proof",
        ],
        "canonical_reuse": (
            "ALLOWED_ONLY_AFTER_FRESH_DURABLE_CONTAINMENT_REPROOF"
        ),
        "mismatch": "HARD_NO_GO",
    },
    "per_attempt_records": {
        "records": ["intent", "apply", "verify", "failure"],
        "exact_binding_fields": [
            "transaction_id", "transaction_digest", "action",
        ],
        "fresh_retry": "NEW_SUPPORTED_TRANSACTION_AND_FRESH_EVIDENCE",
    },
    "failure_evidence": {
        "pre_intent": (
            "NO_MUTATION_FAIL_CLOSED_SUPPORTED_CALLER_CAPTURED_TYPED_ERROR"
        ),
        "post_intent_partial_post_prune": (
            "DURABLE_O_EXCL_HOST_FAILURE_RECEIPT"
        ),
    },
}
_FINITE_CANARY_ROUTE_HOST_CONTROL_STATE = {
    "status": "PRELAUNCH_REQUIRED",
    "location": (
        "fixed_host_path_outside_all_historical_and_canary_workspaces"
    ),
    "directory_identity": {
        "type": "directory",
        "uid": 0,
        "gid": 0,
        "mode": "0700",
        "symlink_free": True,
    },
    "writes": "dirfd_relative_no_follow_atomic_file_and_directory_fsync",
    "contains": [
        "transaction_independent_global_containment_marker_v2",
        "per_attempt_transaction_intents",
        "per_attempt_apply_and_verify_receipts",
        "bootstrap_success_and_failure_receipts",
        "reconciliation_receipts",
    ],
    "global_marker_exact_fields": ["schema", "profile", "scope", "active"],
    "global_marker_publication": (
        "only_after_durable_unit_job_session_process_containment_proof"
    ),
    "global_marker_reuse": (
        "same_canonical_marker_after_fresh_durable_containment_reproof"
    ),
    "per_attempt_record_exact_fields": [
        "transaction_id", "transaction_digest", "action",
    ],
    "fresh_retry": "new_supported_transaction_and_fresh_evidence",
    "global_marker_mismatch": "HARD_NO_GO",
}
_FINITE_CANARY_CUSTODY_ITEM_STATUSES = {
    "cloud-observation-preflight-rejected-v1":
        "CLEAN_REJECTED_PENDING_BOUNDED_REPAIR_NOT_PREDEPLOY_AUTHORITY",
    "cloud-observation-preflight-repair-v2":
        "CLEAN_ACCEPTED_BOUNDED_SOURCE_INTEGRATION_NOT_PREDEPLOY_AUTHORITY",
    "t1.2-partial-contract-bundles": "DIRTY_PRESERVED_4_PATHS",
    "run-authority-containment": "CLEAN_LOCAL_INTEGRATION_ELIGIBLE_NOT_T0_COMPLETE",
    "t1.1-admission": "DIRTY_PRESERVED_19_PATHS_6_PASS_1_FAIL",
    "t1.7-storage": "DIRTY_PRESERVED_16_PATHS_STAGED_AND_UNSTAGED_79_PASS_1_FAIL",
    "t1.10-notification-rejected": "CLEAN_REJECTED_EVIDENCE_ONLY",
    "t1.5-oversized-rejected": "CLEAN_REJECTED_EVIDENCE_ONLY",
    "t1.5-pass3-rejected": "CLEAN_HARD_FAIL_NOT_CONSUMED_OPERATIONAL_CANARY",
    "t1.8-bounded-release-component": "CLEAN_ACCEPTED_BOUNDED_LOCAL_STAGE_A_ONLY",
    "t1.3-bounded-transport-component": "ACCEPTED_STAGE_A_COMPONENT_ONLY",
    "t5.1-evidence-schema": "CLEAN_CANDIDATE_FOUR_OWNER_DECISIONS_OUTSTANDING",
    "t1.4-prepared-empty-lane": "CLEAN_NO_EDITS_PREPARED_ONLY",
    "t1.9-zero-recovery-launcher":
        "IMPLEMENTED_FINITE_CANARY_LAUNCHER_PENDING_LIVE_ACCEPTANCE",
}


def _finite_canary_custody_contract(
    custody: Any,
) -> tuple[list[dict[str, str]], list[dict[str, str]]] | None:
    """Return the exact substrate/deferred contract, or fail closed.

    Archival custody items are deliberately not the obligation universe.  The
    two operational substrates and fifteen F1/F2 obligations are independent,
    typed, duplicate-free collections with exact status semantics.
    """
    expected_fields = {
        "schema", "captured_at", "empty_sha256", "canonical_checklist",
        "live_cloud_evidence", "capacity_cut", "isolation_receipt_contract",
        "model_evidence_contract", "dirty_snapshot_commits",
        "dirty_capture_recipe", "operational_substrates",
        "deferred_obligations", "items", "contract_updated_at",
        "prelaunch_release_gates", "trusted_host_control_state_contract",
    }
    if (
        not isinstance(custody, dict)
        or set(custody) != expected_fields
        or custody.get("schema")
        != "arnold.critique_ledger.unfinished_work_custody.v3"
        or _parse_iso_datetime(custody.get("contract_updated_at")) is None
        or custody.get("prelaunch_release_gates")
        != _FINITE_CANARY_PENDING_PRELAUNCH_GATES
        or custody.get("trusted_host_control_state_contract")
        != _FINITE_CANARY_HOST_CONTROL_STATE_CONTRACT
    ):
        return None
    items = custody.get("items")
    if not isinstance(items, list) or len(items) != len(
        _FINITE_CANARY_CUSTODY_ITEM_STATUSES
    ):
        return None
    item_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            return None
        item_id = item.get("id")
        if (
            not isinstance(item_id, str)
            or item_id not in _FINITE_CANARY_CUSTODY_ITEM_STATUSES
            or item.get("status") != _FINITE_CANARY_CUSTODY_ITEM_STATUSES[item_id]
        ):
            return None
        item_ids.append(item_id)
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != set(
        _FINITE_CANARY_CUSTODY_ITEM_STATUSES
    ):
        return None

    substrates = custody.get("operational_substrates")
    obligations = custody.get("deferred_obligations")
    if not isinstance(substrates, list) or not isinstance(obligations, list):
        return None
    if any(
        not isinstance(entry, dict)
        or set(entry) != {"id", "disposition"}
        or not isinstance(entry.get("id"), str)
        for entry in substrates
    ):
        return None
    expected_substrates = _FINITE_CANARY_OPERATIONAL_SUBSTRATES
    expected_obligations = _FINITE_CANARY_DEFERRED_OBLIGATIONS
    if (
        substrates != expected_substrates
        or obligations != _FINITE_CANARY_CUSTODY_OBLIGATIONS
        or len({entry["id"] for entry in substrates}) != len(substrates)
        or len({entry["id"] for entry in obligations}) != len(obligations)
    ):
        return None
    return expected_substrates, expected_obligations


def _finite_canary_completion_contract_is_valid(
    substrates: Any,
    obligations: Any,
    *,
    expected_substrates: list[dict[str, str]],
    expected_obligations: list[dict[str, str]],
) -> bool:
    if not isinstance(substrates, list) or not isinstance(obligations, list):
        return False
    if any(
        not isinstance(entry, dict)
        or set(entry) != {"id", "disposition"}
        or not isinstance(entry.get("id"), str)
        for entry in substrates
    ) or any(
        not isinstance(entry, dict)
        or set(entry)
        != {"id", "phase", "status", "operational_disposition"}
        or not isinstance(entry.get("id"), str)
        for entry in obligations
    ):
        return False
    return bool(
        substrates == expected_substrates
        and obligations == expected_obligations
        and len({entry["id"] for entry in substrates}) == len(substrates)
        and len({entry["id"] for entry in obligations}) == len(obligations)
    )


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _strict_json_document(path: Path, *, label: str, spec_path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary receipt is not strict JSON: {exc}",
        ) from exc


_FINITE_CANARY_FENCE_UNITS = [
    "megaplan-watchdog-ensure.timer", "megaplan-resident-ensure.timer",
    "megaplan-progress-audit.timer", "megaplan-repair-trigger.path",
    "megaplan-watchdog-ensure.service", "megaplan-resident-ensure.service",
    "megaplan-progress-audit.service", "megaplan-repair-trigger.service",
]


def _finite_canary_fence_is_valid(fence: Any) -> bool:
    units = fence.get("units") if isinstance(fence, dict) else None
    marker = fence.get("marker") if isinstance(fence, dict) else None
    marker_raw = (
        json.dumps(
            {
                "active": True,
                "profile": "ZERO_RECOVERY_NONROOT_FINITE_CANARY",
                "schema": "arnold.cloud.zero_recovery_marker.v2",
                "scope": "HOST_GLOBAL_PERSISTENT_CONTAINMENT",
            },
            sort_keys=True,
        )
        + "\n"
        if isinstance(fence, dict)
        else ""
    ).encode()
    return bool(
        isinstance(fence, dict)
        and set(fence) == {
            "schema", "status", "stage", "transaction_id", "transaction_digest",
            "marker", "units", "forbidden_sessions", "forbidden_processes", "systemd_jobs", "observed_at",
        }
        and fence.get("schema") == "arnold.cloud.zero_recovery_host_fence.v1"
        and fence.get("status") == "passed"
        and fence.get("stage") == "verify"
        and isinstance(fence.get("transaction_id"), str)
        and fence.get("transaction_id")
        and isinstance(fence.get("transaction_digest"), str)
        and _SHA256_RE.fullmatch(fence.get("transaction_digest"))
        and isinstance(marker, dict)
        and set(marker)
        == {"path", "sha256", "uid", "gid", "mode", "st_dev", "st_ino"}
        and marker.get("path") == "/var/lib/arnold-zero-recovery/active.json"
        and marker.get("sha256") == hashlib.sha256(marker_raw).hexdigest()
        and marker.get("uid") == 0
        and marker.get("gid") == 0
        and marker.get("mode") == 0o600
        and type(marker.get("st_dev")) is int
        and type(marker.get("st_ino")) is int
        and marker.get("st_dev") >= 0
        and marker.get("st_ino") > 0
        and fence.get("forbidden_sessions") == []
        and fence.get("forbidden_processes") == []
        and fence.get("systemd_jobs") == []
        and isinstance(units, list)
        and [item.get("unit") for item in units if isinstance(item, dict)]
        == _FINITE_CANARY_FENCE_UNITS
        and all(
            isinstance(item, dict)
            and set(item) == {
                "unit", "load_state", "active_state", "unit_file_state",
                "persistent_mask", "state",
            }
            and (
                (
                    item.get("state") == "masked"
                    and item.get("active_state") == "inactive"
                    and item.get("unit_file_state") == "masked"
                    and item.get("persistent_mask") is True
                )
                or (
                    item.get("state") == "absent"
                    and item.get("load_state") == "not-found"
                    and item.get("active_state") == "inactive"
                    and item.get("unit_file_state") in {"", "disabled"}
                    and item.get("persistent_mask") is False
                )
            )
            for item in units
        )
        and _parse_iso_datetime(fence.get("observed_at")) is not None
    )


def _finite_canary_conformance_has_trust_evidence(conformance: Any) -> bool:
    if not isinstance(conformance, dict):
        return False
    unsigned = dict(conformance)
    attestation_digest = unsigned.pop("attestation_digest", None)
    reviewer = conformance.get("reviewer")
    return bool(
        set(conformance) == {
            "schema", "status", "subject", "run_receipt_sha256", "checks",
            "reviewer", "reviewed_at", "trust_anchor", "review_input_sha256",
            "review_execution", "attestation_digest",
        }
        and isinstance(reviewer, dict)
        and set(reviewer) == {"kind", "identity", "source_sha256"}
        and reviewer.get("kind") == "detached_host_process"
        and isinstance(reviewer.get("identity"), str)
        and reviewer.get("identity") == "arnold.chain.finite_canary_validator"
        and isinstance(reviewer.get("source_sha256"), str)
        and _SHA256_RE.fullmatch(reviewer.get("source_sha256"))
        and conformance.get("trust_anchor") == "arnold.detached_host_reviewer.v1"
        and isinstance(conformance.get("review_input_sha256"), dict)
        and conformance.get("review_execution")
        == {"mode": "detached_subprocess", "exit_code": 0, "result": "passed"}
        and _parse_iso_datetime(conformance.get("reviewed_at")) is not None
        and isinstance(attestation_digest, str)
        and hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == attestation_digest
    )


def _finite_canary_review_inputs_match(
    conformance: Any,
    artifacts_by_role: dict[str, tuple[Path, str]],
    root: Path,
) -> bool:
    if not isinstance(conformance, dict):
        return False
    reviewer_source = artifacts_by_role.get("detached_reviewer_source")
    if reviewer_source is None:
        return False
    return bool(
        reviewer_source[0] == (root / "arnold_pipelines/megaplan/chain/spec.py").resolve()
        and conformance.get("reviewer", {}).get("source_sha256") == reviewer_source[1]
        and conformance.get("review_input_sha256")
        == {
            role: digest
            for role, (_path, digest) in artifacts_by_role.items()
            if role != "independent_conformance_receipt"
        }
    )


def _finite_canary_repository_integrity_is_valid(
    checkpoints: Any,
    *,
    source_commit: str,
    source_tree: str,
    phases: list[str] | None = None,
) -> bool:
    expected_names = ["baseline"]
    for phase in phases if phases is not None else _FINITE_CANARY_PHASES:
        expected_names.extend([f"pre:{phase}", f"post:{phase}"])
    expected_names.append("final")
    if not isinstance(checkpoints, list) or len(checkpoints) != len(expected_names):
        return False
    allowed_roots = (
        "megaplan/initiatives/critique-ledger-safe-v3-canary/receipts/",
        f"megaplan/plans/critique-ledger-cl2-planning-canary/",
    )
    schema_paths = {
        f".megaplan/schemas/{filename}" for filename in SCHEMAS
    }
    engine_runtime_paths = {
        ".megaplan/.state-locks/critique-ledger-cl2-planning-canary.lock",
        ".megaplan/epics/critique-ledger-cl2-planning-canary/events.jsonl",
    }
    admitted_source_digest: str | None = None
    admitted_git_digest: str | None = None
    admitted_schema_runtime: dict[str, str] | None = None
    previous_engine_runtime: dict[str, Any] | None = None
    for expected_name, checkpoint in zip(expected_names, checkpoints, strict=True):
        if (
            not isinstance(checkpoint, dict)
            or set(checkpoint) != {
                "schema", "checkpoint", "head", "tree", "tracked_clean",
                "source_manifest_digest", "git_metadata_digest",
                "runtime_delta", "runtime_delta_digest", "engine_runtime",
            }
            or checkpoint.get("schema")
            != "arnold.megaplan.finite_canary_repository_integrity.v1"
            or checkpoint.get("checkpoint") != expected_name
            or checkpoint.get("head") != source_commit
            or checkpoint.get("tree") != source_tree
            or checkpoint.get("tracked_clean") is not True
            or not isinstance(checkpoint.get("source_manifest_digest"), str)
            or not _SHA256_RE.fullmatch(checkpoint["source_manifest_digest"])
            or not isinstance(checkpoint.get("git_metadata_digest"), str)
            or not _SHA256_RE.fullmatch(checkpoint["git_metadata_digest"])
            or not isinstance(checkpoint.get("runtime_delta"), list)
            or hashlib.sha256(
                json.dumps(
                    checkpoint.get("runtime_delta"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            != checkpoint.get("runtime_delta_digest")
        ):
            return False
        if admitted_source_digest is None:
            admitted_source_digest = checkpoint["source_manifest_digest"]
            admitted_git_digest = checkpoint["git_metadata_digest"]
        elif (
            checkpoint["source_manifest_digest"] != admitted_source_digest
            or checkpoint["git_metadata_digest"] != admitted_git_digest
        ):
            return False
        schema_runtime: dict[str, str] = {}
        seen_runtime_paths: set[str] = set()
        runtime_by_path: dict[str, dict[str, Any]] = {}
        for item in checkpoint["runtime_delta"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"path", "kind", "sha256"}
                or item.get("kind") not in {"file", "symlink"}
                or not isinstance(item.get("path"), str)
                or not item["path"].startswith(".megaplan/")
                or not isinstance(item.get("sha256"), str)
                or not _SHA256_RE.fullmatch(item["sha256"])
            ):
                return False
            path = item["path"]
            if path in seen_runtime_paths:
                return False
            seen_runtime_paths.add(path)
            runtime_by_path[path] = item
            if path in schema_paths:
                if item["kind"] != "file" or path in schema_runtime:
                    return False
                schema_runtime[path] = item["sha256"]
            elif path in engine_runtime_paths:
                if item["kind"] != "file":
                    return False
            elif not path[1:].startswith(allowed_roots):
                return False
        if set(schema_runtime) != schema_paths:
            return False
        if admitted_schema_runtime is None:
            admitted_schema_runtime = schema_runtime
        elif schema_runtime != admitted_schema_runtime:
            return False
        engine_runtime = checkpoint.get("engine_runtime")
        if not isinstance(engine_runtime, dict) or set(engine_runtime) != {
            "lock", "events",
        }:
            return False
        lock = engine_runtime.get("lock")
        events = engine_runtime.get("events")
        if expected_name in {"baseline", "pre:init"}:
            if lock is not None or events is not None:
                return False
        else:
            if (
                not isinstance(lock, dict)
                or set(lock)
                != {"path", "st_dev", "st_ino", "size", "sha256"}
                or lock.get("path")
                != ".megaplan/.state-locks/critique-ledger-cl2-planning-canary.lock"
                or type(lock.get("st_dev")) is not int
                or type(lock.get("st_ino")) is not int
                or lock["st_dev"] < 0
                or lock["st_ino"] <= 0
                or lock.get("size") != 0
                or lock.get("sha256") != hashlib.sha256(b"").hexdigest()
                or not isinstance(events, dict)
                or set(events)
                != {
                    "path", "st_dev", "st_ino", "size", "sha256",
                    "transaction_count", "last_seq",
                }
                or events.get("path")
                != ".megaplan/epics/critique-ledger-cl2-planning-canary/events.jsonl"
                or type(events.get("st_dev")) is not int
                or type(events.get("st_ino")) is not int
                or events["st_dev"] < 0
                or events["st_ino"] <= 0
                or type(events.get("size")) is not int
                or events["size"] <= 0
                or not isinstance(events.get("sha256"), str)
                or not _SHA256_RE.fullmatch(events["sha256"])
                or type(events.get("transaction_count")) is not int
                or events["transaction_count"] <= 0
                or events.get("last_seq")
                != events["transaction_count"] - 1
                or runtime_by_path.get(lock["path"], {}).get("sha256")
                != lock["sha256"]
                or runtime_by_path.get(events["path"], {}).get("sha256")
                != events["sha256"]
            ):
                return False
            if previous_engine_runtime is not None:
                previous_lock = previous_engine_runtime["lock"]
                previous_events = previous_engine_runtime["events"]
                if (
                    (lock["st_dev"], lock["st_ino"])
                    != (previous_lock["st_dev"], previous_lock["st_ino"])
                    or (events["st_dev"], events["st_ino"])
                    != (previous_events["st_dev"], previous_events["st_ino"])
                    or events["size"] < previous_events["size"]
                    or events["transaction_count"]
                    < previous_events["transaction_count"]
                    or events["last_seq"] < previous_events["last_seq"]
                ):
                    return False
            previous_engine_runtime = engine_runtime
    return True


def _finite_canary_global_scratch_is_valid(value: Any) -> bool:
    """Accept only non-writable global scratch; IPC-none may omit /dev/shm."""
    return bool(
        isinstance(value, dict)
        and set(value) == {"/tmp", "/var/tmp", "/dev/shm"}
        and value.get("/tmp") == "root_nonwritable"
        and value.get("/var/tmp") == "root_nonwritable"
        and value.get("/dev/shm")
        in {"root_nonwritable", "absent_ipc_none"}
    )


def _finite_canary_privilege_receipt_is_valid(
    payload: Any,
    *,
    phase: str,
    plan_iteration: int | None = None,
    dispatch_ordinal: int | None = None,
    plan_dir: Path,
) -> bool:
    if not isinstance(payload, dict):
        return False
    base_fields = {
        "schema", "status", "phase", "plan_iteration", "dispatch_ordinal",
        "model_uid", "model_gid",
        "uid_processes_before", "uid_processes_after", "privilege_observation",
        "command_prefix", "environment_keys", "writable_roots", "global_scratch",
        "limits", "output", "runtime", "recorded_at", "receipt_digest",
    }
    schema = payload.get("schema")
    if schema == "arnold.megaplan.zero_recovery_privilege_receipt.v1":
        if plan_iteration is not None or dispatch_ordinal is not None:
            return False
        fields = base_fields - {"plan_iteration", "dispatch_ordinal"}
        output_name = f".zero-recovery-{phase}-worker-output.json"
        runtime_pattern = re.compile(
            rf"/run/megaplan-zero-recovery/{re.escape(phase)}-[0-9a-f]{{32}}\Z"
        )
    elif schema == "arnold.megaplan.zero_recovery_privilege_receipt.v2":
        if (
            type(plan_iteration) is not int
            or plan_iteration < 1
            or type(dispatch_ordinal) is not int
            or dispatch_ordinal < 1
        ):
            return False
        fields = base_fields
        output_name = (
            f".zero-recovery-{dispatch_ordinal:02d}-{phase}-i{plan_iteration}"
            "-worker-output.json"
        )
        runtime_pattern = re.compile(
            rf"/run/megaplan-zero-recovery/{dispatch_ordinal:02d}-"
            rf"{re.escape(phase)}-i{plan_iteration}-[0-9a-f]{{32}}\Z"
        )
    else:
        return False
    unsigned = dict(payload)
    digest = unsigned.pop("receipt_digest", None)
    output = payload.get("output")
    runtime = payload.get("runtime")
    privilege = payload.get("privilege_observation")
    output_path = plan_dir / output_name
    expected_command_prefix = [
        "/usr/bin/setpriv", "--reuid=65532", "--regid=65532",
        "--clear-groups", "--no-new-privs", "--bounding-set=-all",
        "--inh-caps=-all", "--ambient-caps=-all", "--",
        "/usr/bin/prlimit", "--nproc=64", "--fsize=67108864",
        "--core=0", "--",
    ]
    expected_env = sorted(
        [
            "LANG", "LC_ALL", "HOME", "CODEX_HOME", "TMPDIR",
            "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "PATH", "USER", "LOGNAME",
            "MEGAPLAN_TURN_ID", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE",
            "GIT_CONFIG_NOSYSTEM",
        ]
    )
    try:
        output_stat = output_path.lstat()
    except OSError:
        return False
    if not stat.S_ISREG(output_stat.st_mode) or output_stat.st_nlink != 1:
        return False
    return bool(
        set(payload) == fields
        and payload.get("schema") == schema
        and payload.get("status") == "sealed"
        and payload.get("phase") == phase
        and (
            schema == "arnold.megaplan.zero_recovery_privilege_receipt.v1"
            or (
                payload.get("plan_iteration") == plan_iteration
                and payload.get("dispatch_ordinal") == dispatch_ordinal
            )
        )
        and payload.get("model_uid") == 65532
        and payload.get("model_gid") == 65532
        and payload.get("uid_processes_before") == 0
        and payload.get("uid_processes_after") == 0
        and privilege
        == {
            "Uid": "65532\t65532\t65532\t65532",
            "Gid": "65532\t65532\t65532\t65532",
            "Groups": "",
            "NoNewPrivs": "1",
            "CapInh": "0000000000000000",
            "CapPrm": "0000000000000000",
            "CapEff": "0000000000000000",
            "CapBnd": "0000000000000000",
            "CapAmb": "0000000000000000",
        }
        and payload.get("command_prefix") == expected_command_prefix
        and payload.get("environment_keys") == expected_env
        and isinstance(runtime, dict)
        and set(runtime)
        == {
            "path", "st_dev", "st_ino", "files", "bytes",
            "sealed_uid", "sealed_gid", "mode",
        }
        and isinstance(runtime.get("path"), str)
        and runtime_pattern.fullmatch(runtime["path"])
        and payload.get("writable_roots") == [output_name, runtime["path"]]
        and _finite_canary_global_scratch_is_valid(
            payload.get("global_scratch")
        )
        and payload.get("limits")
        == {
            "nproc": 64,
            "fsize_bytes": 67_108_864,
            "runtime_max_files": 4096,
            "runtime_max_bytes": 134_217_728,
            "output_max_bytes": 16_777_216,
        }
        and isinstance(output, dict)
        and set(output)
        == {"path", "st_dev", "st_ino", "size", "sha256", "sealed_uid", "sealed_gid", "mode", "nlink"}
        and output.get("path") == output_name
        and output.get("sealed_uid") == 0
        and output.get("sealed_gid") == 0
        and output.get("mode") == "0600"
        and output.get("nlink") == 1
        and type(output.get("st_dev")) is int
        and output["st_dev"] >= 0
        and type(output.get("st_ino")) is int
        and output["st_ino"] > 0
        and type(output.get("size")) is int
        and 0 <= output["size"] <= 16_777_216
        and output.get("st_dev") == output_stat.st_dev
        and output.get("st_ino") == output_stat.st_ino
        and output.get("size") == output_stat.st_size
        and output_stat.st_uid == 0
        and output_stat.st_gid == 0
        and stat.S_IMODE(output_stat.st_mode) == 0o600
        and output.get("sha256") == _sha256_file(output_path)
        and type(runtime.get("files")) is int
        and 0 <= runtime["files"] <= 4096
        and type(runtime.get("bytes")) is int
        and 0 <= runtime["bytes"] <= 134_217_728
        and type(runtime.get("st_dev")) is int
        and runtime["st_dev"] >= 0
        and type(runtime.get("st_ino")) is int
        and runtime["st_ino"] > 0
        and runtime.get("sealed_uid") == 0
        and runtime.get("sealed_gid") == 0
        and runtime.get("mode") == "0700"
        and _parse_iso_datetime(payload.get("recorded_at")) is not None
        and isinstance(digest, str)
        and hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == digest
    )


def _finite_canary_success_route(payload: Any) -> dict[str, Any] | None:
    """Return the one admitted finalized route, or fail closed with ``None``."""
    if not isinstance(payload, dict):
        return None
    schema = payload.get("schema")
    phases = payload.get("phases")
    if schema == "arnold.megaplan.finite_canary_run_receipt.v2":
        if (
            phases != _FINITE_CANARY_PHASES
            or payload.get("status") != "passed"
            or payload.get("terminal_state") != "finalized"
            or payload.get("failure") is not None
            or payload.get("phase_results")
            != [
                {"phase": phase, "returncode": 0, "state": state}
                for phase, state in zip(
                    _FINITE_CANARY_PHASES,
                    ["initialized", "planned", "critiqued", "gated", "finalized"],
                    strict=True,
                )
            ]
        ):
            return None
        return {
            "version": 2,
            "dispatch_version": 1,
            "phases": list(_FINITE_CANARY_PHASES),
            "states": ["initialized", "planned", "critiqued", "gated", "finalized"],
            "iterations": [None] * 5,
            "ordinals": [None] * 5,
            "gate_recommendations": [None] * 5,
        }
    if schema != "arnold.megaplan.finite_canary_run_receipt.v3":
        return None
    if phases == _FINITE_CANARY_PHASES:
        states = ["initialized", "planned", "critiqued", "gated", "finalized"]
        iterations = [0, 1, 1, 1, 1]
        ordinals: list[int | None] = [None, 1, 2, 3, 4]
        gate_recommendations: list[str | None] = [None, None, None, "PROCEED", None]
        gate_semantics = [(1, 1, "PROCEED", "gated")]
    elif phases == _FINITE_CANARY_REVISED_PHASES:
        states = [
            "initialized", "planned", "critiqued", "critiqued",
            "planned", "critiqued", "gated", "finalized",
        ]
        iterations = [0, 1, 1, 1, 2, 2, 2, 2]
        ordinals = [None, 1, 2, 3, 4, 5, 6, 7]
        gate_recommendations = [
            None, None, None, "ITERATE", None, None, "PROCEED", None,
        ]
        gate_semantics = [
            (1, 1, "ITERATE", "critiqued"),
            (2, 2, "PROCEED", "gated"),
        ]
    else:
        return None
    gate_attempts = payload.get("gate_attempts")
    if not isinstance(gate_attempts, list) or len(gate_attempts) != len(gate_semantics):
        return None
    for attempt, expected in zip(gate_attempts, gate_semantics, strict=True):
        if (
            not isinstance(attempt, dict)
            or set(attempt)
            != {"attempt", "plan_iteration", "recommendation", "state", "gate_sha256"}
            or (
                attempt.get("attempt"),
                attempt.get("plan_iteration"),
                attempt.get("recommendation"),
                attempt.get("state"),
            )
            != expected
            or type(attempt.get("attempt")) is not int
            or type(attempt.get("plan_iteration")) is not int
            or not isinstance(attempt.get("gate_sha256"), str)
            or not _SHA256_RE.fullmatch(attempt["gate_sha256"])
        ):
            return None
    gate_attempt_count = len(gate_semantics)
    phase_results = payload.get("phase_results")
    if (
        payload.get("status") != "passed"
        or payload.get("terminal_state") != "finalized"
        or payload.get("failure") is not None
        or payload.get("product_outcome")
        != {
            "kind": "proceed_finalized",
            "gate_attempt": gate_attempt_count,
            "recommendation": "PROCEED",
        }
        or gate_attempts[-1]["gate_sha256"] != payload.get("gate_sha256")
        or phase_results
        != [
            {
                "phase": phase,
                "plan_iteration": iteration,
                "dispatch_ordinal": ordinal,
                "returncode": 0,
                "state": state,
                "gate_recommendation": recommendation,
            }
            for phase, iteration, ordinal, state, recommendation in zip(
                phases,
                iterations,
                ordinals,
                states,
                gate_recommendations,
                strict=True,
            )
        ]
    ):
        return None
    for index, result in enumerate(phase_results):
        if (
            type(result.get("plan_iteration")) is not int
            or (
                index == 0
                and result.get("dispatch_ordinal") is not None
            )
            or (
                index > 0
                and type(result.get("dispatch_ordinal")) is not int
            )
        ):
            return None
    return {
        "version": 3,
        "dispatch_version": 2,
        "phases": phases,
        "states": states,
        "iterations": iterations,
        "ordinals": ordinals,
        "gate_recommendations": gate_recommendations,
    }


def _finite_canary_dispatches_are_valid(
    payload: Any, route: dict[str, Any]
) -> bool:
    if not isinstance(payload, dict):
        return False
    dispatches = payload.get("dispatches")
    phases = route["phases"][1:]
    iterations = route["iterations"][1:]
    ordinals = route["ordinals"][1:]
    if not isinstance(dispatches, list) or len(dispatches) != len(phases) * 2:
        return False
    start_fields = {
        "schema", "event", "dispatch_id", "phase", "selected_agent",
        "selected_model", "selected_effort", "model_cli_argv", "attempt",
        "plan_iteration", "dispatch_ordinal", "retry", "fallback",
        "json_repair", "adaptive_routing", "recorded_at",
    }
    terminal_fields = {
        "schema", "event", "dispatch_id", "phase", "actual_agent",
        "actual_model", "model_evidence", "privilege_receipt_path",
        "privilege_receipt_sha256", "rollout_path", "rollout_sha256",
        "actual_effort", "attempt", "plan_iteration", "dispatch_ordinal",
        "retry", "fallback", "json_repair", "adaptive_routing", "result",
        "recorded_at",
    }
    legacy = route.get("version") == 2
    if legacy:
        start_fields -= {"plan_iteration", "dispatch_ordinal"}
        terminal_fields -= {"plan_iteration", "dispatch_ordinal"}
    privilege_hashes: list[str] = []
    dispatch_ids: set[str] = set()
    previous_terminal = None
    for pair_index, (phase, iteration, ordinal) in enumerate(
        zip(phases, iterations, ordinals, strict=True)
    ):
        start = dispatches[pair_index * 2]
        terminal = dispatches[pair_index * 2 + 1]
        privilege_name = (
            f".zero-recovery-{phase}-privilege-receipt.json"
            if legacy
            else (
                f".zero-recovery-{ordinal:02d}-{phase}-i{iteration}"
                "-privilege-receipt.json"
            )
        )
        start_time = _parse_iso_datetime(start.get("recorded_at")) if isinstance(start, dict) else None
        terminal_time = _parse_iso_datetime(terminal.get("recorded_at")) if isinstance(terminal, dict) else None
        rollout_path = terminal.get("rollout_path") if isinstance(terminal, dict) else None
        if (
            not isinstance(start, dict)
            or not isinstance(terminal, dict)
            or set(start) != start_fields
            or set(terminal) != terminal_fields
            or start.get("schema")
            != f"arnold.megaplan.zero_recovery_dispatch.v{route['dispatch_version']}"
            or terminal.get("schema")
            != f"arnold.megaplan.zero_recovery_dispatch.v{route['dispatch_version']}"
            or start.get("event") != "start"
            or terminal.get("event") != "terminal"
            or start.get("dispatch_id") != terminal.get("dispatch_id")
            or not isinstance(start.get("dispatch_id"), str)
            or re.fullmatch(r"[0-9a-f]{32}", start["dispatch_id"]) is None
            or start["dispatch_id"] in dispatch_ids
            or start.get("phase") != phase
            or terminal.get("phase") != phase
            or (
                not legacy
                and (
                    type(start.get("plan_iteration")) is not int
                    or start.get("plan_iteration") != iteration
                    or type(terminal.get("plan_iteration")) is not int
                    or terminal.get("plan_iteration") != iteration
                    or type(start.get("dispatch_ordinal")) is not int
                    or start.get("dispatch_ordinal") != ordinal
                    or type(terminal.get("dispatch_ordinal")) is not int
                    or terminal.get("dispatch_ordinal") != ordinal
                )
            )
            or start.get("selected_agent") != "codex"
            or start.get("selected_model") != "gpt-5.6-sol"
            or start.get("selected_effort") != "high"
            or start.get("model_cli_argv") != ["-c", "model='gpt-5.6-sol'"]
            or terminal.get("actual_agent") != "codex"
            or terminal.get("actual_model") != "gpt-5.6-sol"
            or terminal.get("model_evidence") != "codex_cli_turn_context"
            or terminal.get("actual_effort") != "high"
            or terminal.get("privilege_receipt_path") != privilege_name
            or not isinstance(terminal.get("privilege_receipt_sha256"), str)
            or not _SHA256_RE.fullmatch(terminal["privilege_receipt_sha256"])
            or not isinstance(rollout_path, str)
            or not rollout_path.startswith("sessions/")
            or PurePosixPath(rollout_path).is_absolute()
            or rollout_path != PurePosixPath(rollout_path).as_posix()
            or ".." in PurePosixPath(rollout_path).parts
            or not isinstance(terminal.get("rollout_sha256"), str)
            or not _SHA256_RE.fullmatch(terminal["rollout_sha256"])
            or start.get("attempt") != 1
            or terminal.get("attempt") != 1
            or terminal.get("result") != "returned"
            or any(
                item.get(key) is not False
                for item in (start, terminal)
                for key in ("retry", "fallback", "json_repair", "adaptive_routing")
            )
            or start_time is None
            or terminal_time is None
            or terminal_time < start_time
            or (previous_terminal is not None and start_time < previous_terminal)
        ):
            return False
        dispatch_ids.add(start["dispatch_id"])
        previous_terminal = terminal_time
        privilege_hashes.append(terminal["privilege_receipt_sha256"])
    return payload.get("privilege_receipt_sha256") == privilege_hashes


def _finite_canary_phase_commands_are_valid(
    payload: Any,
    route: dict[str, Any],
    *,
    workspace: str,
    plan_name: str,
) -> bool:
    if not isinstance(payload, dict):
        return False
    commands = payload.get("phase_commands")
    phases = route["phases"]
    if (
        not isinstance(commands, list)
        or len(commands) != len(phases)
        or not commands
        or any(not isinstance(command, list) or len(command) < 5 for command in commands)
    ):
        return False
    executable = commands[0][0]
    if not isinstance(executable, str) or not executable:
        return False
    if any(
        command[:4] != [executable, "-P", "-m", "arnold_pipelines.megaplan"]
        for command in commands
    ):
        return False
    init_tail = [
        "init", "--project-dir", workspace,
        "--name", plan_name, "--auto-approve", "--idea-file",
        workspace + "/.megaplan/initiatives/critique-ledger-safe-v3-canary/briefs/cl2-ledger-persistence-and-replay.md",
        "--north-star", workspace + "/.megaplan/initiatives/critique-ledger-safe-v3-canary/NORTHSTAR.md",
        "--robustness", "full", "--no-adaptive-critique", "--vendor", "codex",
        "--phase-model", "plan=codex:gpt-5.6-sol:high",
        "--phase-model", "critique=codex:gpt-5.6-sol:high",
        "--phase-model", "gate=codex:gpt-5.6-sol:high",
    ]
    if route.get("version") == 3:
        init_tail.extend(["--phase-model", "revise=codex:gpt-5.6-sol:high"])
    init_tail.extend(["--phase-model", "finalize=codex:gpt-5.6-sol:high"])
    if commands[0][4:] != init_tail:
        return False
    return all(
        commands[index][4:] == [phase, "--plan", plan_name, "--fresh"]
        for index, phase in enumerate(phases[1:], start=1)
    )


def _validate_finite_canary_receipt(
    precondition: LaunchPreconditionSpec,
    root: Path,
    spec_path: Path,
    *,
    index: int,
) -> None:
    label = f"launch_preconditions[{index}] {precondition.name!r}"
    if precondition.path is None:
        raise CliError("invalid_spec", f"{label} missing receipt path")
    receipt_path = _resolve_launch_precondition_path(precondition.path, root)
    _require_inside_root(receipt_path, root, label)
    if not receipt_path.is_file():
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary receipt missing at {receipt_path}",
        )
    payload = _strict_json_document(receipt_path, label=label, spec_path=spec_path)
    required_fields = {
        "schema", "status", "phases", "terminal_state", "artifacts",
        "subject", "issued_at", "completed_at", "receipt_digest",
        "operational_substrates", "deferred_obligations",
    }
    if not isinstance(payload, dict) or set(payload) != required_fields:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary receipt has ambiguous top-level fields",
        )
    if (
        payload.get("schema") != _FINITE_CANARY_SCHEMA
        or payload.get("status") != "passed"
        or payload.get("phases")
        not in (_FINITE_CANARY_PHASES, _FINITE_CANARY_REVISED_PHASES)
        or payload.get("terminal_state") != "finalized"
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary status, phases, or terminal state is invalid",
        )
    subject = payload.get("subject")
    subject_fields = {
        "canary_id", "plan_name", "source_commit", "source_tree",
        "engine_commit", "engine_tree", "cloud", "canary_spec_sha256",
    }
    cloud_fields = {
        "provider", "host", "port", "predecessor_container",
        "predecessor_container_id", "canary_container", "image_id", "workspace",
        "predecessor_workspace", "workspace_bind_source",
    }
    issued = _parse_iso_datetime(payload.get("issued_at"))
    completed = _parse_iso_datetime(payload.get("completed_at"))
    unsigned = dict(payload)
    receipt_digest = unsigned.pop("receipt_digest", None)
    if (
        not isinstance(subject, dict)
        or set(subject) != subject_fields
        or not isinstance(subject.get("cloud"), dict)
        or set(subject["cloud"]) != cloud_fields
        or subject["cloud"].get("provider") != "ssh"
        or type(subject["cloud"].get("port")) is not int
        or any(
            not isinstance(subject.get(key), str) or not subject.get(key)
            for key in ("canary_id", "plan_name", "cloud") if key != "cloud"
        )
        or any(not isinstance(subject.get(key), str) or not _GIT_OBJECT_RE.fullmatch(subject.get(key)) for key in ("source_commit", "source_tree", "engine_commit", "engine_tree"))
        or not isinstance(subject.get("canary_spec_sha256"), str)
        or not _SHA256_RE.fullmatch(subject.get("canary_spec_sha256"))
        or any(
            not isinstance(subject["cloud"].get(key), str) or not subject["cloud"].get(key)
            for key in cloud_fields - {"port"}
        )
        or issued is None
        or completed is None
        or completed < issued
        or not isinstance(receipt_digest, str)
        or not _SHA256_RE.fullmatch(receipt_digest)
        or hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        != receipt_digest
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary subject, chronology, or digest is invalid",
        )
    predecessor_workspace = PurePosixPath(subject["cloud"]["predecessor_workspace"])
    workspace_bind_source = PurePosixPath(subject["cloud"]["workspace_bind_source"])
    if (
        subject["cloud"]["workspace"] != "/workspace/Arnold"
        or not predecessor_workspace.is_absolute()
        or workspace_bind_source.parent != predecessor_workspace
        or workspace_bind_source == predecessor_workspace
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary workspace isolation is invalid",
        )
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary artifacts must be non-empty",
        )
    roles: list[str] = []
    paths: list[str] = []
    artifacts_by_role: dict[str, tuple[Path, str]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {
            "role",
            "path",
            "sha256",
        }:
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: finite canary artifact fields are ambiguous",
            )
        role = artifact.get("role")
        raw_path = artifact.get("path")
        expected_hash = artifact.get("sha256")
        if (
            not isinstance(role, str)
            or role not in _FINITE_CANARY_ROLES
            or not isinstance(raw_path, str)
            or not raw_path
            or not isinstance(expected_hash, str)
            or not _SHA256_RE.fullmatch(expected_hash)
        ):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: finite canary artifact identity is invalid",
            )
        relative = PurePosixPath(raw_path)
        if (
            relative.is_absolute()
            or raw_path != relative.as_posix()
            or raw_path in {".", ".."}
            or ".." in relative.parts
        ):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: finite canary artifact path is not a normalized repository-relative path",
            )
        target = (root / Path(*relative.parts)).resolve()
        _require_inside_root(target, root, label)
        if not target.is_file() or _sha256_file(target) != expected_hash:
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: finite canary artifact hash mismatch for {raw_path}",
            )
        roles.append(role)
        paths.append(raw_path)
        artifacts_by_role[role] = (target, expected_hash)
    if set(roles) != _FINITE_CANARY_ROLES or len(roles) != len(set(roles)):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary artifact roles are missing or duplicated",
        )
    if len(paths) != len(set(paths)):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: finite canary artifact paths are duplicated",
        )
    custody = _strict_json_document(
        artifacts_by_role["custody_manifest"][0], label=label, spec_path=spec_path
    )
    operational_route = _strict_json_document(
        artifacts_by_role["finite_canary_operational_route"][0],
        label=label,
        spec_path=spec_path,
    )
    supersession = _strict_json_document(
        artifacts_by_role["supersession_index"][0], label=label, spec_path=spec_path
    )
    unfinished_path = artifacts_by_role["unfinished_work_ledger"][0]
    try:
        unfinished_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: unfinished-work custody is unreadable",
        ) from exc
    custody_contract = _finite_canary_custody_contract(custody)
    expected_substrates, expected_obligations = (
        custody_contract if custody_contract is not None else (None, None)
    )
    superseded = supersession.get("superseded") if isinstance(supersession, dict) else None
    hard_fail_identities = (
        {
            (item.get("commit"), item.get("tree"))
            for item in superseded
            if isinstance(item, dict)
            and item.get("status") == "HARD_FAIL_NOT_CONSUMED_OPERATIONAL_CANARY"
        }
        if isinstance(superseded, list)
        else set()
    )
    if (
        custody_contract is None
        or not _finite_canary_completion_contract_is_valid(
            payload.get("operational_substrates"),
            payload.get("deferred_obligations"),
            expected_substrates=expected_substrates,
            expected_obligations=expected_obligations,
        )
        or not isinstance(operational_route, dict)
        or operational_route.get("schema")
        != "arnold.critique_ledger.finite_canary_operational_route.v2"
        or operational_route.get("profile")
        != "ZERO_RECOVERY_NONROOT_FINITE_CANARY"
        or operational_route.get("model_evidence", {}).get("prelaunch_accepted_label")
        != "codex_cli_turn_context"
        or operational_route.get("additional_bindings", {})
        .get("custody_contract", {})
        .get("path")
        != artifacts_by_role["custody_manifest"][0].relative_to(root).as_posix()
        or operational_route.get("additional_bindings", {}).get(
            "trusted_host_control_state"
        )
        != _FINITE_CANARY_ROUTE_HOST_CONTROL_STATE
        or not isinstance(supersession, dict)
        or supersession.get("schema")
        != "arnold.critique_ledger.supersession_index.v1"
        or supersession.get("current_operational_route", {}).get("path")
        != artifacts_by_role["finite_canary_operational_route"][0]
        .relative_to(root)
        .as_posix()
        or supersession.get("current_operational_route", {}).get("sha256")
        != artifacts_by_role["finite_canary_operational_route"][1]
        or hard_fail_identities
        != {
            (
                "9642193a063d91a6be364f2d11a04b221eae30cf",
                "27a3d61dff39a4c1a26a8a736dc85ce727c57b7c",
            ),
            (
                "0c3d662024bc0497ed3979991a20b3b48ecf19cd",
                "d4c10e167be87e1655704d1beeaf92d6c4e46526",
            ),
        }
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: stable-exit custody is incomplete or ambiguous",
        )
    canary_spec_hash = artifacts_by_role["canary_spec"][1]
    if subject.get("canary_spec_sha256") != canary_spec_hash:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: subject does not bind the canary spec artifact",
        )
    canary_path = artifacts_by_role["canary_spec"][0]
    try:
        canary = yaml.safe_load(canary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: canary spec is invalid: {exc}",
        ) from exc
    canary_fields = {
        "schema", "canary_id", "engine_commit", "engine_tree", "brief",
        "north_star", "plan_name", "phases", "terminal_state", "model_spec",
        "robustness", "adaptive_critique", "receipts", "policy",
    }
    if (
        not isinstance(canary, dict)
        or set(canary) != canary_fields
        or canary.get("schema") != "arnold.megaplan.finite_canary.v1"
        or canary.get("canary_id") != subject.get("canary_id")
        or canary.get("plan_name") != subject.get("plan_name")
        or canary.get("engine_commit") != subject.get("engine_commit")
        or canary.get("engine_tree") != subject.get("engine_tree")
        or canary.get("phases") != _FINITE_CANARY_PHASES
        or canary.get("terminal_state") != "finalized"
        or canary.get("model_spec") != "codex:gpt-5.6-sol:high"
        or canary.get("adaptive_critique") is not False
        or not finite_canary_policy_is_exact(canary.get("policy"))
        or not finite_canary_policy_allows_route(
            canary.get("policy"), payload.get("phases")
        )
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: subject does not match the admitted canary spec",
        )
    proof = _strict_json_document(
        artifacts_by_role["proof_map"][0], label=label, spec_path=spec_path
    )
    trace = _strict_json_document(
        artifacts_by_role["traceability"][0], label=label, spec_path=spec_path
    )
    if (
        not isinstance(proof, dict)
        or proof.get("schema") != "arnold.megaplan.finite_canary_proof_map.v1"
        or proof.get("implementation") != {
            "commit": subject.get("engine_commit"), "tree": subject.get("engine_tree")
        }
        or not isinstance(trace, dict)
        or trace.get("schema") != "arnold.megaplan.finite_canary_traceability.v1"
        or trace.get("implementation_commit") != subject.get("engine_commit")
        or trace.get("implementation_tree") != subject.get("engine_tree")
        or trace.get("launch_manifest_binding")
        != {"method": "derived_clean_head_at_admission"}
        or trace.get("fresh_workspace") != subject["cloud"].get("workspace")
        or trace.get("predecessor_workspace")
        != subject["cloud"].get("predecessor_workspace")
        or trace.get("workspace_bind_source")
        != subject["cloud"].get("workspace_bind_source")
        or trace.get("predecessor_container") != subject["cloud"].get("predecessor_container")
        or trace.get("canary_container") != subject["cloud"].get("canary_container")
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: proof/trace artifacts do not bind the exact subject",
        )
    run_path, run_hash = artifacts_by_role["run_receipt"]
    run_payload = _strict_json_document(run_path, label=label, spec_path=spec_path)
    run_fields = {
        "schema", "status", "canary_id", "plan_name", "phases", "phase_results",
        "terminal_state", "product_outcome", "gate_attempts", "failure",
        "started_at", "completed_at", "source_commit",
        "source_tree", "canary_spec_sha256", "launch_manifest_sha256", "state_sha256", "gate_sha256", "receipt_digest",
        "dispatch_ledger_sha256", "dispatches", "dispatch_integrity", "import_root", "phase_commands",
        "phase_receipt_sha256", "phase_receipts_manifest_sha256",
        "repository_integrity", "privilege_receipt_sha256",
        "privilege_receipts_manifest_sha256",
    }
    if (
        isinstance(run_payload, dict)
        and run_payload.get("schema")
        == "arnold.megaplan.finite_canary_run_receipt.v2"
    ):
        run_fields -= {"product_outcome", "gate_attempts"}
    run_unsigned = dict(run_payload) if isinstance(run_payload, dict) else {}
    run_digest = run_unsigned.pop("receipt_digest", None)
    route = _finite_canary_success_route(run_payload)
    run_started = (
        _parse_iso_datetime(run_payload.get("started_at"))
        if isinstance(run_payload, dict)
        else None
    )
    run_completed = (
        _parse_iso_datetime(run_payload.get("completed_at"))
        if isinstance(run_payload, dict)
        else None
    )
    if (
        not isinstance(run_payload, dict)
        or set(run_payload) != run_fields
        or route is None
        or run_payload.get("canary_id") != subject.get("canary_id")
        or run_payload.get("plan_name") != subject.get("plan_name")
        or payload.get("phases") != route["phases"]
        or run_started is None
        or run_completed is None
        or run_completed < run_started
        or run_payload.get("source_commit") != subject.get("source_commit")
        or run_payload.get("source_tree") != subject.get("source_tree")
        or run_payload.get("canary_spec_sha256") != canary_spec_hash
        or run_payload.get("launch_manifest_sha256")
        != {
            artifacts_by_role["canary_spec"][0].relative_to(root).as_posix(): artifacts_by_role["canary_spec"][1],
            artifacts_by_role["cloud_spec"][0].relative_to(root).as_posix(): artifacts_by_role["cloud_spec"][1],
            artifacts_by_role["proof_map"][0].relative_to(root).as_posix(): artifacts_by_role["proof_map"][1],
            artifacts_by_role["traceability"][0].relative_to(root).as_posix(): artifacts_by_role["traceability"][1],
        }
        or run_payload.get("dispatch_integrity") != "complete"
        or not _finite_canary_repository_integrity_is_valid(
            run_payload.get("repository_integrity"),
            source_commit=str(subject.get("source_commit")),
            source_tree=str(subject.get("source_tree")),
            phases=route["phases"] if route is not None else [],
        )
        or not isinstance(run_payload.get("dispatch_ledger_sha256"), str)
        or not _SHA256_RE.fullmatch(run_payload.get("dispatch_ledger_sha256"))
        or not _finite_canary_dispatches_are_valid(run_payload, route)
        or run_payload.get("import_root")
        != subject["cloud"].get("workspace") + "/arnold_pipelines/megaplan/__init__.py"
        or not _finite_canary_phase_commands_are_valid(
            run_payload,
            route,
            workspace=str(subject["cloud"].get("workspace")),
            plan_name=str(subject.get("plan_name")),
        )
        or not isinstance(run_payload.get("phase_receipt_sha256"), list)
        or len(run_payload.get("phase_receipt_sha256")) != len(route["phases"])
        or any(not isinstance(value, str) or not _SHA256_RE.fullmatch(value) for value in run_payload.get("phase_receipt_sha256"))
        or run_payload.get("state_sha256") != artifacts_by_role["plan_state"][1]
        or run_payload.get("gate_sha256") != artifacts_by_role["gate_result"][1]
        or run_payload.get("dispatch_ledger_sha256")
        != artifacts_by_role["dispatch_ledger"][1]
        or run_payload.get("phase_receipts_manifest_sha256")
        != artifacts_by_role["phase_receipts_manifest"][1]
        or run_payload.get("privilege_receipts_manifest_sha256")
        != artifacts_by_role["privilege_receipts_manifest"][1]
        or not isinstance(run_digest, str)
        or hashlib.sha256(json.dumps(run_unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() != run_digest
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: run receipt is not a bound passed finite run",
        )
    phase_manifest = _strict_json_document(
        artifacts_by_role["phase_receipts_manifest"][0],
        label=label,
        spec_path=spec_path,
    )
    phase_entries = phase_manifest.get("entries") if isinstance(phase_manifest, dict) else None
    modern = route["version"] == 3
    expected_phase_manifest_schema = (
        "arnold.megaplan.finite_canary_phase_receipts_manifest.v2"
        if modern
        else "arnold.megaplan.finite_canary_phase_receipts_manifest.v1"
    )
    expected_phase_paths = [
        f".megaplan/initiatives/critique-ledger-safe-v3-canary/receipts/{index:02d}-{phase}.phase-receipt.json"
        for index, phase in enumerate(route["phases"])
    ]
    if (
        not isinstance(phase_manifest, dict)
        or set(phase_manifest) != {"schema", "canary_id", "plan_name", "entries"}
        or phase_manifest.get("schema")
        != expected_phase_manifest_schema
        or phase_manifest.get("canary_id") != subject.get("canary_id")
        or phase_manifest.get("plan_name") != subject.get("plan_name")
        or not isinstance(phase_entries, list)
        or len(phase_entries) != len(route["phases"])
        or [entry.get("path") for entry in phase_entries if isinstance(entry, dict)]
        != expected_phase_paths
        or [entry.get("sha256") for entry in phase_entries if isinstance(entry, dict)]
        != run_payload.get("phase_receipt_sha256")
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: phase receipt manifest is invalid",
        )
    previous_phase_completed = run_started
    for phase_index, (phase, expected_path, entry) in enumerate(
        zip(route["phases"], expected_phase_paths, phase_entries, strict=True)
    ):
        expected_iteration = route["iterations"][phase_index]
        expected_ordinal = route["ordinals"][phase_index]
        expected_entry_fields = (
            {"phase", "plan_iteration", "dispatch_ordinal", "path", "sha256"}
            if modern
            else {"phase", "path", "sha256"}
        )
        if (
            not isinstance(entry, dict)
            or set(entry) != expected_entry_fields
            or entry.get("phase") != phase
            or (
                modern
                and (
                    type(entry.get("plan_iteration")) is not int
                    or entry.get("plan_iteration") != expected_iteration
                    or (
                        expected_ordinal is None
                        and entry.get("dispatch_ordinal") is not None
                    )
                    or (
                        expected_ordinal is not None
                        and type(entry.get("dispatch_ordinal")) is not int
                    )
                    or entry.get("dispatch_ordinal") != expected_ordinal
                )
            )
        ):
            raise CliError("launch_precondition_failed", f"{label} failed for {spec_path}: phase entry mismatch")
        phase_path = (root / expected_path).resolve()
        _require_inside_root(phase_path, root, label)
        if not phase_path.is_file() or _sha256_file(phase_path) != entry.get("sha256"):
            raise CliError("launch_precondition_failed", f"{label} failed for {spec_path}: phase receipt hash mismatch")
        phase_payload = _strict_json_document(phase_path, label=label, spec_path=spec_path)
        phase_completed = (
            _parse_iso_datetime(phase_payload.get("completed_at"))
            if isinstance(phase_payload, dict)
            else None
        )
        expected_phase_fields = {
            "schema", "phase",
            "status", "returncode", "state", "reason",
            "argv", "state_sha256", "dispatch_ledger_sha256",
            "privilege_receipt_sha256", "integrity_before", "integrity_after",
            "stdout_sha256", "stderr_sha256", "stdout_tail", "stderr_tail",
            "completed_at",
        }
        if modern:
            expected_phase_fields.update({"plan_iteration", "dispatch_ordinal"})
        expected_privilege_hash = (
            None
            if phase == "init"
            else run_payload["privilege_receipt_sha256"][phase_index - 1]
        )
        if (
            not isinstance(phase_payload, dict)
            or set(phase_payload) != expected_phase_fields
            or phase_payload.get("schema")
            != f"arnold.megaplan.finite_canary_phase_receipt.v{route['version']}"
            or phase_payload.get("phase") != phase
            or (
                modern
                and (
                    type(phase_payload.get("plan_iteration")) is not int
                    or phase_payload.get("plan_iteration") != expected_iteration
                    or (
                        expected_ordinal is None
                        and phase_payload.get("dispatch_ordinal") is not None
                    )
                    or (
                        expected_ordinal is not None
                        and type(phase_payload.get("dispatch_ordinal")) is not int
                    )
                    or phase_payload.get("dispatch_ordinal") != expected_ordinal
                )
            )
            or phase_payload.get("status") != "passed"
            or phase_payload.get("returncode") != 0
            or phase_payload.get("state")
            != route["states"][phase_index]
            or phase_payload.get("reason") is not None
            or phase_payload.get("argv") != run_payload["phase_commands"][phase_index]
            or phase_payload.get("integrity_before")
            != run_payload["repository_integrity"][1 + phase_index * 2]
            or phase_payload.get("integrity_after")
            != run_payload["repository_integrity"][2 + phase_index * 2]
            or phase_payload.get("privilege_receipt_sha256")
            != expected_privilege_hash
            or not isinstance(phase_payload.get("state_sha256"), str)
            or not _SHA256_RE.fullmatch(phase_payload["state_sha256"])
            or (
                phase == "init"
                and phase_payload.get("dispatch_ledger_sha256") is not None
            )
            or (
                phase != "init"
                and (
                    not isinstance(phase_payload.get("dispatch_ledger_sha256"), str)
                    or not _SHA256_RE.fullmatch(phase_payload["dispatch_ledger_sha256"])
                )
            )
            or any(
                not isinstance(phase_payload.get(field), str)
                or not _SHA256_RE.fullmatch(phase_payload[field])
                for field in ("stdout_sha256", "stderr_sha256")
            )
            or not isinstance(phase_payload.get("stdout_tail"), str)
            or not isinstance(phase_payload.get("stderr_tail"), str)
            or len(phase_payload["stdout_tail"]) > 4096
            or len(phase_payload["stderr_tail"]) > 4096
            or phase_completed is None
            or previous_phase_completed is None
            or phase_completed < previous_phase_completed
            or phase_completed > run_completed
            or (
                phase_index == len(route["phases"]) - 1
                and (
                    phase_payload.get("state_sha256")
                    != artifacts_by_role["plan_state"][1]
                    or phase_payload.get("dispatch_ledger_sha256")
                    != artifacts_by_role["dispatch_ledger"][1]
                )
            )
        ):
            raise CliError("launch_precondition_failed", f"{label} failed for {spec_path}: phase receipt semantics invalid")
        previous_phase_completed = phase_completed
    privilege_manifest = _strict_json_document(
        artifacts_by_role["privilege_receipts_manifest"][0],
        label=label,
        spec_path=spec_path,
    )
    privilege_entries = (
        privilege_manifest.get("entries")
        if isinstance(privilege_manifest, dict)
        else None
    )
    dispatch_phases = route["phases"][1:]
    dispatch_iterations = route["iterations"][1:]
    dispatch_ordinals = route["ordinals"][1:]
    expected_privilege_paths = [
        (
            ".megaplan/plans/critique-ledger-cl2-planning-canary/"
            f".zero-recovery-{ordinal:02d}-{phase}-i{iteration}"
            "-privilege-receipt.json"
            if modern
            else (
                ".megaplan/plans/critique-ledger-cl2-planning-canary/"
                f".zero-recovery-{phase}-privilege-receipt.json"
            )
        )
        for phase, iteration, ordinal in zip(
            dispatch_phases, dispatch_iterations, dispatch_ordinals, strict=True
        )
    ]
    expected_privilege_manifest_schema = (
        "arnold.megaplan.zero_recovery_privilege_receipts_manifest.v2"
        if modern
        else "arnold.megaplan.zero_recovery_privilege_receipts_manifest.v1"
    )
    if (
        not isinstance(privilege_manifest, dict)
        or set(privilege_manifest) != {"schema", "entries"}
        or privilege_manifest.get("schema")
        != expected_privilege_manifest_schema
        or not isinstance(privilege_entries, list)
        or len(privilege_entries) != len(dispatch_phases)
        or [entry.get("phase") for entry in privilege_entries if isinstance(entry, dict)]
        != dispatch_phases
        or [entry.get("path") for entry in privilege_entries if isinstance(entry, dict)]
        != expected_privilege_paths
        or [entry.get("sha256") for entry in privilege_entries if isinstance(entry, dict)]
        != run_payload.get("privilege_receipt_sha256")
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: privilege receipt manifest is invalid",
        )
    for phase, iteration, ordinal, expected_path, entry in zip(
        dispatch_phases,
        dispatch_iterations,
        dispatch_ordinals,
        expected_privilege_paths,
        privilege_entries,
        strict=True,
    ):
        expected_entry_fields = (
            {"phase", "plan_iteration", "dispatch_ordinal", "path", "sha256"}
            if modern
            else {"phase", "path", "sha256"}
        )
        if (
            not isinstance(entry, dict)
            or set(entry) != expected_entry_fields
            or entry.get("phase") != phase
            or (
                modern
                and (
                    type(entry.get("plan_iteration")) is not int
                    or entry.get("plan_iteration") != iteration
                    or type(entry.get("dispatch_ordinal")) is not int
                    or entry.get("dispatch_ordinal") != ordinal
                )
            )
        ):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: privilege receipt entry is ambiguous",
            )
        privilege_path = (root / expected_path).resolve()
        _require_inside_root(privilege_path, root, label)
        if (
            not privilege_path.is_file()
            or _sha256_file(privilege_path) != entry["sha256"]
        ):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: privilege receipt hash mismatch",
            )
        privilege_payload = _strict_json_document(
            privilege_path, label=label, spec_path=spec_path
        )
        if not _finite_canary_privilege_receipt_is_valid(
            privilege_payload,
            phase=phase,
            plan_iteration=iteration if modern else None,
            dispatch_ordinal=ordinal if modern else None,
            plan_dir=privilege_path.parent,
        ):
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: privilege receipt semantics invalid",
            )
    state_payload = _strict_json_document(
        artifacts_by_role["plan_state"][0], label=label, spec_path=spec_path
    )
    gate_payload = _strict_json_document(
        artifacts_by_role["gate_result"][0], label=label, spec_path=spec_path
    )
    ledger_path = artifacts_by_role["dispatch_ledger"][0]
    try:
        def reject_ledger_duplicates(
            pairs: list[tuple[str, Any]],
        ) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate dispatch field: {key}")
                result[key] = value
            return result

        ledger_payload = [
            json.loads(line, object_pairs_hook=reject_ledger_duplicates)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: dispatch ledger is invalid: {exc}",
        ) from exc
    versioned_gates_valid = True
    if modern:
        versioned_gate_hashes: list[str] = []
        for gate_attempt in run_payload["gate_attempts"]:
            versioned_gate_path = ledger_path.parent / (
                f"gate_v{gate_attempt['plan_iteration']}.json"
            )
            if (
                not versioned_gate_path.is_file()
                or _sha256_file(versioned_gate_path)
                != gate_attempt["gate_sha256"]
            ):
                versioned_gates_valid = False
                break
            versioned_gate = _strict_json_document(
                versioned_gate_path, label=label, spec_path=spec_path
            )
            if (
                not isinstance(versioned_gate, dict)
                or versioned_gate.get("recommendation")
                != gate_attempt["recommendation"]
            ):
                versioned_gates_valid = False
                break
            versioned_gate_hashes.append(gate_attempt["gate_sha256"])
        if (
            len(versioned_gate_hashes) == 2
            and versioned_gate_hashes[0] == versioned_gate_hashes[1]
        ):
            versioned_gates_valid = False
    if (
        not isinstance(state_payload, dict)
        or state_payload.get("current_state") != "finalized"
        or state_payload.get("active_step") not in (None, "")
        or (
            modern
            and (
                type(state_payload.get("iteration")) is not int
                or state_payload.get("iteration") != route["iterations"][-1]
            )
        )
        or not isinstance(gate_payload, dict)
        or gate_payload.get("recommendation") != "PROCEED"
        or not versioned_gates_valid
        or ledger_payload != run_payload.get("dispatches")
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: state, gate, or dispatch artifact mismatch",
        )
    conformance_path, _ = artifacts_by_role["independent_conformance_receipt"]
    conformance = _strict_json_document(conformance_path, label=label, spec_path=spec_path)
    if (
        not isinstance(conformance, dict)
        or set(conformance) != {
            "schema", "status", "subject", "run_receipt_sha256", "checks",
            "reviewer", "reviewed_at", "trust_anchor", "review_input_sha256",
            "review_execution", "attestation_digest",
        }
        or conformance.get("schema") != "arnold.megaplan.finite_canary_conformance_receipt.v1"
        or conformance.get("status") != "passed"
        or conformance.get("subject") != subject
        or conformance.get("run_receipt_sha256") != run_hash
        or conformance.get("checks")
        != ["exact_phase_order", "single_dispatch_pairs", "terminal_finalized", "artifact_hashes", "zero_recovery_fence", "workspace_isolation"]
        or not _finite_canary_conformance_has_trust_evidence(conformance)
        or not _finite_canary_review_inputs_match(
            conformance, artifacts_by_role, root
        )
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: independent conformance did not bind the exact run",
        )
    terminal_path, _ = artifacts_by_role["v2_terminal_fence_receipt"]
    terminal = _strict_json_document(terminal_path, label=label, spec_path=spec_path)
    expected_workspace_bind = {
        "type": "bind",
        "source": subject["cloud"].get("workspace_bind_source"),
        "destination": "/workspace",
        "rw": True,
        "propagation": "rprivate",
    }
    expected_runtime_tmpfs = {
        "/run/megaplan-zero-recovery":
        "rw,noexec,nosuid,nodev,size=256m,mode=0711"
    }
    expected_mount_inventory = [
        expected_workspace_bind,
        {
            "type": "tmpfs", "source": None,
            "destination": "/run/megaplan-zero-recovery", "rw": True,
            "options": "rw,noexec,nosuid,nodev,size=256m,mode=0711",
        },
    ]
    workspace_creation = terminal.get("workspace_creation") if isinstance(terminal, dict) else None
    initial_custody = workspace_creation.get("initial_custody") if isinstance(workspace_creation, dict) else None
    runtime_access = workspace_creation.get("runtime_access") if isinstance(workspace_creation, dict) else None
    terminal_workspace = terminal.get("terminal_workspace") if isinstance(terminal, dict) else None
    terminal_transition = (
        terminal_workspace.get("transition")
        if isinstance(terminal_workspace, dict)
        else None
    )
    if (
        not isinstance(terminal, dict)
        or set(terminal)
        != {
            "schema", "status", "subject", "canary_lifecycle", "restart_policy",
            "host_units_masked", "forbidden_sessions", "forbidden_processes",
            "predecessor_container_id", "workspace_bind", "host_bind_count",
            "runtime_tmpfs", "mount_inventory_sha256", "workspace_creation",
            "terminal_workspace", "container_security",
            "completed_at",
        }
        or terminal.get("schema") != "arnold.cloud.zero_recovery_terminal_fence.v1"
        or terminal.get("status") != "passed"
        or terminal.get("subject") != subject
        or terminal.get("canary_lifecycle") != "stopped"
        or terminal.get("restart_policy") != "no"
        or terminal.get("workspace_bind") != expected_workspace_bind
        or terminal.get("host_bind_count") != 1
        or terminal.get("runtime_tmpfs") != expected_runtime_tmpfs
        or terminal.get("mount_inventory_sha256")
        != hashlib.sha256(
            json.dumps(
                expected_mount_inventory, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        or not isinstance(workspace_creation, dict)
        or set(workspace_creation)
        != {
            "schema", "status", "parent", "parent_realpath", "bind_source",
            "bind_source_realpath", "bind_destination", "initial_custody",
            "runtime_access", "transition_digest", "created_empty", "never_reused",
        }
        or workspace_creation.get("schema")
        != "arnold.cloud.zero_recovery_isolated_workspace.v1"
        or workspace_creation.get("status") != "created"
        or workspace_creation.get("parent")
        != subject["cloud"].get("predecessor_workspace")
        or workspace_creation.get("parent_realpath")
        != subject["cloud"].get("predecessor_workspace")
        or workspace_creation.get("bind_source")
        != subject["cloud"].get("workspace_bind_source")
        or workspace_creation.get("bind_source_realpath")
        != subject["cloud"].get("workspace_bind_source")
        or workspace_creation.get("bind_destination") != "/workspace"
        or workspace_creation.get("created_empty") is not True
        or workspace_creation.get("never_reused") is not True
        or not isinstance(initial_custody, dict)
        or set(initial_custody)
        != {"mode", "uid", "gid", "st_dev", "st_ino", "empty"}
        or initial_custody.get("mode") != "0700"
        or initial_custody.get("uid") != 0
        or initial_custody.get("gid") != 0
        or initial_custody.get("empty") is not True
        or not isinstance(runtime_access, dict)
        or set(runtime_access) != {"mode", "uid", "gid", "st_dev", "st_ino"}
        or runtime_access.get("mode") != "0750"
        or runtime_access.get("uid") != 0
        or runtime_access.get("gid") != 65532
        or runtime_access.get("st_dev") != initial_custody.get("st_dev")
        or runtime_access.get("st_ino") != initial_custody.get("st_ino")
        or workspace_creation.get("transition_digest")
        != hashlib.sha256(
            json.dumps(
                {"initial_custody": initial_custody, "runtime_access": runtime_access},
                sort_keys=True, separators=(",", ":"),
            ).encode()
        ).hexdigest()
        or not isinstance(terminal_workspace, dict)
        or set(terminal_workspace)
        != {"schema", "status", "path", "access_transition_digest", "transition", "transition_digest"}
        or terminal_workspace.get("schema")
        != "arnold.cloud.zero_recovery_terminal_workspace.v1"
        or terminal_workspace.get("status") != "sealed"
        or terminal_workspace.get("path")
        != subject["cloud"].get("workspace_bind_source")
        or terminal_workspace.get("access_transition_digest")
        != workspace_creation.get("transition_digest")
        or not isinstance(terminal_transition, dict)
        or set(terminal_transition) != {"before", "after"}
        or not isinstance(terminal_transition.get("before"), dict)
        or set(terminal_transition["before"])
        != {"st_dev", "st_ino", "uid", "gid", "mode"}
        or not isinstance(terminal_transition.get("after"), dict)
        or set(terminal_transition["after"])
        != {"st_dev", "st_ino", "uid", "gid", "mode"}
        or terminal_transition.get("after")
        != {
            "st_dev": initial_custody.get("st_dev"),
            "st_ino": initial_custody.get("st_ino"),
            "uid": 0,
            "gid": 0,
            "mode": "0700",
        }
        or terminal_transition.get("before", {}).get("st_dev")
        != initial_custody.get("st_dev")
        or terminal_transition.get("before", {}).get("st_ino")
        != initial_custody.get("st_ino")
        or terminal_workspace.get("transition_digest")
        != hashlib.sha256(
            json.dumps(
                terminal_transition, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        or terminal.get("container_security")
        != {
            "cap_drop": ["ALL"],
            "cap_add": [
                "CHOWN", "DAC_READ_SEARCH", "KILL", "SETGID", "SETPCAP", "SETUID"
            ],
            "security_opt": ["no-new-privileges:true"],
            "ipc_mode": "none",
            "pids_limit": 256,
            "memory_limit": 4_294_967_296,
            "memory_swap": 4_294_967_296,
            "port_bindings": {},
        }
        or terminal.get("host_units_masked") is not True
        or terminal.get("forbidden_sessions") != []
        or terminal.get("forbidden_processes") != []
        or terminal.get("predecessor_container_id")
        != subject["cloud"].get("predecessor_container_id")
        or not isinstance(terminal.get("predecessor_container_id"), str)
        or not terminal.get("predecessor_container_id")
        or _parse_iso_datetime(terminal.get("completed_at")) is None
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: terminal stop/no-background fence is invalid",
        )
    fence_path, _ = artifacts_by_role["host_zero_recovery_fence_receipt"]
    fence = _strict_json_document(fence_path, label=label, spec_path=spec_path)
    if not _finite_canary_fence_is_valid(fence):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: host zero-recovery fence is invalid",
        )
    predeploy_path, _ = artifacts_by_role["host_predeploy_receipt"]
    predeploy = _strict_json_document(predeploy_path, label=label, spec_path=spec_path)
    predeploy_unsigned = dict(predeploy) if isinstance(predeploy, dict) else {}
    predeploy_digest = predeploy_unsigned.pop("transaction_digest", None)
    predeploy_issued = _parse_iso_datetime(predeploy.get("issued_at")) if isinstance(predeploy, dict) else None
    predeploy_expires = _parse_iso_datetime(predeploy.get("expires_at")) if isinstance(predeploy, dict) else None
    fence_observed = _parse_iso_datetime(fence.get("observed_at"))
    terminal_completed = _parse_iso_datetime(terminal.get("completed_at"))
    run_started = _parse_iso_datetime(run_payload.get("started_at"))
    run_completed = _parse_iso_datetime(run_payload.get("completed_at"))
    reviewed_at = _parse_iso_datetime(conformance.get("reviewed_at"))
    if (
        not isinstance(predeploy, dict)
        or set(predeploy) != {
            "schema", "transaction_id", "issued_at", "expires_at", "target",
            "container_observation", "capacity_observation", "transaction_digest",
        }
        or predeploy.get("schema") != "arnold.cloud.zero_recovery_predeploy.v1"
        or predeploy.get("target", {}).get("host") != subject["cloud"].get("host")
        or predeploy.get("target", {}).get("workspace")
        != subject["cloud"].get("predecessor_workspace")
        or predeploy.get("target", {}).get("canary_workspace")
        != subject["cloud"].get("workspace_bind_source")
        or predeploy.get("target", {}).get("container_workspace") != "/workspace"
        or predeploy.get("target", {}).get("container") != subject["cloud"].get("predecessor_container")
        or predeploy.get("target", {}).get("canary_container") != subject["cloud"].get("canary_container")
        or predeploy.get("capacity_observation", {}).get("verdict") != "GO"
        or predeploy.get("transaction_id") != fence.get("transaction_id")
        or predeploy.get("transaction_digest") != fence.get("transaction_digest")
        or not isinstance(predeploy_digest, str)
        or hashlib.sha256(json.dumps(predeploy_unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != predeploy_digest
        or None in {predeploy_issued, predeploy_expires, fence_observed, run_started, run_completed, terminal_completed, reviewed_at, issued, completed}
        or not (predeploy_issued <= fence_observed <= run_started <= run_completed <= terminal_completed <= reviewed_at <= issued <= completed)
        or predeploy_expires < fence_observed
    ):
        raise CliError(
            "launch_precondition_failed",
            f"{label} failed for {spec_path}: host predeploy did not bind the subject",
        )


def validate_launch_preconditions(spec: ChainSpec, root: Path, spec_path: Path) -> None:
    root = Path(root).expanduser().resolve()
    for index, precondition in enumerate(spec.launch_preconditions):
        label = f"launch_preconditions[{index}] {precondition.name!r}"
        if precondition.kind == "chain_completed":
            _validate_chain_completed_precondition(
                precondition,
                root,
                spec_path,
                index=index,
            )
            continue
        if precondition.kind == "finite_canary_receipt":
            _validate_finite_canary_receipt(
                precondition,
                root,
                spec_path,
                index=index,
            )
            continue
        if precondition.kind == "git_tracked":
            _validate_git_tracked_precondition(
                precondition,
                root,
                spec_path,
                index=index,
            )
            continue
        if precondition.path is None:
            raise CliError("invalid_spec", f"{label} missing artifact path")
        target = _resolve_launch_precondition_path(precondition.path, root)
        _require_inside_root(target, root, label)
        if not target.exists():
            raise CliError(
                "launch_precondition_failed",
                f"{label} failed for {spec_path}: required artifact missing at {target}",
            )
        if precondition.check == "contains_text":
            try:
                contents = target.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise CliError(
                    "launch_precondition_failed",
                    f"{label} failed for {spec_path}: artifact is not UTF-8 text at {target}",
                ) from exc
            expected = precondition.text or ""
            if expected not in contents:
                raise CliError(
                    "launch_precondition_failed",
                    f"{label} failed for {spec_path}: artifact {target} does not contain required text {expected!r}",
                )
        if precondition.check == "review_log_clean":
            try:
                contents = target.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise CliError(
                    "launch_precondition_failed",
                    f"{label} failed for {spec_path}: artifact is not UTF-8 text at {target}",
                ) from exc
            _validate_review_log_clean(
                contents=contents,
                target=target,
                label=label,
                spec_path=spec_path,
            )


def validate_paths(spec: ChainSpec, root: Path, spec_path: Path | None = None) -> None:
    root = Path(root).expanduser().resolve()
    for milestone in spec.milestones:
        idea_path = Path(milestone.idea).expanduser()
        if not idea_path.is_absolute():
            idea_path = root / idea_path
        idea_path = idea_path.resolve()
        if not idea_path.is_file():
            raise CliError(
                "missing_idea_file",
                f"milestone {milestone.label!r} idea file not found under {root}: {idea_path}",
            )
    if spec.seed_plan:
        try:
            resolve_plan_dir(root, spec.seed_plan)
        except CliError as exc:
            raise CliError(
                "missing_seed_plan",
                f"seed plan {spec.seed_plan!r} not found under {root}: {exc.message}",
            ) from exc
    if spec_path is not None:
        validate_anchor_paths(spec, spec_path)
        validate_launch_preconditions(spec, root, spec_path)
