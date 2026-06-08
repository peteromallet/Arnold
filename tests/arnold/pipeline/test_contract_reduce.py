"""Focused reducer tests for ``reduce_contract_results`` (M4 T2).

Covers empty / all-None / mixed inputs, all status combinations,
deterministic child ordering, failed+suspended cursor preservation,
composite suspension fields, JSON-compatible payloads, and
unimplemented policy / scope behavior.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from arnold.pipeline.contract_reduce import (
    ReducePolicy,
    reduce_contract_results,
)
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Provenance,
    Suspension,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suspension(
    *,
    child_hint: str = "",
    kind: str = "human",
    awaitable: str | None = None,
    thread_ref: str | None = None,
    actor: str | None = None,
    resume_cursor: str | None = None,
) -> Suspension:
    """Build a minimal Suspension for a child step."""
    prompt = f"Awaiting input for child {child_hint}" if child_hint else "Default prompt"
    return Suspension(
        kind=kind,
        awaitable=awaitable or f"awaitable/{child_hint}" if child_hint else None,
        prompt=prompt,
        resume_cursor=resume_cursor or f"cursor-{child_hint}" if child_hint else None,
        thread_ref=thread_ref,
        actor=actor,
    )


def _make_contract(
    *,
    status: ContractStatus,
    suspension: Suspension | None = None,
    payload_override: dict[str, Any] | None = None,
) -> ContractResult:
    """Construct a ContractResult for a single child."""
    payload: dict[str, Any] = {"source": "test"}
    if payload_override is not None:
        payload = payload_override
    return ContractResult(
        status=status,
        suspension=suspension,
        payload=payload,
    )


def _assert_json_serializable(obj: object) -> None:
    """Confirm that *obj* can be serialized and deserialized via json."""
    raw = json.dumps(obj, default=str)
    json.loads(raw)


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


def test_reduce_empty_results_defaults() -> None:
    """An empty iterable produces a completed contract with default fields."""
    result = reduce_contract_results([])
    assert result.status is ContractStatus.COMPLETED
    assert result.suspension is None
    assert isinstance(result.payload, dict)
    assert result.payload.get("reduce_policy") == "max_wins"
    assert result.payload.get("status_lattice") == "completed<suspended<failed"


def test_reduce_empty_results_explicit_child_ids_raises() -> None:
    """child_ids must match result count — mismatched lengths raise ValueError."""
    with pytest.raises(ValueError, match="child_ids length"):
        reduce_contract_results([], child_ids=["a"])


# ---------------------------------------------------------------------------
# All-None inputs
# ---------------------------------------------------------------------------


def test_reduce_all_none() -> None:
    """All-None results behave as implicit completed children."""
    result = reduce_contract_results([None])
    assert result.status is ContractStatus.COMPLETED
    assert result.suspension is None
    sources = result.payload.get("source_contracts", [])
    assert len(sources) == 1
    assert sources[0]["child_id"] == "child_0"
    assert sources[0]["status"] == "completed"
    assert sources[0]["contract"] is None


def test_reduce_all_none_multiple() -> None:
    """Multiple None entries all map to completed status."""
    result = reduce_contract_results([None, None, None])
    assert result.status is ContractStatus.COMPLETED
    sources = result.payload.get("source_contracts", [])
    assert len(sources) == 3
    for entry in sources:
        assert entry["status"] == "completed"
        assert entry["contract"] is None


# ---------------------------------------------------------------------------
# Mixed None / real inputs
# ---------------------------------------------------------------------------


def test_reduce_none_and_completed() -> None:
    """None entries alongside real completed entries stay completed."""
    real = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([None, real])
    assert result.status is ContractStatus.COMPLETED
    sources = result.payload["source_contracts"]
    assert sources[0]["child_id"] == "child_0"
    assert sources[0]["contract"] is None
    assert sources[1]["child_id"] == "child_1"
    assert sources[1]["status"] == "completed"
    assert sources[1]["contract"] is not None


def test_reduce_none_and_suspended() -> None:
    """None (completed) + suspended → suspended wins (lattice)."""
    sus = _make_suspension(child_hint="b")
    suspended = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=sus,
    )
    result = reduce_contract_results([None, suspended])
    assert result.status is ContractStatus.SUSPENDED
    assert result.suspension is not None
    assert result.suspension.kind == "human"
    # pending_suspensions should only list the suspended child, not the None one
    pending = result.payload.get("pending_suspensions", [])
    assert len(pending) == 1
    assert pending[0]["child_id"] == "child_1"


def test_reduce_none_and_failed() -> None:
    """None (completed) + failed → failed wins (lattice)."""
    failed = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([None, failed])
    assert result.status is ContractStatus.FAILED


# ---------------------------------------------------------------------------
# All status combinations — single child
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        ContractStatus.COMPLETED,
        ContractStatus.SUSPENDED,
        ContractStatus.FAILED,
    ],
)
def test_reduce_single_child(status: ContractStatus) -> None:
    """A single child contract passes its status through."""
    sus = None
    if status is ContractStatus.SUSPENDED:
        sus = _make_suspension(child_hint="a")
    contract = _make_contract(status=status, suspension=sus)
    result = reduce_contract_results([contract])
    assert result.status is status
    if status is ContractStatus.SUSPENDED:
        assert result.suspension is not None
    else:
        assert result.suspension is None


# ---------------------------------------------------------------------------
# All status combinations — two children (lattice ordering)
# ---------------------------------------------------------------------------


def test_reduce_completed_completed() -> None:
    """completed + completed → completed."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    b = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.COMPLETED


def test_reduce_completed_suspended() -> None:
    """suspended beats completed."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="b"),
    )
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.SUSPENDED
    assert result.suspension is not None


def test_reduce_suspended_completed() -> None:
    """suspended beats completed (order-independent)."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a"),
    )
    b = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.SUSPENDED


def test_reduce_completed_failed() -> None:
    """failed beats completed."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    b = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.FAILED


def test_reduce_failed_completed() -> None:
    """failed beats completed (order-independent)."""
    a = _make_contract(status=ContractStatus.FAILED)
    b = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.FAILED


def test_reduce_suspended_failed() -> None:
    """failed beats suspended."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a"),
    )
    b = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.FAILED


def test_reduce_failed_suspended() -> None:
    """failed beats suspended (order-independent)."""
    a = _make_contract(status=ContractStatus.FAILED)
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="b"),
    )
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.FAILED


# ---------------------------------------------------------------------------
# Deterministic child ordering
# ---------------------------------------------------------------------------


def test_reduce_source_contracts_preserve_input_order() -> None:
    """source_contracts list appears in the same order as input iterable."""
    a = _make_contract(status=ContractStatus.FAILED)
    b = _make_contract(status=ContractStatus.COMPLETED)
    c = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="c"),
    )
    result = reduce_contract_results([a, b, c])
    sources = result.payload["source_contracts"]
    assert sources[0]["child_id"] == "child_0"
    assert sources[0]["status"] == "failed"
    assert sources[1]["child_id"] == "child_1"
    assert sources[1]["status"] == "completed"
    assert sources[2]["child_id"] == "child_2"
    assert sources[2]["status"] == "suspended"


def test_reduce_explicit_child_ids_preserve_order() -> None:
    """When child_ids are provided, they appear in the given order."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    b = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results(
        [a, b], child_ids=["alpha", "beta"],
    )
    sources = result.payload["source_contracts"]
    assert sources[0]["child_id"] == "alpha"
    assert sources[1]["child_id"] == "beta"


def test_reduce_implicit_child_ids_are_stable() -> None:
    """Implicit child IDs are always child_0, child_1, ... (deterministic)."""
    result_1 = reduce_contract_results([None, None])
    result_2 = reduce_contract_results([None, None])
    assert result_1.payload["source_contracts"] == result_2.payload["source_contracts"]


# ---------------------------------------------------------------------------
# Failed + suspended cursor preservation
# ---------------------------------------------------------------------------


def test_reduce_failed_wins_but_preserves_suspended_cursor() -> None:
    """When failed beats suspended, pending_suspensions still records the
    suspended child's cursor metadata."""
    failed = _make_contract(
        status=ContractStatus.FAILED,
        payload_override={"error": "timeout"},
    )
    sus_child = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="sus", resume_cursor="cursor-sus-1"),
        payload_override={"q": "approve?"},
    )
    result = reduce_contract_results([failed, sus_child])
    assert result.status is ContractStatus.FAILED

    pending = result.payload.get("pending_suspensions", [])
    assert len(pending) == 1
    assert pending[0]["child_id"] == "child_1"
    assert pending[0]["status"] == "suspended"
    assert pending[0]["cursor"] == "cursor-sus-1"
    assert isinstance(pending[0]["suspension"], dict)
    assert pending[0]["suspension"]["kind"] == "human"


def test_reduce_multiple_failed_one_suspended() -> None:
    """Two failed + one suspended → failed, still with pending_suspensions."""
    f1 = _make_contract(status=ContractStatus.FAILED)
    sus = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="mid"),
    )
    f2 = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([f1, sus, f2])
    assert result.status is ContractStatus.FAILED
    pending = result.payload.get("pending_suspensions", [])
    assert len(pending) == 1


def test_reduce_failed_no_suspension_children() -> None:
    """Pure failed children produce no pending_suspensions key."""
    a = _make_contract(status=ContractStatus.FAILED)
    b = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([a, b])
    assert result.status is ContractStatus.FAILED
    assert "pending_suspensions" not in result.payload


# ---------------------------------------------------------------------------
# Composite suspension fields
# ---------------------------------------------------------------------------


def test_reduce_one_suspended_child_passes_suspension_through() -> None:
    """Single suspended child → its suspension is used directly."""
    sus = _make_suspension(
        child_hint="only",
        kind="human",
        thread_ref="thread/1",
        actor="alice",
        resume_cursor="c1",
    )
    child = _make_contract(status=ContractStatus.SUSPENDED, suspension=sus)
    result = reduce_contract_results([child])
    assert result.suspension is sus  # identity preserved for single


def test_reduce_two_suspended_children_produces_composite() -> None:
    """Multiple suspended children → composite Suspension."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(
            child_hint="a", kind="human", awaitable="a-1", resume_cursor="ca",
        ),
    )
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(
            child_hint="b", kind="human", awaitable="b-2", resume_cursor="cb",
        ),
    )
    result = reduce_contract_results([a, b], child_ids=["child_a", "child_b"])
    assert result.status is ContractStatus.SUSPENDED
    assert result.suspension is not None
    comp = result.suspension
    assert comp.kind == "composite_suspension"
    assert comp.prompt == "Awaiting input from suspended child steps"
    assert comp.resume_cursor is None  # composite cursors use state.json, not a string
    schema = dict(comp.resume_input_schema)
    assert schema.get("type") == "object"
    assert set(schema.get("required", [])) == {"child_a", "child_b"}
    props = schema.get("properties", {})
    assert "child_a" in props
    assert "child_b" in props
    assert isinstance(props["child_a"], dict)


def test_reduce_composite_suspension_shared_awaitable() -> None:
    """When all suspended children share the same awaitable, composite inherits it."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a", awaitable="shared"),
    )
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="b", awaitable="shared"),
    )
    result = reduce_contract_results([a, b])
    assert result.suspension.awaitable == "shared"


def test_reduce_composite_suspension_shared_thread_ref() -> None:
    """Shared thread_ref is propagated; different values → None."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a", thread_ref="t1"),
    )
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="b", thread_ref="t1"),
    )
    result = reduce_contract_results([a, b])
    assert result.suspension.thread_ref == "t1"

    c = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="c", thread_ref="t2"),
    )
    result_diff = reduce_contract_results([a, c])
    assert result_diff.suspension.thread_ref is None


def test_reduce_composite_suspension_shared_actor() -> None:
    """Shared actor is propagated; different → None."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a", actor="alice"),
    )
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="b", actor="alice"),
    )
    result = reduce_contract_results([a, b])
    assert result.suspension.actor == "alice"

    c = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="c", actor="bob"),
    )
    result_diff = reduce_contract_results([a, c])
    assert result_diff.suspension.actor is None


def test_reduce_composite_suspension_merge_display_refs() -> None:
    """Composite suspension deduplicates display refs across children."""
    ref = EvidenceArtifactRef(uri="file://a", content_type="text/plain")
    sus_a = Suspension(
        kind="human", display_refs=(ref,),
        prompt="Approve?",
    )
    sus_b = Suspension(
        kind="human", display_refs=(ref,),
        prompt="Confirm?",
    )
    a = _make_contract(status=ContractStatus.SUSPENDED, suspension=sus_a)
    b = _make_contract(status=ContractStatus.SUSPENDED, suspension=sus_b)
    result = reduce_contract_results([a, b])
    # Should be deduplicated to a single ref
    assert len(result.suspension.display_refs) == 1


def test_reduce_composite_suspension_pending_includes_all_suspended() -> None:
    """pending_suspensions lists every suspended child, even in composite."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a", resume_cursor="ca"),
    )
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="b", resume_cursor="cb"),
    )
    c = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([a, b, c])
    pending = result.payload.get("pending_suspensions", [])
    assert len(pending) == 2
    cursors = {entry["cursor"] for entry in pending}
    assert cursors == {"ca", "cb"}


# ---------------------------------------------------------------------------
# JSON-compatible payloads
# ---------------------------------------------------------------------------


def test_reduce_payload_is_json_serializable() -> None:
    """The entire ContractResult payload round-trips through json."""
    sus = _make_suspension(child_hint="x")
    a = _make_contract(
        status=ContractStatus.SUSPENDED, suspension=sus,
        payload_override={"int": 42, "float": 3.14, "bool": True, "list": [1, 2]},
    )
    b = _make_contract(
        status=ContractStatus.FAILED,
        payload_override={"error": "fail", "nested": {"key": "val"}},
    )
    result = reduce_contract_results([a, b])
    # Use to_json() then round-trip
    as_dict = result.to_json()
    raw = json.dumps(as_dict)
    round_tripped = json.loads(raw)
    assert round_tripped["status"] == "failed"
    assert "payload" in round_tripped
    assert "pending_suspensions" in round_tripped["payload"]


def test_reduce_payload_no_non_json_types() -> None:
    """Reducer payload values must be serializable — verify no custom objects leak."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([a])
    payload = result.payload
    # Walk the payload tree and ensure every value is JSON-compatible
    _assert_json_serializable(payload)
    _assert_json_serializable(result.to_json())


def test_reduce_source_contract_payload_is_json() -> None:
    """Each source_contract entry is JSON-compatible."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    result = reduce_contract_results([a])
    _assert_json_serializable(result.payload["source_contracts"])


def test_reduce_pending_suspension_payload_is_json() -> None:
    """pending_suspensions entries are JSON-compatible."""
    a = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="a"),
    )
    result = reduce_contract_results([a])
    _assert_json_serializable(result.payload["pending_suspensions"])


# ---------------------------------------------------------------------------
# Unimplemented policy / scope behavior
# ---------------------------------------------------------------------------


def test_reduce_quorum_raises_not_implemented() -> None:
    """QUORUM policy is not implemented."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    with pytest.raises(NotImplementedError, match="reduce_policy='quorum'"):
        reduce_contract_results([a], reduce_policy=ReducePolicy.QUORUM)


def test_reduce_best_effort_raises_not_implemented() -> None:
    """BEST_EFFORT policy is not implemented."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    with pytest.raises(NotImplementedError, match="reduce_policy='best_effort'"):
        reduce_contract_results([a], reduce_policy=ReducePolicy.BEST_EFFORT)


def test_reduce_budget_raises_not_implemented() -> None:
    """BUDGET policy is not implemented."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    with pytest.raises(NotImplementedError, match="reduce_policy='budget'"):
        reduce_contract_results([a], reduce_policy=ReducePolicy.BUDGET)


def test_reduce_saturation_raises_not_implemented() -> None:
    """SATURATION policy is not implemented."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    with pytest.raises(NotImplementedError, match="reduce_policy='saturation'"):
        reduce_contract_results([a], reduce_policy=ReducePolicy.SATURATION)


def test_reduce_suspension_scope_raises_not_implemented() -> None:
    """Non-None suspension_scope raises NotImplementedError."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    with pytest.raises(
        NotImplementedError,
        match="suspension_scope is reserved for a later milestone",
    ):
        reduce_contract_results([a], suspension_scope="fan-out")


# ---------------------------------------------------------------------------
# Evidence refs and provenance merging
# ---------------------------------------------------------------------------


def test_reduce_merges_evidence_refs() -> None:
    """Evidence refs from multiple children are merged and deduplicated."""
    ref_a = EvidenceArtifactRef(uri="s3://a", content_type="text/plain")
    ref_b = EvidenceArtifactRef(uri="s3://b", content_type="application/json")
    a = ContractResult(
        status=ContractStatus.COMPLETED,
        evidence_refs=(ref_a,),
    )
    b = ContractResult(
        status=ContractStatus.COMPLETED,
        evidence_refs=(ref_b,),
    )
    result = reduce_contract_results([a, b])
    assert len(result.evidence_refs) == 2


def test_reduce_deduplicates_evidence_refs() -> None:
    """Duplicate evidence refs are merged."""
    ref = EvidenceArtifactRef(uri="s3://x", content_type="text/plain")
    a = ContractResult(
        status=ContractStatus.COMPLETED,
        evidence_refs=(ref,),
    )
    b = ContractResult(
        status=ContractStatus.COMPLETED,
        evidence_refs=(ref,),
    )
    result = reduce_contract_results([a, b])
    assert len(result.evidence_refs) == 1


def test_reduce_merges_provenance() -> None:
    """Provenance sources are union-merged; chain sequences concatenated."""
    prov_a = Provenance(sources=("s1",), chain=("c1",))
    prov_b = Provenance(sources=("s2",), chain=("c2",))
    a = ContractResult(status=ContractStatus.COMPLETED, provenance=prov_a)
    b = ContractResult(status=ContractStatus.COMPLETED, provenance=prov_b)
    result = reduce_contract_results([a, b])
    assert set(result.provenance.sources) == {"s1", "s2"}
    assert result.provenance.chain == ("c1", "c2")


# ---------------------------------------------------------------------------
# Winner field propagation
# ---------------------------------------------------------------------------


def test_reduce_winner_authority_level() -> None:
    """The winner's authority_level is propagated."""
    a = ContractResult(
        status=ContractStatus.COMPLETED, authority_level="asserted",
    )
    b = ContractResult(
        status=ContractStatus.FAILED, authority_level="verified",
    )
    result = reduce_contract_results([a, b])
    # failed wins
    assert result.authority_level == "verified"


def test_reduce_winner_freshness() -> None:
    """The winner's freshness is propagated."""
    fresh = Freshness(
        observed_at="2026-06-05T10:00:00Z",
        ttl_seconds=3600,
    )
    a = ContractResult(status=ContractStatus.COMPLETED)
    b = ContractResult(status=ContractStatus.FAILED, freshness=fresh)
    result = reduce_contract_results([a, b])
    assert result.freshness.observed_at == "2026-06-05T10:00:00Z"
    assert result.freshness.ttl_seconds == 3600


def test_reduce_winner_provenance_generator() -> None:
    """The winner's provenance generator is propagated."""
    prov = Provenance(generator="scanner@2.0", generated_at="2026-01-01T00:00:00Z")
    a = ContractResult(status=ContractStatus.COMPLETED)
    b = ContractResult(status=ContractStatus.FAILED, provenance=prov)
    result = reduce_contract_results([a, b])
    assert result.provenance.generator == "scanner@2.0"
    assert result.provenance.generated_at == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_reduce_suspended_without_suspension_object() -> None:
    """SUSPENDED status without a Suspension object — behaves like completed."""
    # This is an edge case (m0a allows status/suspension mismatch)
    child = _make_contract(status=ContractStatus.SUSPENDED, suspension=None)
    result = reduce_contract_results([child])
    # Its status is SUSPENDED but since suspension is None, it acts like no suspension
    assert result.status is ContractStatus.SUSPENDED
    assert result.suspension is None
    assert result.payload.get("pending_suspensions") is None


def test_reduce_completed_with_suspension_object() -> None:
    """COMPLETED with Suspension — suspension is ignored (status-driven)."""
    sus = _make_suspension(child_hint="orphan")
    child = _make_contract(status=ContractStatus.COMPLETED, suspension=sus)
    result = reduce_contract_results([child])
    assert result.status is ContractStatus.COMPLETED
    assert result.suspension is None  # suspension only follows SUSPENDED status
    assert "pending_suspensions" not in result.payload


def test_reduce_all_three_statuses() -> None:
    """completed + suspended + failed → failed, with pending_suspensions."""
    a = _make_contract(status=ContractStatus.COMPLETED)
    b = _make_contract(
        status=ContractStatus.SUSPENDED,
        suspension=_make_suspension(child_hint="sus"),
    )
    c = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([a, b, c])
    assert result.status is ContractStatus.FAILED
    pending = result.payload.get("pending_suspensions", [])
    assert len(pending) == 1
    assert pending[0]["child_id"] == "child_1"


def test_reduce_large_count() -> None:
    """Smoke-test with 100 entries for determinism and non-exploding memory."""
    results = [
        _make_contract(status=ContractStatus.COMPLETED) for _ in range(100)
    ]
    result = reduce_contract_results(results)
    assert result.status is ContractStatus.COMPLETED
    assert len(result.payload["source_contracts"]) == 100


def test_reduce_preserves_payload_keys() -> None:
    """Standard keys are always present in reducer payload."""
    result = reduce_contract_results([])
    keys = set(result.payload.keys())
    assert {"reduce_policy", "status_lattice", "source_contracts"} <= keys


def test_reduce_result_is_frozen() -> None:
    """ContractResult is frozen — verify attribute assignment is blocked."""
    a = _make_contract(status=ContractStatus.FAILED)
    result = reduce_contract_results([a])
    # The ContractResult dataclass is frozen=True, so field re-assignment raises
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        result.status = ContractStatus.COMPLETED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Exports cross-check
# ---------------------------------------------------------------------------


def test_reduce_policy_and_reducer_exported_from_arnold_pipeline() -> None:
    """Ensure ReducePolicy and reduce_contract_results are accessible from
    arnold.pipeline (integration with __init__.py)."""
    from arnold.pipeline import ReducePolicy, reduce_contract_results  # noqa: F811

    assert ReducePolicy.MAX_WINS == "max_wins"
    result = reduce_contract_results([])
    assert result.status is ContractStatus.COMPLETED


def test_reduce_policy_max_wins_is_default() -> None:
    """MAX_WINS is the implicit default reduce_policy."""
    a = _make_contract(status=ContractStatus.FAILED)
    explicit = reduce_contract_results([a], reduce_policy=ReducePolicy.MAX_WINS)
    implicit = reduce_contract_results([a])
    assert explicit.status == implicit.status
    assert explicit.to_json() == implicit.to_json()
