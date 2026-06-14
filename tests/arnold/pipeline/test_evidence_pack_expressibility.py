"""Evidence-pack expressibility guardrail test (M2 T2).

Co-design test for the evidence-pack verifier shape — a structurally-different,
model-LESS pipeline — expressed using ONLY the frozen type primitives from
``arnold.pipeline.types`` plus a locally-defined ``StepInvocation`` adapter
seam.

This is an *expressibility* guardrail — it constructs shapes and validates
they are representable, not that an executor runs them.

Covers:
- StepInvocation shapes (tool-shaped without registering tool/human/state
  adapters)
- By-reference multi-content-type artifacts via EvidenceArtifactRef
- Collection fan-out-reduce via Port/PortRef + cardinality semantics
- Typed verdict ContractResult payloads
- Fail-closed unknown adapter kinds
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

import pytest

from arnold.pipeline.types import (
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Port,
    PortRef,
    Provenance,
    ReduceResult,
    Suspension,
)
from arnold.pipeline.step_invocation import (
    StepInvocation as RuntimeStepInvocation,
    StepInvocationAdapterRegistry,
)
from arnold.pipeline.validator import validate
from arnold.pipelines.evidence_pack.pipelines import build_initial_pipeline


class _NoopRuntimeToolAdapter:
    def invoke(self, invocation: RuntimeStepInvocation) -> object:  # pragma: no cover
        raise AssertionError("validation must not invoke evidence-pack adapters")


# ---------------------------------------------------------------------------
# Locally-defined StepInvocation seam (expressibility guardrail — production
# implementation lands in later tasks; this test proves the shape is
# expressible without contorting the type surface).
# ---------------------------------------------------------------------------


@runtime_checkable
class Adapter(Protocol):
    """Protocol for adapters that can render/capture step invocations.

    Each adapter kind (model, tool, human, state) implements this protocol.
    Unknown kinds fail closed at adapter lookup time.
    """

    kind: str

    def render(self, invocation: "StepInvocation") -> Any: ...

    def capture(self, invocation: "StepInvocation", output: Any) -> ContractResult: ...


@dataclass(frozen=True)
class StepInvocation:
    """Foundation primitive for step→adapter dispatch.

    Carries the typed ports, artifact refs, and a reference to the adapter
    that will render/capture the invocation.
    """

    step_id: str
    adapter_kind: str
    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)
    artifacts: tuple[EvidenceArtifactRef, ...] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)


class AdapterRegistry:
    """Registry mapping adapter kinds to Adapter instances.

    Only the ``model`` slot is wired (placeholder). Unknown kinds fail closed.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        if adapter.kind in self._adapters:
            raise ValueError(f"adapter kind {adapter.kind!r} already registered")
        self._adapters[adapter.kind] = adapter

    def lookup(self, kind: str) -> Adapter:
        """Return the adapter for *kind* or raise ``KeyError`` (fail-closed)."""
        if kind not in self._adapters:
            raise KeyError(
                f"unknown adapter kind {kind!r}; "
                f"registered kinds: {sorted(self._adapters)}"
            )
        return self._adapters[kind]

    @property
    def registered_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters.keys()))


# ---------------------------------------------------------------------------
# Cardinality helpers (singleton / collection / stream reserved)
# ---------------------------------------------------------------------------

_CARDINALITY_SINGLETON = "singleton"
_CARDINALITY_COLLECTION = "collection"
_CARDINALITY_STREAM = "stream"  # RESERVED, not implemented


def _port(name: str, ct: str, cardinality: str = _CARDINALITY_SINGLETON) -> Port:
    """Construct a Port with first-class public cardinality metadata."""
    return Port(name=name, content_type=ct, cardinality=cardinality)


def _port_ref(name: str, ct: str) -> PortRef:
    return PortRef(port_name=name, content_type=ct)


# ---------------------------------------------------------------------------
# Test: StepInvocation shapes (tool-shaped invocations)
# ---------------------------------------------------------------------------


class TestStepInvocationShapes:
    """StepInvocation can express tool-shaped invocations."""

    def test_tool_invocation_shape(self) -> None:
        """A model-less tool step is expressible."""
        ref = EvidenceArtifactRef(
            uri="s3://evidence/scan-001.json",
            content_type="application/json",
            name="scan-output",
        )
        inv = StepInvocation(
            step_id="security-scan",
            adapter_kind="tool",
            produces=(_port("scan_result", "application/json"),),
            consumes=(),
            artifacts=(ref,),
            payload={"command": "bandit -r src/"},
        )
        assert inv.step_id == "security-scan"
        assert inv.adapter_kind == "tool"
        assert len(inv.produces) == 1
        assert inv.produces[0].content_type == "application/json"
        assert len(inv.artifacts) == 1
        assert inv.artifacts[0].content_type == "application/json"

    def test_runtime_invocation_uses_same_adapter_config_shape_for_model_and_tool(self) -> None:
        """Production StepInvocation supports future tool shape without construction-time lookup."""
        model = RuntimeStepInvocation.with_adapter_config(
            kind="model",
            adapter_config={"model": "gpt-5.4", "prompt": "summarize evidence"},
        )
        tool = RuntimeStepInvocation.with_adapter_config(
            kind="tool",
            adapter_config={"command": "scan", "artifact": "pack.json"},
        )

        assert model.kind == "model"
        assert tool.kind == "tool"
        assert model.metadata["adapter_config"]["model"] == "gpt-5.4"
        assert tool.metadata["adapter_config"]["command"] == "scan"

        registry = StepInvocationAdapterRegistry()
        with pytest.raises(KeyError, match="unknown adapter kind 'tool'"):
            registry.resolve(tool.kind)

    def test_evidence_pack_pipeline_authors_model_and_tool_invocation_metadata(self) -> None:
        """Evidence-pack stages can carry invocation metadata without live adapter calls."""
        pipeline = build_initial_pipeline()
        validators = pipeline.stages["content_validators"]
        reduce_stage = pipeline.stages["reduce"]

        assert validators.invocation == RuntimeStepInvocation.with_adapter_config(
            kind="tool",
            adapter_config={
                "tool": "evidence-pack-checkpoint-validator",
                "mode": "local-deterministic",
            },
        )
        assert reduce_stage.invocation == RuntimeStepInvocation.with_adapter_config(
            kind="model",
            adapter_config={
                "model": "evidence-pack-verdict-summarizer",
                "mode": "metadata-only",
            },
        )

        registry = StepInvocationAdapterRegistry()
        registry.register("tool", _NoopRuntimeToolAdapter())
        assert validate(pipeline, adapter_registry=registry).defects == []

    def test_evidence_pack_tool_invocation_fails_closed_without_adapter(self) -> None:
        """The future tool shape remains fail-closed until an adapter is registered."""
        diag = validate(build_initial_pipeline())
        assert any(
            issue.code == "invocation.unknown_adapter"
            and issue.stage == "content_validators"
            and issue.details["invocation_kind"] == "tool"
            for issue in diag.issues
        )

    def test_multi_content_type_artifacts(self) -> None:
        """By-reference artifacts of different content types."""
        png_ref = EvidenceArtifactRef(
            uri="s3://evidence/diagram.png",
            content_type="image/png",
            name="architecture-diagram",
        )
        md_ref = EvidenceArtifactRef(
            uri="s3://evidence/report.md",
            content_type="text/markdown",
            name="summary-report",
        )
        diff_ref = EvidenceArtifactRef(
            uri="s3://evidence/changes.diff",
            content_type="application/x-git-diff",
            name="patch",
        )
        inv = StepInvocation(
            step_id="fan-out-analyze",
            adapter_kind="tool",
            produces=(
                _port("analysis", "application/x-verdict+json", _CARDINALITY_COLLECTION),
            ),
            consumes=(),
            artifacts=(png_ref, md_ref, diff_ref),
            payload={"analysis_type": "multi-modal"},
        )
        assert len(inv.artifacts) == 3
        content_types = {a.content_type for a in inv.artifacts}
        assert "image/png" in content_types
        assert "text/markdown" in content_types
        assert "application/x-git-diff" in content_types


# ---------------------------------------------------------------------------
# Test: Collection fan-out-reduce ports
# ---------------------------------------------------------------------------


class TestCollectionFanOutReduce:
    """Collection ports can express fan-out→reduce patterns."""

    def test_collection_port_declaration(self) -> None:
        """A collection port carries first-class collection cardinality."""
        port = _port("panel_results", "application/x-verdict+json", _CARDINALITY_COLLECTION)
        assert port.name == "panel_results"
        assert port.cardinality == "collection"

    def test_singleton_port_declaration(self) -> None:
        """A singleton port carries first-class singleton cardinality."""
        port = _port("verdict", "application/x-verdict+json", _CARDINALITY_SINGLETON)
        assert port.name == "verdict"
        assert port.cardinality == "singleton"

    def test_stream_port_reserved(self) -> None:
        """Stream cardinality is representable but reserved/not implemented."""
        port = _port("live_feed", "text/markdown", _CARDINALITY_STREAM)
        assert port.cardinality == "stream"
        # Stream exists in the vocabulary but runtime binding should reject it.
        # Expressibility test only proves the shape is representable.

    def test_fan_out_reduce_shape(self) -> None:
        """Fan-out: a collection producer feeds reduce-join consumers."""
        # Producer: emits a collection
        producer_port = _port("candidates", "application/x-verdict+json", _CARDINALITY_COLLECTION)
        # Consumers: each takes a singleton from the collection
        consumer_ref = _port_ref("candidates", "application/x-verdict+json")
        # Reduce: produces a singleton verdict from collection input
        reduce_port = _port("winner", "application/x-verdict+json", _CARDINALITY_SINGLETON)

        fan_out_inv = StepInvocation(
            step_id="fan-out",
            adapter_kind="tool",
            produces=(producer_port,),
            consumes=(),
        )
        reduce_inv = StepInvocation(
            step_id="reduce",
            adapter_kind="tool",
            produces=(reduce_port,),
            consumes=(consumer_ref,),
        )

        assert fan_out_inv.produces[0].name == "candidates"
        assert fan_out_inv.produces[0].cardinality == "collection"
        assert reduce_inv.consumes[0].port_name == "candidates"
        assert reduce_inv.produces[0].name == "winner"
        assert reduce_inv.produces[0].cardinality == "singleton"

    def test_reduce_result_embedded_in_contract_result(self) -> None:
        """A ReduceResult can be embedded in a ContractResult payload."""
        rr = ReduceResult(
            value="proceed",
            scores=(3.0, 1.0),
            tally={"proceed": 3, "halt": 1},
            provenance=("fan-out-step",),
            label="proceed",
        )
        cr = ContractResult(
            payload={"reduce_outcome": rr},
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            authority_level="verified",
        )
        assert cr.payload["reduce_outcome"] == rr
        assert rr.label == "proceed"
        assert rr.scores == (3.0, 1.0)


# ---------------------------------------------------------------------------
# Test: Typed verdict ContractResult payloads
# ---------------------------------------------------------------------------


class TestTypedVerdictPayloads:
    """ContractResult carries typed verdict payloads with evidence refs and provenance."""

    def test_verdict_with_evidence_and_provenance(self) -> None:
        """A typed verdict payload with evidence refs and provenance."""
        ev = EvidenceArtifactRef(
            uri="s3://evidence/verdict-report.json",
            content_type="application/json",
            digest="sha256:abc123",
            name="verdict-report",
        )
        prov = Provenance(
            sources=("policy:scan-v1",),
            generator="verdict-engine@2.0",
            generated_at="2026-06-06T10:00:00Z",
            chain=("scan-step", "fan-out-step", "reduce-step"),
        )
        fresh = Freshness(
            observed_at="2026-06-06T10:00:00Z",
            ttl_seconds=3600,
            expires_at="2026-06-06T11:00:00Z",
        )
        cr = ContractResult(
            payload={
                "verdict": "pass",
                "score": 0.97,
                "gates_cleared": 5,
                "reasoning": "All evidence pack gates green.",
            },
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(ev,),
            authority_level="verified",
            provenance=prov,
            freshness=fresh,
        )
        assert cr.status == ContractStatus.COMPLETED
        assert cr.payload["verdict"] == "pass"
        assert cr.payload["score"] == 0.97
        assert len(cr.evidence_refs) == 1
        assert cr.provenance.generator == "verdict-engine@2.0"
        assert cr.freshness.ttl_seconds == 3600

    def test_verdict_round_trips(self) -> None:
        """Verdict ContractResult survives to_json/from_json round-trip."""
        cr = ContractResult(
            payload={"verdict": "fail", "score": 0.3, "reason": "evidence gap"},
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                EvidenceArtifactRef(
                    uri="s3://evidence/gap-report.json",
                    content_type="application/json",
                    name="gap-report",
                ),
            ),
            authority_level="verified",
            provenance=Provenance(generator="verdict-engine@2.0"),
            freshness=Freshness(),
        )
        rt = ContractResult.from_json(cr.to_json())
        assert rt == cr
        assert rt.payload["verdict"] == "fail"
        assert rt.payload["score"] == 0.3

    def test_failed_verdict_with_suspension_none(self) -> None:
        """A FAILED verdict must have suspension=None (no await)."""
        cr = ContractResult(
            payload={"verdict": "fail", "error": "timeout"},
            status=ContractStatus.FAILED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            authority_level="verified",
        )
        assert cr.status == ContractStatus.FAILED
        assert cr.suspension is None

    def test_suspended_verdict_with_human_gate(self) -> None:
        """A SUSPENDED verdict carries a human-gate Suspension."""
        display = EvidenceArtifactRef(
            uri="s3://prompts/gate-diff.png",
            content_type="image/png",
            name="approval-diff",
        )
        sus = Suspension(
            kind="human",
            awaitable="approval/evidence-gate-1",
            prompt="Review the evidence pack: approve or reject?",
            display_refs=(display,),
            resume_input_schema={"approved": "bool", "comment": "str"},
            thread_ref="thread/gate-1",
            actor="security-reviewer",
            deadline="2026-06-06T12:00:00Z",
            on_timeout="reject",
            default_action="reject",
        )
        cr = ContractResult(
            payload={"gate": "evidence-pack-approval"},
            status=ContractStatus.SUSPENDED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            suspension=sus,
            evidence_refs=(display,),
            authority_level="verified",
        )
        assert cr.status == ContractStatus.SUSPENDED
        assert cr.suspension is not None
        assert cr.suspension.kind == "human"
        assert cr.suspension.default_action == "reject"
        assert len(cr.suspension.display_refs) == 1


# ---------------------------------------------------------------------------
# Test: Fail-closed unknown adapter kinds
# ---------------------------------------------------------------------------


class TestAdapterRegistryFailClosed:
    """AdapterRegistry fails closed for unknown kinds; only model slot wired."""

    @staticmethod
    def _make_placeholder_model_adapter() -> Adapter:
        """Return a placeholder model adapter (implementation deferred to M3)."""

        class _PlaceholderModelAdapter:
            kind: str = "model"

            def render(self, invocation: StepInvocation) -> Any:
                return {"placeholder": "model-render", "step_id": invocation.step_id}

            def capture(self, invocation: StepInvocation, output: Any) -> ContractResult:
                return ContractResult(
                    payload={"captured": True, "step_id": invocation.step_id},
                    status=ContractStatus.COMPLETED,
                    schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
                )

        return _PlaceholderModelAdapter()  # type: ignore[return-value]

    def test_registry_starts_empty(self) -> None:
        """A fresh registry has no registered kinds."""
        registry = AdapterRegistry()
        assert registry.registered_kinds == ()

    def test_model_slot_is_wired(self) -> None:
        """Only the model adapter slot is registrable."""
        registry = AdapterRegistry()
        adapter = self._make_placeholder_model_adapter()
        registry.register(adapter)
        assert registry.registered_kinds == ("model",)

    def test_duplicate_registration_raises(self) -> None:
        """Registering the same kind twice raises ValueError."""
        registry = AdapterRegistry()
        registry.register(self._make_placeholder_model_adapter())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(self._make_placeholder_model_adapter())

    def test_tool_kind_fails_closed(self) -> None:
        """Looking up 'tool' adapter kind raises KeyError (fail-closed)."""
        registry = AdapterRegistry()
        # Only model is registered; tool is unknown.
        registry.register(self._make_placeholder_model_adapter())
        with pytest.raises(KeyError, match="unknown adapter kind 'tool'"):
            registry.lookup("tool")

    def test_human_kind_fails_closed(self) -> None:
        """Looking up 'human' adapter kind raises KeyError (fail-closed)."""
        registry = AdapterRegistry()
        registry.register(self._make_placeholder_model_adapter())
        with pytest.raises(KeyError, match="unknown adapter kind 'human'"):
            registry.lookup("human")

    def test_state_kind_fails_closed(self) -> None:
        """Looking up 'state' adapter kind raises KeyError (fail-closed)."""
        registry = AdapterRegistry()
        registry.register(self._make_placeholder_model_adapter())
        with pytest.raises(KeyError, match="unknown adapter kind 'state'"):
            registry.lookup("state")

    def test_arbitrary_unknown_kind_fails_closed(self) -> None:
        """Any arbitrary unknown kind fails closed."""
        registry = AdapterRegistry()
        registry.register(self._make_placeholder_model_adapter())
        with pytest.raises(KeyError, match="unknown adapter kind 'render-job'"):
            registry.lookup("render-job")

    def test_no_tool_human_state_adapters_registered(self) -> None:
        """Registry has no tool/human/state adapters — only model slot."""
        registry = AdapterRegistry()
        registry.register(self._make_placeholder_model_adapter())
        kinds = set(registry.registered_kinds)
        assert "model" in kinds
        assert "tool" not in kinds
        assert "human" not in kinds
        assert "state" not in kinds

    def test_lookup_model_succeeds(self) -> None:
        """Looking up the registered model adapter succeeds."""
        registry = AdapterRegistry()
        adapter = self._make_placeholder_model_adapter()
        registry.register(adapter)
        found = registry.lookup("model")
        assert found.kind == "model"
        assert isinstance(found, Adapter)


# ---------------------------------------------------------------------------
# Test: Complete evidence-pack pipeline shape
# ---------------------------------------------------------------------------


class TestEvidencePackPipelineShape:
    """The full evidence-pack verifier shape is expressible: scan→fan-out→
    human-suspend→reduce-verdict→fail, all model-less, all by-reference."""

    def test_full_pipeline_shape_is_expressible(self) -> None:
        """Construct all five stages of the evidence-pack verifier."""

        # -- Stage 1: Security scan (tool, no model) -------------------------
        scan_artifact = EvidenceArtifactRef(
            uri="s3://evidence/scan-001.json",
            content_type="application/json",
            digest="sha256:aaa111",
            size_bytes=2048,
            name="scan-output",
        )
        scan_inv = StepInvocation(
            step_id="scan",
            adapter_kind="tool",
            produces=(_port("scan_result", "application/json"),),
            consumes=(),
            artifacts=(scan_artifact,),
            payload={"tool": "bandit", "target": "src/"},
        )

        # -- Stage 2: Multi-content fan-out (tool) ---------------------------
        png_ref = EvidenceArtifactRef(
            uri="s3://evidence/diagram.png",
            content_type="image/png",
            name="diagram",
        )
        md_ref = EvidenceArtifactRef(
            uri="s3://evidence/report.md",
            content_type="text/markdown",
            name="report",
        )
        diff_ref = EvidenceArtifactRef(
            uri="s3://evidence/patch.diff",
            content_type="application/x-git-diff",
            name="patch",
        )
        fan_inv = StepInvocation(
            step_id="fan-out",
            adapter_kind="tool",
            produces=(_port("analyzed", "application/x-verdict+json", _CARDINALITY_COLLECTION),),
            consumes=(_port_ref("scan_result", "application/json"),),
            artifacts=(png_ref, md_ref, diff_ref),
            payload={"strategy": "broadcast"},
        )

        # -- Stage 3: Human suspend -----------------------------------------
        display = EvidenceArtifactRef(
            uri="s3://prompts/approval-diff.png",
            content_type="image/png",
            name="approval-diff",
        )
        gate_inv = StepInvocation(
            step_id="human-gate",
            adapter_kind="human",  # unknown kind — fails closed at lookup
            produces=(_port("gate_decision", "application/x-verdict+json"),),
            consumes=(_port_ref("analyzed", "application/x-verdict+json"),),
            artifacts=(display,),
            payload={"gate": "security-approval"},
        )

        # -- Stage 4: Reduce verdict (tool, fan-out-reduce) ------------------
        reduce_inv = StepInvocation(
            step_id="verdict",
            adapter_kind="tool",
            produces=(_port("final_verdict", "application/x-verdict+json"),),
            consumes=(_port_ref("analyzed", "application/x-verdict+json"),),
            artifacts=(),
            payload={"strategy": "majority-vote"},
        )

        # -- Stage 5: Failure handler (tool) ---------------------------------
        fail_inv = StepInvocation(
            step_id="fail-handler",
            adapter_kind="tool",
            produces=(_port("error_report", "application/json"),),
            consumes=(_port_ref("final_verdict", "application/x-verdict+json"),),
            artifacts=(
                EvidenceArtifactRef(
                    uri="s3://logs/error.log",
                    content_type="text/plain",
                    name="error-log",
                ),
            ),
            payload={"on_failure": "notify"},
        )

        # Assertions: the shape is expressible
        assert scan_inv.adapter_kind == "tool"
        assert fan_inv.adapter_kind == "tool"
        assert gate_inv.adapter_kind == "human"
        assert reduce_inv.adapter_kind == "tool"
        assert fail_inv.adapter_kind == "tool"

        # All produce ports are declared
        assert scan_inv.produces[0].name == "scan_result"
        assert fan_inv.produces[0].name == "analyzed"
        assert fan_inv.produces[0].cardinality == "collection"
        assert gate_inv.produces[0].name == "gate_decision"
        assert reduce_inv.produces[0].name == "final_verdict"
        assert fail_inv.produces[0].name == "error_report"

        # Fan-out has multi-content-type by-reference artifacts
        fan_content_types = {a.content_type for a in fan_inv.artifacts}
        assert "image/png" in fan_content_types
        assert "text/markdown" in fan_content_types
        assert "application/x-git-diff" in fan_content_types

        # Adapter registry: only model registered; tool/human/state fail closed
        registry = AdapterRegistry()
        registry.register(TestAdapterRegistryFailClosed._make_placeholder_model_adapter())

        # model lookup succeeds
        assert registry.lookup("model").kind == "model"

        # tool/human/state fail closed
        with pytest.raises(KeyError):
            registry.lookup("tool")
        with pytest.raises(KeyError):
            registry.lookup("human")
        with pytest.raises(KeyError):
            registry.lookup("state")

    def test_contract_result_payloads_for_all_stages(self) -> None:
        """Each stage's result can be expressed as a ContractResult."""
        # Scan result
        scan_cr = ContractResult(
            payload={"scan_type": "security", "findings": 0},
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                EvidenceArtifactRef(
                    uri="s3://evidence/scan-001.json",
                    content_type="application/json",
                    name="scan-output",
                ),
            ),
            authority_level="verified",
            provenance=Provenance(generator="scanner@1.2"),
            freshness=Freshness(ttl_seconds=3600),
        )

        # Fan-out result
        fan_cr = ContractResult(
            payload={"fan_out_count": 3, "strategy": "broadcast"},
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            evidence_refs=(
                EvidenceArtifactRef(uri="s3://evidence/diagram.png", content_type="image/png", name="diagram"),
                EvidenceArtifactRef(uri="s3://evidence/report.md", content_type="text/markdown", name="report"),
            ),
            authority_level="advisory",
            provenance=Provenance(generator="fanout@1.0"),
            freshness=Freshness(ttl_seconds=600),
        )

        # Verdict result
        verdict_cr = ContractResult(
            payload={"verdict": "pass", "score": 0.97},
            status=ContractStatus.COMPLETED,
            schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
            authority_level="verified",
            provenance=Provenance(generator="verdict-engine@2.0"),
            freshness=Freshness(ttl_seconds=3600),
        )

        assert scan_cr.status == ContractStatus.COMPLETED
        assert fan_cr.status == ContractStatus.COMPLETED
        assert verdict_cr.status == ContractStatus.COMPLETED
        assert verdict_cr.payload["verdict"] == "pass"
        assert len(scan_cr.evidence_refs) == 1
        assert len(fan_cr.evidence_refs) == 2
