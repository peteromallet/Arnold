"""Repair-runner adapter with broken-CLI resilience.

M9: Repair eligibility classification consumes canonical source-cursor
projections plus exact failure signatures.  Raw labels, mutable markers, or
stale projections cannot grant repair eligibility — only verify-only
acceptance against current evidence.
"""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorVector,
)
from arnold_pipelines.megaplan.run_state.quality_family import (
    QualityFamily,
    normalize_quality_family,
)


# ── M9: Repair eligibility classification ──────────────────────────────────


class RepairEligibilityVerdict(Enum):
    """Typed repair eligibility verdict.

    * ELIGIBLE — canonical source-cursor projections + exact failure
      signatures confirm eligibility.
    * INELIGIBLE — evidence is insufficient, stale, or blocked by
      non-authoritative markers.
    * INDETERMINATE — cannot determine eligibility (missing evidence,
      contradictory sources, migration gap).
    """

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class RepairFailureSignature:
    """Exact failure signature for repair eligibility classification.

    Binds a specific failure occurrence to its source evidence so that
    stale, recycled, or cross-plan occurrences cannot be mistaken for
    current eligibility.
    """

    criterion_id: str = ""
    """Structured criterion identifier (e.g. quality check id, test name)."""

    quality_family: str = ""
    """Canonical quality family (fail, error, timeout, etc.) from QualityFamily."""

    content_hash: str = ""
    """sha256 over the original failure evidence (status + command + occurrence)."""

    occurred_at: str = ""
    """ISO-8601 timestamp when the failure was first observed."""

    exit_code: Optional[int] = None
    """Process exit code associated with the failure (if any)."""

    detail: str = ""
    """Human-readable detail from the original failure."""

    evidence_id: str = ""
    """Content-addressed evidence identifier for this exact signature."""

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raw = (
                f"{self.criterion_id}\\x00{self.quality_family}\\x00"
                f"{self.content_hash}\\x00{self.occurred_at}"
            )
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "evidence_id", f"sha256:{digest}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "quality_family": self.quality_family,
            "content_hash": self.content_hash,
            "occurred_at": self.occurred_at,
            "exit_code": self.exit_code,
            "detail": self.detail,
            "evidence_id": self.evidence_id,
        }

    @classmethod
    def from_failure(
        cls,
        *,
        criterion_id: str = "",
        original_status: str = "",
        command: str = "",
        occurred_at: str = "",
        exit_code: Optional[int] = None,
        detail: str = "",
    ) -> "RepairFailureSignature":
        """Create a signature from original failure evidence.

        The content_hash is computed over (original_status, command, criterion_id)
        for deterministic identity.  No mutable marker or label is used for
        the hash — only the original evidence.
        """
        quality_family = normalize_quality_family(original_status).value
        raw_hash = f"{original_status}\\x00{command}\\x00{criterion_id}"
        content_hash = "sha256:" + hashlib.sha256(raw_hash.encode("utf-8")).hexdigest()
        return cls(
            criterion_id=criterion_id,
            quality_family=quality_family,
            content_hash=content_hash,
            occurred_at=occurred_at,
            exit_code=exit_code,
            detail=detail,
        )


@dataclass(frozen=True)
class RepairEligibility:
    """Typed repair eligibility — verify-only, never bearer authority.

    Repair eligibility is classified from canonical source-cursor
    projections plus exact failure signatures.  Raw labels, mutable
    markers, or stale projections **cannot** grant eligibility.

    This is a verify-only gate: even when ``verdict`` is ELIGIBLE, the
    caller must still reread current grant/fence, custody lease/epoch,
    and WBC evidence before any positive repair action.
    """

    verdict: RepairEligibilityVerdict
    """ELIGIBLE, INELIGIBLE, or INDETERMINATE."""

    failure_signatures: Tuple[RepairFailureSignature, ...] = ()
    """Exact failure signatures that were evaluated."""

    source_cursor: Optional[SourceCursorVector] = None
    """Canonical source-cursor projection used for classification."""

    blocking_reasons: Tuple[str, ...] = ()
    """Why eligibility was denied or deferred (empty when ELIGIBLE)."""

    evidence_ids: Tuple[str, ...] = ()

    positive_dispatch_requires_reread: bool = True

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)
        eids = [sig.evidence_id for sig in self.failure_signatures]
        if self.source_cursor is not None:
            eids.append(self.source_cursor.vector_id)
        object.__setattr__(self, "evidence_ids", tuple(eids))

    @property
    def is_eligible(self) -> bool:
        return self.verdict == RepairEligibilityVerdict.ELIGIBLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "failure_signatures": [s.to_dict() for s in self.failure_signatures],
            "source_cursor": self.source_cursor.to_dict() if self.source_cursor else None,
            "blocking_reasons": list(self.blocking_reasons),
            "evidence_ids": list(self.evidence_ids),
            "positive_dispatch_requires_reread": self.positive_dispatch_requires_reread,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def classify(
        cls,
        *,
        failure_signatures: Sequence[RepairFailureSignature],
        source_cursor: Optional[SourceCursorVector] = None,
    ) -> "RepairEligibility":
        """Classify repair eligibility from canonical projections + exact signatures.

        Rules (verify-only; none grant authority):
        1. No failure signatures → INELIGIBLE (nothing to repair)
        2. Source cursor absent → INDETERMINATE
        3. Any blocking dimension (stale/unknown/incoherent) → INDETERMINATE
        4. All failure signatures are quality-family UNKNOWN → INELIGIBLE
           (cannot classify without recognized failures)
        5. At least one FAIL/ERROR/TIMEOUT signature with fresh source
           cursor → ELIGIBLE
        6. WARN-only → INELIGIBLE (warnings are not repair-triggering)
        """
        failure_blocking: list[str] = []
        cursor_blocking: list[str] = []

        if not failure_signatures:
            return cls(
                verdict=RepairEligibilityVerdict.INELIGIBLE,
                blocking_reasons=("no failure signatures provided",),
                source_cursor=source_cursor,
            )

        if source_cursor is None:
            return cls(
                verdict=RepairEligibilityVerdict.INDETERMINATE,
                failure_signatures=tuple(failure_signatures),
                blocking_reasons=("no source-cursor projection available",),
            )

        # Check source-cursor dimensions — tracked separately from
        # failure-based blocking so that actionable failures with a stale
        # cursor become INDETERMINATE instead of INELIGIBLE.
        stale_dims = source_cursor.stale_dimensions()
        if stale_dims:
            cursor_blocking.append(
                f"source-cursor has non-fresh dimensions: {', '.join(stale_dims)}"
            )

        # Classify failure signatures for actionable vs non-actionable
        actionable_families = {"fail", "error", "timeout"}
        has_actionable = any(
            s.quality_family in actionable_families for s in failure_signatures
        )
        all_unknown = all(
            s.quality_family == QualityFamily.UNKNOWN.value
            for s in failure_signatures
        )

        if all_unknown:
            failure_blocking.append("all failure signatures are quality-family unknown")
        elif not has_actionable:
            failure_blocking.append(
                "failure signatures are pass/skip/warn only — no actionable failures"
            )

        # When failures themselves block eligibility, return INELIGIBLE
        # regardless of cursor staleness.
        if failure_blocking:
            return cls(
                verdict=RepairEligibilityVerdict.INELIGIBLE,
                failure_signatures=tuple(failure_signatures),
                source_cursor=source_cursor,
                blocking_reasons=tuple(failure_blocking),
            )

        # Actionable failures exist but cursor has stale/unknown/incoherent
        # dimensions — cannot confirm eligibility, return INDETERMINATE
        # with both failure and cursor context.
        if stale_dims:
            return cls(
                verdict=RepairEligibilityVerdict.INDETERMINATE,
                failure_signatures=tuple(failure_signatures),
                source_cursor=source_cursor,
                blocking_reasons=tuple(cursor_blocking),
            )

        # Actionable failures + fresh cursor → ELIGIBLE
        return cls(
            verdict=RepairEligibilityVerdict.ELIGIBLE,
            failure_signatures=tuple(failure_signatures),
            source_cursor=source_cursor,
        )


@dataclass(frozen=True)
class RepairResult:
    status: str
    stdout: str
    stderr: str
    rc: int | None


_MEGAPLAN_SUBCOMMANDS: frozenset[str] = frozenset({
    "doctor",
    "auto",
    "resume",
    "chain",
})


class RepairRunner:
    """Run allowlisted repair commands via subprocess.

    Megaplan subcommands (``doctor``, ``auto``, ``resume``, ``chain``) are
    executed as ``python -m arnold_pipelines.megaplan <subcommand> ...`` inside
    the plan's project directory. System commands (``rm``, ``kill``) are run
    directly. If the executable is missing or the command cannot be run, returns
    a ``command_unavailable`` result instead of crashing.
    """

    def __init__(
        self,
        executable_search_path: Sequence[str] | None = None,
        python_bin: str | None = None,
    ) -> None:
        self._search_path = executable_search_path
        self._python_bin = python_bin or shutil.which("python3") or shutil.which("python") or "python"

    def _is_dry_run(self) -> bool:
        """An empty search path signals dry-run: do not execute anything."""
        return self._search_path is not None and len(self._search_path) == 0

    @staticmethod
    def _with_default_profile(parts: list[str]) -> list[str]:
        """Inject ``--profile partnered-5`` for allowlisted repair subcommands.

        Megaplan repair commands (``doctor``/``auto``/``resume``/``chain``) inherit
        the engine default profile when none is given. The meta-loop repair layer
        runs under the partnered-5 profile (validated at
        ``arnold_pipelines/megaplan/profiles/partnered-5.toml``); route repairs
        through it unless the caller already pinned a ``--profile``.
        """
        if any(p == "--profile" or p.startswith("--profile=") for p in parts):
            return parts
        return parts + ["--profile", "partnered-5"]

    def _argv_for_command(self, command: str) -> tuple[list[str], str | None, bool]:
        """Return (argv, cwd, is_megaplan_subcommand) for *command*.

        Megaplan subcommands are always rewritten to
        ``python -P -m arnold_pipelines.megaplan`` so the subprocess cannot
        import stale checkout-local packages from the active workflow cwd.
        System commands are passed through. The returned cwd is the directory in
        which the command should run, or None for the current directory.
        """
        if self._is_dry_run():
            return [], None, False

        parts = shlex.split(command)
        if not parts:
            return [], None, False

        first = parts[0]
        # Detect an explicit project-dir marker injected by the CLI: "cd /path && cmd"
        if first == "cd" and len(parts) >= 4 and parts[2] == "&&":
            cwd = parts[1].strip("'\"")
            parts = parts[3:]
            first = parts[0] if parts else ""
        else:
            cwd = None

        if first in _MEGAPLAN_SUBCOMMANDS:
            return [self._python_bin, "-P", "-m", "arnold_pipelines.megaplan"] + parts, cwd, True

        # Bare subcommands like "rm" or "kill" that are not standalone executables
        # but are safe shell builtins/utilities.
        if first in {"rm", "kill"}:
            return ["/bin/bash", "-c", " ".join(parts)], cwd, False

        executable = shutil.which(first, path=self._search_path)
        if executable is None:
            return [], cwd, False
        return [executable] + parts[1:], cwd, False

    def _megaplan_subcommand_env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        """Anchor Megaplan subprocesses to the editable install engine checkout."""

        from arnold_pipelines.megaplan.runtime.process import megaplan_engine_env, megaplan_engine_root

        env = megaplan_engine_env(base)
        env["MEGAPLAN_ENGINE_ROOT"] = str(megaplan_engine_root())
        env["PYTHONSAFEPATH"] = "1"
        # Meta-loop repairs default to the validated partnered-5 profile
        # (arnold_pipelines/megaplan/profiles/partnered-5.toml). Plan configs that
        # pin an explicit profile still win; this only fills the gap when a
        # repair context would otherwise inherit the engine default "partnered".
        env.setdefault("MEGAPLAN_DEFAULT_PROFILE", "partnered-5")
        env.setdefault("MEGAPLAN_REPAIR_PROFILE", "partnered-5")
        return env

    def run(
        self,
        command: str,
        *,
        plan_dir: str | None = None,
        project_dir: str | None = None,
    ) -> RepairResult:
        """Execute *command* and return a structured result."""
        argv, argv_cwd, is_megaplan_subcommand = self._argv_for_command(command)
        if not argv:
            return RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"executable not found or unsupported command: {command!r}",
                rc=None,
            )

        cwd = argv_cwd or project_dir
        if cwd is None and plan_dir is not None:
            # Fall back to the plan directory's repo root.
            try:
                cwd = str(Path(plan_dir).parents[2])
            except Exception:
                pass

        env = (
            self._megaplan_subcommand_env(os.environ.copy())
            if is_megaplan_subcommand
            else os.environ.copy()
        )
        if cwd is not None:
            env["MEGAPLAN_PLAN_DIR"] = str(plan_dir) if plan_dir else cwd
            env["MEGAPLAN_PROJECT_DIR"] = cwd

        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                cwd=cwd,
                env=env,
            )
            status = "success" if result.returncode == 0 else "failed"
            return RepairResult(
                status=status,
                stdout=result.stdout,
                stderr=result.stderr,
                rc=result.returncode,
            )
        except (FileNotFoundError, OSError) as exc:
            return RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"could not execute {argv!r}: {exc}",
                rc=None,
            )
        except subprocess.TimeoutExpired:
            return RepairResult(
                status="timeout",
                stdout="",
                stderr="command timed out after 300s",
                rc=None,
            )


__all__ = [
    "RepairEligibilityVerdict",
    "RepairFailureSignature",
    "RepairEligibility",
    "RepairResult",
    "RepairRunner",
]
