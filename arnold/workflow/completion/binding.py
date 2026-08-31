"""Completion binding — spec-to-instance association with evidence windows.

This module defines the :class:`CompletionBinding` record that associates a
:class:`CompletionSpec` with a concrete subject instance and its evidence
window.  The binding is content-addressed via a deterministic hash
(``binding_hash``) that incorporates the spec hash, instance identity, and
evidence window parameters.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.workflow.completion.hashing import hash_canonical
from arnold.workflow.completion.spec import CompletionSpec
from arnold.workflow.completion.spec import SubjectKind

# ---------------------------------------------------------------------------
# SubjectInstanceId — type alias
# ---------------------------------------------------------------------------

#: Canonical type for a subject instance identifier.
#:
#: A ``SubjectInstanceId`` is a string that uniquely identifies a single
#: occurrence of a subject within a workflow execution (e.g. a step run,
#: a workflow invocation, a human review gate instance).
@dataclass(frozen=True)
class SubjectInstanceId:
    """Typed identity of one occurrence of a completion subject."""

    id: str
    subject_kind: SubjectKind

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("CompletionBinding.subject_instance_id.id must be non-empty")
        if isinstance(self.subject_kind, str):
            object.__setattr__(self, "subject_kind", SubjectKind(self.subject_kind))
        if not isinstance(self.subject_kind, SubjectKind):
            raise TypeError("SubjectInstanceId.subject_kind must be a SubjectKind")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "subject_kind": self.subject_kind.value}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.id == other
        if isinstance(other, SubjectInstanceId):
            return (self.id, self.subject_kind) == (other.id, other.subject_kind)
        return NotImplemented

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubjectInstanceId":
        return cls(str(data["id"]), str(data["subject_kind"]))

# ---------------------------------------------------------------------------
# CompletionBinding — spec-to-instance association
# ---------------------------------------------------------------------------


def _binding_hash_payload(
    spec_hash: str,
    subject_instance_id: SubjectInstanceId,
    evidence_window: tuple[str, str],
    obligation_id: str = "legacy",
    admission_source: str = "legacy",
    bound_artifacts: tuple[str, ...] = (),
    schema_version: str = "arnold.workflow.completion_binding.v1",
) -> dict[str, Any]:
    """Build the canonical dict used for ``binding_hash`` computation."""
    return {
        "spec_hash": spec_hash,
        "subject_instance_id": subject_instance_id.to_dict(),
        "evidence_window": list(evidence_window),
        "obligation_id": obligation_id,
        "admission_source": admission_source,
        "bound_artifacts": list(bound_artifacts),
        "schema_version": schema_version,
    }


def compute_binding_hash(
    spec_hash: str,
    subject_instance_id: SubjectInstanceId,
    evidence_window: tuple[str, str] | Mapping[str, Any] = ("", ""),
    evidence_window_start: str | None = None,
    evidence_window_end: str | None = None,
    obligation_id: str = "legacy",
    admission_source: str = "legacy",
    bound_artifacts: tuple[str, ...] = (),
    schema_version: str = "arnold.workflow.completion_binding.v1",
) -> str:
    """Compute the deterministic content hash for a :class:`CompletionBinding`.

    The hash is ``sha256:`` + SHA-256 of the canonical JSON of all fields
    **except** ``binding_hash`` itself.  This uses the same canonical JSON
    serialisation as :func:`.hashing.hash_canonical`.
    """
    if isinstance(subject_instance_id, str):
        subject_instance_id = SubjectInstanceId(subject_instance_id, SubjectKind.STEP)
    if evidence_window_start is not None or evidence_window_end is not None:
        evidence_window = (evidence_window_start or "", evidence_window_end or "")
    elif isinstance(evidence_window, Mapping):
        evidence_window = (
            str(evidence_window.get("start", evidence_window.get("evidence_window_start", ""))),
            str(evidence_window.get("end", evidence_window.get("evidence_window_end", ""))),
        )
    else:
        evidence_window = tuple(str(v) for v in evidence_window)
    if len(evidence_window) != 2:
        raise ValueError("evidence_window must contain start and end")
    payload = _binding_hash_payload(
        spec_hash,
        subject_instance_id,
        evidence_window,
        obligation_id,
        admission_source,
        tuple(str(v) for v in bound_artifacts),
        schema_version,
    )
    return hash_canonical(payload)


@dataclass(frozen=True)
class CompletionBinding:
    """Content-addressed association of a spec to a subject instance.

    A :class:`CompletionBinding` records that a particular :class:`CompletionSpec`
    (identified by its ``spec_hash``) was bound to a concrete subject
    instance (identified by ``subject_instance_id``) with a specific
    evidence window.  The ``binding_hash`` provides deterministic content
    addressing for the binding itself.

    The evidence window defines the time range during which evidence for
    this binding may be collected.  Window boundaries are expressed as
    ISO-8601 datetime strings.
    """

    binding_hash: str
    """Content hash of all other fields (``sha256:`` + 64-hex format)."""

    spec_hash: str
    """Bound spec hash in required ``sha256:`` + 64-hex format."""

    subject_instance_id: SubjectInstanceId
    """The subject instance this binding applies to."""

    obligation_id: str = "legacy"
    """Stable obligation identity copied from the bound spec."""

    admission_source: str = "legacy"
    """S2F source/template reference that admitted this binding."""

    evidence_window: tuple[str, str] = ("", "")
    """Canonical ``(start, end)`` evidence window."""

    bound_artifacts: tuple[str, ...] = ()
    """Content-addressed artifacts covered by this binding."""

    schema_version: str = "arnold.workflow.completion_binding.v1"
    """Binding schema version."""

    evidence_window_start: str = ""
    evidence_window_end: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.subject_instance_id, str):
            object.__setattr__(self, "subject_instance_id", SubjectInstanceId(self.subject_instance_id, SubjectKind.STEP))
        if self.evidence_window == ("", "") and (self.evidence_window_start or self.evidence_window_end):
            object.__setattr__(self, "evidence_window", (self.evidence_window_start, self.evidence_window_end))
        if not self.binding_hash:
            raise ValueError("CompletionBinding.binding_hash must be non-empty")
        if not self.spec_hash:
            raise ValueError("CompletionBinding.spec_hash must be non-empty")
        if not isinstance(self.subject_instance_id, SubjectInstanceId):
            raise TypeError("CompletionBinding.subject_instance_id must be SubjectInstanceId")
        if not self.obligation_id:
            raise ValueError("CompletionBinding.obligation_id must be non-empty")
        if not self.admission_source:
            raise ValueError("CompletionBinding.admission_source must be non-empty")
        if isinstance(self.evidence_window, Mapping):
            object.__setattr__(
                self,
                "evidence_window",
                (
                    str(self.evidence_window.get("start", self.evidence_window.get("evidence_window_start", ""))),
                    str(self.evidence_window.get("end", self.evidence_window.get("evidence_window_end", ""))),
                ),
            )
        else:
            object.__setattr__(self, "evidence_window", tuple(str(v) for v in self.evidence_window))
        if len(self.evidence_window) != 2:
            raise ValueError("CompletionBinding.evidence_window must contain start and end")
        object.__setattr__(self, "bound_artifacts", tuple(str(v) for v in self.bound_artifacts))
        if not self.schema_version.startswith("arnold.workflow.completion_binding"):
            raise ValueError("CompletionBinding.schema_version is unsupported")
        if not self.subject_instance_id.id:
            raise ValueError(
                "CompletionBinding.subject_instance_id must be non-empty"
            )
        # Verify the binding_hash matches the other fields
        expected = compute_binding_hash(
            self.spec_hash,
            self.subject_instance_id,
            self.evidence_window,
            obligation_id=self.obligation_id,
            admission_source=self.admission_source,
            bound_artifacts=self.bound_artifacts,
            schema_version=self.schema_version,
        )
        if self.binding_hash != expected:
            raise ValueError(
                f"CompletionBinding binding_hash mismatch: got "
                f"{self.binding_hash!r}, expected {expected!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization dict with primitive values."""
        payload: dict[str, Any] = {
            "binding_hash": self.binding_hash,
            "spec_hash": self.spec_hash,
            "obligation_id": self.obligation_id,
            "subject_instance_id": self.subject_instance_id.to_dict(),
            "admission_source": self.admission_source,
            "evidence_window": list(self.evidence_window),
            "bound_artifacts": list(self.bound_artifacts),
            "schema_version": self.schema_version,
        }
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CompletionBinding:
        """Reconstruct from a serialized dict, verifying ``binding_hash``."""
        return cls(
            binding_hash=str(data["binding_hash"]),
            spec_hash=str(data["spec_hash"]),
            obligation_id=str(data["obligation_id"]),
            subject_instance_id=SubjectInstanceId.from_dict(data["subject_instance_id"]),
            admission_source=str(data["admission_source"]),
            evidence_window=tuple(str(v) for v in data.get("evidence_window", ("", ""))),
            bound_artifacts=tuple(str(v) for v in data.get("bound_artifacts", ())),
            schema_version=str(data.get("schema_version", "arnold.workflow.completion_binding.v1")),
        )


# ---------------------------------------------------------------------------
# Factory — bind
# ---------------------------------------------------------------------------


def bind(
    spec: CompletionSpec,
    subject_instance_id: SubjectInstanceId | str,
    evidence_window_start: str = "",
    evidence_window_end: str = "",
    admission_source: str = "shadow",
    bound_artifacts: tuple[str, ...] = (),
) -> CompletionBinding:
    """Create a :class:`CompletionBinding` from a spec and instance id.

    This is the canonical way to produce a binding.  It computes a
    deterministic ``binding_hash`` from the spec hash and instance
    identity, then validates the hash in the constructor.

    Parameters
    ----------
    spec:
        The :class:`CompletionSpec` being bound.
    subject_instance_id:
        The instance identifier for the concrete subject.
    evidence_window_start:
        ISO-8601 datetime for the evidence window start.
    evidence_window_end:
        ISO-8601 datetime for the evidence window end.

    Returns
    -------
    CompletionBinding
        A binding with auto-computed ``binding_hash``.
    """
    if isinstance(subject_instance_id, str):
        subject_instance_id = SubjectInstanceId(subject_instance_id, spec.subject_kind)
    evidence_window = (evidence_window_start, evidence_window_end)
    binding_hash = compute_binding_hash(
        spec.spec_hash,
        subject_instance_id,
        evidence_window,
        obligation_id=spec.obligation_id,
        admission_source=admission_source,
        bound_artifacts=bound_artifacts,
        schema_version="arnold.workflow.completion_binding.v1",
    )
    return CompletionBinding(
        binding_hash=binding_hash,
        spec_hash=spec.spec_hash,
        obligation_id=spec.obligation_id,
        subject_instance_id=subject_instance_id,
        admission_source=admission_source,
        evidence_window=evidence_window,
        bound_artifacts=bound_artifacts,
    )
