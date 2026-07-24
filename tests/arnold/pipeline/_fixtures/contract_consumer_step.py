"""Fixture consumer step that reads via ctx.contract_results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arnold.pipeline.types import PortRef, StepContext, StepResult


@dataclass
class ContractConsumerStep:
    """Records the artifact_path read from ctx.contract_results['agent']."""

    name: str
    producer_step: str = "agent"
    consumes: tuple = field(default_factory=tuple)

    # Captured at run time for assertions
    received_artifact_path: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        artifact_path: str | None = None
        if ctx.contract_results and self.producer_step in ctx.contract_results:
            artifact_path = ctx.contract_results[self.producer_step].payload["artifact_path"]
        self.received_artifact_path = artifact_path
        return StepResult(outputs={}, next="halt", state_patch={})
