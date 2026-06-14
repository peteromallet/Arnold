"""Tests for AgentStep contract_result handoff (T8 / SC8).

Proves:
* AgentStep.run() returns StepResult with empty outputs and contract_result
  carrying artifact_path in payload.
* A fixture consumer step reads via ctx.contract_results['agent'].payload['artifact_path'].
* No outputs={self.name: ...} remains in the generic AgentStep source.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import arnold.pipeline.steps.agent as _agent_module
from arnold.pipeline import run_pipeline
from arnold.pipeline.steps.agent import AgentStep
from arnold.pipeline.types import Edge, Pipeline, Port, PortRef, Stage, StepContext, StepResult
from arnold.runtime.envelope import RuntimeEnvelope

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_fixtures"))
from contract_consumer_step import ContractConsumerStep  # noqa: E402


# ---------------------------------------------------------------------------
# Unit: AgentStep emits via contract_result, not outputs
# ---------------------------------------------------------------------------


class TestAgentStepContractResult:
    def test_outputs_is_empty(self, tmp_path: Path) -> None:
        step = AgentStep(name="agent", _prompt_source="Write.")
        ctx = StepContext(artifact_root=str(tmp_path), state={}, inputs={})
        result = step.run(ctx)

        assert result.outputs == {}

    def test_contract_result_carries_artifact_path(self, tmp_path: Path) -> None:
        step = AgentStep(name="agent", _prompt_source="Write.")
        ctx = StepContext(artifact_root=str(tmp_path), state={}, inputs={})
        result = step.run(ctx)

        assert result.contract_result is not None
        assert "artifact_path" in result.contract_result.payload
        artifact_path = Path(result.contract_result.payload["artifact_path"])
        assert artifact_path.exists()

    def test_contract_result_carries_label(self, tmp_path: Path) -> None:
        step = AgentStep(name="agent", _prompt_source="Write.", _output_label="json", _output_suffix="json")
        ctx = StepContext(artifact_root=str(tmp_path), state={}, inputs={})
        result = step.run(ctx)

        assert result.contract_result is not None
        assert result.contract_result.payload["label"] == "json"

    def test_no_legacy_outputs_dict_in_source(self) -> None:
        """Generic AgentStep source must not contain outputs={self.name: ...}."""
        source = inspect.getsource(_agent_module)
        assert "outputs={self.name" not in source


# ---------------------------------------------------------------------------
# Integration: consumer reads via ctx.contract_results
# ---------------------------------------------------------------------------


class TestContractConsumerFixture:
    def test_consumer_receives_artifact_path_via_contract_results(self, tmp_path: Path) -> None:
        producer = AgentStep(
            name="agent",
            _prompt_source="Hello.",
            produces=(Port(name="artifact", content_type="text/plain"),),
        )
        consumer = ContractConsumerStep(
            name="consumer",
            producer_step="agent",
            consumes=(PortRef(port_name="artifact", content_type="text/plain"),),
        )

        pipeline = Pipeline(
            stages={
                "agent": Stage(
                    name="agent",
                    step=producer,
                    edges=(Edge(label="done", target="consumer"),),
                ),
                "consumer": Stage(
                    name="consumer",
                    step=consumer,
                    edges=(),
                ),
            },
            entry="agent",
            binding_map={("consumer", "input"): ("agent", "artifact")},
        )

        env = RuntimeEnvelope(plugin_id="test", run_id="t1", artifact_root=str(tmp_path))
        run_pipeline(pipeline, {}, env)

        assert consumer.received_artifact_path is not None
        artifact_path = Path(consumer.received_artifact_path)
        assert artifact_path.exists()
        assert artifact_path.read_text() == "Hello."
