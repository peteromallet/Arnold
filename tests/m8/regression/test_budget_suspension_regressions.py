"""M8 acceptance regression: budget overflow and suspension propagation (T3).

Covers the remaining two motivating failure classes from the README:

3. Model budget overflow escaping the seam without a typed failure contract or
   explicit budget diagnostic.
4. Suspended child contracts not propagating suspension to the parent reduce
   result under the ``MAX_WINS`` status lattice.

Fixtures are M8-distinct; they reference the megaplan ``model_seam`` and the
neutral ``reduce_contract_results`` primitive directly.
"""

from __future__ import annotations

import pytest

from arnold.pipeline import ContractResult, ContractStatus, reduce_contract_results
from arnold.pipeline.contract_reduce import ReducePolicy
from arnold.pipeline.types import Suspension
from arnold_pipelines.megaplan.model_seam import (
    BudgetStatus,
    ModelBudgetError,
    ModelTier,
    budget_model_input,
    classify_model_family,
    render_step_message,
)
from arnold.pipeline import StepInvocation

from .helpers import (
    BUDGET_OVERFLOW_PAYLOAD,
    SOURCE_TICKET,
    SUSPENSION_PROPAGATION_PAYLOAD,
    make_budget_overflow_contract,
    make_contract_result,
    assert_contract_status,
    assert_payload_contains,
    assert_suspension_propagated,
)


# ---------------------------------------------------------------------------
# budget overflow
# ---------------------------------------------------------------------------


def test_budget_model_input_raises_model_budget_error_for_unknown_model() -> None:
    """An unrecognized model family must raise ModelBudgetError."""
    with pytest.raises(ModelBudgetError):
        budget_model_input(
            "some text",
            model="unknown-model-v99",
            tier=ModelTier.ENFORCED,
        )


def test_classify_model_family_rejects_raw_provider_prefix() -> None:
    """Provider-prefixed names (openrouter/...) must be rejected at the seam."""
    with pytest.raises(ModelBudgetError, match="provider-prefixed"):
        classify_model_family("openrouter/deepseek-v4")


def test_budget_overflow_payload_carries_ticket_and_error_kind() -> None:
    """The shared BUDGET_OVERFLOW_PAYLOAD identifies the source ticket."""
    assert BUDGET_OVERFLOW_PAYLOAD["failure_class"] == "model_budget_overflow"
    assert BUDGET_OVERFLOW_PAYLOAD["ticket"] == SOURCE_TICKET
    assert BUDGET_OVERFLOW_PAYLOAD["error_kind"] == "budget_exceeded"


def test_make_budget_overflow_contract_status_is_failed() -> None:
    """The helper constructs a FAILED contract with the overflow payload."""
    contract = make_budget_overflow_contract("Ran out of tokens at 95%")
    assert contract.status is ContractStatus.FAILED
    assert contract.payload.get("failure_class") == "model_budget_overflow"
    assert contract.payload.get("message") == "Ran out of tokens at 95%"


def test_budget_overflow_contract_is_distinct_from_helpers_default() -> None:
    """M8 budget-overflow contracts are not accidentally the generic helpers."""
    default = make_contract_result()
    overflow = make_budget_overflow_contract("")
    assert default.status is not ContractStatus.FAILED
    assert overflow.status is ContractStatus.FAILED
    assert "failure_class" not in default.payload
    assert overflow.payload.get("failure_class") == "model_budget_overflow"


def test_render_step_message_budgets_named_model() -> None:
    """render_step_message runs budget_model_input and attaches it."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.4",
            "normalized_model": "gpt-5.4",
            "prompt": "Hello world",
        },
    )

    rendered = render_step_message(invocation)

    assert rendered.budget is not None
    assert rendered.budget.budget_result in (
        BudgetStatus.WITHIN_BUDGET,
        BudgetStatus.DEGRADED_FALLBACK,
    )
    assert rendered.telemetry.budget_result in (
        BudgetStatus.WITHIN_BUDGET,
        BudgetStatus.DEGRADED_FALLBACK,
    )


def test_render_step_message_blocks_budget_overflow_at_assembly() -> None:
    """A declared input budget overflow is rejected before model dispatch."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.4",
            "normalized_model": "gpt-5.4",
            "prompt": "x" * 80,
            "max_input_tokens": 10,
        },
    )

    with pytest.raises(ModelBudgetError, match="budget exceeded"):
        render_step_message(invocation)


# ---------------------------------------------------------------------------
# suspension propagation under MAX_WINS
# ---------------------------------------------------------------------------


def _make_suspended_child(child_id: str = "child_0") -> ContractResult:
    """Return a minimal SUSPENDED contract for a child step."""
    suspension = Suspension(
        kind="human",
        awaitable=f"awaitable/{child_id}",
        prompt=f"Awaiting input for {child_id}",
        resume_cursor=f"cursor-{child_id}",
    )
    return ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=suspension,
        payload={"child": child_id},
    )


def _make_completed_child(child_id: str = "child_0") -> ContractResult:
    """Return a minimal COMPLETED contract for a child step."""
    return ContractResult(
        status=ContractStatus.COMPLETED,
        payload={"child": child_id},
    )


def test_suspended_child_propagates_to_parent() -> None:
    """When a single SUSPENDED child is reduced, parent is SUSPENDED."""
    child = _make_suspended_child()
    parent = reduce_contract_results([child])
    assert parent.status is ContractStatus.SUSPENDED
    assert parent.suspension is not None
    assert parent.suspension.kind == "human"


def test_suspended_plus_completed_propagates_suspended() -> None:
    """SUSPENDED + COMPLETED → SUSPENDED (suspended beats completed)."""
    suspended = _make_suspended_child("sus")
    completed = _make_completed_child("done")
    parent = reduce_contract_results([completed, suspended])
    assert parent.status is ContractStatus.SUSPENDED


def test_completed_plus_suspended_propagates_suspended() -> None:
    """Order should not matter: COMPLETED + SUSPENDED → SUSPENDED."""
    suspended = _make_suspended_child("sus")
    completed = _make_completed_child("done")
    parent = reduce_contract_results([suspended, completed])
    assert parent.status is ContractStatus.SUSPENDED


def test_multiple_suspended_children_produce_composite() -> None:
    """Multiple suspended children produce a composite suspension."""
    a = _make_suspended_child("a")
    b = _make_suspended_child("b")
    parent = reduce_contract_results([a, b])
    assert parent.status is ContractStatus.SUSPENDED
    assert parent.suspension is not None
    # Composite suspension merges multiple suspensions
    assert parent.suspension.kind == "composite_suspension"


def test_suspended_child_source_contracts_record_status() -> None:
    """The source_contracts payload records each child's status."""
    suspended = _make_suspended_child("sus")
    completed = _make_completed_child("done")
    parent = reduce_contract_results([completed, suspended])
    sources = parent.payload["source_contracts"]
    assert len(sources) == 2
    statuses = {s["child_id"]: s["status"] for s in sources}
    assert statuses["child_0"] == "completed"
    assert statuses["child_1"] == "suspended"


def test_pending_suspensions_record_suspended_cursor() -> None:
    """The pending_suspensions payload records cursor metadata for
    suspended children even when parent status is SUSPENDED."""
    suspended = _make_suspended_child("sus")
    completed = _make_completed_child("done")
    parent = reduce_contract_results([completed, suspended])
    pending = parent.payload.get("pending_suspensions", [])
    assert len(pending) == 1
    assert pending[0]["child_id"] == "child_1"
    assert pending[0]["status"] == "suspended"
    assert pending[0]["cursor"] == "cursor-sus"


def test_suspension_propagation_payload_shared_constant() -> None:
    """The SUSPENSION_PROPAGATION_PAYLOAD carries the lattice and ticket."""
    assert SUSPENSION_PROPAGATION_PAYLOAD["failure_class"] == "suspension_propagation"
    assert SUSPENSION_PROPAGATION_PAYLOAD["ticket"] == SOURCE_TICKET
    assert SUSPENSION_PROPAGATION_PAYLOAD["status_lattice"] == "completed<suspended<failed"


def test_assert_suspension_propagated_helper() -> None:
    """The assert_suspension_propagated helper works on a contract directly
    carrying the SUSPENSION_PROPAGATION_PAYLOAD (not a reduce output)."""
    from .helpers import make_suspended_contract

    contract = make_suspended_contract()
    # Must not raise — contract was built with the shared payload
    assert_suspension_propagated(contract)
