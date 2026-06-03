"""Neutral frozen dataclasses and Protocol for the Arnold pipeline boundary.

This module defines the pure-data, opinion-free type surface that any
pipeline runtime can consume.  Opinionated vocabulary (typed gate/override
literals, run envelopes, plan directories, profiles, budgets) is deliberately
excluded — this is the *structural* skeleton only.

Sub-module of ``arnold.pipeline``.  Import from here or from the parent
package once ``arnold/pipeline/__init__.py`` re-exports are wired.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
    """

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()


@dataclass(frozen=True)
class ParallelStage:
    """A fan-out stage whose steps run concurrently and then barrier-join.

    ``steps`` is the tuple of concurrent units.  ``join`` receives the
    ordered list of ``StepResult`` values and the shared ``StepContext``,
    and returns a single ``StepResult`` whose ``next`` label dispatches
    like a regular ``Stage``.  ``max_workers`` caps the thread/process pool
    size (``None`` means unbounded).
    """

    name: str
    steps: tuple[Step, ...]
    join: Callable[[list[StepResult], StepContext], StepResult]
    edges: tuple[Edge, ...] = ()
    max_workers: int | None = None


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
