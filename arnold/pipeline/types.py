"""Neutral frozen dataclasses and Protocol for the Arnold pipeline boundary.

This module defines the pure-data, opinion-free type surface that any
pipeline runtime can consume.  Opinionated vocabulary (typed gate/override
literals, run envelopes, plan directories, profiles, budgets) is deliberately
excluded — this is the *structural* skeleton only.

Sub-module of ``arnold.pipeline``.  Import from here or from the parent
package once ``arnold/pipeline/__init__.py`` re-exports are wired.

``ContractResult`` (appended at end-of-file) is the ONE shared seam primitive
imported by both planes — the Step-IO data plane and the Evidence-First
control plane.  It carries a neutral ``payload``, a 3-status discriminant
(``completed`` / ``suspended`` / ``failed``) via :class:`ContractStatus`, a
typed :class:`Suspension` interaction envelope, first-class
:class:`EvidenceArtifactRef` / ``evidence_refs`` / ``authority_level`` /
:class:`Provenance` / :class:`Freshness` fields, and a content-addressed
``schema_version``.  It is conceptually part of the typed-seam vocabulary
introduced at :class:`Port` / :class:`PortRef` above; the block is appended
at end-of-file because :func:`register_schema` must already be defined when
``CONTRACT_RESULT_SCHEMA_VERSION`` is computed at module-import time.  The
import contract is ``from arnold.pipeline import ContractResult`` for every
downstream milestone.

``ContractResult`` is **adjacent** to — not composed with —
``RunEnvelope`` / ``RuntimeEnvelope``: the envelopes carry run-level identity
and cross-cutting state, while ``ContractResult`` is a per-step / per-seam
**result**.

The evidence-by-reference type is named :class:`EvidenceArtifactRef` (not
``ArtifactRef``) to avoid a collision with the Pydantic ``ArtifactRef`` row
in ``arnold/pipelines/megaplan/store/base.py:147``; the two types are
semantically different (one is a megaplan storage row, the other a neutral
evidence pointer) and keeping distinct names eliminates any import-collision
risk.

``CONTRACT_RESULT_SCHEMA_VERSION`` is deliberately a SHA-256 hex string
(content-addressed structural shape, to be hashed by ~50–100 pipelines and
re-validated at every seam) while ``RUNTIME_ENVELOPE_SCHEMA_VERSION`` is an
``int`` migration counter for a single owner's run-level envelope.  Both
forms are valid; callers cross-checking schema versions across types MUST
treat them as type-distinct namespaces.
"""

from __future__ import annotations

import hashlib
import json
import re as _re
from dataclasses import dataclass, field, fields as _dc_fields
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, TypeAlias, runtime_checkable


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Edge:
    """A labelled transition from one stage to another.

    ``label`` is the dispatch key used by the executor (matched against
    ``StepResult.next``).  ``target`` names the next stage in
    ``Pipeline.stages``.  The reserved target ``'halt'`` terminates the
    pipeline.  ``kind`` is always ``str`` at the Arnold boundary — no
    opinionated EdgeKind literal.
    """

    label: str
    target: str
    kind: str = "normal"
    recommendation: str | None = None


# ---------------------------------------------------------------------------
# PipelineVerdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineVerdict:
    """Structured output of a judge-style Step.

    ``score`` is a float (conventionally [0.0, 1.0] but not enforced).
    ``flags`` and ``notes`` are free-form.  ``payload`` is an opaque
    ``Mapping`` for arbitrary structured detail.

    ``recommendation`` and ``override`` are ``str | None`` — the Arnold
    boundary keeps them as plain strings; opinionated literal narrowing
    belongs to the consuming runtime.
    """

    score: float
    flags: tuple[str, ...] = ()
    notes: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    recommendation: str | None = None
    override: str | None = None


# ---------------------------------------------------------------------------
# StepContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepContext:
    """Runtime context passed to every ``Step.run`` invocation.

    ``artifact_root`` is the root directory for artifacts produced by the
    step (neutral name — no ``plan_dir``).  ``state`` is opaque (``Any``)
    so that consumers can supply their own state shape.  ``resource_handles``
    is a generic ``Mapping[str, Any]`` for passing opaque resources (file
    handles, API clients, etc.).  ``mode`` is a plain string with no
    enforced literal set at this boundary.  ``inputs`` maps label strings
    to paths or other typed values.
    """

    artifact_root: str
    state: Any
    resource_handles: Mapping[str, Any] = field(default_factory=dict)
    mode: str = "default"
    inputs: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# StepResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepResult:
    """What a ``Step.run`` invocation returns.

    ``outputs`` maps a label to an arbitrary value (typically a filesystem
    path).  ``verdict`` is an optional ``PipelineVerdict`` for judge-style
    steps.  ``next`` is matched against the enclosing stage's edges (with
    ``'halt'`` reserved as the terminal sentinel).  ``state_patch`` is a
    ``Mapping`` that the executor applies to working state.
    """

    outputs: Mapping[str, Any] = field(default_factory=dict)
    verdict: PipelineVerdict | None = None
    next: str = "halt"
    state_patch: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Step (Protocol)
# ---------------------------------------------------------------------------


@runtime_checkable
class Step(Protocol):
    """Structural protocol for pipeline steps.

    Implementations must expose ``name`` and ``kind`` as attributes, plus a
    ``run(ctx)`` method returning a ``StepResult``.  ``@runtime_checkable``
    enables ``isinstance(obj, Step)`` for sanity checks.

    The Arnold boundary keeps ``kind`` as a plain ``str`` — no opinionated
    ``Literal`` narrowing.  ``prompt_key``, ``slot``, ``produces``, and
    ``consumes`` are NOT part of this neutral surface (they are Megaplan
    concerns).
    """

    name: str
    kind: str

    def run(self, ctx: StepContext) -> StepResult: ...


# ---------------------------------------------------------------------------
# Stage  &  ParallelStage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    """A single-step stage with labelled outgoing edges.

    ``name`` identifies the stage within ``Pipeline.stages``.  ``step`` is
    the executable unit.  ``edges`` is the set of labelled transitions that
    the executor follows after the step completes.

    ``decision_vocabulary`` declares the set of valid decision strings
    that this stage may produce (e.g. ``frozenset({"proceed", "iterate"})``).
    An empty set means the stage does not participate in decision-typed
    routing — all dispatch is label-based.  ``override_vocabulary`` is the
    corresponding set of valid override-action strings (e.g.
    ``frozenset({"force_proceed", "abort"})``).  Both are plugin-owned:
    Arnold imposes no literal set; runtimes declare their own vocabulary.
    """

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()
    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    override_vocabulary: frozenset[str] = field(default_factory=frozenset)
    reads: tuple["ReadRef", ...] = field(default_factory=tuple)
    writes: tuple["WriteRef", ...] = field(default_factory=tuple)
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)
    loop_condition: Callable[[Any], bool] | None = None


@dataclass(frozen=True)
class ParallelStage:
    """A fan-out stage whose steps run concurrently and then barrier-join.

    ``steps`` is the tuple of concurrent units.  ``join`` receives the
    ordered list of ``StepResult`` values and the shared ``StepContext``,
    and returns a single ``StepResult`` whose ``next`` label dispatches
    like a regular ``Stage``.  ``max_workers`` caps the thread/process pool
    size (``None`` means unbounded).

    ``decision_vocabulary`` and ``override_vocabulary`` serve the same
    purpose as in :class:`Stage` — they declare the set of valid decision
    and override-action strings for the join result's dispatch.
    """

    name: str
    steps: tuple[Step, ...]
    join: Callable[[list[StepResult], StepContext], StepResult]
    edges: tuple[Edge, ...] = ()
    max_workers: int | None = None
    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    override_vocabulary: frozenset[str] = field(default_factory=frozenset)
    reads: tuple["ReadRef", ...] = field(default_factory=tuple)
    writes: tuple["WriteRef", ...] = field(default_factory=tuple)
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)
    loop_condition: Callable[[Any], bool] | None = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pipeline:
    """A named directed graph of stages with an entry point.

    ``stages`` maps stage names to ``Stage`` or ``ParallelStage`` values.
    ``entry`` is the name of the stage where execution begins.

    Notable omissions from the Megaplan counterpart:
    * No ``overlays`` — overlays are a Megaplan opinion.
    * No ``binding_map`` — typed-port binding is a Megaplan concern.
    * No ``builder()`` or ``run_phase()`` classmethods — those belong to
      the opinionated runtime.
    """

    stages: Mapping[str, Stage | ParallelStage]
    entry: str
    binding_map: dict | None = None
    resource_bundles: tuple[Any, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Typed Port primitives (concrete, neutral dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Port:
    """A named typed port that declares its content type.

    Every pipeline Step declares zero-or-more ports via ``produces`` and
    ``consumes``.  The executor uses these declarations for
    contract-level validation and routing-key construction when
    typed-port support is enabled by the consuming runtime.

    ``taint`` is a frozenset of security/trust labels (e.g.
    ``frozenset({"secret", "pii"})``) that are propagated through the
    dependency graph by the runtime's taint engine.
    """

    name: str
    content_type: str
    taint: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class PortRef:
    """A reference to a named port with its declared content type."""

    port_name: str
    content_type: str


@dataclass(frozen=True)
class RoutingKey:
    """A content-type–qualified routing key for fan-out dispatch.

    Concretely::

        RoutingKey(key="text/markdown")

    The executor constructs routing keys formed from the
    content type declared on a producing port.
    """

    key: str


# ---------------------------------------------------------------------------
# Dataflow reference wrappers (neutral carriers)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadRef:
    """A reference to data read by a stage.

    ``name`` identifies the data artifact.  ``optional`` means the
    stage can proceed if the data is absent.  ``external`` marks data
    sourced from outside the pipeline (e.g. user-provided files).
    ``late_bound`` means the referent is resolved at runtime rather
    than at construction time.
    """

    name: str
    optional: bool = False
    external: bool = False
    late_bound: bool = False


@dataclass(frozen=True)
class WriteRef:
    """A reference to data written by a stage.

    ``name`` identifies the data artifact.  ``optional`` means the
    write is best-effort (the pipeline can continue if it fails).
    ``external`` marks an output destined for a consumer outside the
    pipeline.  ``late_bound`` means the referent is resolved at
    runtime rather than at construction time.
    """

    name: str
    optional: bool = False
    external: bool = False
    late_bound: bool = False


@dataclass(frozen=True)
class BindingRef:
    """A reference to a typed-port binding between stages.

    ``name`` identifies the binding.  ``optional`` means the binding
    may be elided when the target port is absent.  ``external`` marks
    a binding that crosses a pipeline boundary.  ``late_bound`` means
    the binding target is resolved at runtime rather than at
    construction time.
    """

    name: str
    optional: bool = False
    external: bool = False
    late_bound: bool = False


# ---------------------------------------------------------------------------
# Content type registry
# ---------------------------------------------------------------------------


def _canonical_json_dumps(value: Any) -> str:
    """Serialize *value* deterministically with sorted keys.

    Mirrors :func:`megaplan.store.snapshot.canonical_json_dumps` but kept
    local so the ``arnold.pipeline`` package has zero dependency on the
    store layer.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def register_schema(schema_obj: Any) -> str:
    """Return the deterministic SHA-256 hex digest of *schema_obj*'s
    canonical JSON representation.

    ``schema_obj`` may be any JSON-serialisable value (typically a
    ``dict``, ``list``, or Pydantic ``BaseModel``).  The returned string
    is the raw hex digest (no ``sha256:`` prefix) so callers can format
    the prefix as they wish.
    """
    raw = _canonical_json_dumps(schema_obj)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ContentTypeRegistry:
    """Map content-type names → schema SHA-256 digests.

    Mirrors :class:`PipelineRegistry` (``registry.py``) but for
    content-type schemas instead of pipeline builders.  Duplicate
    registration raises ``ValueError``.
    """

    _schemas: dict[str, str] = field(default_factory=dict)

    def register(self, name: str, schema_obj: Any) -> str:
        if name in self._schemas:
            raise ValueError(f"content type {name!r} already registered")
        digest = register_schema(schema_obj)
        self._schemas[name] = digest
        return digest

    def get(self, name: str) -> str:
        """Return the SHA-256 digest registered for *name*.

        Raises ``KeyError`` when *name* is not registered.
        """
        if name not in self._schemas:
            raise KeyError(
                f"no content type named {name!r}; "
                f"available: {sorted(self._schemas)}"
            )
        return self._schemas[name]

    def __contains__(self, name: str) -> bool:
        return name in self._schemas

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._schemas))


# ── Module-level builtins ───────────────────────────────────────────────

_BUILTIN_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/markdown",
        "image/png",
        "application/x-git-diff",
        "application/x-verdict+json",
        "application/x-routing-key+json",
        "application/x-fanout-results+json",
        "application/x-evaluand-record+json",
    }
)

CONTENT_TYPES = ContentTypeRegistry()
for _ct in sorted(_BUILTIN_CONTENT_TYPES):
    CONTENT_TYPES.register(_ct, {"content_type": _ct})


# ---------------------------------------------------------------------------
# Reduce / Selection result primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReduceResult:
    """Structured output of a reduce-kind step.

    ``value`` is the reduced value; ``scores`` is a per-input ordered
    tuple of floats; ``tally`` is a mapping of label → count; ``provenance``
    records source step / port identifiers; ``label`` optionally names
    the chosen variant (e.g. ``"winner"``).
    """

    value: Any
    scores: tuple[float, ...] = ()
    tally: Mapping[str, int] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()
    label: str | None = None


@dataclass(frozen=True)
class SelectionResult:
    """Structured output of a selection / tournament reduce.

    ``winner`` is the selected index; ``subset`` are the candidates
    that survived an earlier filter; ``losers`` are the eliminated
    candidates; ``scores`` is per-candidate; ``cleared`` is true when the
    decision unambiguously cleared the tiebreaker threshold.
    """

    winner: int
    subset: tuple[int, ...] = ()
    losers: tuple[int, ...] = ()
    scores: tuple[float, ...] = ()
    cleared: bool = False


# ---------------------------------------------------------------------------
# ContractResult and friends — single shared seam primitive
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceArtifactRef:
    """Reference to an evidence artifact stored elsewhere.

    Named ``EvidenceArtifactRef`` (not ``ArtifactRef``) to avoid collision
    with ``arnold.pipelines.megaplan.store.base.ArtifactRef``.
    """

    uri: str
    content_type: str
    digest: str | None = None
    size_bytes: int | None = None
    name: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "content_type": self.content_type,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "name": self.name,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "EvidenceArtifactRef":
        return cls(
            uri=str(data.get("uri", "")),
            content_type=str(data.get("content_type", "")),
            digest=data.get("digest"),
            size_bytes=data.get("size_bytes"),
            name=data.get("name"),
        )


class ContractStatus(str, Enum):
    """3-value discriminant for :class:`ContractResult`."""

    COMPLETED = "completed"
    SUSPENDED = "suspended"
    FAILED = "failed"


@dataclass(frozen=True)
class Suspension:
    """Typed interaction envelope for ``status == SUSPENDED``.

    All baked fields are present; only ``kind="human"`` semantics are
    implemented downstream in this milestone — other ``kind`` values
    (``"render-job"`` / ``"quota"`` / ``"upload"``) are reserved.
    """

    kind: str
    awaitable: str | None = None
    prompt: str = ""
    display_refs: tuple[EvidenceArtifactRef, ...] = field(default_factory=tuple)
    resume_input_schema: Mapping[str, Any] = field(default_factory=dict)
    resume_cursor: str | None = None
    thread_ref: str | None = None
    actor: str | None = None
    deadline: str | None = None
    on_timeout: str | None = None
    default_action: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "awaitable": self.awaitable,
            "prompt": self.prompt,
            "display_refs": [r.to_json() for r in self.display_refs],
            "resume_input_schema": dict(self.resume_input_schema),
            "resume_cursor": self.resume_cursor,
            "thread_ref": self.thread_ref,
            "actor": self.actor,
            "deadline": self.deadline,
            "on_timeout": self.on_timeout,
            "default_action": self.default_action,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Suspension":
        refs = tuple(
            EvidenceArtifactRef.from_json(r)
            for r in (data.get("display_refs") or ())
        )
        return cls(
            kind=str(data.get("kind", "")),
            awaitable=data.get("awaitable"),
            prompt=str(data.get("prompt", "")),
            display_refs=refs,
            resume_input_schema=dict(data.get("resume_input_schema") or {}),
            resume_cursor=data.get("resume_cursor"),
            thread_ref=data.get("thread_ref"),
            actor=data.get("actor"),
            deadline=data.get("deadline"),
            on_timeout=data.get("on_timeout"),
            default_action=data.get("default_action"),
        )


@dataclass(frozen=True)
class Provenance:
    """Lineage of a :class:`ContractResult`.

    ``generator`` encodes tool/version inline (e.g. ``"scanner@1.2"``);
    ``sources`` may include policy refs (e.g. ``"policy:<id>"``) — degenerate
    fields are deferred until a real consumer demands the split.
    """

    sources: tuple[str, ...] = ()
    generator: str | None = None
    generated_at: str | None = None
    chain: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "generator": self.generator,
            "generated_at": self.generated_at,
            "chain": list(self.chain),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Provenance":
        return cls(
            sources=tuple(data.get("sources") or ()),
            generator=data.get("generator"),
            generated_at=data.get("generated_at"),
            chain=tuple(data.get("chain") or ()),
        )


@dataclass(frozen=True)
class Freshness:
    """Time-to-live envelope for a :class:`ContractResult`."""

    observed_at: str | None = None
    ttl_seconds: int | None = None
    expires_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at,
            "ttl_seconds": self.ttl_seconds,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Freshness":
        return cls(
            observed_at=data.get("observed_at"),
            ttl_seconds=data.get("ttl_seconds"),
            expires_at=data.get("expires_at"),
        )


@dataclass(frozen=True)
class ContractResult:
    """The single shared seam primitive.

    ``payload`` is opaque ``Mapping[str, Any]`` — callers are responsible
    for ensuring it contains only ``json.dumps``-compatible values. To
    embed an :class:`EvidenceArtifactRef` inside payload, pass
    ``ref.to_json()`` (a plain dict), not the dataclass.

    ``authority_level`` is a free ``str``; conventional values are
    ``"asserted"`` / ``"verified"`` / ``"advisory"``. Closed-enum
    tightening is a downstream concern.

    No ``status`` / ``suspension`` consistency validation is enforced here
    (m0b's concern); the conventional pairing is
    ``status == SUSPENDED`` ⇔ ``suspension is not None``.
    """

    payload: Mapping[str, Any] = field(default_factory=dict)
    status: ContractStatus = ContractStatus.COMPLETED
    schema_version: str = ""
    suspension: Suspension | None = None
    evidence_refs: tuple[EvidenceArtifactRef, ...] = field(default_factory=tuple)
    authority_level: str = ""
    provenance: Provenance = field(default_factory=Provenance)
    freshness: Freshness = field(default_factory=Freshness)

    def __post_init__(self) -> None:
        if not self.schema_version:
            object.__setattr__(self, "schema_version", CONTRACT_RESULT_SCHEMA_VERSION)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "payload": dict(self.payload),
            "suspension": self.suspension.to_json() if self.suspension else None,
            "evidence_refs": [r.to_json() for r in self.evidence_refs],
            "authority_level": self.authority_level,
            "provenance": self.provenance.to_json(),
            "freshness": self.freshness.to_json(),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ContractResult":
        persisted = data.get("schema_version")
        if persisted is not None and persisted != "" and persisted != CONTRACT_RESULT_SCHEMA_VERSION:
            raise ValueError(
                f"ContractResult schema_version mismatch: persisted={persisted!r}, "
                f"expected={CONTRACT_RESULT_SCHEMA_VERSION!r}"
            )
        sus = data.get("suspension")
        return cls(
            payload=dict(data.get("payload") or {}),
            status=ContractStatus(data.get("status", "completed")),
            schema_version=str(persisted or CONTRACT_RESULT_SCHEMA_VERSION),
            suspension=Suspension.from_json(sus) if isinstance(sus, Mapping) else None,
            evidence_refs=tuple(
                EvidenceArtifactRef.from_json(r)
                for r in (data.get("evidence_refs") or ())
            ),
            authority_level=str(data.get("authority_level", "")),
            provenance=Provenance.from_json(data.get("provenance") or {}),
            freshness=Freshness.from_json(data.get("freshness") or {}),
        )


def _normalise_type_name(t: Any) -> str:
    s = t if isinstance(t, str) else str(t)
    s = _re.sub(r"\s+", "", s)
    s = _re.sub(r"typing\.", "", s)
    return s


_CONTRACT_RESULT_DESCRIPTOR: dict[str, str] = {
    f.name: _normalise_type_name(f.type) for f in _dc_fields(ContractResult)
}
CONTRACT_RESULT_SCHEMA_VERSION: str = register_schema(_CONTRACT_RESULT_DESCRIPTOR)
