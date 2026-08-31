"""Megaplan adapter — bridges megaplan artifacts to the completion kernel.

This module provides:

* :class:`CompletionSubject` — typed mapping of megaplan artifact kinds
  to :class:`~arnold.workflow.completion.spec.SubjectKind`.
* :func:`megaplan_subject_inventory` — generate a subject inventory from
  megaplan artifacts.
* :func:`shadow_runner` — run shadow evaluation using megaplan-specific
  defaults (S2F discovery).
* :class:`S2FShadowRunner` — configurable runner class wrapping discovery
  and shadow evaluation.

CompletionSubject.kind mapping
------------------------------
Megaplan artifact type → :class:`~arnold.workflow.completion.spec.SubjectKind`:

* ``plan`` → ``WORKFLOW``        — a plan is a top-level workflow definition.
* ``milestone`` → ``WORKFLOW``   — a milestone is a sub-workflow within a plan.
* ``phase`` → ``STEP``           — a phase within a milestone is a step.
* ``step`` → ``STEP``            — a step (workflow step).
* ``stage`` → ``STEP``           — a stage (grouped step).
* ``task`` → ``DYNAMIC_TASK``    — a dynamic task (fan-out child).
* ``effect`` → ``EFFECT``        — a registered side effect adapter.
* ``review`` → ``HUMAN_BOUNDARY`` — a human review gate.

.. caution::
   This package is **experimental and non-authoritative**.  Shadow verdicts
   have **zero authority** and **cannot satisfy completion**.  See S2R GO-0
   for the future live-enablement gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from arnold.workflow.completion.spec import (
    SubjectKind,
)
from arnold.workflow.completion.shadow import (
    DEFAULT_S2F_SCAN_DIRS,
    S2F_SCHEMA_MARKERS,
    S2FGapReport,
    S2FTemplatesUnavailable,
    ShadowEvaluation,
    evaluate_shadow,
    s2f_discovery_gap_report,
)
from arnold.workflow.completion.source_declaration import (
    SourceDeclaration,
    SubjectDeclaration,
)

# ---------------------------------------------------------------------------
# CompletionSubject — kind mapping
# ---------------------------------------------------------------------------

#: Mapping from megaplan artifact type strings to
#: :class:`~arnold.workflow.completion.spec.SubjectKind`.
#:
#: This is the authoritative crosswalk for translating megaplan concepts
#: into completion-kernel subject kinds.
MEGAPLAN_KIND_MAPPING: dict[str, SubjectKind] = {
    "plan": SubjectKind.WORKFLOW,
    "milestone": SubjectKind.WORKFLOW,
    "phase": SubjectKind.STEP,
    "step": SubjectKind.STEP,
    "stage": SubjectKind.STEP,
    "task": SubjectKind.DYNAMIC_TASK,
    "effect": SubjectKind.EFFECT,
    "review": SubjectKind.HUMAN_BOUNDARY,
}


def _inverse_kind_mapping(kind: SubjectKind) -> tuple[str, ...]:
    """Return all megaplan artifact type strings that map to *kind*.

    Parameters
    ----------
    kind:
        The :class:`SubjectKind` to invert.

    Returns
    -------
    tuple[str, ...]
        Megaplan artifact type strings for *kind*.
    """
    return tuple(k for k, v in MEGAPLAN_KIND_MAPPING.items() if v == kind)


@dataclass(frozen=True)
class CompletionSubject:
    """Typed representation of a single megaplan artifact as a completion subject.

    Parameters
    ----------
    artifact_type:
        The megaplan artifact type string (e.g. ``"plan"``, ``"phase"``).
    identifier:
        Unique identifier for this artifact within the megaplan context.
    name:
        Human-readable name of the artifact.
    kind:
        The :class:`SubjectKind` derived from *artifact_type* via
        :data:`MEGAPLAN_KIND_MAPPING`.
    """

    artifact_type: str
    identifier: str
    name: str = ""
    kind: SubjectKind | None = None

    def __post_init__(self) -> None:
        if not self.artifact_type:
            raise ValueError("CompletionSubject.artifact_type must be non-empty")
        if not self.identifier:
            raise ValueError("CompletionSubject.identifier must be non-empty")
        mapped_kind = MEGAPLAN_KIND_MAPPING.get(self.artifact_type)
        if mapped_kind is None:
            raise ValueError(
                "Unsupported megaplan artifact type "
                f"{self.artifact_type!r}; no completion-subject mapping exists"
            )
        if self.kind is None:
            object.__setattr__(self, "kind", mapped_kind)
        elif self.kind != mapped_kind:
            raise ValueError(
                "CompletionSubject.kind must match MEGAPLAN_KIND_MAPPING for "
                f"{self.artifact_type!r}"
            )

    def to_source_declaration(self) -> SourceDeclaration:
        """Convert this subject to a :class:`SourceDeclaration`.

        Returns
        -------
        SourceDeclaration
            A source declaration suitable for
            :class:`SubjectDeclaration` construction.
        """
        return SourceDeclaration(
            source_id=f"megaplan:{self.artifact_type}:{self.identifier}",
            kind=self.kind,
            canonical_name=self.name or self.identifier,
        )

    def to_subject_declaration(
        self,
        declaration_id: str | None = None,
        subject_instance_id: str | None = None,
    ) -> SubjectDeclaration:
        """Convert this subject to a :class:`SubjectDeclaration`.

        Parameters
        ----------
        declaration_id:
            Optional explicit declaration ID.  Auto-generated if omitted.
        subject_instance_id:
            Optional explicit subject instance ID.  Auto-generated if omitted.

        Returns
        -------
        SubjectDeclaration
            A subject declaration ready for shadow evaluation.
        """
        source = self.to_source_declaration()
        return SubjectDeclaration(
            source=source,
            subject_kind=self.kind,
            subject_instance_id=(
                subject_instance_id
                or f"megaplan:{self.artifact_type}:{self.identifier}:inst"
            ),
            declaration_id=(
                declaration_id
                or f"megaplan:{self.artifact_type}:{self.identifier}:decl"
            ),
        )


# ---------------------------------------------------------------------------
# Subject inventory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectInventory:
    """An inventory of :class:`CompletionSubject` instances from megaplan artifacts.

    Parameters
    ----------
    subjects:
        The :class:`CompletionSubject` instances in this inventory.
    """

    subjects: tuple[CompletionSubject, ...] = ()

    def to_declarations(self) -> tuple[SubjectDeclaration, ...]:
        """Convert all subjects to :class:`SubjectDeclaration` instances.

        Returns
        -------
        tuple[SubjectDeclaration, ...]
            Declarations ready for shadow evaluation.
        """
        return tuple(s.to_subject_declaration() for s in self.subjects)

    def __len__(self) -> int:
        return len(self.subjects)


def megaplan_subject_inventory(
    artifacts: Iterable[Mapping[str, Any]] | None = None,
    *,
    scan_dirs: tuple[str, ...] | None = None,
    schema_markers: tuple[str, ...] | None = None,
) -> tuple[SubjectDeclaration, ...]:
    """Return typed subject declarations from S2F or explicit artifacts.

    With no *artifacts*, this is the production adapter entry point: it uses
    the S2F discovery protocol and returns all available typed declarations.
    Partial S2F availability is retained for shadow evaluation and is exposed
    by :func:`s2f_discovery_gap_report`; zero discovered templates hard-stop
    with :class:`S2FTemplatesUnavailable`.

    The optional *artifacts* form is retained for bounded synthetic callers.
    Each mapping must contain ``artifact_type`` and ``identifier`` and is
    converted directly to a :class:`SubjectDeclaration`.

    Parameters
    ----------
    artifacts:
        Optional explicit megaplan artifact mappings to process.
    scan_dirs:
        S2F directories to scan when *artifacts* is omitted.
    schema_markers:
        S2F schema markers to match when *artifacts* is omitted.

    Returns
    -------
    tuple[SubjectDeclaration, ...]
        Typed declarations with populated ``subject_id``, ``subject_kind``,
        and ``source`` values.
    """
    if artifacts is None:
        report = s2f_discovery_gap_report(
            scan_dirs=scan_dirs,
            schema_markers=schema_markers,
        )
        if not report.discovered_files:
            raise S2FTemplatesUnavailable(report)
        return report.parsed_declarations

    subjects: list[CompletionSubject] = []
    for artifact in artifacts:
        artifact_type = str(artifact.get("artifact_type", ""))
        identifier = str(artifact.get("identifier", ""))
        name = str(artifact.get("name", ""))
        if not artifact_type or not identifier:
            continue
        subjects.append(
            CompletionSubject(
                artifact_type=artifact_type,
                identifier=identifier,
                name=name,
            )
        )
    return tuple(subject.to_subject_declaration() for subject in subjects)


# ---------------------------------------------------------------------------
# Shadow runner
# ---------------------------------------------------------------------------


@dataclass
class S2FShadowRunner:
    """Configurable runner that wraps S2F discovery and shadow evaluation.

    Parameters
    ----------
    scan_dirs:
        Directories to scan for S2F templates.  Defaults to
        :data:`~arnold.workflow.completion.shadow.DEFAULT_S2F_SCAN_DIRS`.
    schema_markers:
        Schema markers for identifying S2F template files.  Defaults to
        :data:`~arnold.workflow.completion.shadow.S2F_SCHEMA_MARKERS`.
    """

    scan_dirs: tuple[str, ...] = field(
        default_factory=lambda: DEFAULT_S2F_SCAN_DIRS
    )
    schema_markers: tuple[str, ...] = field(
        default_factory=lambda: S2F_SCHEMA_MARKERS
    )
    last_gap_report: S2FGapReport | None = field(default=None, init=False)
    """Latest structured S2F qualification emitted with a shadow run."""

    def discovery_gap_report(self) -> S2FGapReport:
        """Produce an S2F discovery gap report.

        Returns
        -------
        S2FGapReport
            The structured gap report.
        """
        report = s2f_discovery_gap_report(
            scan_dirs=self.scan_dirs,
            schema_markers=self.schema_markers,
        )
        self.last_gap_report = report
        return report

    def run_shadow(self) -> ShadowEvaluation:
        """Run a full shadow evaluation using S2F discovery.

        Discovers S2F templates, parses them into declarations, and
        runs shadow evaluation.  Partial template availability yields a
        qualified result; no discovered templates raises
        :class:`S2FTemplatesUnavailable`.

        Returns
        -------
        ShadowEvaluation
            The shadow evaluation results.
        """
        report = s2f_discovery_gap_report(
            scan_dirs=self.scan_dirs,
            schema_markers=self.schema_markers,
        )
        self.last_gap_report = report
        if not report.discovered_files:
            raise S2FTemplatesUnavailable(report)
        return evaluate_shadow(report.parsed_declarations)

    def run_shadow_with_inventory(
        self,
        inventory: SubjectInventory,
    ) -> ShadowEvaluation:
        """Run shadow evaluation against a given :class:`SubjectInventory`.

        Parameters
        ----------
        inventory:
            The subject inventory to evaluate.

        Returns
        -------
        ShadowEvaluation
            The shadow evaluation results with specs, bindings, and
            verdicts.
        """
        return evaluate_shadow(inventory.to_declarations())


def shadow_runner(
    scan_dirs: tuple[str, ...] | None = None,
) -> S2FShadowRunner:
    """Convenience factory for creating an :class:`S2FShadowRunner`.

    Parameters
    ----------
    scan_dirs:
        Optional override for scan directories.

    Returns
    -------
    S2FShadowRunner
        A configured runner.
    """
    if scan_dirs is not None:
        return S2FShadowRunner(scan_dirs=scan_dirs)
    return S2FShadowRunner()
