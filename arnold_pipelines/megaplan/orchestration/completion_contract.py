"""Completion-verification contract — SHADOW-MODE foundation.

A terminal "done" state is a *claim* the plan asserts; this module computes a
typed :class:`CompletionVerdict` from **objective evidence** (git, on-disk
artifacts, cached suite results) so a future "enforce" mode can refuse the
transition when the evidence contradicts the claim.

**Current status: shadow only.** Nothing here blocks a transition, runs the
test suite, or changes control flow. The drivers compute + persist + log a
verdict and discard the result. Every code path is fail-open: callers wrap the
top-level entry point (:func:`compute_verdict`) in try/except and swallow
errors. The historical hardening-epic design notes compose
existing helpers rather than re-implementing evidence collection:

- ``phase_coverage``   → ``PhaseResult`` + ``_latest_execution_batch_all_tasks_done``
- ``landed_diff``      → ``execution_evidence.validate_execution_evidence``
- ``worker_did_work``  → delegate ``tool_trace``/``api_calls`` + ``execution_batch_*.json``
- ``green_suite``      → authoritative verification run (always runs the suite; freshness-cached)
- ``review_disposition`` → ``review.json`` (detects rework-cap force-proceed)
- ``declared_noop``    → typed waiver artifact if present (absence is not a failure)

See module-level ``SHADOW_TODOS`` for the explicit list of follow-ups deferred
to the warn/enforce rollout.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from arnold_pipelines.megaplan._core.io import (
    list_batch_artifacts,
    sha256_file,
    sha256_text,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    ArtifactRef,
    EVIDENCE_CONTRACT_SCHEMA_VERSION,
    EvidenceRef,
    EvidenceStatus,
    TrustClass,
    normalize_evidence_status,
)

log = logging.getLogger("arnold_pipelines.megaplan.orchestration.completion_contract")


def _resolve_test_idle_timeout(config: dict[str, Any]) -> int:
    """Idle (no-output) stall cap for verification suite runs, default 180s.

    Mirrors the baseline idle cap in handlers/finalize.py: the suite is only
    killed when its output log goes silent, never merely for being large. So a
    growing post-execute verification suite no longer false-times-out (the m6
    "delta not computable" failure mode). Override via test_verification_idle_timeout
    (config) or MEGAPLAN_TEST_VERIFICATION_IDLE_TIMEOUT_S (env).
    """
    raw = config.get("test_verification_idle_timeout") if isinstance(config, dict) else None
    if raw is None:
        raw = os.getenv("MEGAPLAN_TEST_VERIFICATION_IDLE_TIMEOUT_S")
    # 300s default: pytest -q reports progress per-completed-test, so the idle gap
    # is the slowest single test; 300s tolerates a slow integration test while
    # still catching an infinitely-wedged suite.
    try:
        value = int(raw) if raw is not None else 300
        return value if value > 0 else 300
    except (ValueError, TypeError):
        return 300


# ---------------------------------------------------------------------------
# Follow-ups deliberately NOT built in the shadow foundation
# ---------------------------------------------------------------------------

#: Documented TODOs for the warn/enforce rollout. Kept as data so tests and
#: tooling can assert the foundation is honest about what it does not yet do.
SHADOW_TODOS: tuple[str, ...] = (
    "landed_diff: capture a per-milestone base-ref checkpoint "
    "(milestone_base_sha = git rev-parse HEAD at milestone start) and diff "
    "<base>..HEAD instead of relying on working-tree `git status`. "
    "validate_execution_evidence reads working-tree status only, which "
    "mis-attributes carried WIP in a chain (the m5a worktree-carry false-pass).",
    "worker_did_work: surface delegate tool_trace into a durable per-phase "
    "activity record; today shadow reads execution_batch_*.json commands_run/"
    "files_changed and marks 'unknown' when neither is present.",
    "modes: implement real 'warn' (status surfacing) and 'enforce' "
    "(fail-closed terminal -> blocked, _record_lifecycle_failure, "
    "override-waive-evidence). Currently warn/enforce behave like shadow + a "
    "logged WARNING.",
    "declared_noop: define + author a typed Waiver artifact "
    "(completion/noop.json or a finalize task `deferral` field). Today only "
    "criterion-level deferred_human exists; whole-milestone no-op has no home.",
)


# ---------------------------------------------------------------------------
# Verdict mode
# ---------------------------------------------------------------------------

CONTRACT_MODE_OFF = "off"
CONTRACT_MODE_SHADOW = "shadow"
CONTRACT_MODE_WARN = "warn"
CONTRACT_MODE_ENFORCE = "enforce"
CONTRACT_MODE_ATOMIC = "atomic"

VALID_CONTRACT_MODES: frozenset[str] = frozenset(
    {
        CONTRACT_MODE_OFF,
        CONTRACT_MODE_SHADOW,
        CONTRACT_MODE_WARN,
        CONTRACT_MODE_ENFORCE,
        CONTRACT_MODE_ATOMIC,
    }
)

# Modes that gate transitions (fail-closed).  ``atomic`` is a synonym for
# ``enforce`` and normalizes to it at load time; both carry the same semantics.
FAIL_CLOSED_CONTRACT_MODES: frozenset[str] = frozenset(
    {CONTRACT_MODE_ENFORCE, CONTRACT_MODE_ATOMIC}
)

DEFAULT_CONTRACT_MODE = CONTRACT_MODE_SHADOW

# Canonicalizer: ``atomic`` → ``enforce`` so every consumer only needs to check
# ``enforce``.  The raw value ``atomic`` is still recorded in
# ``ChainState.completion_contract_mode`` for audit but all behavioral gates
# use the canonical form.
_ATOMIC_TO_ENFORCE: dict[str, str] = {CONTRACT_MODE_ATOMIC: CONTRACT_MODE_ENFORCE}

COMPLETION_VERDICT_SCHEMA = "megaplan.completion_verdict"
COMPLETION_VERDICT_SCHEMA_VERSION = 1
COMPLETION_VERDICT_CONTRACT_VERSION = EVIDENCE_CONTRACT_SCHEMA_VERSION


def is_fail_closed_mode(mode: str) -> bool:
    """Return ``True`` when *mode* is a fail-closed (atomic/enforce) variant."""
    return mode in FAIL_CLOSED_CONTRACT_MODES or mode == CONTRACT_MODE_ENFORCE


def normalize_contract_mode(value: Any) -> str:
    """Coerce *value* to a valid contract mode, defaulting to shadow.

    ``atomic`` normalizes to ``enforce`` for all behavioral gates, but
    callers that need the raw persisted value should inspect
    ``ChainState.completion_contract_mode`` directly.
    """
    if isinstance(value, str) and value in VALID_CONTRACT_MODES:
        return _ATOMIC_TO_ENFORCE.get(value, value)
    return DEFAULT_CONTRACT_MODE


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletionSubject:
    """What is being verified."""

    kind: str  # "plan" | "milestone" | "phase"
    name: str
    to_state: str
    from_state: str | None = None
    phase: str | None = None
    plan_name: str | None = None
    milestone_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "to_state": self.to_state,
            "from_state": self.from_state,
            "phase": self.phase,
            "plan_name": self.plan_name,
            "milestone_label": self.milestone_label,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CompletionSubject":
        return cls(
            kind=str(d.get("kind", "")),
            name=str(d.get("name", "")),
            to_state=str(d.get("to_state", "")),
            from_state=_optional_str(d.get("from_state")),
            phase=_optional_str(d.get("phase")),
            plan_name=_optional_str(d.get("plan_name")),
            milestone_label=_optional_str(d.get("milestone_label")),
        )


@dataclass(frozen=True)
class CompletionVerdict:
    """The computed verdict for a subject's terminal transition.

    ``accepted`` is True iff no evidence is canonically ``unsatisfied``.
    Legacy review ``fail-not-success`` is normalized to ``unsatisfied`` during
    evidence deserialization. ``would_block`` mirrors what an enforce mode
    would do; in shadow it is purely informational.
    """

    mode: str
    subject: CompletionSubject
    evidence: tuple[EvidenceRef, ...]
    accepted: bool
    failures: tuple[str, ...] = ()
    schema: str = COMPLETION_VERDICT_SCHEMA
    schema_version: int = COMPLETION_VERDICT_SCHEMA_VERSION
    evidence_contract_version: int = COMPLETION_VERDICT_CONTRACT_VERSION
    providers_used: tuple[str, ...] = ()
    legacy_evidence_count: int = 0
    unknown_evidence_count: int = 0
    would_block_reasons: tuple[str, ...] = ()
    # Typed predicate failures — populated only in fail-closed modes (atomic/enforce).
    # In shadow/warn/off mode this tuple is empty; failures remain as string entries.
    predicate_failures: tuple["BlockingPredicateFailure", ...] = ()

    @property
    def would_block(self) -> bool:
        return self.mode in {CONTRACT_MODE_WARN, CONTRACT_MODE_ENFORCE} and not self.accepted

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": COMPLETION_VERDICT_SCHEMA,
            "schema_version": COMPLETION_VERDICT_SCHEMA_VERSION,
            "evidence_contract_version": COMPLETION_VERDICT_CONTRACT_VERSION,
            "mode": self.mode,
            "subject": self.subject.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "accepted": self.accepted,
            "would_block": self.would_block,
            "failures": list(self.failures),
            "providers_used": list(self.providers_used),
            "legacy_evidence_count": self.legacy_evidence_count,
            "unknown_evidence_count": self.unknown_evidence_count,
            "would_block_reasons": list(self.would_block_reasons),
            "predicate_failures": [pf.to_dict() for pf in self.predicate_failures],
        }
        # Surface green_suite.delta at the top level for easy consumption
        # (also available under evidence[].details.delta for the green_suite ref).
        for e in self.evidence:
            if e.kind == "green_suite" and isinstance(e.details, dict):
                gs: dict[str, Any] = {}
                if "delta" in e.details:
                    gs["delta"] = e.details["delta"]
                d["green_suite"] = gs
                break
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CompletionVerdict":
        raw_subject = d.get("subject")
        subject = (
            CompletionSubject.from_dict(raw_subject)
            if isinstance(raw_subject, dict)
            else CompletionSubject(kind="", name="", to_state="")
        )
        raw_evidence = d.get("evidence", ())
        if not isinstance(raw_evidence, (list, tuple)):
            raw_evidence = ()
        evidence = tuple(
            EvidenceRef.from_dict(item)
            for item in raw_evidence
            if isinstance(item, dict)
        )
        failures = d.get("failures", ())
        if not isinstance(failures, (list, tuple)):
            failures = ()
        providers_used = d.get("providers_used", ())
        if not isinstance(providers_used, (list, tuple)):
            providers_used = ()
        would_block_reasons = d.get("would_block_reasons", ())
        if not isinstance(would_block_reasons, (list, tuple)):
            would_block_reasons = ()
        raw_predicate_failures = d.get("predicate_failures", ())
        if not isinstance(raw_predicate_failures, (list, tuple)):
            raw_predicate_failures = ()
        predicate_failures = tuple(
            BlockingPredicateFailure.from_dict(item)
            for item in raw_predicate_failures
            if isinstance(item, dict)
        )
        return cls(
            mode=normalize_contract_mode(d.get("mode")),
            subject=subject,
            evidence=evidence,
            accepted=bool(d.get("accepted", False)),
            failures=tuple(str(item) for item in failures),
            schema=str(d.get("schema", COMPLETION_VERDICT_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")),
            evidence_contract_version=_optional_int(d.get("evidence_contract_version")),
            providers_used=tuple(str(item) for item in providers_used),
            legacy_evidence_count=_optional_int(d.get("legacy_evidence_count")),
            unknown_evidence_count=_optional_int(d.get("unknown_evidence_count")),
            would_block_reasons=tuple(str(item) for item in would_block_reasons),
            predicate_failures=predicate_failures,
        )

    def one_line(self) -> str:
        verdict = "accepted" if self.accepted else "blocked-would-be"
        if not self.would_block and not self.accepted:
            verdict = "accepted-for-mode"
        fails = ",".join(self.failures) if self.failures else "none"
        providers = ",".join(self.providers_used) if self.providers_used else "none"
        return (
            f"completion verdict ({self.mode}): {verdict} "
            f"subject={self.subject.kind}:{self.subject.name} failures=[{fails}] "
            f"providers=[{providers}] "
            f"legacy_evidence={self.legacy_evidence_count} "
            f"unknown_evidence={self.unknown_evidence_count}"
        )


# ---------------------------------------------------------------------------
# Typed blocking predicate failures
# ---------------------------------------------------------------------------

#: Canonical predicate kinds for typed blocking failures in fail-closed modes.
PREDICATE_KIND_UNKNOWN = "unknown"
PREDICATE_KIND_MISSING = "missing"
PREDICATE_KIND_STALE = "stale"
PREDICATE_KIND_REJECTED = "rejected"
PREDICATE_KIND_DIVERGENT = "divergent"
PREDICATE_KIND_OUT_OF_ORDER = "out_of_order"
PREDICATE_KIND_UNBOUND_EVIDENCE = "unbound_evidence"
PREDICATE_KIND_PROVIDER_CRASH = "provider_crash"
PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE = "unknown_acceptance_failure"

VALID_PREDICATE_KINDS: frozenset[str] = frozenset(
    {
        PREDICATE_KIND_UNKNOWN,
        PREDICATE_KIND_MISSING,
        PREDICATE_KIND_STALE,
        PREDICATE_KIND_REJECTED,
        PREDICATE_KIND_DIVERGENT,
        PREDICATE_KIND_OUT_OF_ORDER,
        PREDICATE_KIND_UNBOUND_EVIDENCE,
        PREDICATE_KIND_PROVIDER_CRASH,
        PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
    }
)


@dataclass(frozen=True)
class BlockingPredicateFailure:
    """Typed predicate failure — structured reason why evidence blocks a transition.

    In atomic/enforce (fail-closed) modes every blocking condition produces a
    typed :class:`BlockingPredicateFailure` so downstream consumers can match on
    predicate kind rather than parsing unstructured error strings.  In shadow
    mode the ``predicate_failures`` tuple on :class:`CompletionVerdict` remains
    empty; all failures stay as legacy string entries in ``failures``.
    """

    kind: str  # one of VALID_PREDICATE_KINDS
    evidence_kind: str  # which evidence provider this relates to
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    schema: str = COMPLETION_VERDICT_SCHEMA
    schema_version: int = COMPLETION_VERDICT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.kind not in VALID_PREDICATE_KINDS:
            raise ValueError(
                f"invalid predicate kind {self.kind!r}; must be one of "
                f"{sorted(VALID_PREDICATE_KINDS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "kind": self.kind,
            "evidence_kind": self.evidence_kind,
            "summary": self.summary,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BlockingPredicateFailure":
        details = d.get("details")
        return cls(
            kind=str(d.get("kind", "")),
            evidence_kind=str(d.get("evidence_kind", "")),
            summary=str(d.get("summary", "")),
            details=dict(details) if isinstance(details, dict) else {},
            schema=str(d.get("schema", COMPLETION_VERDICT_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")),
        )

    def one_line(self) -> str:
        return f"[{self.kind}] {self.evidence_kind}: {self.summary}"


def _classify_predicate_kind(ref: "EvidenceRef", *, provider_crashed: bool = False) -> str | None:
    """Classify an evidence ref into a predicate kind for typed failures.

    Returns ``None`` when the ref does not represent a blocking condition.
    """
    if provider_crashed:
        return PREDICATE_KIND_PROVIDER_CRASH

    status = ref.status
    if status == EvidenceStatus.unknown:
        return PREDICATE_KIND_UNKNOWN
    if status == EvidenceStatus.unsatisfied:
        details = ref.details if isinstance(ref.details, dict) else {}
        diag = details.get("diagnostics")
        if isinstance(diag, dict) and diag.get("legacy_status") == "fail-not-success":
            return PREDICATE_KIND_REJECTED
        summary = ref.summary.lower() if ref.summary else ""
        if "stale" in summary or "baseline" in summary:
            if "stale" in summary:
                return PREDICATE_KIND_STALE
        if "missing" in summary or "not found" in summary:
            return PREDICATE_KIND_MISSING
        if "divergent" in summary or "contradict" in summary:
            return PREDICATE_KIND_DIVERGENT
        if "out of order" in summary or "order" in summary:
            return PREDICATE_KIND_OUT_OF_ORDER
        if "unbound" in summary or "not bound" in summary:
            return PREDICATE_KIND_UNBOUND_EVIDENCE
        # Default for unsatisfied without a more specific signal
        return PREDICATE_KIND_REJECTED
    return None


def extract_green_suite_info(verdict: "CompletionVerdict") -> tuple[dict[str, Any] | None, str | None]:
    """Extract ``(delta_dict, result_status)`` from a verdict's green_suite evidence.

    Returns ``(None, None)`` when no green_suite evidence is present.
    Used by both the plan driver (auto.py) and the chain driver to make
    enforce-mode blocking decisions without duplicating the extraction logic.
    ``result_status`` is the suite run status string (``passed``, ``failed``,
    ``runner_error``, ``timeout``, ``not_applicable``), or ``None`` when
    unknown.
    """
    for e in verdict.evidence:
        if e.kind == "green_suite":
            details = e.details if isinstance(e.details, dict) else {}
            delta = details.get("delta")
            status = details.get("result_status") or details.get("status")
            if status is None:
                ev_status = getattr(e.status, "value", str(e.status))
                if ev_status == "unsatisfied":
                    failures = details.get("failures") or []
                    status = "runner_error" if "runner_error" in failures else "failed"
                elif ev_status == "satisfied":
                    status = "passed"
                elif ev_status == "not_applicable":
                    status = "not_applicable"
            return (dict(delta) if isinstance(delta, dict) else None, status)
    return None, None


# ---------------------------------------------------------------------------
# Suite delta — re-exported from arnold.pipeline.suite_delta
# ---------------------------------------------------------------------------

from arnold.pipeline.suite_delta import SuiteDelta, SuiteRunProtocol, compute_delta  # noqa: F401

# ---------------------------------------------------------------------------
# Evidence context + provider protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletionContext:
    """Read-only inputs an EvidenceProvider needs. No LLM, no plan-state trust."""

    plan_dir: Path
    project_dir: Path
    state: dict[str, Any]
    subject: CompletionSubject
    git_base_ref: str | None = None


@runtime_checkable
class EvidenceProvider(Protocol):
    """One instance per evidence class. Pure function of observable facts."""

    kind: str

    def collect(self, ctx: CompletionContext) -> EvidenceRef: ...


# ---------------------------------------------------------------------------
# Small artifact helpers (local, fail-soft)
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any | None:
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_finalize(plan_dir: Path) -> dict[str, Any]:
    data = _read_json(plan_dir / "finalize.json")
    return data if isinstance(data, dict) else {}


def _read_execution_acceptance_contract(plan_dir: Path) -> dict[str, Any] | None:
    gate = _read_json(plan_dir / "gate.json")
    if isinstance(gate, dict):
        signals = gate.get("signals")
        if isinstance(signals, dict):
            contract = signals.get("execution_acceptance_contract")
            if isinstance(contract, dict):
                return contract
            legacy = signals.get("unverifiable_checks")
            if isinstance(legacy, list) and legacy:
                return {
                    "scope": "execute",
                    "verification_mode": "verification_suite",
                    "required_checks": legacy,
                }

    for path in sorted(plan_dir.glob("gate_signals_v*.json"), reverse=True):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        signals = payload.get("signals")
        if not isinstance(signals, dict):
            continue
        contract = signals.get("execution_acceptance_contract")
        if isinstance(contract, dict):
            return contract
        legacy = signals.get("unverifiable_checks")
        if isinstance(legacy, list) and legacy:
            return {
                "scope": "execute",
                "verification_mode": "verification_suite",
                "required_checks": legacy,
            }
    return None


def _evidence_id(
    kind: str,
    subject: CompletionSubject,
    payload: dict[str, Any],
) -> str:
    """Return a deterministic id for one evidence observation."""
    canonical = json.dumps(
        {
            "kind": kind,
            "subject": subject.to_dict(),
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(canonical)


def _artifact_ref_for_path(path: Path, *, root: Path, artifact_type: str) -> ArtifactRef | None:
    try:
        if not path.is_file():
            return None
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = str(path)
        return ArtifactRef(
            path=rel,
            sha256=sha256_file(path),
            artifact_type=artifact_type,
        )
    except OSError:
        return None


def _suite_run_record(plan_dir: Path, phase: str, run_id: str) -> dict[str, Any] | None:
    from arnold_pipelines.megaplan.orchestration.suite_runs_log import latest_run_for_phase

    record = latest_run_for_phase(plan_dir, phase)
    if not isinstance(record, dict):
        return None
    if str(record.get("run_id", "")) != run_id:
        return None
    return record


def _latest_suite_run_result(plan_dir: Path, phase: str) -> Any | None:
    from arnold_pipelines.megaplan.orchestration.suite_runs_log import (
        _record_to_result,
        latest_run_for_phase,
    )

    record = latest_run_for_phase(plan_dir, phase)
    if not isinstance(record, dict):
        return None
    try:
        return _record_to_result(record)
    except (KeyError, TypeError, ValueError):
        return None


def _provider_evidence_ref(
    *,
    kind: str,
    status: EvidenceStatus,
    summary: str,
    details: dict[str, Any],
    ctx: CompletionContext,
    trust_class: TrustClass,
    artifact: ArtifactRef | None = None,
    artifacts: tuple[ArtifactRef, ...] = (),
    source: str | None = None,
    code_hash: str | None = None,
    provider: str | None = None,
) -> EvidenceRef:
    """Build a provider ref with stable provenance common to contract providers."""
    payload = {
        "status": status.value,
        "summary": summary,
        "details": details,
        "artifact": artifact.to_dict() if artifact is not None else None,
        "artifacts": [a.to_dict() for a in artifacts],
        "source": source,
        "code_hash": code_hash,
    }
    enriched_details = dict(details)
    enriched_details["evidence_id"] = _evidence_id(kind, ctx.subject, payload)
    return EvidenceRef(
        kind,
        status,
        summary,
        enriched_details,
        trust_class=trust_class,
        provider=provider or f"{type(ctx).__module__}.{kind}",
        provider_version=str(EVIDENCE_CONTRACT_SCHEMA_VERSION),
        artifact=artifact,
        artifacts=artifacts,
        source=source,
        subject=ctx.subject.name,
        code_hash=code_hash,
    )


# ---------------------------------------------------------------------------
# Evidence providers
# ---------------------------------------------------------------------------


class PhaseCoverageProvider:
    """phase_coverage — did execute really finish all its tasks?

    Composes ``PhaseResult`` (latest phase exit) with
    ``_latest_execution_batch_all_tasks_done`` (every task in the latest batch
    is done + finalize tasks consistent).
    """

    kind = "phase_coverage"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        from arnold_pipelines.megaplan.chain import _latest_execution_batch_all_tasks_done
        from arnold_pipelines.megaplan.orchestration.phase_result import (
            PHASE_RESULT_FILENAME,
            read_phase_result,
        )

        details: dict[str, Any] = {}
        artifact = _artifact_ref_for_path(
            ctx.plan_dir / PHASE_RESULT_FILENAME,
            root=ctx.plan_dir,
            artifact_type="application/json",
        )
        phase_result = read_phase_result(ctx.plan_dir)
        if phase_result is not None:
            details["phase"] = phase_result.phase
            details["exit_kind"] = phase_result.exit_kind

        try:
            all_done, reason = _latest_execution_batch_all_tasks_done(ctx.plan_dir)
        except Exception as exc:  # fail-soft → unknown, never crash
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary=f"could not evaluate batch coverage: {exc}",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=artifact,
                source=PHASE_RESULT_FILENAME if artifact is not None else None,
                provider=type(self).__name__,
            )

        details["reason"] = reason
        if all_done:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.satisfied,
                summary="all batch tasks done",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=artifact,
                source=PHASE_RESULT_FILENAME if artifact is not None else None,
                provider=type(self).__name__,
            )
        if "no execution_batch" in reason:
            # No execute artifact at all (e.g. prose/plan-only) → can't judge.
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary=reason,
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=artifact,
                source=PHASE_RESULT_FILENAME if artifact is not None else None,
                provider=type(self).__name__,
            )
        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.unsatisfied,
            summary=reason,
            details=details,
            ctx=ctx,
            trust_class=TrustClass.judgment,
            artifact=artifact,
            source=PHASE_RESULT_FILENAME if artifact is not None else None,
            provider=type(self).__name__,
        )


class LandedDiffProvider:
    """landed_diff — is there a real, claim-consistent diff on disk?

    Reuses ``validate_execution_evidence`` wholesale. Its hollow-done +
    phantom-claim checks already catch the "abandoned after planning, zero
    diff" case.
    """

    kind = "landed_diff"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    is_prose_mode,
)
        from arnold_pipelines.megaplan.orchestration.execution_evidence import (
            validate_execution_evidence,
        )

        finalize = _read_finalize(ctx.plan_dir)
        finalize_artifact = _artifact_ref_for_path(
            ctx.plan_dir / "finalize.json",
            root=ctx.plan_dir,
            artifact_type="application/json",
        )
        if not finalize:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no finalize.json to evaluate landed diff",
                details={},
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=finalize_artifact,
                source="finalize.json" if finalize_artifact is not None else None,
                provider=type(self).__name__,
            )

        try:
            result = validate_execution_evidence(
                finalize,
                ctx.project_dir,
                plan_dir=ctx.plan_dir,
                artifact_prefix="execution_audit_completion_contract",
                state=ctx.state,
                base_ref=ctx.git_base_ref,
            )
        except Exception as exc:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary=f"could not evaluate landed diff: {exc}",
                details={},
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=finalize_artifact,
                source="execution_evidence.validate_execution_evidence",
                provider=type(self).__name__,
            )

        findings = result.get("findings") or []
        files_in_diff = result.get("files_in_diff") or []
        evidence_window = result.get("evidence_window") or {}
        declared_authoritative = (
            evidence_window.get("source") == "declared"
            and bool(evidence_window.get("base_sha"))
        )
        if declared_authoritative:
            diff_source = "declared_authoritative"
        elif ctx.git_base_ref:
            diff_source = "declared_unresolved"
        else:
            diff_source = "heuristic"

        details = {
            "findings": findings,
            "files_in_diff": files_in_diff,
            "files_in_committed_range": result.get("files_in_committed_range") or [],
            "files_claimed": result.get("files_claimed") or [],
            "skipped": bool(result.get("skipped")),
            "skip_reason": result.get("reason") or "",
            "diff_source": diff_source,
            "evidence_window": evidence_window,
        }

        if result.get("skipped"):
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary=f"evidence check skipped: {result.get('reason')}",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=finalize_artifact,
                source="execution_evidence.validate_execution_evidence",
                provider=type(self).__name__,
            )

        prose = False
        try:
            prose = is_prose_mode(ctx.state)
        except Exception:
            prose = False

        # Without a base..HEAD ref (see SHADOW_TODOS), the "unclaimed working-tree
        # changes" finding is unreliable noise on a dirty/carried tree (the m5a
        # carry case), so it is advisory-only in shadow. Real signals — phantom
        # claims, hollow-done, pending/blocked-without-reason, perfunctory notes —
        # still drive unsatisfied.
        _advisory_prefix = "Git status shows changed files not claimed"
        if declared_authoritative:
            real_findings = list(findings)
            details["advisory_findings"] = []
        else:
            real_findings = [
                f for f in findings if not str(f).startswith(_advisory_prefix)
            ]
            details["advisory_findings"] = [
                f for f in findings if str(f).startswith(_advisory_prefix)
            ]

        # Empty diff in code mode == abandonment signal (unless a waiver exists,
        # which the driver folds in separately). Prose mode tracks sections.
        if real_findings:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary="execution evidence findings: " + "; ".join(str(f) for f in real_findings),
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=finalize_artifact,
                source="execution_evidence.validate_execution_evidence",
                provider=type(self).__name__,
            )
        if not prose and not files_in_diff:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary="no files in working-tree diff (possible abandonment / zero-diff)",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=finalize_artifact,
                source="execution_evidence.validate_execution_evidence",
                provider=type(self).__name__,
            )
        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary="diff present and claim-consistent",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.judgment,
            artifact=finalize_artifact,
            source="execution_evidence.validate_execution_evidence",
            provider=type(self).__name__,
        )


class WorkerDidWorkProvider:
    """worker_did_work — did the executor actually do anything?

    Per B-impl-reuse the activity signal is NOT in cli_provenance (config keys
    only). We read ``execution_batch_*.json`` task records for non-empty
    ``files_changed`` / ``commands_run`` (and ``sections_written`` in prose
    mode). If no batch artifact / no signal is present we mark ``unknown``
    rather than guess.
    """

    kind = "worker_did_work"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        batches = sorted(list_batch_artifacts(ctx.plan_dir))
        artifacts = tuple(
            ref
            for ref in (
                _artifact_ref_for_path(
                    batch_path,
                    root=ctx.plan_dir,
                    artifact_type="application/json",
                )
                for batch_path in batches
            )
            if ref is not None
        )
        if not batches:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no execution_batch_*.json to assess worker activity",
                details={},
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="execution_batch_*.json",
                provider=type(self).__name__,
            )

        files_changed = 0
        commands_run = 0
        sections_written = 0
        for batch_path in batches:
            payload = _read_json(batch_path)
            if not isinstance(payload, dict):
                continue
            files_changed += len(payload.get("files_changed") or [])
            commands_run += len(payload.get("commands_run") or [])
            sections_written += len(payload.get("sections_written") or [])
            records: list[dict[str, Any]] = []
            for key in ("task_updates", "tasks"):
                raw = payload.get(key)
                if isinstance(raw, list):
                    records.extend(r for r in raw if isinstance(r, dict))
            for rec in records:
                files_changed += len(rec.get("files_changed") or [])
                commands_run += len(rec.get("commands_run") or [])
                sections_written += len(rec.get("sections_written") or [])

        details = {
            "files_changed": files_changed,
            "commands_run": commands_run,
            "sections_written": sections_written,
            "batches": len(batches),
            "batch_artifacts": [artifact.path for artifact in artifacts],
            # TODO(enforce): incorporate delegate tool_trace / api_calls count.
            "activity_source": "execution_batch_records",
        }
        if files_changed or commands_run or sections_written:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.satisfied,
                summary="worker activity present",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.evidence,
                artifacts=artifacts,
                source="execution_batch_*.json",
                provider=type(self).__name__,
            )
        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.unsatisfied,
            summary="no files changed, commands run, or sections written across any batch",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.evidence,
            artifacts=artifacts,
            source="execution_batch_*.json",
            provider=type(self).__name__,
        )


class GreenSuiteProvider:
    """green_suite — always runs the authoritative post-execute suite.

    Runs :func:`~megaplan.orchestration.suite_runner.run_suite` unconditionally
    in every mode (off/shadow/warn/enforce).  The mode flag gates ENFORCEMENT
    only; measurement runs regardless to close the Layer-A verification gap.

    Uses ``freshness_skip`` to short-circuit when the ``code_hash`` matches
    the latest verification record already on disk.

    Also computes a nodeid-level :class:`SuiteDelta` between the baseline and
    verification runs, with a single bounded flake-retry for tests whose
    pass/fail state flipped versus baseline.
    """

    kind = "green_suite"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _baseline_from_log(plan_dir: Path) -> "SuiteRunResult | None":
        """Return the most recent baseline SuiteRunResult from the ndjson log."""
        from arnold_pipelines.megaplan.orchestration.suite_runner import (
            SuiteRunResult,
            latest_run_for_phase,
        )

        record = latest_run_for_phase(plan_dir, "baseline")
        if record is None:
            return None
        raw_log_path = record.get("raw_log_path", "")
        try:
            return SuiteRunResult(
                run_id=str(record["run_id"]),
                phase=str(record["phase"]),
                code_hash=str(record["code_hash"]),
                command=str(record["command"]),
                duration=float(record["duration"]),
                collected=int(record["collected"]),
                collected_ids=list(record["collected_ids"]),
                failures=list(record["failures"]),
                passes=list(record["passes"]),
                status=str(record["status"]),
                exit_code=record.get("exit_code"),
                raw_log_path=Path(raw_log_path) if raw_log_path else Path(),
                collections_parse_ok=bool(
                    record.get("collections_parse_ok", False)
                ),
                collection_errors=list(record.get("collection_errors") or []),
            )
        except (KeyError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # flake retry
    # ------------------------------------------------------------------

    def _flake_retry(
        self,
        ctx: CompletionContext,
        config: dict[str, Any],
        baseline: "SuiteRunResult",
        verification: "SuiteRunResult",
        flips: set[str],
        timeout: int,
    ) -> tuple["SuiteRunResult", SuiteDelta, set[str], set[str]]:
        """Run one retry of the flipped nodeids; return (retry_result, delta, stable_failing, stable_passing).

        *flips* is the set of nodeids whose pass/fail state differs between
        baseline and verification.  The retry runs *only* those nodeids.

        Returns the retry SuiteRunResult, a recomputed delta against baseline,
        and the *stable* newly-failing / newly-passing sets (nodeids that stayed
        flipped across both runs).  Everything else becomes a flake.
        """
        flip_count = len(flips)
        if flip_count > 1000:
            return self._skipped_flake_retry(baseline, verification, flips)

        retry_result = self._run_flake_retry_suite(
            ctx, config, baseline, flips, timeout
        )
        stable_newly_failing, stable_newly_passing, flakes = (
            self._classify_flake_retry(baseline, verification, retry_result, flips)
        )
        delta = self._flake_retry_delta(
            baseline,
            verification,
            retry_result,
            stable_newly_failing,
            stable_newly_passing,
            flakes,
        )
        return retry_result, delta, stable_newly_failing, stable_newly_passing

    @staticmethod
    def _skipped_flake_retry(
        baseline: "SuiteRunResult",
        verification: "SuiteRunResult",
        flips: set[str],
    ) -> tuple["SuiteRunResult", SuiteDelta, set[str], set[str]]:
        flip_count = len(flips)
        log.warning(
            "flake_retry: %d flipped nodeids (>1000) — skipping retry; "
            "all flips classified as flakes.  "
            "Baseline run_id=%s verification run_id=%s",
            flip_count,
            baseline.run_id,
            verification.run_id,
        )
        delta = SuiteDelta(
            computable=True,
            newly_failing=(),
            newly_passing=(),
            still_red=tuple(
                sorted(
                    set(baseline.failures)
                    & set(verification.failures)
                    & set(verification.collected_ids)
                )
            ),
            still_green=tuple(
                sorted(
                    (set(baseline.collected_ids) & set(verification.collected_ids))
                    - set(baseline.failures)
                    - set(verification.failures)
                )
            ),
            deleted_tests=tuple(
                sorted(set(baseline.collected_ids) - set(verification.collected_ids))
            ),
            added_tests=tuple(
                sorted(set(verification.collected_ids) - set(baseline.collected_ids))
            ),
            flakes=tuple(sorted(flips)),
            tests_collected=len(verification.collected_ids),
            duration=verification.duration,
            flake_retry_skipped=True,
            flake_retry_reason=f">{1000} flipped nodeids ({flip_count}); retry suppressed",
        )
        return verification, delta, set(), set()

    def _run_flake_retry_suite(
        self,
        ctx: CompletionContext,
        config: dict[str, Any],
        baseline: "SuiteRunResult",
        flips: set[str],
        timeout: int,
    ) -> "SuiteRunResult":
        from arnold_pipelines.megaplan.orchestration.suite_runner import (
            append_suite_run,
            run_suite,
        )

        retry_command, from_file_path = self._flake_retry_command(config, flips)
        retry_config: dict[str, Any] = dict(config)
        retry_config["test_command"] = retry_command
        retry_config["plan_dir"] = str(ctx.plan_dir)
        retry_deadline = time.monotonic() + min(
            timeout, max(300.0, baseline.duration * 2)
        )

        retry_result = run_suite(
            ctx.project_dir,
            retry_config,
            phase="flake_retry",
            deadline_seconds=retry_deadline,
            idle_seconds=_resolve_test_idle_timeout(config),
        )
        append_suite_run(ctx.plan_dir, retry_result)
        self._cleanup_flake_retry_file(from_file_path)
        return retry_result

    @staticmethod
    def _flake_retry_command(
        config: dict[str, Any],
        flips: set[str],
    ) -> tuple[str, "Path | None"]:
        base_cmd = config.get("test_command") if isinstance(config, dict) else None
        if not base_cmd:
            base_cmd = "pytest"

        for flag in ("--tb=no", "-q", "--no-header", "-rN", "-rA"):
            base_cmd = base_cmd.replace(flag, "")
        base_cmd = base_cmd.strip()

        nodeid_args: list[str] = []
        use_from_file = len(flips) > 100
        from_file_path: Path | None = None
        if use_from_file:
            fd, tmpname = tempfile.mkstemp(
                suffix=".txt", prefix="flake_retry_nodeids_"
            )
            from_file_path = Path(tmpname)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for nid in sorted(flips):
                    fh.write(nid + "\n")
            nodeid_args = sorted(flips)
        else:
            nodeid_args = sorted(flips)

        retry_command = " ".join(
            [base_cmd, "--tb=no", "-q", "--no-header", "-rA"]
            + [shlex.quote(a) for a in nodeid_args]
        )
        return retry_command, from_file_path

    @staticmethod
    def _cleanup_flake_retry_file(from_file_path: "Path | None") -> None:
        if from_file_path is not None:
            try:
                from_file_path.unlink()
            except OSError:
                pass

    @staticmethod
    def _classify_flake_retry(
        baseline: "SuiteRunResult",
        verification: "SuiteRunResult",
        retry_result: "SuiteRunResult",
        flips: set[str],
    ) -> tuple[set[str], set[str], set[str]]:
        retry_failures: set[str] = set(retry_result.failures)
        verification_fail = set(verification.failures)
        baseline_fail = set(baseline.failures)

        stable_newly_failing: set[str] = set()
        stable_newly_passing: set[str] = set()
        flakes: set[str] = set()

        for nid in flips:
            in_baseline_fail = nid in baseline_fail
            in_verification_fail = nid in verification_fail
            in_retry_fail = nid in retry_failures

            if in_baseline_fail and not in_verification_fail:
                # Was failing in baseline, passing in verification → newly_passing candidate
                if nid in retry_failures:
                    # Retry says it still fails → flake (unstable)
                    flakes.add(nid)
                else:
                    # Retry confirms it passes → stable newly_passing
                    stable_newly_passing.add(nid)
            elif not in_baseline_fail and in_verification_fail:
                # Was passing in baseline, failing in verification → newly_failing candidate
                if nid in retry_failures:
                    # Retry confirms it fails → stable newly_failing
                    stable_newly_failing.add(nid)
                else:
                    # Retry says it passes → flake (unstable)
                    flakes.add(nid)
            else:
                # Shouldn't happen given flips definition, but be safe.
                flakes.add(nid)
        return stable_newly_failing, stable_newly_passing, flakes

    @staticmethod
    def _flake_retry_delta(
        baseline: "SuiteRunResult",
        verification: "SuiteRunResult",
        retry_result: "SuiteRunResult",
        stable_newly_failing: set[str],
        stable_newly_passing: set[str],
        flakes: set[str],
    ) -> SuiteDelta:
        baseline_fail = set(baseline.failures)
        retry_failures = set(retry_result.failures)
        return SuiteDelta(
            computable=True,
            newly_failing=tuple(sorted(stable_newly_failing)),
            newly_passing=tuple(sorted(stable_newly_passing)),
            still_red=tuple(
                sorted(
                    baseline_fail
                    & retry_failures
                    & set(verification.collected_ids)
                )
            ),
            still_green=tuple(
                sorted(
                    (set(baseline.collected_ids) & set(retry_result.collected_ids))
                    - baseline_fail
                    - retry_failures
                )
            ),
            deleted_tests=tuple(
                sorted(
                    set(baseline.collected_ids) - set(retry_result.collected_ids)
                )
            ),
            added_tests=tuple(
                sorted(
                    set(retry_result.collected_ids) - set(baseline.collected_ids)
                )
            ),
            flakes=tuple(sorted(flakes)),
            tests_collected=len(retry_result.collected_ids),
            duration=retry_result.duration,
            flake_retry_skipped=False,
            flake_retry_reason="",
        )

    # ------------------------------------------------------------------
    # collect
    # ------------------------------------------------------------------

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        config, timeout = self._suite_config_and_timeout(ctx)
        current_code_hash = self._current_code_hash(ctx, config)
        result, cached = self._verification_result(
            ctx, config, timeout, current_code_hash
        )
        baseline = self._baseline_from_log(ctx.plan_dir)
        baseline_stale = (
            baseline.code_hash != current_code_hash if baseline is not None else False
        )
        result, delta, flake_retried = self._verification_delta(
            ctx, config, baseline, result, timeout
        )
        details = self._suite_details(
            ctx, result, cached, delta, flake_retried, baseline_stale
        )
        return self._evidence_from_suite_status(
            ctx, result, delta, details, cached, baseline, timeout
        )

    @staticmethod
    def _suite_config_and_timeout(
        ctx: CompletionContext,
    ) -> tuple[dict[str, Any], int]:
        raw_config = (
            ctx.state.get("config", {}) if isinstance(ctx.state, dict) else {}
        )
        config: dict[str, Any] = dict(raw_config) if isinstance(raw_config, dict) else {}
        config["plan_dir"] = str(ctx.plan_dir)
        if not config.get("test_command"):
            finalize = _read_json(ctx.plan_dir / "finalize.json")
            baseline_command = (
                finalize.get("baseline_test_command")
                if isinstance(finalize, dict)
                else None
            )
            test_selection = (
                finalize.get("test_selection") if isinstance(finalize, dict) else None
            )
            selected_command = (
                test_selection.get("command_override")
                if isinstance(test_selection, dict)
                else None
            )
            for candidate in (baseline_command, selected_command):
                if isinstance(candidate, str) and candidate.strip():
                    config["test_command"] = candidate.strip()
                    break
        timeout: int = config.get("test_baseline_timeout", 900)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 900
        return config, timeout

    @staticmethod
    def _hash_paths_from_config(config: dict[str, Any]) -> "list[str] | None":
        hash_paths: list[str] | None = None
        if isinstance(config, dict):
            test_dirs = config.get("test_dirs")
            source_globs = config.get("source_globs")
            if test_dirs or source_globs:
                hash_paths = []
                if test_dirs:
                    if isinstance(test_dirs, list):
                        hash_paths.extend(test_dirs)
                    elif isinstance(test_dirs, str):
                        hash_paths.append(test_dirs)
                if source_globs:
                    if isinstance(source_globs, list):
                        hash_paths.extend(source_globs)
                    elif isinstance(source_globs, str):
                        hash_paths.append(source_globs)
        return hash_paths

    def _current_code_hash(
        self,
        ctx: CompletionContext,
        config: dict[str, Any],
    ) -> str:
        from arnold_pipelines.megaplan.orchestration.suite_runner import _compute_code_hash

        return _compute_code_hash(
            ctx.project_dir,
            paths=self._hash_paths_from_config(config),
        )

    @staticmethod
    def _verification_result(
        ctx: CompletionContext,
        config: dict[str, Any],
        timeout: int,
        current_code_hash: str,
    ) -> tuple["SuiteRunResult", "SuiteRunResult | None"]:
        from arnold_pipelines.megaplan.orchestration.suite_runner import (
            append_suite_run,
            freshness_skip,
            run_suite,
        )

        cached = freshness_skip(ctx.plan_dir, current_code_hash, phase="verification")
        if cached is not None:
            return cached, cached
        deadline = time.monotonic() + timeout
        result = run_suite(
            ctx.project_dir,
            config,
            phase="verification",
            deadline_seconds=deadline,
            idle_seconds=_resolve_test_idle_timeout(config),
        )
        append_suite_run(ctx.plan_dir, result)
        return result, None

    def _verification_delta(
        self,
        ctx: CompletionContext,
        config: dict[str, Any],
        baseline: "SuiteRunResult | None",
        result: "SuiteRunResult",
        timeout: int,
    ) -> tuple["SuiteRunResult", "SuiteDelta | None", bool]:
        flake_retried = False
        if baseline is not None and (
            not baseline.collections_parse_ok
            or not result.collections_parse_ok
        ):
            return result, self._noncomputable_delta(result), flake_retried
        if baseline is None:
            if result.collection_errors:
                return result, self._collection_error_delta(result), flake_retried
            return result, None, flake_retried

        delta = compute_delta(baseline, result)
        flips: set[str] = set(delta.newly_failing) | set(delta.newly_passing)
        if flips:
            result, delta, _, _ = self._flake_retry(
                ctx, config, baseline, result, flips, timeout
            )
            flake_retried = True
        return result, delta, flake_retried

    @staticmethod
    def _noncomputable_delta(result: "SuiteRunResult") -> SuiteDelta:
        return SuiteDelta(
            computable=False,
            newly_failing=(),
            newly_passing=(),
            still_red=(),
            still_green=(),
            deleted_tests=(),
            added_tests=(),
            flakes=(),
            tests_collected=0,
            duration=result.duration,
        )

    @staticmethod
    def _collection_error_delta(result: "SuiteRunResult") -> SuiteDelta:
        collection_errors = tuple(sorted(result.collection_errors or result.failures))
        return SuiteDelta(
            computable=True,
            newly_failing=collection_errors,
            newly_passing=(),
            still_red=(),
            still_green=(),
            deleted_tests=(),
            added_tests=tuple(collection_errors),
            flakes=(),
            tests_collected=len(result.collected_ids),
            duration=result.duration,
        )

    @staticmethod
    def _suite_details(
        ctx: CompletionContext,
        result: "SuiteRunResult",
        cached: "SuiteRunResult | None",
        delta: "SuiteDelta | None",
        flake_retried: bool,
        baseline_stale: bool,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {
            "run_id": result.run_id,
            "phase": result.phase,
            "command": result.command,
            "duration": result.duration,
            "collected": result.collected,
            "collected_ids": result.collected_ids[:20],
            "failure_count": len(result.failures),
            "failures": result.failures[:20],
            "pass_count": len(result.passes),
            "status": result.status,
            "exit_code": result.exit_code,
            "code_hash": result.code_hash,
            "collections_parse_ok": result.collections_parse_ok,
            "collection_errors": list(result.collection_errors or []),
            "raw_log_path": str(result.raw_log_path),
            "freshness_cache_hit": cached is not None,
        }

        finalize = _read_finalize(ctx.plan_dir)
        baseline_command = finalize.get("baseline_test_command")
        note = finalize.get("baseline_test_note")
        details["baseline_test_command"] = baseline_command
        details["baseline_test_note"] = note

        if delta is not None:
            details["delta"] = delta.to_dict()
            details["delta.computable"] = delta.computable
            details["flake_retried"] = flake_retried
            details["baseline_stale"] = baseline_stale
        return details

    def _suite_evidence_ref(
        self,
        ctx: CompletionContext,
        status: EvidenceStatus,
        summary: str,
        result: "SuiteRunResult",
        details: dict[str, Any],
    ) -> EvidenceRef:
        verification_log = ctx.plan_dir / "verification" / "suite_runs.ndjson"
        log_record = _suite_run_record(ctx.plan_dir, result.phase, result.run_id)
        artifacts = tuple(
            artifact
            for artifact in (
                _artifact_ref_for_path(
                    result.raw_log_path,
                    root=ctx.plan_dir,
                    artifact_type="text/plain",
                ),
                _artifact_ref_for_path(
                    verification_log,
                    root=ctx.plan_dir,
                    artifact_type="application/x-ndjson",
                ),
            )
            if artifact is not None
        )
        details["artifact_refs"] = [artifact.to_dict() for artifact in artifacts]
        details["suite_run_log_path"] = (
            verification_log.relative_to(ctx.plan_dir).as_posix()
            if verification_log.exists()
            else "verification/suite_runs.ndjson"
        )
        if log_record is not None:
            details["suite_run_log_ts"] = log_record.get("ts")
        details["evidence_id"] = _evidence_id(
            self.kind,
            ctx.subject,
            {
                "run_id": result.run_id,
                "phase": result.phase,
                "command": result.command,
                "exit_code": result.exit_code,
                "status": result.status,
                "code_hash": result.code_hash,
                "failure_count": details.get("failure_count"),
                "collected": details.get("collected"),
                "freshness_cache_hit": details.get("freshness_cache_hit"),
                "delta": details.get("delta"),
                "artifacts": [artifact.to_dict() for artifact in artifacts],
            },
        )
        return EvidenceRef(
            self.kind,
            status,
            summary,
            details,
            trust_class=TrustClass.evidence,
            provider=self.__class__.__name__,
            provider_version=str(EVIDENCE_CONTRACT_SCHEMA_VERSION),
            artifact=artifacts[0] if artifacts else None,
            artifacts=artifacts,
            source=f"{result.phase}:{result.run_id}",
            subject=f"{ctx.subject.kind}:{ctx.subject.name}",
            observed_at=_optional_str(log_record.get("ts")) if log_record is not None else None,
            code_hash=result.code_hash,
        )

    def _evidence_from_suite_status(
        self,
        ctx: CompletionContext,
        result: "SuiteRunResult",
        delta: "SuiteDelta | None",
        details: dict[str, Any],
        cached: "SuiteRunResult | None",
        baseline: "SuiteRunResult | None",
        timeout: int,
    ) -> EvidenceRef:
        if delta is not None and not delta.computable:
            details["failures"] = ["runner_error"]
            self._emit_telemetry(ctx, result, delta, details, cached)
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.unsatisfied,
                "verification suite ran but delta is not computable "
                "(collection parse failure in baseline or verification)",
                result,
                details,
            )

        if result.status == "not_applicable":
            return self._not_applicable_evidence(
                ctx, result, delta, details, cached, baseline
            )

        if result.status == "passed":
            self._emit_telemetry(ctx, result, delta, details, cached)
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.satisfied,
                "verification suite passed",
                result,
                details,
            )
        elif result.status == "failed":
            return self._failed_suite_evidence(ctx, result, delta, details, cached)
        elif result.status == "timeout":
            details["failures"] = ["runner_error"]
            self._emit_telemetry(ctx, result, delta, details, cached)
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.unsatisfied,
                f"verification suite timed out after {timeout}s",
                result,
                details,
            )
        elif result.status == "runner_error":
            details["failures"] = ["runner_error"]
            self._emit_telemetry(ctx, result, delta, details, cached)
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.unsatisfied,
                "verification suite runner error",
                result,
                details,
            )
        else:  # unknown/unexpected status – treat as runner_error
            details["failures"] = ["runner_error"]
            self._emit_telemetry(ctx, result, delta, details, cached)
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.unsatisfied,
                f"verification suite unexpected status: {result.status}",
                result,
                details,
            )

    def _not_applicable_evidence(
        self,
        ctx: CompletionContext,
        result: "SuiteRunResult",
        delta: "SuiteDelta | None",
        details: dict[str, Any],
        cached: "SuiteRunResult | None",
        baseline: "SuiteRunResult | None",
    ) -> EvidenceRef:
        baseline_collected = baseline.collected if baseline is not None else 0
        if baseline_collected > 0:
            details["failures"] = ["runner_error"]
            self._emit_telemetry(ctx, result, delta, details, cached)
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.unsatisfied,
                "verification suite runner error: "
                f"baseline collected {baseline_collected} test(s) "
                "but verification collected 0 (partial-drop / catastrophic failure)",
                result,
                details,
            )
        self._emit_telemetry(ctx, result, delta, details, cached)
        return self._suite_evidence_ref(
            ctx,
            EvidenceStatus.not_applicable,
            "verification suite not applicable (no tests collected)",
            result,
            details,
        )

    def _failed_suite_evidence(
        self,
        ctx: CompletionContext,
        result: "SuiteRunResult",
        delta: "SuiteDelta | None",
        details: dict[str, Any],
        cached: "SuiteRunResult | None",
    ) -> EvidenceRef:
        self._emit_telemetry(ctx, result, delta, details, cached)
        if result.collection_errors:
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.unsatisfied,
                "verification suite has collection/import error(s) "
                f"({len(result.collection_errors)}); structural suite failures "
                "are not deferred by baseline status",
                result,
                details,
            )
        if (
            delta is not None
            and delta.computable
            and not delta.newly_failing
            and not delta.deleted_tests
        ):
            return self._suite_evidence_ref(
                ctx,
                EvidenceStatus.satisfied,
                "verification suite has only pre-existing baseline "
                f"failures ({len(result.failures)}); no new regressions",
                result,
                details,
            )
        return self._suite_evidence_ref(
            ctx,
            EvidenceStatus.unsatisfied,
            f"verification suite has {len(result.failures)} failing test(s)",
            result,
            details,
        )

    # ------------------------------------------------------------------
    # telemetry
    # ------------------------------------------------------------------

    @staticmethod
    def _emit_telemetry(
        ctx: CompletionContext,
        result: "SuiteRunResult",
        delta: "SuiteDelta | None",
        details: dict[str, Any],
        cached: "SuiteRunResult | None",
    ) -> None:
        """Emit one structured telemetry log line per post-execute run.

        Summarises ``{mode, status, newly_failing_count, deleted_tests,
        duration, code_hash, freshness_skip}`` so operators can monitor
        verification health without parsing the full verdict JSON.
        """
        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            normalize_contract_mode,
        )

        config: dict[str, Any] = (
            ctx.state.get("config", {}) if isinstance(ctx.state, dict) else {}
        )
        mode = normalize_contract_mode(
            config.get("completion_contract_mode", "shadow")
        )

        newly_failing_count = len(delta.newly_failing) if delta is not None else 0
        deleted_count = len(delta.deleted_tests) if delta is not None else 0

        log.info(
            "green_suite telemetry "
            "mode=%s status=%s newly_failing=%d deleted_tests=%d "
            "duration=%.2f code_hash=%s freshness_skip=%s",
            mode,
            result.status,
            newly_failing_count,
            deleted_count,
            result.duration,
            result.code_hash,
            "true" if cached is not None else "false",
        )


class ExecuteAcceptanceContractProvider:
    """execution_acceptance_contract — verify execute-only checks via the suite."""

    kind = "execution_acceptance_contract"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        contract = _read_execution_acceptance_contract(ctx.plan_dir)
        if not isinstance(contract, dict):
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.not_applicable,
                summary="no execute acceptance contract exported from gate",
                details={},
                ctx=ctx,
                trust_class=TrustClass.claim,
                source="gate.json|gate_signals_v*.json",
                provider=type(self).__name__,
            )

        required_checks = contract.get("required_checks")
        if not isinstance(required_checks, list) or not required_checks:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.not_applicable,
                summary="execute acceptance contract has no required checks",
                details={"contract": contract},
                ctx=ctx,
                trust_class=TrustClass.claim,
                source="gate.json|gate_signals_v*.json",
                provider=type(self).__name__,
            )

        verification = _latest_suite_run_result(ctx.plan_dir, "verification")
        if verification is None:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="execute acceptance contract has no recorded verification suite run",
                details={
                    "contract": contract,
                    "required_check_count": len(required_checks),
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="verification/suite_runs.ndjson",
                provider=type(self).__name__,
            )

        baseline = _latest_suite_run_result(ctx.plan_dir, "baseline")
        details = {
            "contract": contract,
            "required_check_count": len(required_checks),
            "suite_status": verification.status,
            "suite_run_id": verification.run_id,
        }
        if verification.status == "passed":
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.satisfied,
                summary=(
                    "verification suite satisfied the execute acceptance contract "
                    f"for {len(required_checks)} check(s)"
                ),
                details=details,
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="gate.json|gate_signals_v*.json + verification/suite_runs.ndjson",
                provider=type(self).__name__,
            )
        if verification.status == "not_applicable":
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=(
                    "execute acceptance contract requires verification evidence, "
                    "but the verification suite was not applicable"
                ),
                details=details,
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="gate.json|gate_signals_v*.json + verification/suite_runs.ndjson",
                provider=type(self).__name__,
            )
        if verification.status == "failed":
            if baseline is not None:
                if not baseline.collections_parse_ok or not verification.collections_parse_ok:
                    return _provider_evidence_ref(
                        kind=self.kind,
                        status=EvidenceStatus.unsatisfied,
                        summary=(
                            "execute acceptance contract verification failed: "
                            "suite delta is not computable"
                        ),
                        details=details,
                        ctx=ctx,
                        trust_class=TrustClass.evidence,
                        source="gate.json|gate_signals_v*.json + verification/suite_runs.ndjson",
                        provider=type(self).__name__,
                    )
                delta = compute_delta(baseline, verification)
                details["delta"] = delta.to_dict()
                if not delta.newly_failing and not delta.deleted_tests:
                    return _provider_evidence_ref(
                        kind=self.kind,
                        status=EvidenceStatus.satisfied,
                        summary=(
                            "verification suite satisfied the execute acceptance contract "
                            f"for {len(required_checks)} check(s) with no new regressions"
                        ),
                        details=details,
                        ctx=ctx,
                        trust_class=TrustClass.evidence,
                        source="gate.json|gate_signals_v*.json + verification/suite_runs.ndjson",
                        provider=type(self).__name__,
                    )
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=(
                    "execute acceptance contract verification failed: "
                    f"verification suite has {len(verification.failures)} failing test(s)"
                ),
                details=details,
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="gate.json|gate_signals_v*.json + verification/suite_runs.ndjson",
                provider=type(self).__name__,
            )
        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.unknown,
            summary=(
                "execute acceptance contract could not be verified because "
                f"suite evidence is {verification.status}"
            ),
            details=details,
            ctx=ctx,
            trust_class=TrustClass.evidence,
            source="gate.json|gate_signals_v*.json + verification/suite_runs.ndjson",
            provider=type(self).__name__,
        )


class ReviewDispositionProvider:
    """review_disposition — was review a genuine success or a force-proceed?

    Reads ``review.json``. If review force-proceeded at the rework cap
    (review.py:248-252 appends a "Force-proceeding…" issue), record canonical
    ``unsatisfied`` with legacy provenance in details. Absence of review.json
    is ``not_applicable`` (e.g. bare robustness skips review).
    """

    kind = "review_disposition"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        review_path = ctx.plan_dir / "review.json"
        review_artifact = _artifact_ref_for_path(
            review_path,
            root=ctx.plan_dir,
            artifact_type="application/json",
        )
        review = _read_json(review_path)
        if not isinstance(review, dict):
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.not_applicable,
                summary="no review.json (review may have been skipped)",
                details={},
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=review_artifact,
                source="review.json" if review_artifact is not None else None,
                provider=type(self).__name__,
            )

        issues = review.get("issues") or []
        issue_texts = [str(i) for i in issues if isinstance(i, (str, int, float))]
        forced = any(
            "force-proceed" in t.lower() or "max review rework" in t.lower()
            for t in issue_texts
        )
        verdict = review.get("review_verdict")
        details = {
            "review_verdict": verdict,
            "issue_count": len(issue_texts),
            "force_proceeded": forced,
        }
        if forced:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary="review force-proceeded at the rework cap with unresolved issues",
                details={
                    **details,
                    "diagnostics": {
                        "legacy_status": "fail-not-success",
                        "canonical_status": EvidenceStatus.unsatisfied.value,
                    },
                },
                ctx=ctx,
                trust_class=TrustClass.judgment,
                artifact=review_artifact,
                source="review.json",
                provider=type(self).__name__,
            )
        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary="review reported success",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.judgment,
            artifact=review_artifact,
            source="review.json",
            provider=type(self).__name__,
        )


class DeclaredNoopProvider:
    """declared_noop / waiver — does a typed no-op artifact justify a no-op?

    Looks for a typed waiver artifact (``completion/noop.json`` or
    ``completion_noop.json``). If absent, that is simply absence — it does NOT
    fail the run; status = ``not_applicable``. The typed Waiver schema is a
    documented TODO (see SHADOW_TODOS).
    """

    kind = "declared_noop"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        for candidate in (
            ctx.plan_dir / "completion" / "noop.json",
            ctx.plan_dir / "completion_noop.json",
        ):
            data = _read_json(candidate)
            if isinstance(data, dict):
                artifact = _artifact_ref_for_path(
                    candidate,
                    root=ctx.plan_dir,
                    artifact_type="application/json",
                )
                return _provider_evidence_ref(
                    kind=self.kind,
                    status=EvidenceStatus.waived,
                    summary="typed no-op/waiver artifact present",
                    details={
                        "artifact": candidate.name,
                        "reason": data.get("reason") or data.get("reason_code"),
                    },
                    ctx=ctx,
                    trust_class=TrustClass.claim,
                    artifact=artifact,
                    source=artifact.path if artifact is not None else candidate.name,
                    provider=type(self).__name__,
                )
        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.not_applicable,
            summary="no declared no-op/waiver artifact (absence is not a failure)",
            details={},
            ctx=ctx,
            trust_class=TrustClass.claim,
            source="completion/noop.json|completion_noop.json",
            provider=type(self).__name__,
        )


class AcceptanceReceiptProvider:
    """acceptance_receipt — validate the accepted receipt.json is content-address valid.

    Reads ``receipt.json`` (or ``_acceptance/receipt.json``) from the plan
    directory and validates:

    * The receipt is present and well-formed JSON.
    * Its ``snapshot_hash`` points to a content-addressed snapshot that exists
      on disk and whose stored hash matches the receipt's claim.
    * The receipt identity fields (milestone_label, plan_name, milestone_index)
      are internally consistent.
    * The receipt is NOT treated as a grant — it is evidence that a prior
      acceptance boundary committed, not authority to skip re-verification.

    In fail-closed mode a missing, stale, divergent, or tampered receipt
    produces a typed :class:`BlockingPredicateFailure`.
    """

    kind = "acceptance_receipt"

    _RECEIPT_CANDIDATES: tuple[str, ...] = (
        "receipt.json",
        "_acceptance/receipt.json",
    )

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        receipt_path: Path | None = None
        receipt_data: dict[str, Any] | None = None
        for candidate_name in self._RECEIPT_CANDIDATES:
            candidate = ctx.plan_dir / candidate_name
            data = _read_json(candidate)
            if isinstance(data, dict):
                receipt_path = candidate
                receipt_data = data
                break

        if receipt_data is None:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no receipt.json found — acceptance boundary has not committed",
                details={"candidates_checked": list(self._RECEIPT_CANDIDATES)},
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="receipt.json",
                provider=type(self).__name__,
            )

        receipt_artifact = _artifact_ref_for_path(
            receipt_path,
            root=ctx.plan_dir,
            artifact_type="application/json",
        ) if receipt_path is not None else None

        # Validate required receipt fields
        snapshot_hash = receipt_data.get("snapshot_hash")
        transaction_id = receipt_data.get("transaction_id")
        milestone_label = receipt_data.get("milestone_label")
        plan_name = receipt_data.get("plan_name")
        milestone_index = receipt_data.get("milestone_index")

        missing_fields: list[str] = []
        if not isinstance(snapshot_hash, str) or not snapshot_hash.strip():
            missing_fields.append("snapshot_hash")
        if not isinstance(transaction_id, str) or not transaction_id.strip():
            missing_fields.append("transaction_id")
        if not isinstance(milestone_label, str) or not milestone_label.strip():
            missing_fields.append("milestone_label")
        if not isinstance(plan_name, str) or not plan_name.strip():
            missing_fields.append("plan_name")
        if milestone_index is None or not isinstance(milestone_index, (int, float)):
            missing_fields.append("milestone_index")

        if missing_fields:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"receipt.json missing required fields: {', '.join(sorted(missing_fields))}",
                details={
                    "missing_fields": missing_fields,
                    "receipt": receipt_data,
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                artifact=receipt_artifact,
                source="receipt.json",
                provider=type(self).__name__,
            )

        snapshot_hash = str(snapshot_hash).strip()
        transaction_id = str(transaction_id).strip()
        milestone_label = str(milestone_label).strip()
        plan_name = str(plan_name).strip()
        milestone_index = int(milestone_index)

        # Check that the content-addressed snapshot exists and its hash matches.
        from arnold_pipelines.megaplan.orchestration.completion_io import (
            store_acceptance_snapshot,
            load_acceptance_snapshot,
        )

        # Attempt to load the snapshot by its content hash to verify it exists
        # and is untampered (load validates the stored hash against recomputed).
        snapshot = None
        snapshot_load_error: str | None = None
        try:
            snapshot = load_acceptance_snapshot(ctx.plan_dir, snapshot_hash)
        except Exception as exc:
            snapshot_load_error = str(exc)

        if snapshot is None:
            # Use unsatisfied for both missing and tampered snapshots; predicate
            # kind (stale/missing) is classified later by _classify_predicate_kind.
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=(
                    f"receipt snapshot {snapshot_hash[:16]}... not found or tampered"
                    if snapshot_load_error is None
                    else f"receipt snapshot {snapshot_hash[:16]}... load failed: {snapshot_load_error}"
                ),
                details={
                    "snapshot_hash": snapshot_hash,
                    "transaction_id": transaction_id,
                    "load_error": snapshot_load_error,
                    "receipt": receipt_data,
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                artifact=receipt_artifact,
                source="receipt.json",
                provider=type(self).__name__,
            )

        # Snapshot exists and is valid. Cross-check receipt identity against snapshot.
        identity_mismatches: list[str] = []
        if snapshot.milestone_label != milestone_label:
            identity_mismatches.append(
                f"milestone_label: receipt={milestone_label!r} snapshot={snapshot.milestone_label!r}"
            )
        if snapshot.plan_name != plan_name:
            identity_mismatches.append(
                f"plan_name: receipt={plan_name!r} snapshot={snapshot.plan_name!r}"
            )
        if snapshot.milestone_index != milestone_index:
            identity_mismatches.append(
                f"milestone_index: receipt={milestone_index!r} snapshot={snapshot.milestone_index!r}"
            )
        if snapshot.transaction_id != transaction_id:
            identity_mismatches.append(
                f"transaction_id: receipt={transaction_id!r} snapshot={snapshot.transaction_id!r}"
            )

        if identity_mismatches:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"receipt identity does not match snapshot: {'; '.join(identity_mismatches)}",
                details={
                    "snapshot_hash": snapshot_hash,
                    "transaction_id": transaction_id,
                    "identity_mismatches": identity_mismatches,
                    "receipt": receipt_data,
                    "snapshot_milestone_label": snapshot.milestone_label,
                    "snapshot_plan_name": snapshot.plan_name,
                    "snapshot_milestone_index": snapshot.milestone_index,
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                artifact=receipt_artifact,
                source="receipt.json",
                provider=type(self).__name__,
            )

        # Cross-check subject identity consistency (advisory, not blocking on its own).
        advisory_notes: list[str] = []
        if ctx.subject.milestone_label and ctx.subject.milestone_label != milestone_label:
            advisory_notes.append(
                f"subject milestone_label={ctx.subject.milestone_label!r} differs from receipt {milestone_label!r}"
            )
        if ctx.subject.plan_name and ctx.subject.plan_name != plan_name:
            advisory_notes.append(
                f"subject plan_name={ctx.subject.plan_name!r} differs from receipt {plan_name!r}"
            )

        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary=f"acceptance receipt valid for {milestone_label} (snapshot {snapshot_hash[:16]}...)",
            details={
                "snapshot_hash": snapshot_hash,
                "transaction_id": transaction_id,
                "milestone_label": milestone_label,
                "plan_name": plan_name,
                "milestone_index": milestone_index,
                "snapshot_content_hash": snapshot.content_hash,
                "source_commit_ref": snapshot.source_commit_ref,
                "runtime_identity": snapshot.runtime_identity,
                "advisory_notes": advisory_notes,
            },
            ctx=ctx,
            trust_class=TrustClass.evidence,
            artifact=receipt_artifact,
            source="receipt.json",
            provider=type(self).__name__,
        )


class DivergenceProvider:
    """divergence — detect contradictory evidence between claims and on-disk state.

    Checks for content-address mismatches between:
    * Declared artifact hashes in finalize.json vs actual file content.
    * Execution batch claims (files_changed) vs working-tree diff.
    * Acceptance snapshot evidence vs the current plan state.

    Divergence is NOT a ``not_applicable`` skip — when there is nothing to
    compare (no finalize, no batch artifacts) the provider returns ``unknown``
    rather than ``satisfied``, because the absence of comparable evidence is
    itself a signal in fail-closed mode.
    """

    kind = "divergence"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        divergences: list[str] = []
        checks_performed: list[str] = []
        details: dict[str, Any] = {}

        finalize = _read_finalize(ctx.plan_dir)
        finalize_artifact = _artifact_ref_for_path(
            ctx.plan_dir / "finalize.json",
            root=ctx.plan_dir,
            artifact_type="application/json",
        )

        # ── Check 1: declared artifact hashes in finalize vs actual files ──
        if isinstance(finalize, dict):
            declared_files = finalize.get("files_changed")
            if isinstance(declared_files, list) and declared_files:
                checks_performed.append("declared_artifact_hash_check")
                hash_mismatches = self._check_declared_hashes(
                    ctx.project_dir, declared_files
                )
                if hash_mismatches:
                    divergences.extend(hash_mismatches)
                details["declared_artifact_check"] = {
                    "declared_count": len(declared_files),
                    "mismatches": hash_mismatches,
                }

        # ── Check 2: execution batch file claims vs git status ──
        batches = sorted(list_batch_artifacts(ctx.plan_dir))
        if batches:
            checks_performed.append("batch_vs_diff_check")
            batch_files: set[str] = set()
            for batch_path in batches:
                payload = _read_json(batch_path)
                if not isinstance(payload, dict):
                    continue
                fc = payload.get("files_changed")
                if isinstance(fc, list):
                    for item in fc:
                        if isinstance(item, str):
                            batch_files.add(item)
            if batch_files:
                details["batch_claimed_files"] = sorted(batch_files)
                # Check that claimed files actually exist on disk
                missing_claimed: list[str] = []
                for f in sorted(batch_files):
                    fp = ctx.project_dir / f
                    if not fp.exists():
                        missing_claimed.append(f)
                if missing_claimed:
                    divergences.append(
                        f"{len(missing_claimed)} file(s) claimed in batch but missing on disk"
                    )
                    details["missing_claimed_files"] = missing_claimed

        # ── Check 3: acceptance snapshot evidence consistency ──
        # Look for acceptance snapshots and verify their evidence refs point to real artifacts.
        snapshots_dir = ctx.plan_dir / "_acceptance" / "snapshots"
        if snapshots_dir.exists():
            checks_performed.append("acceptance_snapshot_consistency")
            snapshot_divergences = self._check_snapshot_consistency(
                ctx.plan_dir, snapshots_dir
            )
            if snapshot_divergences:
                divergences.extend(snapshot_divergences)
            details["snapshot_consistency"] = {
                "divergences": snapshot_divergences,
            }

        if not checks_performed:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no comparable evidence available for divergence check",
                details={"checks_performed": checks_performed},
                ctx=ctx,
                trust_class=TrustClass.judgment,
                source="finalize.json + execution_batch_*.json + _acceptance/snapshots",
                provider=type(self).__name__,
            )

        if divergences:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"evidence divergence detected: {'; '.join(divergences[:5])}"
                + (f" ... and {len(divergences) - 5} more" if len(divergences) > 5 else ""),
                details={
                    **details,
                    "divergences": divergences,
                    "divergence_count": len(divergences),
                    "checks_performed": checks_performed,
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                artifact=finalize_artifact,
                source="finalize.json + execution_batch_*.json + _acceptance/snapshots",
                provider=type(self).__name__,
            )

        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary=f"no divergence detected across {len(checks_performed)} check(s)",
            details={
                **details,
                "divergences": [],
                "checks_performed": checks_performed,
            },
            ctx=ctx,
            trust_class=TrustClass.evidence,
            artifact=finalize_artifact,
            source="finalize.json + execution_batch_*.json + _acceptance/snapshots",
            provider=type(self).__name__,
        )

    @staticmethod
    def _check_declared_hashes(
        project_dir: Path,
        declared_files: list[Any],
    ) -> list[str]:
        """Check that declared file paths exist on disk and their hashes match."""
        mismatches: list[str] = []
        for entry in declared_files:
            if not isinstance(entry, dict):
                continue
            path_str = entry.get("path") or entry.get("file")
            declared_hash = entry.get("sha256") or entry.get("hash")
            if not isinstance(path_str, str) or not path_str.strip():
                continue
            fp = project_dir / path_str.strip()
            if not fp.is_file():
                if isinstance(declared_hash, str) and declared_hash.strip():
                    mismatches.append(f"{path_str}: file missing (declared hash {declared_hash[:16]}...)")
                continue
            if isinstance(declared_hash, str) and declared_hash.strip():
                try:
                    actual_hash = sha256_file(fp)
                    if actual_hash != declared_hash:
                        mismatches.append(
                            f"{path_str}: hash mismatch declared={declared_hash[:16]}... actual={actual_hash[:16]}..."
                        )
                except OSError:
                    mismatches.append(f"{path_str}: could not read for hash verification")
        return mismatches

    @staticmethod
    def _check_snapshot_consistency(
        plan_dir: Path,
        snapshots_dir: Path,
    ) -> list[str]:
        """Verify that acceptance snapshots reference evidence that is internally consistent."""
        divergences: list[str] = []
        try:
            from arnold_pipelines.megaplan.orchestration.completion_io import (
                load_acceptance_snapshot,
            )

            for hex_prefix_dir in sorted(snapshots_dir.iterdir()):
                if not hex_prefix_dir.is_dir():
                    continue
                for snapshot_file in sorted(hex_prefix_dir.glob("*.json")):
                    try:
                        data = _read_json(snapshot_file)
                        if not isinstance(data, dict):
                            continue
                        stored_hash = data.get("content_hash", "")
                        if not stored_hash:
                            divergences.append(
                                f"snapshot {snapshot_file.name}: missing content_hash"
                            )
                            continue
                        # Verify the snapshot can be loaded (re-hashes on load)
                        snapshot = load_acceptance_snapshot(plan_dir, stored_hash)
                        if snapshot is None:
                            divergences.append(
                                f"snapshot {snapshot_file.name}: failed to load with hash {stored_hash[:16]}..."
                            )
                    except ValueError as exc:
                        divergences.append(
                            f"snapshot {snapshot_file.name}: {exc}"
                        )
                    except Exception:
                        continue  # skip unparseable snapshots
        except Exception:
            pass  # best-effort check
        return divergences


class ManifestFreshnessProvider:
    """manifest_freshness — validate manifest content-address and freshness.

    Checks that:
    * Artifact manifests (execution_batch_*.json, finalize.json) have not been
      tampered with by verifying their content hashes against declared values.
    * Manifest ordering is consistent — batch indices are sequential without gaps
      and timestamps are monotonically non-decreasing.
    * The manifest's declared ``code_hash`` or content identity matches the
      current working-tree state (freshness check).

    In shadow mode stale manifests produce ``unknown``; in fail-closed mode
    they produce typed ``stale`` predicate failures.
    """

    kind = "manifest_freshness"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        details: dict[str, Any] = {}
        issues: list[str] = []

        # ── Batch manifest ordering check ──
        batches = sorted(list_batch_artifacts(ctx.plan_dir))
        batch_artifacts = tuple(
            ref
            for ref in (
                _artifact_ref_for_path(
                    batch_path,
                    root=ctx.plan_dir,
                    artifact_type="application/json",
                )
                for batch_path in batches
            )
            if ref is not None
        )

        if batches:
            ordering_issues = self._check_batch_ordering(batches)
            if ordering_issues:
                issues.extend(ordering_issues)
            details["batch_count"] = len(batches)
            details["batch_ordering_issues"] = ordering_issues

        # ── Finalize manifest integrity ──
        finalize = _read_finalize(ctx.plan_dir)
        finalize_artifact = _artifact_ref_for_path(
            ctx.plan_dir / "finalize.json",
            root=ctx.plan_dir,
            artifact_type="application/json",
        )

        if isinstance(finalize, dict):
            # Check that finalize hashes of batch artifacts match actual files
            batch_integrity_issues = self._check_finalize_batch_integrity(
                ctx.plan_dir, finalize
            )
            if batch_integrity_issues:
                issues.extend(batch_integrity_issues)
            details["finalize_batch_integrity_issues"] = batch_integrity_issues

            # Check freshness: does finalize's declared state match current state?
            freshness_issues = self._check_manifest_freshness(ctx, finalize)
            if freshness_issues:
                issues.extend(freshness_issues)
            details["freshness_issues"] = freshness_issues

        # ── Content-address: verify batch artifacts are internally consistent ──
        ca_issues = self._check_content_addressing(ctx.plan_dir, batches)
        if ca_issues:
            issues.extend(ca_issues)
        details["content_address_issues"] = ca_issues

        if not batches and not isinstance(finalize, dict):
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no manifest artifacts to validate freshness",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                source="execution_batch_*.json + finalize.json",
                provider=type(self).__name__,
            )

        # If we only have an empty/nearly-empty finalize and no batches, that's
        # also insufficient evidence.
        if not batches and isinstance(finalize, dict) and not finalize:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no manifest artifacts to validate freshness",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                source="execution_batch_*.json + finalize.json",
                provider=type(self).__name__,
            )

        if issues:
            # All issues produce unsatisfied EvidenceStatus; the specific predicate
            # kind (stale/out_of_order/divergent) is classified later by
            # _classify_predicate_kind based on the summary text.
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"manifest freshness issues: {'; '.join(issues[:5])}"
                + (f" ... and {len(issues) - 5} more" if len(issues) > 5 else ""),
                details={
                    **details,
                    "issues": issues,
                    "issue_count": len(issues),
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                artifacts=batch_artifacts,
                artifact=finalize_artifact,
                source="execution_batch_*.json + finalize.json",
                provider=type(self).__name__,
            )

        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary="manifest artifacts are fresh and content-address validated",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.evidence,
            artifacts=batch_artifacts,
            artifact=finalize_artifact,
            source="execution_batch_*.json + finalize.json",
            provider=type(self).__name__,
        )

    @staticmethod
    def _check_batch_ordering(batches: list[Path]) -> list[str]:
        """Verify batch indices are sequential without gaps and timestamps monotonic."""
        issues: list[str] = []
        batch_info: list[dict[str, Any]] = []
        for bp in batches:
            data = _read_json(bp)
            if isinstance(data, dict):
                batch_info.append({
                    "path": bp.name,
                    "batch_index": data.get("batch_index") or data.get("index"),
                    "timestamp": data.get("timestamp") or data.get("ts") or data.get("completed_at"),
                })

        if len(batch_info) < 2:
            return issues

        # Check sequential indices
        indices: list[int] = []
        for bi in batch_info:
            idx = bi["batch_index"]
            if isinstance(idx, (int, float)) and not isinstance(idx, bool):
                indices.append(int(idx))
        if indices:
            expected = list(range(min(indices), max(indices) + 1))
            if sorted(indices) != expected:
                missing = sorted(set(expected) - set(indices))
                issues.append(
                    f"non-sequential batch indices: missing {missing} "
                    f"(have {sorted(indices)}, expected {expected})"
                )

        # Check monotonic timestamps
        timestamps: list[str] = []
        for bi in batch_info:
            ts = bi["timestamp"]
            if isinstance(ts, str) and ts.strip():
                timestamps.append(ts.strip())
        if len(timestamps) >= 2:
            for i in range(1, len(timestamps)):
                if timestamps[i] < timestamps[i - 1]:
                    issues.append(
                        f"non-monotonic batch timestamp at index {i}: "
                        f"{timestamps[i-1]} -> {timestamps[i]}"
                    )
                    break  # one violation is enough

        return issues

    @staticmethod
    def _check_finalize_batch_integrity(
        plan_dir: Path, finalize: dict[str, Any]
    ) -> list[str]:
        """Verify that finalize.json's declared batch hashes match actual batch files."""
        issues: list[str] = []
        batch_hashes = finalize.get("batch_hashes") or finalize.get("batch_artifacts")
        if not isinstance(batch_hashes, dict):
            return issues

        for batch_name, declared_hash in batch_hashes.items():
            if not isinstance(declared_hash, str) or not declared_hash.strip():
                continue
            batch_path = plan_dir / batch_name
            if not batch_path.is_file():
                issues.append(
                    f"finalize references batch {batch_name!r} but file is missing"
                )
                continue
            try:
                actual_hash = sha256_file(batch_path)
                if actual_hash != declared_hash:
                    issues.append(
                        f"batch {batch_name!r}: hash mismatch "
                        f"declared={declared_hash[:16]}... actual={actual_hash[:16]}..."
                    )
            except OSError:
                issues.append(f"batch {batch_name!r}: could not read for hash verification")
        return issues

    @staticmethod
    def _check_manifest_freshness(
        ctx: CompletionContext, finalize: dict[str, Any]
    ) -> list[str]:
        """Check that manifest-declared state is not stale relative to current state."""
        issues: list[str] = []
        declared_base_sha = finalize.get("base_sha") or finalize.get("base_ref")
        if isinstance(declared_base_sha, str) and declared_base_sha.strip():
            if ctx.git_base_ref and ctx.git_base_ref != declared_base_sha:
                issues.append(
                    f"finalize base_sha {declared_base_sha[:12]}... does not match "
                    f"current git_base_ref {ctx.git_base_ref[:12]}... (manifest may be stale)"
                )
        return issues

    @staticmethod
    def _check_content_addressing(
        plan_dir: Path, batches: list[Path]
    ) -> list[str]:
        """Verify that batch artifacts are internally content-address consistent."""
        issues: list[str] = []
        for bp in batches:
            data = _read_json(bp)
            if not isinstance(data, dict):
                continue
            declared_hash = data.get("content_hash") or data.get("artifact_hash")
            if isinstance(declared_hash, str) and declared_hash.strip():
                try:
                    actual_hash = sha256_file(bp)
                    if actual_hash != declared_hash:
                        issues.append(
                            f"{bp.name}: content hash mismatch "
                            f"declared={declared_hash[:16]}... actual={actual_hash[:16]}..."
                        )
                except OSError:
                    pass  # best-effort
        return issues


class CommitRuntimeProvider:
    """commit_runtime — validate commit and runtime identity are exact, not mutable aliases.

    Ties completion evidence to exact tested code and runtime identity across
    orchestration and execution binding.  Rejects mutable aliases that could
    make Git or CI state look authoritative when it is not:

    * **Branch names** (``main``, ``feature/xyz``) — not an exact commit.
    * **``HEAD``** and symbolic refs — not a stable identity.
    * **Short SHAs** (< 40 hex chars) — ambiguous, could collide.
    * **PR refs** (``refs/pull/123/head``, ``refs/pull/123/merge``) — mutable.
    * **Stale PR refs** — PR state may have changed since evidence was collected.
    * **Missing or empty** commit ref — unbound evidence.

    In fail-closed mode a mutable, missing, or stale commit ref produces a
    typed ``unbound_evidence`` or ``stale`` predicate failure.

    Also validates that ``runtime_identity`` is a stable, non-empty identifier
    and not a shadow/warning-only placeholder.
    """

    kind = "commit_runtime"

    #: Pattern for a full 40-character lowercase hex SHA.
    _FULL_SHA_RE = __import__("re").compile(r"^[0-9a-f]{40}$")

    #: Known mutable ref patterns that are rejected even if they look like hex.
    _MUTABLE_REF_PREFIXES: tuple[str, ...] = (
        "refs/heads/",
        "refs/pull/",
        "refs/tags/",
        "refs/remotes/",
    )

    _MUTABLE_NAMES: frozenset[str] = frozenset({"HEAD", "ORIG_HEAD", "FETCH_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD"})

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        details: dict[str, Any] = {}
        issues: list[str] = []

        # ── Discover commit/runtime identity from acceptance artifacts ──
        commit_refs: list[tuple[str, str]] = []  # (source_label, ref_value)
        runtime_ids: list[tuple[str, str]] = []  # (source_label, id_value)

        # Check acceptance snapshots
        snapshots_dir = ctx.plan_dir / "_acceptance" / "snapshots"
        if snapshots_dir.exists():
            try:
                from arnold_pipelines.megaplan.orchestration.completion_io import (
                    load_acceptance_snapshot,
                )
                for hex_prefix_dir in sorted(snapshots_dir.iterdir()):
                    if not hex_prefix_dir.is_dir():
                        continue
                    for snapshot_file in sorted(hex_prefix_dir.glob("*.json")):
                        data = _read_json(snapshot_file)
                        if not isinstance(data, dict):
                            continue
                        stored_hash = data.get("content_hash", "")
                        if not stored_hash:
                            continue
                        try:
                            snapshot = load_acceptance_snapshot(ctx.plan_dir, stored_hash)
                            if snapshot is not None:
                                commit_refs.append(
                                    ("snapshot", getattr(snapshot, "source_commit_ref", ""))
                                )
                                runtime_ids.append(
                                    ("snapshot", getattr(snapshot, "runtime_identity", ""))
                                )
                        except Exception:
                            pass
            except Exception:
                pass  # best-effort; can't import means no snapshots to check

        # Check receipts
        for candidate_name in ("receipt.json", "_acceptance/receipt.json"):
            receipt_data = _read_json(ctx.plan_dir / candidate_name)
            if isinstance(receipt_data, dict):
                src_ref = receipt_data.get("source_commit_ref") or receipt_data.get("tested_commit_ref")
                if isinstance(src_ref, str) and src_ref.strip():
                    commit_refs.append(("receipt", src_ref.strip()))
                rt_id = receipt_data.get("runtime_identity") or receipt_data.get("tested_runtime_identity")
                if isinstance(rt_id, str) and rt_id.strip():
                    runtime_ids.append(("receipt", rt_id.strip()))
                break

        # Check finalize.json for commit ref hints
        finalize = _read_finalize(ctx.plan_dir)
        if isinstance(finalize, dict):
            base_sha = finalize.get("base_sha") or finalize.get("base_ref")
            if isinstance(base_sha, str) and base_sha.strip():
                commit_refs.append(("finalize", base_sha.strip()))

        # Check ctx.git_base_ref
        if ctx.git_base_ref:
            commit_refs.append(("context", ctx.git_base_ref))

        # ── Validate commit refs ──
        validated_refs: list[dict[str, Any]] = []
        for source_label, ref in commit_refs:
            validation = self._validate_commit_ref(ref)
            validated_refs.append({
                "source": source_label,
                "ref": ref,
                **validation,
            })
            if not validation["valid"]:
                issues.append(
                    f"{source_label} commit ref {ref[:40]!r}: {validation['reason']}"
                )

        details["commit_refs"] = validated_refs
        details["commit_ref_count"] = len(commit_refs)

        # ── Validate runtime identities ──
        validated_runtimes: list[dict[str, Any]] = []
        for source_label, rid in runtime_ids:
            rt_validation = self._validate_runtime_identity(rid)
            validated_runtimes.append({
                "source": source_label,
                "runtime_identity": rid,
                **rt_validation,
            })
            if not rt_validation["valid"]:
                issues.append(
                    f"{source_label} runtime identity {rid!r}: {rt_validation['reason']}"
                )

        details["runtime_ids"] = validated_runtimes
        details["runtime_id_count"] = len(runtime_ids)

        # ── No evidence at all ──
        if not commit_refs and not runtime_ids:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unknown,
                summary="no commit or runtime identity evidence available to validate",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                source="acceptance snapshots + receipt.json + finalize.json",
                provider=type(self).__name__,
            )

        if issues:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"commit/runtime identity issues: {'; '.join(issues[:5])}"
                + (f" ... and {len(issues) - 5} more" if len(issues) > 5 else ""),
                details={
                    **details,
                    "issues": issues,
                    "issue_count": len(issues),
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="acceptance snapshots + receipt.json + finalize.json",
                provider=type(self).__name__,
            )

        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary=f"commit and runtime identity validated ({len(commit_refs)} commit ref(s), {len(runtime_ids)} runtime id(s))",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.evidence,
            source="acceptance snapshots + receipt.json + finalize.json",
            provider=type(self).__name__,
        )

    @classmethod
    def _validate_commit_ref(cls, ref: str) -> dict[str, Any]:
        """Validate a single commit ref, returning ``{valid, reason, kind}``."""
        ref = ref.strip() if isinstance(ref, str) else ""

        if not ref:
            return {"valid": False, "reason": "empty commit ref", "kind": "missing"}

        # Reject known mutable names
        if ref in cls._MUTABLE_NAMES:
            return {"valid": False, "reason": f"mutable symbolic ref {ref!r}", "kind": "mutable_alias"}

        # Reject refs/ paths (branch, tag, PR, remote refs)
        for prefix in cls._MUTABLE_REF_PREFIXES:
            if ref.startswith(prefix):
                return {"valid": False, "reason": f"mutable ref path {ref!r}", "kind": "mutable_alias"}

        # Reject branch-like names (contain '/' but aren't full SHAs)
        if "/" in ref and not cls._FULL_SHA_RE.match(ref):
            return {"valid": False, "reason": f"branch-like ref {ref!r} is not a full commit SHA", "kind": "mutable_alias"}

        # Must be a full 40-char hex SHA
        if not cls._FULL_SHA_RE.match(ref):
            if len(ref) < 40 and all(c in "0123456789abcdef" for c in ref.lower()):
                return {"valid": False, "reason": f"short SHA {ref!r} ({len(ref)} chars, need 40)", "kind": "short_sha"}
            return {"valid": False, "reason": f"not a valid full commit SHA: {ref[:40]!r}", "kind": "invalid_format"}

        return {"valid": True, "reason": "valid full commit SHA", "kind": "full_sha"}

    @classmethod
    def _validate_runtime_identity(cls, rid: str) -> dict[str, Any]:
        """Validate a runtime identity, returning ``{valid, reason, kind}``."""
        rid = rid.strip() if isinstance(rid, str) else ""

        if not rid:
            return {"valid": False, "reason": "empty runtime identity", "kind": "missing"}

        # Reject shadow/warning-only placeholders
        shadow_placeholders = {"shadow", "warning", "warn", "unknown", "none", "placeholder", "advisory-only"}
        if rid.lower() in shadow_placeholders:
            return {"valid": False, "reason": f"shadow/warning placeholder runtime identity {rid!r}", "kind": "shadow_placeholder"}

        # Reject HEAD-like mutable aliases
        if rid.strip().upper() in cls._MUTABLE_NAMES:
            return {"valid": False, "reason": f"mutable runtime identity {rid!r} (symbolic ref)", "kind": "mutable_alias"}

        # Reject ref paths in runtime identity
        for prefix in cls._MUTABLE_REF_PREFIXES:
            if rid.startswith(prefix):
                return {"valid": False, "reason": f"mutable ref path in runtime identity {rid!r}", "kind": "mutable_alias"}

        return {"valid": True, "reason": "valid runtime identity", "kind": "stable"}


class AttestationProvider:
    """attestation — validate attestation evidence is bound to exact commit/runtime identity.

    Attestations are claims that a specific artifact or outcome was observed.
    This provider validates that:

    * Attestation evidence (if present) references exact commit SHAs, not
      mutable aliases (branch names, HEAD, PR refs).
    * Attestations are not **shadow receipts** — receipts that lack a valid
      backing acceptance snapshot or only have warning-mode evidence.
    * Attestation evidence is not **warning-only** — it must be backed by
      authoritative evidence, not advisory signals.
    * Attestations cross-reference correctly with the acceptance snapshot
      evidence when both are present.

    Shadow receipts and warning-only evidence produce ``unsatisfied`` verdicts
    because they are non-authoritative claims that should not gate a
    transition in fail-closed mode.
    """

    kind = "attestation"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        details: dict[str, Any] = {}
        issues: list[str] = []

        # ── Discover attestation artifacts ──
        attestation_paths = self._find_attestation_files(ctx.plan_dir)
        details["attestation_file_count"] = len(attestation_paths)

        if attestation_paths:
            for ap in attestation_paths:
                file_issues = self._validate_attestation_file(ctx.plan_dir, ap)
                if file_issues:
                    issues.extend(file_issues)
            details["attestation_files"] = [
                str(ap.relative_to(ctx.plan_dir)) if ap.is_relative_to(ctx.plan_dir) else str(ap)
                for ap in attestation_paths
            ]
            details["attestation_issues"] = issues

        # ── Check for shadow receipts ──
        shadow_receipt_checks = self._check_shadow_receipts(ctx.plan_dir)
        if shadow_receipt_checks:
            issues.extend(shadow_receipt_checks)
        details["shadow_receipt_checks"] = shadow_receipt_checks

        # ── Check for warning-only evidence ──
        warning_only_checks = self._check_warning_only_evidence(ctx.plan_dir)
        if warning_only_checks:
            issues.extend(warning_only_checks)
        details["warning_only_checks"] = warning_only_checks

        if not attestation_paths and not shadow_receipt_checks and not warning_only_checks:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.not_applicable,
                summary="no attestation evidence to validate",
                details=details,
                ctx=ctx,
                trust_class=TrustClass.judgment,
                source="attestation files + receipt.json + _acceptance/",
                provider=type(self).__name__,
            )

        if issues:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"attestation issues: {'; '.join(issues[:5])}"
                + (f" ... and {len(issues) - 5} more" if len(issues) > 5 else ""),
                details={
                    **details,
                    "issues": issues,
                    "issue_count": len(issues),
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source="attestation files + receipt.json + _acceptance/",
                provider=type(self).__name__,
            )

        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary="attestation evidence validated",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.evidence,
            source="attestation files + receipt.json + _acceptance/",
            provider=type(self).__name__,
        )

    @staticmethod
    def _find_attestation_files(plan_dir: Path) -> list[Path]:
        """Find attestation-related files in the plan directory."""
        paths: list[Path] = []
        # Look for explicit attestation files
        candidates = [
            plan_dir / "attestation.json",
            plan_dir / "_acceptance" / "attestation.json",
        ]
        for candidate in candidates:
            if candidate.is_file():
                paths.append(candidate)

        # Also check for boundary receipt files
        boundary_dir = plan_dir / "boundary_receipts"
        if boundary_dir.is_dir():
            try:
                for item in sorted(boundary_dir.iterdir()):
                    if item.is_file() and item.suffix == ".json":
                        paths.append(item)
            except OSError:
                pass

        return paths

    @staticmethod
    def _validate_attestation_file(plan_dir: Path, attestation_path: Path) -> list[str]:
        """Validate a single attestation file for mutable aliases and shadow evidence."""
        issues: list[str] = []
        data = _read_json(attestation_path)
        if not isinstance(data, dict):
            return issues

        ref = data.get("commit_ref") or data.get("source_commit_ref") or data.get("sha") or data.get("tested_commit_ref")
        if isinstance(ref, str) and ref.strip():
            validation = CommitRuntimeProvider._validate_commit_ref(ref)
            if not validation["valid"]:
                issues.append(
                    f"attestation {attestation_path.name}: commit ref {ref[:40]!r} — {validation['reason']}"
                )

        rt_id = data.get("runtime_identity") or data.get("tested_runtime_identity")
        if isinstance(rt_id, str) and rt_id.strip():
            rt_validation = CommitRuntimeProvider._validate_runtime_identity(rt_id)
            if not rt_validation["valid"]:
                issues.append(
                    f"attestation {attestation_path.name}: runtime identity {rt_id!r} — {rt_validation['reason']}"
                )

        # Check for warning-only mode marker
        mode = data.get("mode") or data.get("contract_mode")
        if isinstance(mode, str) and mode.strip().lower() in {"shadow", "warn", "warning"}:
            issues.append(
                f"attestation {attestation_path.name}: non-authoritative mode {mode!r} "
                f"(shadow/warn evidence is not sufficient for fail-closed acceptance)"
            )

        return issues

    @staticmethod
    def _check_shadow_receipts(plan_dir: Path) -> list[str]:
        """Check for shadow receipts — receipts without valid snapshot backing."""
        issues: list[str] = []
        for candidate_name in ("receipt.json", "_acceptance/receipt.json"):
            receipt_data = _read_json(plan_dir / candidate_name)
            if not isinstance(receipt_data, dict):
                continue

            snapshot_hash = receipt_data.get("snapshot_hash")
            if not isinstance(snapshot_hash, str) or not snapshot_hash.strip():
                issues.append(
                    f"{candidate_name}: shadow receipt — missing snapshot_hash "
                    f"(no content-addressed snapshot backing)"
                )
                continue

            # Verify the snapshot actually exists
            try:
                from arnold_pipelines.megaplan.orchestration.completion_io import (
                    load_acceptance_snapshot,
                )
                snapshot = load_acceptance_snapshot(plan_dir, str(snapshot_hash).strip())
                if snapshot is None:
                    issues.append(
                        f"{candidate_name}: shadow receipt — snapshot {str(snapshot_hash)[:16]}... "
                        f"not found (receipt points to non-existent evidence)"
                    )
            except Exception:
                issues.append(
                    f"{candidate_name}: shadow receipt — could not verify snapshot "
                    f"{str(snapshot_hash)[:16]}..."
                )

            # Check that the receipt has an accepted verdict backing
            accepted = receipt_data.get("accepted")
            if accepted is False:
                issues.append(
                    f"{candidate_name}: shadow receipt — receipt marked as not accepted "
                    f"(cannot use unaccepted receipt as attestation)"
                )
            break  # only check the first found receipt
        return issues

    @staticmethod
    def _check_warning_only_evidence(plan_dir: Path) -> list[str]:
        """Check for warning-only evidence that should not gate transitions."""
        issues: list[str] = []
        # Check if the completion verdict was produced in shadow/warn mode
        verdict_path = plan_dir / "completion_verdict.json"
        verdict = _read_json(verdict_path)
        if isinstance(verdict, dict):
            mode = verdict.get("mode", "")
            if mode in {"shadow", "warn", "off"}:
                accepted = verdict.get("accepted", False)
                if accepted:
                    issues.append(
                        f"completion_verdict.json: accepted in {mode!r} mode — "
                        f"warning-only evidence should not gate fail-closed transitions"
                    )

        # Check for shadow-mode gate signals
        gate_path = plan_dir / "gate.json"
        gate = _read_json(gate_path)
        if isinstance(gate, dict):
            signals = gate.get("signals", {})
            if isinstance(signals, dict):
                mode_signal = signals.get("contract_mode") or signals.get("completion_contract_mode")
                if isinstance(mode_signal, str) and mode_signal.lower() in {"shadow", "warn", "warning"}:
                    issues.append(
                        f"gate.json: contract mode is {mode_signal!r} — "
                        f"non-authoritative (shadow/warn) evidence is not sufficient"
                    )

        return issues


class RetirementOrderProvider:
    """retirement_order — validate .retired marker ordering and timestamps.

    Checks that:
    * ``.retired`` marker files (if present) carry valid timestamps and
      milestone labels that match the chain spec ordering.
    * Retirement markers are not **premature** — a milestone cannot be retired
      before all its predecessor evidence predicates are satisfied.
    * The canonical verification output referenced by a retirement marker is
      consistent with the acceptance snapshot evidence.

    Retirement markers are **evidence of prior completion**, NOT authority to
    skip re-verification.  A retirement marker whose timestamp predates the
    required evidence predicates produces a typed ``out_of_order`` predicate
    failure in fail-closed mode.
    """

    kind = "retirement_order"

    _RETIRED_SUFFIX = ".retired"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        details: dict[str, Any] = {}
        issues: list[str] = []

        # ── Discover .retired markers ──
        retired_markers = self._find_retired_markers(ctx.plan_dir)
        if not retired_markers:
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.not_applicable,
                summary="no .retired markers present — retirement check not applicable",
                details={},
                ctx=ctx,
                trust_class=TrustClass.judgment,
                source=".retired markers",
                provider=type(self).__name__,
            )

        details["retired_marker_count"] = len(retired_markers)
        details["retired_markers"] = [
            {
                "path": str(m["path"].relative_to(ctx.plan_dir))
                if m.get("path") else None,
                "milestone_label": m.get("milestone_label"),
                "timestamp": m.get("timestamp"),
            }
            for m in retired_markers
        ]

        # ── Check 1: marker ordering is consistent with chain spec ──
        ordering_issues = self._check_retirement_ordering(
            retired_markers, ctx.state
        )
        if ordering_issues:
            issues.extend(ordering_issues)
        details["ordering_issues"] = ordering_issues

        # ── Check 2: no premature retirement (all predecessor evidence must be present) ──
        premature_issues = self._check_premature_retirement(
            ctx.plan_dir, retired_markers
        )
        if premature_issues:
            issues.extend(premature_issues)
        details["premature_issues"] = premature_issues

        # ── Check 3: canonical verification output consistency ──
        verification_issues = self._check_verification_consistency(
            ctx.plan_dir, retired_markers
        )
        if verification_issues:
            issues.extend(verification_issues)
        details["verification_issues"] = verification_issues

        if issues:
            # All issues produce unsatisfied EvidenceStatus; the specific predicate
            # kind (out_of_order/divergent) is classified later by
            # _classify_predicate_kind based on the summary text.
            return _provider_evidence_ref(
                kind=self.kind,
                status=EvidenceStatus.unsatisfied,
                summary=f"retirement order issues: {'; '.join(issues[:5])}"
                + (f" ... and {len(issues) - 5} more" if len(issues) > 5 else ""),
                details={
                    **details,
                    "issues": issues,
                    "issue_count": len(issues),
                },
                ctx=ctx,
                trust_class=TrustClass.evidence,
                source=".retired markers",
                provider=type(self).__name__,
            )

        return _provider_evidence_ref(
            kind=self.kind,
            status=EvidenceStatus.satisfied,
            summary=f"{len(retired_markers)} retirement marker(s) in valid order",
            details=details,
            ctx=ctx,
            trust_class=TrustClass.evidence,
            source=".retired markers",
            provider=type(self).__name__,
        )

    @classmethod
    def _find_retired_markers(cls, plan_dir: Path) -> list[dict[str, Any]]:
        """Find all .retired marker files and parse their content."""
        markers: list[dict[str, Any]] = []
        # Search in plan_dir and direct subdirectories
        search_roots = [plan_dir]
        acceptance_dir = plan_dir / "_acceptance"
        if acceptance_dir.is_dir():
            search_roots.append(acceptance_dir)

        for root in search_roots:
            try:
                for item in sorted(root.iterdir()):
                    if item.is_file() and item.name.endswith(cls._RETIRED_SUFFIX):
                        data = _read_json(item)
                        marker: dict[str, Any] = {
                            "path": item,
                            "filename": item.name,
                        }
                        if isinstance(data, dict):
                            marker["milestone_label"] = data.get("milestone_label") or data.get("label")
                            marker["timestamp"] = data.get("timestamp") or data.get("retired_at") or data.get("ts")
                            marker["canonical_verification_ref"] = (
                                data.get("canonical_verification_ref")
                                or data.get("verification_ref")
                            )
                            marker["transaction_id"] = data.get("transaction_id")
                        markers.append(marker)
            except OSError:
                continue

        # Sort by timestamp if available, else by filename
        def _sort_key(m: dict[str, Any]) -> str:
            ts = m.get("timestamp")
            if isinstance(ts, str):
                return ts
            return m.get("filename", "")

        markers.sort(key=_sort_key)
        return markers

    @staticmethod
    def _check_retirement_ordering(
        markers: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> list[str]:
        """Check that retirement markers follow the chain spec milestone order."""
        issues: list[str] = []
        # Get the milestone order from chain state if available
        milestones = state.get("milestones") or state.get("chain_milestones")
        if isinstance(milestones, list) and len(milestones) >= 2:
            milestone_order: dict[str, int] = {}
            for idx, ms in enumerate(milestones):
                label = ms.get("label") if isinstance(ms, dict) else str(ms)
                milestone_order[label] = idx

            if len(milestone_order) >= 2:
                last_idx = -1
                for marker in markers:
                    label = marker.get("milestone_label")
                    if isinstance(label, str) and label in milestone_order:
                        idx = milestone_order[label]
                        if idx < last_idx:
                            issues.append(
                                f"retirement order violation: {label!r} (index {idx}) "
                                f"appears after index {last_idx}"
                            )
                        last_idx = max(last_idx, idx)

        # Check timestamp monotonicity
        timestamps: list[str] = []
        for marker in markers:
            ts = marker.get("timestamp")
            if isinstance(ts, str) and ts.strip():
                timestamps.append(ts.strip())
        if len(timestamps) >= 2:
            for i in range(1, len(timestamps)):
                if timestamps[i] < timestamps[i - 1]:
                    issues.append(
                        f"retirement timestamp regression: "
                        f"{timestamps[i-1]} -> {timestamps[i]}"
                    )
                    break

        return issues

    @staticmethod
    def _check_premature_retirement(
        plan_dir: Path,
        markers: list[dict[str, Any]],
    ) -> list[str]:
        """Check that retirement markers are not premature — required evidence must exist."""
        issues: list[str] = []
        for marker in markers:
            label = marker.get("milestone_label")
            if not isinstance(label, str):
                continue
            # Check that a completion verdict exists for this milestone
            verdict_path = plan_dir / "completion_verdict.json"
            verdict = _read_json(verdict_path)
            if isinstance(verdict, dict):
                subject = verdict.get("subject", {})
                if isinstance(subject, dict):
                    v_label = subject.get("milestone_label")
                    v_accepted = verdict.get("accepted", False)
                    if v_label == label and not v_accepted:
                        issues.append(
                            f"premature retirement: {label!r} has a retirement marker "
                            f"but completion verdict is not accepted"
                        )

            # Check that acceptance receipt exists
            receipt_found = False
            for candidate_name in ("receipt.json", "_acceptance/receipt.json"):
                receipt_data = _read_json(plan_dir / candidate_name)
                if isinstance(receipt_data, dict):
                    if receipt_data.get("milestone_label") == label:
                        receipt_found = True
                        break
            if not receipt_found:
                # Not necessarily an issue if retirement happened via a different path,
                # but note it for audit.
                pass

        return issues

    @staticmethod
    def _check_verification_consistency(
        plan_dir: Path,
        markers: list[dict[str, Any]],
    ) -> list[str]:
        """Check that retirement markers' canonical verification refs are consistent."""
        issues: list[str] = []
        for marker in markers:
            verification_ref = marker.get("canonical_verification_ref")
            if not isinstance(verification_ref, str) or not verification_ref.strip():
                continue

            # Check that the referenced verification output exists
            ref_path = plan_dir / verification_ref
            if not ref_path.exists():
                # Try relative to _acceptance
                ref_path = plan_dir / "_acceptance" / verification_ref
            if not ref_path.exists():
                issues.append(
                    f"retirement marker for {marker.get('milestone_label', 'unknown')!r} "
                    f"references canonical verification {verification_ref!r} which does not exist"
                )
        return issues


# The shared, phase-agnostic provider set. Reused verbatim across plan +
# milestone subjects (the generalization the design calls for).
DEFAULT_PROVIDERS: tuple[EvidenceProvider, ...] = (
    PhaseCoverageProvider(),
    LandedDiffProvider(),
    WorkerDidWorkProvider(),
    GreenSuiteProvider(),
    ExecuteAcceptanceContractProvider(),
    ReviewDispositionProvider(),
    DeclaredNoopProvider(),
    AcceptanceReceiptProvider(),
    DivergenceProvider(),
    ManifestFreshnessProvider(),
    RetirementOrderProvider(),
    CommitRuntimeProvider(),
    AttestationProvider(),
)


# ---------------------------------------------------------------------------
# Verdict computation
# ---------------------------------------------------------------------------

#: Statuses that are always blocking in any mode.
_ALWAYS_BLOCKING_STATUSES: frozenset[EvidenceStatus] = frozenset({EvidenceStatus.unsatisfied})

#: Additional statuses that block only in fail-closed (atomic/enforce) mode.
_FAIL_CLOSED_BLOCKING_STATUSES: frozenset[EvidenceStatus] = frozenset({EvidenceStatus.unknown})


def _blocking_statuses_for_mode(mode: str) -> frozenset[EvidenceStatus]:
    """Return the set of :class:`EvidenceStatus` values that block for *mode*.

    In shadow/warn/off mode only ``unsatisfied`` blocks.  In fail-closed
    (atomic/enforce) modes ``unknown`` also blocks so that providers returning
    indeterminate results refuse the transition.
    """
    if is_fail_closed_mode(mode):
        return _ALWAYS_BLOCKING_STATUSES | _FAIL_CLOSED_BLOCKING_STATUSES
    return _ALWAYS_BLOCKING_STATUSES


def compute_verdict(
    *,
    plan_dir: Path,
    project_dir: Path,
    state: dict[str, Any],
    subject: CompletionSubject,
    mode: str = DEFAULT_CONTRACT_MODE,
    providers: tuple[EvidenceProvider, ...] = DEFAULT_PROVIDERS,
    git_base_ref: str | None = None,
) -> CompletionVerdict:
    """Compute a :class:`CompletionVerdict` from objective evidence.

    Mode-aware behaviour:

    * **shadow / warn / off** (fail-open): each provider is individually
      wrapped so one provider bug degrades to ``unknown`` rather than aborting
      the verdict.  Only ``unsatisfied`` evidence blocks; ``unknown`` is
      non-blocking.  ``predicate_failures`` is empty — all failures are legacy
      strings.

    * **atomic / enforce** (fail-closed): ``unknown`` evidence and provider
      crashes also block the transition, and every blocking condition produces a
      typed :class:`BlockingPredicateFailure` in the verdict.

    A ``declared_noop`` ``satisfied`` or ``waived`` ref acts as a waiver: it
    downgrades a ``landed_diff``/``worker_did_work`` blocking status to
    non-blocking, so an honestly-declared no-op passes while silent abandonment
    still fails.
    """
    mode = normalize_contract_mode(mode)
    fail_closed = is_fail_closed_mode(mode)
    blocking_statuses = _blocking_statuses_for_mode(mode)
    refs: list[EvidenceRef] = []
    providers_invoked: list[str] = []
    # Track which evidence kinds had a provider crash so we can emit typed
    # predicate failures even when shadow mode would silently swallow them.
    crashed_kinds: dict[str, str] = {}  # kind -> exception message
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=subject,
        git_base_ref=git_base_ref,
    )
    for provider in providers:
        kind = getattr(provider, "kind", "unknown")
        providers_invoked.append(kind)
        try:
            refs.append(provider.collect(ctx))
        except Exception as exc:  # fail-open per provider in shadow; tracked for fail-closed
            crash_msg = f"provider crashed: {exc}"
            crashed_kinds[kind] = crash_msg
            refs.append(
                EvidenceRef(
                    kind,
                    EvidenceStatus.unknown,
                    crash_msg,
                    {},
                )
            )

    has_waiver = any(
        r.kind == "declared_noop"
        and r.status in {EvidenceStatus.satisfied, EvidenceStatus.waived}
        for r in refs
    )
    waivable = {"landed_diff", "worker_did_work"}

    failures: list[str] = []
    predicate_failures: list[BlockingPredicateFailure] = []

    for ref in refs:
        if ref.status not in blocking_statuses:
            continue
        if has_waiver and ref.kind in waivable:
            continue  # honest declared no-op excuses missing diff/activity

        # Legacy string failure (always present for backward compatibility)
        failure_msg = f"{ref.kind}: {ref.summary}"
        failures.append(failure_msg)

        # Typed predicate failure — only in fail-closed mode
        if fail_closed:
            predicate_kind = _classify_predicate_kind(ref)
            if predicate_kind is not None:
                ref_details = ref.details if isinstance(ref.details, dict) else {}
                predicate_failures.append(
                    BlockingPredicateFailure(
                        kind=predicate_kind,
                        evidence_kind=ref.kind,
                        summary=ref.summary,
                        details=dict(ref_details),
                    )
                )

    # In fail-closed mode, provider crashes always produce typed predicate
    # failures even when the crash evidence ref wasn't caught by the
    # blocking-statuses loop (e.g. when crash evidence was produced as
    # unknown but we want an explicit provider_crash predicate).
    if fail_closed:
        for kind, crash_msg in crashed_kinds.items():
            # Avoid duplicates: only add if not already covered
            already = any(
                pf.evidence_kind == kind and pf.kind == PREDICATE_KIND_PROVIDER_CRASH
                for pf in predicate_failures
            )
            if not already:
                predicate_failures.append(
                    BlockingPredicateFailure(
                        kind=PREDICATE_KIND_PROVIDER_CRASH,
                        evidence_kind=kind,
                        summary=crash_msg,
                        details={},
                    )
                )
                # Also ensure a legacy string failure exists
                crash_failure = f"{kind}: {crash_msg}"
                if crash_failure not in failures:
                    failures.append(crash_failure)

    # --- telemetry counts (purely informational, no control-flow impact) ---
    legacy_count = 0
    unknown_count = 0
    for ref in refs:
        if ref.status == EvidenceStatus.unknown:
            unknown_count += 1
        details = ref.details if isinstance(ref.details, dict) else {}
        diag = details.get("diagnostics")
        if isinstance(diag, dict) and "legacy_status" in diag:
            legacy_count += 1

    # would_block_reasons: mirror failures (reasons that would block in enforce)
    would_block_reasons = tuple(failures)

    return CompletionVerdict(
        mode=mode,
        subject=subject,
        evidence=tuple(refs),
        accepted=not failures,
        failures=tuple(failures),
        providers_used=tuple(providers_invoked),
        legacy_evidence_count=legacy_count,
        unknown_evidence_count=unknown_count,
        would_block_reasons=would_block_reasons,
        predicate_failures=tuple(predicate_failures),
    )
