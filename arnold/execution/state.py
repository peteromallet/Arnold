"""Routing state containers for deterministic manifest projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arnold.manifest import WorkflowManifest


_UNSET = object()


@dataclass(frozen=True, order=True)
class RouteCoordinate:
    """A deterministic coordinate inside a routing projection.

    ``scope_stack`` captures nested subpipeline scopes. ``attempt`` counts
    retries, ``iteration`` counts loop reentries, and ``child_key`` identifies
    a fanout child.
    """

    node_ref: str
    scope_stack: tuple[str, ...] = ()
    attempt: int = 1
    iteration: int = 1
    child_key: str | None = None

    def replace(
        self,
        *,
        node_ref: str | None = None,
        scope_stack: tuple[str, ...] | None = None,
        attempt: int | None = None,
        iteration: int | None = None,
        child_key: str | None | object = _UNSET,
    ) -> "RouteCoordinate":
        return RouteCoordinate(
            node_ref=node_ref if node_ref is not None else self.node_ref,
            scope_stack=scope_stack if scope_stack is not None else self.scope_stack,
            attempt=attempt if attempt is not None else self.attempt,
            iteration=iteration if iteration is not None else self.iteration,
            child_key=self.child_key if child_key is _UNSET else child_key,
        )


@dataclass(frozen=True)
class LoopProjection:
    """Current loop state for a coordinate."""

    coordinate: RouteCoordinate
    current_iteration: int
    max_iterations: int | None


@dataclass(frozen=True)
class RetryProjection:
    """Current retry state for a coordinate."""

    coordinate: RouteCoordinate
    current_attempt: int
    max_attempts: int


@dataclass(frozen=True)
class FanoutProjection:
    """Fanout children and reducer ordering for a fanout node."""

    parent: RouteCoordinate
    width: int
    children: tuple[RouteCoordinate, ...]
    reducer_coordinate: RouteCoordinate | None = None


@dataclass
class RoutingState:
    """Deterministic projection of runnable workflow state.

    State is derived from the manifest plus journal events, never from mutable
    overwrite-only runner state.
    """

    manifest: WorkflowManifest
    completed: set[RouteCoordinate] = field(default_factory=set)
    failed: set[RouteCoordinate] = field(default_factory=set)
    suspended: set[RouteCoordinate] = field(default_factory=set)
    ready: tuple[RouteCoordinate, ...] = ()
    blocked: tuple[RouteCoordinate, ...] = ()
    loops: dict[RouteCoordinate, LoopProjection] = field(default_factory=dict)
    retries: dict[RouteCoordinate, RetryProjection] = field(default_factory=dict)
    fanouts: dict[RouteCoordinate, FanoutProjection] = field(default_factory=dict)
    reducer_inputs: dict[RouteCoordinate, tuple[RouteCoordinate, ...]] = field(
        default_factory=dict
    )
    scope_hashes: dict[tuple[str, ...], str] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Whether all manifest nodes have been completed in their scopes."""

        return not self.ready and not self.suspended

    def node_is_completed(self, node_ref: str, scope_stack: tuple[str, ...] = ()) -> bool:
        return RouteCoordinate(node_ref=node_ref, scope_stack=scope_stack) in self.completed

    def node_is_failed(self, node_ref: str, scope_stack: tuple[str, ...] = ()) -> bool:
        return RouteCoordinate(node_ref=node_ref, scope_stack=scope_stack) in self.failed


__all__ = [
    "FanoutProjection",
    "LoopProjection",
    "RetryProjection",
    "RouteCoordinate",
    "RoutingState",
]
