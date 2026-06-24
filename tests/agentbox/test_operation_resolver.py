from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from arnold.runtime.durable_ops import OperationRun, OperationState

from agentbox.config import AgentBoxConfig
from agentbox.operation_resolver import resolve_operation
from agentbox.operations import create_agentbox_operation, open_operation_store, update_agentbox_operation


def test_resolver_returns_exact_operation_id_before_fuzzy_metadata_matches(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    exact = create_agentbox_operation(
        config,
        "app",
        command="echo exact",
        metadata={"resolved_spec_path": "old-spec.yaml"},
    )
    update_agentbox_operation(config, exact.id, state=OperationState.FAILED)
    running = create_agentbox_operation(
        config,
        "chain-running",
        command="echo fuzzy",
        repo_names=["app"],
        metadata={"resolved_spec_path": "app/chain.yaml"},
    )
    update_agentbox_operation(config, running.id, state=OperationState.RUNNING)

    result = resolve_operation(config, "app")

    assert result.status == "single"
    assert result.operation is not None
    assert result.operation.operation_id == "app"
    assert result.operation.matched_by == "operation_id_exact"


def test_resolver_orders_running_and_blocked_before_terminal_matches(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    store = open_operation_store(config)
    succeeded = store.create_operation_run(
        OperationRun(
            id="done-chain",
            operation_type="agentbox_host",
            metadata={"resolved_spec_path": "checkout/chain.yaml"},
        ).transition_to(OperationState.RUNNING).transition_to(OperationState.SUCCEEDED)
    )
    blocked = store.create_operation_run(
        OperationRun(
            id="blocked-chain",
            operation_type="agentbox_host",
            metadata={"resolved_spec_path": "checkout/other.yaml", "chain_status": "blocked"},
        ).transition_to(OperationState.RUNNING).transition_to(OperationState.FAILED)
    )
    running = create_agentbox_operation(
        config,
        "running-chain",
        command="echo run",
        metadata={"resolved_spec_path": "checkout/latest.yaml"},
    )
    update_agentbox_operation(config, running.id, state=OperationState.RUNNING)

    result = resolve_operation(config, "checkout")

    assert result.status == "ambiguous"
    assert [candidate.operation_id for candidate in result.candidates] == [
        "running-chain",
        "blocked-chain",
        "done-chain",
    ]
    assert result.question == "Which operation did you mean: running-chain, blocked-chain, done-chain?"
    assert succeeded.id == "done-chain"
    assert blocked.id == "blocked-chain"


def test_resolver_shapes_no_match_single_and_ambiguous_results(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    only = create_agentbox_operation(
        config,
        "solo-chain",
        command="echo solo",
        metadata={"resolved_spec_path": "solo/spec.yaml"},
    )
    update_agentbox_operation(config, only.id, state=OperationState.RUNNING)
    create_agentbox_operation(
        config,
        "alpha-chain",
        command="echo alpha",
        metadata={"resolved_spec_path": "shared/spec.yaml"},
    )
    create_agentbox_operation(
        config,
        "beta-chain",
        command="echo beta",
        metadata={"resolved_spec_path": "shared/spec.yaml"},
    )

    no_match = resolve_operation(config, "missing")
    single = resolve_operation(config, "solo")
    ambiguous = resolve_operation(config, "shared")

    assert no_match.to_dict() == {
        "status": "no_match",
        "query": "missing",
        "operation": None,
        "candidates": [],
        "question": "No AgentBox operation matched 'missing'. Which operation id should I use?",
    }
    assert single.status == "single"
    assert single.operation is not None
    assert single.operation.operation_id == "solo-chain"
    assert ambiguous.status == "ambiguous"
    assert ambiguous.operation is None
    assert len(ambiguous.candidates) == 2
    assert ambiguous.question == "Which operation did you mean: alpha-chain, beta-chain?"
