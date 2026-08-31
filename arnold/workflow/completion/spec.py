"""Subject-kind enumeration, CompletionSpec, obligation, and proof-mode schemas.

This module defines the unified :class:`SubjectKind` enum — the single
taxonomy that replaces both the string-literal ``subject_kind`` field on the
old ``CompletionSpec`` prototype and the separate ``DurableSubjectKind``
enumeration from the durability lint prototype.

:class:`CompletionSpec` is a frozen, content-addressed identity record for a
completion obligation.  :class:`Obligation` describes a single proof
condition.  :class:`ProofMode` enumerates the four proof-mode kinds.

All serialization is deterministic (sorted-key, compact JSON) and produces
``spec_hash`` values that match the ``sha256:`` prefix convention from
:mod:`.hashing`.

.. note::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from arnold.workflow.completion.hashing import hash_canonical

# ---------------------------------------------------------------------------
# SubjectKind — unified single taxonomy
# ---------------------------------------------------------------------------

#: Mapping from :class:`SubjectKind` to the set of applicable platform
#: disposition rule IDs from
#: :file:`docs/arnold/workflow-execution-mode-dispositions.yaml`.
#:
#: Each entry lists the *always_hard* rules that **always** block for this
#: kind across all execution modes, the *non_durable_only* rules that permit
#: the kind only in authoring-preview mode, and the *production_admission*
#: rules that gate admitted production claims.
#:
#: .. caution::
#:    This mapping is authoritative for the disposition *rules* referenced,
#:    but the per-mode disposition *action* (reject, warn, advisory, etc.)
#:    is governed exclusively by the YAML rule matrix.  Do not duplicate
#:    the action logic here — reference the rule IDs and let the YAML
#:    determine the action in each mode.
SUBJECT_KIND_DISPOSITIONS: dict[str, set[str]] = {
    "WORKFLOW": {
        "DISP-1",     # always_hard — step_invokes_workflow_or_decorated_step,
                      #                recursive_workflow_call,
                      #                descriptor_source_disagreement,
                      #                preview_artifact_claims_durable_history,
                      #                admitted_history_or_identity_impersonation
        "DISP-3",     # production_admission_gate — identity_drift_against_pinned_occurrence
    },
    "STEP": {
        "DISP-1",     # always_hard — same as WORKFLOW
        "DISP-3",     # production_admission_gate
    },
    "DYNAMIC_TASK": {
        "DISP-1",     # always_hard — step_invokes_workflow_or_decorated_step
        "DISP-6",     # non_durable_only — dynamic_topology_or_dynamic_pype_import
    },
    "EFFECT": {
        "DISP-1",     # always_hard — hidden_effect_or_nondeterminism_in_helper
        "DISP-3",     # production_admission_gate
    },
    "HUMAN_BOUNDARY": {
        "DISP-1",     # always_hard — descriptor_source_disagreement
        "DISP-3",     # production_admission_gate
    },
}


class SubjectKind(StrEnum):
    """Unified single taxonomy for completion subjects.

    This enum replaces the previous approach with two separate taxonomies
    (string literals on ``CompletionSpec.subject_kind`` and the separate
    ``DurableSubjectKind``) — see SD-C1-001.  Every completion obligation
    is associated with exactly one :class:`SubjectKind`.
    """

    #: A top-level workflow definition.
    WORKFLOW = "workflow"
    #: A durable or non-durable step within a workflow.
    STEP = "step"
    #: A dynamically created task (fan-out child, iteration, etc.).
    DYNAMIC_TASK = "dynamic_task"
    #: A registered side effect adapter.
    EFFECT = "effect"
    #: A human boundary (review gate, approval step, manual intervention).
    HUMAN_BOUNDARY = "human_boundary"


# ---------------------------------------------------------------------------
# ProofMode — proof-kind enumeration
# ---------------------------------------------------------------------------


class ProofMode(StrEnum):
    """The four proof-mode kinds for an :class:`Obligation`.

    .. note::
       ``AGGREGATE`` remains experimental until the Platform S6 boundary
       mapping stabilises.  Code consuming ``AGGREGATE`` obligations must
       handle the possibility that this mode will be renamed or removed.
    """

    #: Presence-only — prove the evidence type exists, no completeness
    #: requirement.
    PRESENCE = "presence"
    #: Complete-capture absence — prove that no evidence of a given kind
    #: exists across a known complete capture window.
    COMPLETE_CAPTURE_ABSENCE = "complete_capture_absence"
    #: Set equality — the evidence set must match the declared set exactly.
    SET_EQUALITY = "set_equality"
    #: Aggregate — the evidence must satisfy an aggregate condition (sum,
    #: threshold, distribution).  Experimental until Platform S6.
    AGGREGATE = "aggregate"


# ---------------------------------------------------------------------------
# Obligation — single proof condition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Obligation:
    """A single proof condition within a :class:`CompletionSpec`.

    Each obligation describes one piece of evidence that must be
    satisfied for the spec to be completed.
    """

    obligation_id: str
    """Unique identifier for this obligation within its spec."""

    kind: ProofMode
    """The proof-mode kind for this obligation."""

    description: str
    """Human-readable description of what this obligation proves."""

    target_evidence_kinds: tuple[str, ...] = ()
    """The evidence kinds that satisfy this obligation."""

    required: bool = True
    """Whether this obligation is required for completion."""

    def __post_init__(self) -> None:
        # Normalize enum values passed as strings
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", ProofMode(self.kind))
        object.__setattr__(
            self, "target_evidence_kinds",
            tuple(str(k) for k in self.target_evidence_kinds),
        )
        if not self.obligation_id:
            raise ValueError("Obligation.obligation_id must be non-empty")
        if not self.description:
            raise ValueError("Obligation.description must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization dict with primitive values."""
        payload: dict[str, Any] = {
            "obligation_id": self.obligation_id,
            "kind": self.kind.value,
            "description": self.description,
        }
        if self.target_evidence_kinds:
            payload["target_evidence_kinds"] = list(self.target_evidence_kinds)
        if not self.required:
            payload["required"] = self.required
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Obligation:
        """Reconstruct from a serialized dict."""
        return cls(
            obligation_id=str(data["obligation_id"]),
            kind=ProofMode(data["kind"]),
            description=str(data["description"]),
            target_evidence_kinds=tuple(
                str(k) for k in data.get("target_evidence_kinds", ())
            ),
            required=bool(data.get("required", True)),
        )


# ---------------------------------------------------------------------------
# CompletionSpec — content-addressed completion identity
# ---------------------------------------------------------------------------


def _spec_hash_payload(
    obligation_id: str,
    subject_kind: SubjectKind,
    obligations: tuple[Obligation, ...],
    schema_version: str,
    canonical_name: str,
) -> dict[str, Any]:
    """Build the canonical dict used for ``spec_hash`` computation.

    All fields except ``spec_hash`` itself are serialised here with
    deterministic key ordering.
    """
    return {
        "obligation_id": obligation_id,
        "subject_kind": subject_kind.value,
        "obligations": [
            o.to_dict() for o in obligations
        ],
        "schema_version": schema_version,
        "canonical_name": canonical_name,
    }


def compute_spec_hash(
    obligation_id: str,
    subject_kind: SubjectKind,
    obligations: tuple[Obligation, ...],
    schema_version: str,
    canonical_name: str,
) -> str:
    """Compute the deterministic content hash for a :class:`CompletionSpec`.

    The hash is ``sha256:`` + SHA-256 of the canonical JSON of all fields
    **except** ``spec_hash`` itself.  This matches the algorithm in
    :func:`.hashing.hash_canonical`.
    """
    payload = _spec_hash_payload(
        obligation_id, subject_kind, obligations, schema_version, canonical_name,
    )
    return hash_canonical(payload)


@dataclass(frozen=True)
class CompletionSpec:
    """Content-addressed identity record for a completion obligation.

    A :class:`CompletionSpec` uniquely identifies *what* must be proved
    complete — the subject kind, the specific obligation, and the set of
    proof conditions.  The ``spec_hash`` is a deterministic content hash
    of all other fields, making the spec self-certifying.

    Identity is defined by the pair ``(spec_hash, obligation_id)`` —
    see :func:`obligation_identity`.
    """

    spec_hash: str
    """Content hash of all other fields (``sha256:``+hex)."""

    obligation_id: str
    """Unique identifier for this obligation within its subject context."""

    subject_kind: SubjectKind
    """The kind of subject this spec governs."""

    obligations: tuple[Obligation, ...] = ()
    """The proof conditions that must be satisfied."""

    schema_version: str = "arnold.workflow.completion_spec.v1"
    """Schema version for forward-compatibility."""

    canonical_name: str = ""
    """Canonical name / identifier for the subject or obligation."""

    def __post_init__(self) -> None:
        if isinstance(self.subject_kind, str):
            object.__setattr__(self, "subject_kind", SubjectKind(self.subject_kind))
        if isinstance(self.schema_version, str) and not self.schema_version.startswith("arnold.workflow.completion_spec"):
            raise ValueError(
                f"CompletionSpec.schema_version must start with "
                f"'arnold.workflow.completion_spec', got {self.schema_version!r}"
            )
        if not self.obligation_id:
            raise ValueError("CompletionSpec.obligation_id must be non-empty")
        if not self.spec_hash:
            raise ValueError("CompletionSpec.spec_hash must be non-empty")
        # Verify the spec_hash matches the other fields
        expected = compute_spec_hash(
            self.obligation_id,
            self.subject_kind,
            self.obligations,
            self.schema_version,
            self.canonical_name,
        )
        if self.spec_hash != expected:
            raise ValueError(
                f"CompletionSpec spec_hash mismatch: got {self.spec_hash!r}, "
                f"expected {expected!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization with ``spec_hash`` included."""
        payload: dict[str, Any] = {
            "spec_hash": self.spec_hash,
            "obligation_id": self.obligation_id,
            "subject_kind": self.subject_kind.value,
            "schema_version": self.schema_version,
        }
        if self.canonical_name:
            payload["canonical_name"] = self.canonical_name
        if self.obligations:
            payload["obligations"] = [o.to_dict() for o in self.obligations]
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CompletionSpec:
        """Reconstruct from a serialized dict, verifying ``spec_hash``."""
        obligations_data = data.get("obligations", ())
        obligations = tuple(
            Obligation.from_dict(o) if isinstance(o, dict) else o
            for o in obligations_data
        )
        return cls(
            spec_hash=str(data["spec_hash"]),
            obligation_id=str(data["obligation_id"]),
            subject_kind=SubjectKind(data["subject_kind"]),
            obligations=obligations,
            schema_version=str(
                data.get("schema_version", "arnold.workflow.completion_spec.v1")
            ),
            canonical_name=str(data.get("canonical_name", "")),
        )


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------


def obligation_identity(spec: CompletionSpec) -> tuple[str, str]:
    """Return the executable identity tuple ``(spec_hash, obligation_id)``.

    This pair is the stable identity of a single completion obligation
    across time, bindings, and shadow generations.  Two specs with the
    same identity are the *same obligation*, regardless of other metadata.
    """
    return (spec.spec_hash, spec.obligation_id)


def tombstone_spec(spec: CompletionSpec) -> CompletionSpec:
    """Create a tombstone spec that preserves hash lineage but changes identity.

    A tombstone spec is a new :class:`CompletionSpec` with the same
    :class:`SubjectKind` and structure but a distinct ``obligation_id``
    (prefixed with ``tombstone:``) and ``canonical_name`` suffixed with
    ``__tombstone``.  It produces a **different** ``spec_hash`` from the
    original, so ``obligation_identity(tombstone) != obligation_identity(original)``.

    Tombstones are used to mark an obligation as superseded while
    preserving its lineage for divergence tracking.
    """
    tombstone_id = f"tombstone:{spec.obligation_id}"
    tombstone_name = f"{spec.canonical_name}__tombstone" if spec.canonical_name else ""
    return make_completion_spec(
        obligation_id=tombstone_id,
        subject_kind=spec.subject_kind,
        obligations=spec.obligations,
        schema_version=spec.schema_version,
        canonical_name=tombstone_name,
    )


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def make_completion_spec(
    obligation_id: str,
    subject_kind: SubjectKind,
    obligations: tuple[Obligation, ...] = (),
    schema_version: str = "arnold.workflow.completion_spec.v1",
    canonical_name: str = "",
) -> CompletionSpec:
    """Construct a :class:`CompletionSpec` with an auto-computed ``spec_hash``.

    This is the preferred way to create a ``CompletionSpec`` — it computes
    the deterministic content hash from the other fields and passes it to
    the constructor for validation.
    """
    spec_hash = compute_spec_hash(
        obligation_id, subject_kind, obligations, schema_version, canonical_name,
    )
    return CompletionSpec(
        spec_hash=spec_hash,
        obligation_id=obligation_id,
        subject_kind=subject_kind,
        obligations=obligations,
        schema_version=schema_version,
        canonical_name=canonical_name,
    )


# ---------------------------------------------------------------------------
# SubjectKind-to-disposition crosswalk
# ---------------------------------------------------------------------------


#: Compact crosswalk table — lists every :class:`SubjectKind` with the
#: disposition rule IDs that apply to it.
#:
#: Each rule ID maps to a :file:`docs/arnold/workflow-execution-mode-dispositions.yaml`
#: rule in the ``rule_mode_matrix`` section.  The per-mode action (reject,
#: warn, advisory, etc.) is governed exclusively by the YAML matrix — this
#: table only documents *which* rules apply to *which* subject kinds.
SUBJECT_KIND_DISCIPLINE_CROSSWALK: dict[str, dict[str, list[str]]] = {
    "WORKFLOW": {
        "always_hard": [
            "step_invokes_workflow_or_decorated_step",
            "descriptor_source_disagreement",
            "preview_artifact_claims_durable_history",
            "admitted_history_or_identity_impersonation",
            "recursive_workflow_call",
        ],
        "production_admission_gate": [
            "identity_drift_against_pinned_occurrence",
        ],
        "stable_publication_gate": [
            "stable_profile_or_unrelated_consumer_missing",
        ],
    },
    "STEP": {
        "always_hard": [
            "step_invokes_workflow_or_decorated_step",
            "descriptor_source_disagreement",
            "preview_artifact_claims_durable_history",
            "admitted_history_or_identity_impersonation",
        ],
        "production_admission_gate": [
            "identity_drift_against_pinned_occurrence",
        ],
        "stable_publication_gate": [
            "stable_profile_or_unrelated_consumer_missing",
        ],
    },
    "DYNAMIC_TASK": {
        "always_hard": [
            "step_invokes_workflow_or_decorated_step",
        ],
        "non_durable_only": [
            "dynamic_topology_or_dynamic_pype_import",
        ],
    },
    "EFFECT": {
        "always_hard": [
            "hidden_effect_or_nondeterminism_in_helper",
            "descriptor_source_disagreement",
            "preview_artifact_claims_durable_history",
            "admitted_history_or_identity_impersonation",
        ],
        "production_admission_gate": [
            "identity_drift_against_pinned_occurrence",
        ],
    },
    "HUMAN_BOUNDARY": {
        "always_hard": [
            "descriptor_source_disagreement",
            "preview_artifact_claims_durable_history",
            "admitted_history_or_identity_impersonation",
        ],
        "production_admission_gate": [
            "identity_drift_against_pinned_occurrence",
        ],
    },
}
