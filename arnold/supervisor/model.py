"""Shared supervisor data model for chain and bakeoff orchestration.

The supervisor tier needs one persisted shape that can represent both the
serial chain variant and the bakeoff variant that fans out multiple runs in an
explicit parallel group before reducing to a winner.  This module only defines
the data model and JSON-friendly serialization helpers; persistence and
dependency validation live in ``megaplan.supervisor.state``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from arnold.pipelines.megaplan.run_outcome import RunOutcome


class SupervisorVariantKind(StrEnum):
    """Supported supervisor orchestration variants."""

    CHAIN = "chain"
    BAKEOFF = "bakeoff"


@dataclass(frozen=True)
class DependencyAssertion:
    """Declarative dependency requirement for one run node.

    Chain keeps sequential DAG semantics: the dependency list is an assertion
    that referenced nodes must already appear earlier in the persisted node
    order.  Bakeoff can additionally group sibling nodes under an explicit
    ``BakeoffParallelGroup`` while still declaring any upstream prerequisites
    here.
    """

    node_id: str
    depends_on: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DependencyAssertion":
        depends_on_raw = raw.get("depends_on") or []
        if isinstance(depends_on_raw, str):
            depends_on = (depends_on_raw,)
        elif isinstance(depends_on_raw, list):
            depends_on = tuple(
                item for item in depends_on_raw if isinstance(item, str) and item
            )
        else:
            depends_on = ()
        return cls(
            node_id=str(raw.get("node_id", "")),
            depends_on=depends_on,
        )


@dataclass(frozen=True)
class BakeoffParallelGroup:
    """Explicit fan-out unit for the bakeoff supervisor variant."""

    group_id: str
    member_node_ids: tuple[str, ...]
    comparison_node_id: str | None = None
    selection_node_id: str | None = None
    merge_node_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "member_node_ids": list(self.member_node_ids),
            "comparison_node_id": self.comparison_node_id,
            "selection_node_id": self.selection_node_id,
            "merge_node_id": self.merge_node_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BakeoffParallelGroup":
        members_raw = raw.get("member_node_ids") or []
        if isinstance(members_raw, str):
            member_node_ids = (members_raw,)
        elif isinstance(members_raw, list):
            member_node_ids = tuple(
                item for item in members_raw if isinstance(item, str) and item
            )
        else:
            member_node_ids = ()
        return cls(
            group_id=str(raw.get("group_id", "")),
            member_node_ids=member_node_ids,
            comparison_node_id=_optional_str(raw.get("comparison_node_id")),
            selection_node_id=_optional_str(raw.get("selection_node_id")),
            merge_node_id=_optional_str(raw.get("merge_node_id")),
        )


@dataclass(frozen=True)
class RunNode:
    """One supervisor-managed run node.

    ``spec_ref`` is variant-defined: for chain it will usually be a milestone
    label; for bakeoff it can be a profile name or reducer step identifier.
    ``metadata`` carries variant-local details without forcing the shared model
    to understand chain YAML or bakeoff comparison internals.
    """

    node_id: str
    spec_ref: str
    description: str | None = None
    parallel_group_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "spec_ref": self.spec_ref,
            "description": self.description,
            "parallel_group_id": self.parallel_group_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RunNode":
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            node_id=str(raw.get("node_id", "")),
            spec_ref=str(raw.get("spec_ref", "")),
            description=_optional_str(raw.get("description")),
            parallel_group_id=_optional_str(raw.get("parallel_group_id")),
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class RunRecord:
    """Persisted neutral record for one run attempt."""

    node_id: str
    attempt: int
    outcome: RunOutcome | None = None
    original_status: str | None = None
    plan_id: str | None = None
    final_state: str | None = None
    current_state: str | None = None
    reason: str | None = None
    last_phase: str | None = None
    resume_cursor: dict[str, Any] | None = None
    blocking_reasons: tuple[str, ...] = ()
    total_cost_usd: float | None = None
    tier_escalations_used: int = 0
    escalation_tier_pin: int | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "attempt": self.attempt,
            "outcome": self.outcome.value if self.outcome is not None else None,
            "original_status": self.original_status,
            "plan_id": self.plan_id,
            "final_state": self.final_state,
            "current_state": self.current_state,
            "reason": self.reason,
            "last_phase": self.last_phase,
            "resume_cursor": dict(self.resume_cursor) if self.resume_cursor else None,
            "blocking_reasons": list(self.blocking_reasons),
            "total_cost_usd": self.total_cost_usd,
            "tier_escalations_used": self.tier_escalations_used,
            "escalation_tier_pin": self.escalation_tier_pin,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RunRecord":
        outcome = _parse_run_outcome(raw.get("outcome"))
        resume_cursor = raw.get("resume_cursor")
        if not isinstance(resume_cursor, dict):
            resume_cursor = None
        blocking_raw = raw.get("blocking_reasons") or []
        if isinstance(blocking_raw, str):
            blocking_reasons = (blocking_raw,)
        elif isinstance(blocking_raw, list):
            blocking_reasons = tuple(
                item for item in blocking_raw if isinstance(item, str) and item
            )
        else:
            blocking_reasons = ()
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            node_id=str(raw.get("node_id", "")),
            attempt=int(raw.get("attempt", 0)),
            outcome=outcome,
            original_status=_optional_str(raw.get("original_status")),
            plan_id=_optional_str(raw.get("plan_id")),
            final_state=_optional_str(raw.get("final_state")),
            current_state=_optional_str(raw.get("current_state")),
            reason=_optional_str(raw.get("reason")),
            last_phase=_optional_str(raw.get("last_phase")),
            resume_cursor=dict(resume_cursor) if resume_cursor is not None else None,
            blocking_reasons=blocking_reasons,
            total_cost_usd=_optional_float(raw.get("total_cost_usd")),
            tier_escalations_used=int(raw.get("tier_escalations_used", 0)),
            escalation_tier_pin=_optional_int(raw.get("escalation_tier_pin")),
            pr_number=_optional_int(raw.get("pr_number")),
            pr_state=_optional_str(raw.get("pr_state")),
            metadata=dict(metadata),
        )


@dataclass
class SupervisorState:
    """Persisted supervisor state shared by chain and bakeoff runners."""

    variant: SupervisorVariantKind
    run_nodes: list[RunNode]
    dependency_assertions: list[DependencyAssertion] = field(default_factory=list)
    run_records: list[RunRecord] = field(default_factory=list)
    bakeoff_parallel_groups: list[BakeoffParallelGroup] = field(default_factory=list)
    current_node_id: str | None = None
    completed_node_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "variant": self.variant.value,
            "run_nodes": [node.to_dict() for node in self.run_nodes],
            "dependency_assertions": [
                assertion.to_dict() for assertion in self.dependency_assertions
            ],
            "run_records": [record.to_dict() for record in self.run_records],
            "bakeoff_parallel_groups": [
                group.to_dict() for group in self.bakeoff_parallel_groups
            ],
            "current_node_id": self.current_node_id,
            "completed_node_ids": list(self.completed_node_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SupervisorState":
        variant = SupervisorVariantKind(raw.get("variant", "chain"))
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        run_nodes_raw = raw.get("run_nodes") or []
        dependency_assertions_raw = raw.get("dependency_assertions") or []
        run_records_raw = raw.get("run_records") or []
        bakeoff_groups_raw = raw.get("bakeoff_parallel_groups") or []
        completed_node_ids_raw = raw.get("completed_node_ids") or []
        return cls(
            schema_version=int(raw.get("schema_version", 1)),
            variant=variant,
            run_nodes=[
                RunNode.from_dict(item)
                for item in run_nodes_raw
                if isinstance(item, dict)
            ],
            dependency_assertions=[
                DependencyAssertion.from_dict(item)
                for item in dependency_assertions_raw
                if isinstance(item, dict)
            ],
            run_records=[
                RunRecord.from_dict(item)
                for item in run_records_raw
                if isinstance(item, dict)
            ],
            bakeoff_parallel_groups=[
                BakeoffParallelGroup.from_dict(item)
                for item in bakeoff_groups_raw
                if isinstance(item, dict)
            ],
            current_node_id=_optional_str(raw.get("current_node_id")),
            completed_node_ids=[
                item
                for item in completed_node_ids_raw
                if isinstance(item, str) and item
            ],
            metadata=dict(metadata),
        )


def dependency_assertions_for_nodes(nodes: list[RunNode]) -> list[DependencyAssertion]:
    """Project dependency assertions from ``RunNode.metadata['depends_on']``.

    The shared model keeps dependencies explicit as first-class assertions, but
    early chain/bakeoff conversion code can still attach a ``depends_on`` list
    inside node metadata while the runners are being extracted.
    """

    assertions: list[DependencyAssertion] = []
    for node in nodes:
        depends_on_raw = node.metadata.get("depends_on", [])
        if isinstance(depends_on_raw, str):
            depends_on = (depends_on_raw,)
        elif isinstance(depends_on_raw, list):
            depends_on = tuple(
                item for item in depends_on_raw if isinstance(item, str) and item
            )
        else:
            depends_on = ()
        assertions.append(DependencyAssertion(node_id=node.node_id, depends_on=depends_on))
    return assertions


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_run_outcome(value: Any) -> RunOutcome | None:
    if value is None:
        return None
    try:
        return RunOutcome(str(value))
    except ValueError:
        return None


__all__ = [
    "BakeoffParallelGroup",
    "DependencyAssertion",
    "RunNode",
    "RunRecord",
    "SupervisorState",
    "SupervisorVariantKind",
    "dependency_assertions_for_nodes",
]
