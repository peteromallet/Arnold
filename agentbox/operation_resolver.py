"""Deterministic AgentBox operation resolver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

from arnold.runtime.durable_ops import OperationRun, OperationState, is_terminal_operation_state

from agentbox.operations import list_agentbox_operations


ResolveStatus = Literal["single", "no_match", "ambiguous"]


@dataclass(frozen=True)
class OperationResolveCandidate:
    """One resolver candidate with the reason it matched."""

    operation_id: str
    operation_type: str
    operation_state: str
    launch_state: str | None
    repo_names: tuple[str, ...]
    matched_by: str

    @classmethod
    def from_run(cls, run: OperationRun, *, matched_by: str) -> "OperationResolveCandidate":
        return cls(
            operation_id=run.id,
            operation_type=run.operation_type,
            operation_state=run.state.value,
            launch_state=_metadata_str(run.metadata, "launch_state"),
            repo_names=tuple(str(value) for value in run.metadata.get("repo_names", ())),
            matched_by=matched_by,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "operation_state": self.operation_state,
            "launch_state": self.launch_state,
            "repo_names": list(self.repo_names),
            "matched_by": self.matched_by,
        }


@dataclass(frozen=True)
class OperationResolveResult:
    """Stable resolver result for Discord tools and tests."""

    status: ResolveStatus
    query: str
    operation: OperationResolveCandidate | None = None
    candidates: tuple[OperationResolveCandidate, ...] = ()
    question: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "operation": self.operation.to_dict() if self.operation else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "question": self.question,
        }


def resolve_operation(
    config: Any,
    query: str,
    *,
    limit: int = 5,
) -> OperationResolveResult:
    """Resolve ``query`` to one AgentBox operation or one clarification question."""

    normalized = _normalize(query)
    runs = list_agentbox_operations(config)
    if not normalized:
        return OperationResolveResult(
            status="no_match",
            query=query,
            question="Which operation should I inspect?",
        )

    exact = [run for run in runs if _normalize(run.id) == normalized]
    if exact:
        candidates = _rank_runs(exact, query=normalized, matched_by="operation_id_exact")
    else:
        candidates = _rank_runs(
            [
                run
                for run in runs
                if _fuzzy_match_reason(run, normalized) is not None
            ],
            query=normalized,
            matched_by=None,
        )

    if not candidates:
        return OperationResolveResult(
            status="no_match",
            query=query,
            question=f"No AgentBox operation matched {query!r}. Which operation id should I use?",
        )
    if len(candidates) == 1:
        return OperationResolveResult(status="single", query=query, operation=candidates[0])

    limited = tuple(candidates[:limit])
    return OperationResolveResult(
        status="ambiguous",
        query=query,
        candidates=limited,
        question=_clarification_question(limited),
    )


def _rank_runs(
    runs: Sequence[OperationRun],
    *,
    query: str,
    matched_by: str | None,
) -> tuple[OperationResolveCandidate, ...]:
    ranked = sorted(
        runs,
        key=lambda run: (
            _match_priority(run, query, matched_by=matched_by),
            _state_priority(run),
            -int(run.updated_at.timestamp()),
            run.id,
        ),
    )
    return tuple(
        OperationResolveCandidate.from_run(
            run,
            matched_by=matched_by or _fuzzy_match_reason(run, query) or "metadata",
        )
        for run in ranked
    )


def _match_priority(run: OperationRun, query: str, *, matched_by: str | None) -> int:
    if matched_by == "operation_id_exact" or _normalize(run.id) == query:
        return 0
    reason = _fuzzy_match_reason(run, query)
    if reason == "operation_id_contains":
        return 1
    if reason == "metadata":
        return 2
    if reason == "operation_type":
        return 3
    return 4


def _state_priority(run: OperationRun) -> int:
    if _metadata_has_blocked(run):
        return 1
    if run.state is OperationState.RUNNING:
        return 0
    if run.state in {OperationState.SUSPENDED, OperationState.AWAITING_APPROVAL, OperationState.PENDING}:
        return 2
    if is_terminal_operation_state(run.state):
        return 3
    return 4


def _metadata_has_blocked(run: OperationRun) -> bool:
    values = " ".join(str(value).lower() for value in _metadata_values(run.metadata))
    return "blocked" in values


def _fuzzy_match_reason(run: OperationRun, query: str) -> str | None:
    if query in _normalize(run.id):
        return "operation_id_contains"
    if query in _normalize(run.operation_type):
        return "operation_type"
    for value in _metadata_values(run.metadata):
        if query in _normalize(str(value)):
            return "metadata"
    return None


def _metadata_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, dict):
        items: list[Any] = []
        for key, item in value.items():
            items.append(key)
            items.extend(_metadata_values(item))
        return tuple(items)
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            items.extend(_metadata_values(item))
        return tuple(items)
    return (value,)


def _clarification_question(candidates: Sequence[OperationResolveCandidate]) -> str:
    ids = ", ".join(candidate.operation_id for candidate in candidates[:3])
    return f"Which operation did you mean: {ids}?"


def _metadata_str(metadata: Any, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return str(value) if value is not None else None


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


__all__ = [
    "OperationResolveCandidate",
    "OperationResolveResult",
    "resolve_operation",
]
