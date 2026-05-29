"""Completion-verification contract — SHADOW-MODE foundation.

A terminal "done" state is a *claim* the plan asserts; this module computes a
typed :class:`CompletionVerdict` from **objective evidence** (git, on-disk
artifacts, cached suite results) so a future "enforce" mode can refuse the
transition when the evidence contradicts the claim.

**Current status: shadow only.** Nothing here blocks a transition, runs the
test suite, or changes control flow. The drivers compute + persist + log a
verdict and discard the result. Every code path is fail-open: callers wrap the
top-level entry point (:func:`compute_verdict`) in try/except and swallow
errors. The design (per ``briefs/hardening-epic/analysis/deeper``) composes
existing helpers rather than re-implementing evidence collection:

- ``phase_coverage``   → ``PhaseResult`` + ``_latest_execution_batch_all_tasks_done``
- ``landed_diff``      → ``execution_evidence.validate_execution_evidence``
- ``worker_did_work``  → delegate ``tool_trace``/``api_calls`` + ``execution_batch_*.json``
- ``green_suite``      → cached finalize baseline only (NEVER runs the suite in shadow)
- ``review_disposition`` → ``review.json`` (detects rework-cap force-proceed)
- ``declared_noop``    → typed waiver artifact if present (absence is not a failure)

See module-level ``SHADOW_TODOS`` for the explicit list of follow-ups deferred
to the warn/enforce rollout.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger("megaplan.orchestration.completion_contract")


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
    "green_suite: add an authoritative post-execute suite run that writes "
    "verification/suite_run.json {head_sha, command, exit, failures, ran_at} "
    "and a freshness cache (reuse iff baseline_head_sha == HEAD). Shadow only "
    "reads an already-captured baseline; it NEVER runs the ~6.5min suite.",
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

VALID_CONTRACT_MODES: frozenset[str] = frozenset(
    {CONTRACT_MODE_OFF, CONTRACT_MODE_SHADOW, CONTRACT_MODE_WARN, CONTRACT_MODE_ENFORCE}
)

DEFAULT_CONTRACT_MODE = CONTRACT_MODE_SHADOW


def normalize_contract_mode(value: Any) -> str:
    """Coerce *value* to a valid contract mode, defaulting to shadow."""
    if isinstance(value, str) and value in VALID_CONTRACT_MODES:
        return value
    return DEFAULT_CONTRACT_MODE


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class EvidenceStatus(str, Enum):
    """Status of one evidence class for a subject.

    ``unsatisfied`` is the only status that (in a future enforce mode) would
    deny a transition. ``unknown`` is for "couldn't evaluate" (e.g. signal
    unavailable) and must NEVER be treated as a failure — we mark unknown
    rather than guess (per B-impl-reuse).
    """

    satisfied = "satisfied"
    unsatisfied = "unsatisfied"
    not_applicable = "not_applicable"
    not_evaluated = "not_evaluated"
    unknown = "unknown"
    # review-specific: review reported success but only via a force-proceed at
    # the rework cap — informational in shadow.
    fail_not_success = "fail-not-success"


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


@dataclass(frozen=True)
class EvidenceRef:
    """One evidence class's observation for a subject."""

    kind: str
    status: EvidenceStatus
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status.value,
            "summary": self.summary,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvidenceRef":
        raw_status = d.get("status", EvidenceStatus.unknown.value)
        try:
            status = EvidenceStatus(raw_status)
        except ValueError:
            status = EvidenceStatus.unknown
        details = d.get("details")
        return cls(
            kind=str(d.get("kind", "?")),
            status=status,
            summary=str(d.get("summary", "")),
            details=dict(details) if isinstance(details, dict) else {},
        )


@dataclass(frozen=True)
class CompletionVerdict:
    """The computed verdict for a subject's terminal transition.

    ``accepted`` is True iff no evidence is ``unsatisfied`` (review
    ``fail-not-success`` is treated as a soft failure that flips ``accepted``
    to False so the verdict surfaces the force-proceed, but in shadow it does
    not affect control flow). ``would_block`` mirrors what an enforce mode
    would do; in shadow it is purely informational.
    """

    mode: str
    subject: CompletionSubject
    evidence: tuple[EvidenceRef, ...]
    accepted: bool
    failures: tuple[str, ...] = ()

    @property
    def would_block(self) -> bool:
        return not self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "subject": self.subject.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "accepted": self.accepted,
            "failures": list(self.failures),
        }

    def one_line(self) -> str:
        verdict = "accepted" if self.accepted else "blocked-would-be"
        fails = ",".join(self.failures) if self.failures else "none"
        return (
            f"completion verdict ({self.mode}): {verdict} "
            f"subject={self.subject.kind}:{self.subject.name} failures=[{fails}]"
        )


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
    git_base_ref: str | None = None  # TODO(enforce): per-milestone base SHA


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
        from megaplan.chain import _latest_execution_batch_all_tasks_done
        from megaplan.orchestration.phase_result import read_phase_result

        details: dict[str, Any] = {}
        phase_result = read_phase_result(ctx.plan_dir)
        if phase_result is not None:
            details["phase"] = phase_result.phase
            details["exit_kind"] = phase_result.exit_kind

        try:
            all_done, reason = _latest_execution_batch_all_tasks_done(ctx.plan_dir)
        except Exception as exc:  # fail-soft → unknown, never crash
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unknown,
                f"could not evaluate batch coverage: {exc}",
                details,
            )

        details["reason"] = reason
        if all_done:
            return EvidenceRef(
                self.kind, EvidenceStatus.satisfied, "all batch tasks done", details
            )
        if "no execution_batch" in reason:
            # No execute artifact at all (e.g. prose/plan-only) → can't judge.
            return EvidenceRef(self.kind, EvidenceStatus.unknown, reason, details)
        return EvidenceRef(self.kind, EvidenceStatus.unsatisfied, reason, details)


class LandedDiffProvider:
    """landed_diff — is there a real, claim-consistent diff on disk?

    Reuses ``validate_execution_evidence`` wholesale. Its hollow-done +
    phantom-claim checks already catch the "abandoned after planning, zero
    diff" case. NOTE (per B-impl-reuse): it reads the **working tree**
    (`git status`), NOT base..HEAD. Acceptable for shadow; see SHADOW_TODOS
    for the per-milestone base-ref follow-up.
    """

    kind = "landed_diff"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        from megaplan._core import is_prose_mode
        from megaplan.orchestration.execution_evidence import (
            validate_execution_evidence,
        )

        finalize = _read_finalize(ctx.plan_dir)
        if not finalize:
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unknown,
                "no finalize.json to evaluate landed diff",
                {},
            )

        try:
            result = validate_execution_evidence(
                finalize, ctx.project_dir, state=ctx.state
            )
        except Exception as exc:
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unknown,
                f"could not evaluate landed diff: {exc}",
                {},
            )

        findings = result.get("findings") or []
        files_in_diff = result.get("files_in_diff") or []
        details = {
            "findings": findings,
            "files_in_diff": files_in_diff,
            "files_claimed": result.get("files_claimed") or [],
            "skipped": bool(result.get("skipped")),
            "skip_reason": result.get("reason") or "",
            # TODO(enforce): replace working-tree status with base..HEAD diff.
            "diff_source": "working_tree_git_status",
        }

        if result.get("skipped"):
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unknown,
                f"evidence check skipped: {result.get('reason')}",
                details,
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
        real_findings = [f for f in findings if not str(f).startswith(_advisory_prefix)]
        details["advisory_findings"] = [
            f for f in findings if str(f).startswith(_advisory_prefix)
        ]

        # Empty diff in code mode == abandonment signal (unless a waiver exists,
        # which the driver folds in separately). Prose mode tracks sections.
        if real_findings:
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unsatisfied,
                "execution evidence findings: " + "; ".join(str(f) for f in real_findings),
                details,
            )
        if not prose and not files_in_diff:
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unsatisfied,
                "no files in working-tree diff (possible abandonment / zero-diff)",
                details,
            )
        return EvidenceRef(
            self.kind, EvidenceStatus.satisfied, "diff present and claim-consistent", details
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
        batches = sorted(ctx.plan_dir.glob("execution_batch_*.json"))
        if not batches:
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unknown,
                "no execution_batch_*.json to assess worker activity",
                {},
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
            # TODO(enforce): incorporate delegate tool_trace / api_calls count.
            "activity_source": "execution_batch_records",
        }
        if files_changed or commands_run or sections_written:
            return EvidenceRef(
                self.kind, EvidenceStatus.satisfied, "worker activity present", details
            )
        return EvidenceRef(
            self.kind,
            EvidenceStatus.unsatisfied,
            "no files changed, commands run, or sections written across any batch",
            details,
        )


class GreenSuiteProvider:
    """green_suite — SHADOW MUST NOT RUN THE SUITE (~6.5min).

    Only consult an already-captured baseline (finalize.json
    ``baseline_test_failures``). If none present, status = ``not_evaluated``
    (NOT fail). The authoritative post-run + freshness cache is a documented
    TODO (see SHADOW_TODOS).
    """

    kind = "green_suite"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        finalize = _read_finalize(ctx.plan_dir)
        baseline_failures = finalize.get("baseline_test_failures")
        baseline_command = finalize.get("baseline_test_command")
        note = finalize.get("baseline_test_note")

        details: dict[str, Any] = {
            "baseline_test_command": baseline_command,
            "baseline_test_note": note,
            "suite_run_in_shadow": False,
        }

        if baseline_failures is None:
            # No usable cached result (no runner detected, timed out, or absent).
            details["reason"] = note or "no cached baseline test result available"
            return EvidenceRef(
                self.kind,
                EvidenceStatus.not_evaluated,
                "no cached suite result; shadow does not run the suite",
                details,
            )

        details["baseline_failure_count"] = len(baseline_failures)
        details["baseline_failures"] = list(baseline_failures)[:20]
        if baseline_failures:
            # Pre-existing red is informational in shadow; flag as unsatisfied so
            # the verdict surfaces it (no NEW-vs-baseline diff exists yet — TODO).
            return EvidenceRef(
                self.kind,
                EvidenceStatus.unsatisfied,
                f"cached baseline has {len(baseline_failures)} failing test(s)",
                details,
            )
        return EvidenceRef(
            self.kind, EvidenceStatus.satisfied, "cached baseline suite is green", details
        )


class ReviewDispositionProvider:
    """review_disposition — was review a genuine success or a force-proceed?

    Reads ``review.json``. If review force-proceeded at the rework cap
    (review.py:248-252 appends a "Force-proceeding…" issue), record
    ``fail-not-success`` (informational in shadow). Absence of review.json is
    ``not_applicable`` (e.g. bare robustness skips review).
    """

    kind = "review_disposition"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        review = _read_json(ctx.plan_dir / "review.json")
        if not isinstance(review, dict):
            return EvidenceRef(
                self.kind,
                EvidenceStatus.not_applicable,
                "no review.json (review may have been skipped)",
                {},
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
            return EvidenceRef(
                self.kind,
                EvidenceStatus.fail_not_success,
                "review force-proceeded at the rework cap with unresolved issues",
                details,
            )
        return EvidenceRef(
            self.kind, EvidenceStatus.satisfied, "review reported success", details
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
                return EvidenceRef(
                    self.kind,
                    EvidenceStatus.satisfied,
                    "typed no-op/waiver artifact present",
                    {
                        "artifact": candidate.name,
                        "reason": data.get("reason") or data.get("reason_code"),
                    },
                )
        return EvidenceRef(
            self.kind,
            EvidenceStatus.not_applicable,
            "no declared no-op/waiver artifact (absence is not a failure)",
            {},
        )


# The shared, phase-agnostic provider set. Reused verbatim across plan +
# milestone subjects (the generalization the design calls for).
DEFAULT_PROVIDERS: tuple[EvidenceProvider, ...] = (
    PhaseCoverageProvider(),
    LandedDiffProvider(),
    WorkerDidWorkProvider(),
    GreenSuiteProvider(),
    ReviewDispositionProvider(),
    DeclaredNoopProvider(),
)


# ---------------------------------------------------------------------------
# Verdict computation
# ---------------------------------------------------------------------------

#: Statuses that, in a future enforce mode, would deny a terminal transition.
_BLOCKING_STATUSES: frozenset[EvidenceStatus] = frozenset(
    {EvidenceStatus.unsatisfied, EvidenceStatus.fail_not_success}
)


def compute_verdict(
    *,
    plan_dir: Path,
    project_dir: Path,
    state: dict[str, Any],
    subject: CompletionSubject,
    mode: str = DEFAULT_CONTRACT_MODE,
    providers: tuple[EvidenceProvider, ...] = DEFAULT_PROVIDERS,
) -> CompletionVerdict:
    """Compute a :class:`CompletionVerdict` from objective evidence.

    Pure + fail-open: each provider is individually wrapped so one provider
    bug degrades to ``unknown`` rather than aborting the verdict. This is the
    single entry point the drivers call (inside their own try/except).

    A ``declared_noop`` ``satisfied`` ref acts as a waiver: it downgrades a
    ``landed_diff``/``worker_did_work`` ``unsatisfied`` to non-blocking, so an
    honestly-declared no-op passes while silent abandonment still fails.
    """
    mode = normalize_contract_mode(mode)
    refs: list[EvidenceRef] = []
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=subject,
    )
    for provider in providers:
        try:
            refs.append(provider.collect(ctx))
        except Exception as exc:  # fail-open per provider
            refs.append(
                EvidenceRef(
                    getattr(provider, "kind", "unknown"),
                    EvidenceStatus.unknown,
                    f"provider crashed: {exc}",
                    {},
                )
            )

    has_waiver = any(
        r.kind == "declared_noop" and r.status == EvidenceStatus.satisfied for r in refs
    )
    waivable = {"landed_diff", "worker_did_work"}

    failures: list[str] = []
    for ref in refs:
        if ref.status not in _BLOCKING_STATUSES:
            continue
        if has_waiver and ref.kind in waivable:
            continue  # honest declared no-op excuses missing diff/activity
        failures.append(f"{ref.kind}: {ref.summary}")

    return CompletionVerdict(
        mode=mode,
        subject=subject,
        evidence=tuple(refs),
        accepted=not failures,
        failures=tuple(failures),
    )
