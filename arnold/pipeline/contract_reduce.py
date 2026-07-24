"""Status-lattice reduction for composed ``ContractResult`` values.

This reducer is shared by suspension-aware composition paths that need a
deterministic parent contract without mutating the frozen m0a dataclasses.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Provenance,
    Suspension,
)

__all__ = ["ReducePolicy", "reduce_contract_results"]

_STATUS_RANK: dict[ContractStatus, int] = {
    ContractStatus.COMPLETED: 0,
    ContractStatus.SUSPENDED: 1,
    ContractStatus.FAILED: 2,
}
_STATUS_LATTICE = "completed<suspended<failed"


class ReducePolicy(str, Enum):
    """Reserved reducer-policy vocabulary for composed contracts."""

    MAX_WINS = "max_wins"
    QUORUM = "quorum"
    BEST_EFFORT = "best_effort"
    BUDGET = "budget"
    SATURATION = "saturation"


def reduce_contract_results(
    results: Iterable[ContractResult | None],
    *,
    reduce_policy: ReducePolicy = ReducePolicy.MAX_WINS,
    suspension_scope: str | None = None,
    child_ids: Iterable[str] | None = None,
) -> ContractResult:
    """Reduce child contracts into one parent contract.

    ``MAX_WINS`` implements the settled status lattice
    ``completed < suspended < failed``. ``None`` inputs are treated as
    implicit completed children so fan-out callers can keep positional
    alignment between results and child identifiers.
    """

    if reduce_policy is not ReducePolicy.MAX_WINS:
        raise NotImplementedError(f"reduce_policy={reduce_policy.value!r} is not implemented")
    if suspension_scope is not None:
        raise NotImplementedError("suspension_scope is reserved for a later milestone")

    result_items = tuple(results)
    resolved_child_ids = _resolve_child_ids(result_items, child_ids)
    entries = tuple(
        _ChildEntry(
            child_id=child_id,
            contract=contract,
            status=(contract.status if contract is not None else ContractStatus.COMPLETED),
        )
        for child_id, contract in zip(resolved_child_ids, result_items)
    )

    winner = _select_winner(entries)
    pending_suspensions = _pending_suspension_payload(entries)
    payload: dict[str, object] = {
        "reduce_policy": reduce_policy.value,
        "status_lattice": _STATUS_LATTICE,
        "source_contracts": [_source_contract_payload(entry) for entry in entries],
    }
    if pending_suspensions:
        payload["pending_suspensions"] = pending_suspensions

    return ContractResult(
        payload=payload,
        status=winner.status if winner is not None else ContractStatus.COMPLETED,
        suspension=_compose_suspension(entries),
        evidence_refs=_merge_evidence_refs(entries),
        authority_level=_winner_field(winner, "authority_level", default=""),
        provenance=_merge_provenance(entries, winner),
        freshness=_winner_field(winner, "freshness", default=Freshness()),
    )


class _ChildEntry:
    __slots__ = ("child_id", "contract", "status")

    def __init__(
        self,
        *,
        child_id: str,
        contract: ContractResult | None,
        status: ContractStatus,
    ) -> None:
        self.child_id = child_id
        self.contract = contract
        self.status = status


def _resolve_child_ids(
    results: tuple[ContractResult | None, ...],
    child_ids: Iterable[str] | None,
) -> tuple[str, ...]:
    if child_ids is None:
        return tuple(f"child_{index}" for index in range(len(results)))
    resolved = tuple(str(child_id) for child_id in child_ids)
    if len(resolved) != len(results):
        raise ValueError("child_ids length must match the number of reduced results")
    return resolved


def _select_winner(entries: tuple[_ChildEntry, ...]) -> _ChildEntry | None:
    winner: _ChildEntry | None = None
    winner_rank = -1
    for entry in entries:
        rank = _STATUS_RANK[entry.status]
        if rank > winner_rank:
            winner = entry
            winner_rank = rank
    return winner


def _source_contract_payload(entry: _ChildEntry) -> dict[str, object]:
    contract = entry.contract
    return {
        "child_id": entry.child_id,
        "status": entry.status.value,
        "contract": contract.to_json() if contract is not None else None,
    }


def _pending_suspension_payload(entries: tuple[_ChildEntry, ...]) -> list[dict[str, object]]:
    pending: list[dict[str, object]] = []
    for entry in entries:
        suspension = entry.contract.suspension if entry.contract is not None else None
        if entry.status is not ContractStatus.SUSPENDED or suspension is None:
            continue
        pending.append(
            {
                "child_id": entry.child_id,
                "status": entry.status.value,
                "cursor": suspension.resume_cursor,
                "suspension": suspension.to_json(),
            }
        )
    return pending


def _compose_suspension(entries: tuple[_ChildEntry, ...]) -> Suspension | None:
    suspended = tuple(
        entry for entry in entries
        if entry.status is ContractStatus.SUSPENDED
        and entry.contract is not None
        and entry.contract.suspension is not None
    )
    if not suspended:
        return None
    if len(suspended) == 1:
        return suspended[0].contract.suspension

    suspensions = tuple(entry.contract.suspension for entry in suspended)
    prompt = "Awaiting input from suspended child steps"
    display_refs = _merge_display_refs(suspensions)
    properties = {
        entry.child_id: {
            "type": "object",
            "description": f"Resume payload for suspended child '{entry.child_id}'",
        }
        for entry in suspended
    }
    return Suspension(
        kind="composite_suspension",
        awaitable=_shared_value(suspensions, "awaitable") or "all",
        prompt=prompt,
        display_refs=display_refs,
        resume_input_schema={
            "type": "object",
            "properties": properties,
            "required": [entry.child_id for entry in suspended],
            "additionalProperties": False,
        },
        resume_cursor=None,
        thread_ref=_shared_value(suspensions, "thread_ref"),
        actor=_shared_value(suspensions, "actor"),
        deadline=_shared_value(suspensions, "deadline"),
        on_timeout=_shared_value(suspensions, "on_timeout"),
        default_action=_shared_value(suspensions, "default_action"),
    )


def _merge_display_refs(suspensions: tuple[Suspension, ...]) -> tuple[EvidenceArtifactRef, ...]:
    merged: list[EvidenceArtifactRef] = []
    seen: set[tuple[str, str, str | None, int | None, str | None]] = set()
    for suspension in suspensions:
        for ref in suspension.display_refs:
            key = (ref.uri, ref.content_type, ref.digest, ref.size_bytes, ref.name)
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
    return tuple(merged)


def _merge_evidence_refs(entries: tuple[_ChildEntry, ...]) -> tuple[EvidenceArtifactRef, ...]:
    merged: list[EvidenceArtifactRef] = []
    seen: set[tuple[str, str, str | None, int | None, str | None]] = set()
    for entry in entries:
        contract = entry.contract
        if contract is None:
            continue
        for ref in contract.evidence_refs:
            key = (ref.uri, ref.content_type, ref.digest, ref.size_bytes, ref.name)
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
    return tuple(merged)


def _merge_provenance(
    entries: tuple[_ChildEntry, ...],
    winner: _ChildEntry | None,
) -> Provenance:
    merged_sources: list[str] = []
    seen_sources: set[str] = set()
    chain: list[str] = []
    for entry in entries:
        contract = entry.contract
        if contract is None:
            continue
        for source in contract.provenance.sources:
            if source in seen_sources:
                continue
            seen_sources.add(source)
            merged_sources.append(source)
        chain.extend(contract.provenance.chain)
    return Provenance(
        sources=tuple(merged_sources),
        generator=_winner_field(winner, "provenance.generator"),
        generated_at=_winner_field(winner, "provenance.generated_at"),
        chain=tuple(chain),
    )


def _winner_field(winner: _ChildEntry | None, path: str, *, default: object = None) -> object:
    if winner is None or winner.contract is None:
        return default
    value: object = winner.contract
    for part in path.split("."):
        value = getattr(value, part)
    return value


def _shared_value(suspensions: tuple[Suspension, ...], field_name: str) -> str | None:
    values = {getattr(suspension, field_name) for suspension in suspensions}
    if len(values) == 1:
        return next(iter(values))
    return None
