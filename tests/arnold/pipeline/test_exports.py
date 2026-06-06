"""Import smoke tests for ``arnold.pipeline`` public surface (M3a T5).

Verifies that every promised public symbol is importable from
``arnold.pipeline`` and that the bridge re-exports in megaplan
continue to work.
"""

from __future__ import annotations


class TestArnoldPipelinePublicExports:
    """Every symbol in arnold.pipeline.__all__ must be importable."""

    def test_core_types_importable(self) -> None:
        from arnold.pipeline import (
            Edge,
            ParallelStage,
            Pipeline,
            PipelineVerdict,
            Stage,
            Step,
            StepContext,
            StepResult,
        )
        # Smoke: all symbols resolved without ImportError.
        assert Edge is not None
        assert ParallelStage is not None
        assert Pipeline is not None
        assert PipelineVerdict is not None
        assert Stage is not None
        assert Step is not None
        assert StepContext is not None
        assert StepResult is not None

    def test_state_symbols_importable(self) -> None:
        from arnold.pipeline import StateDelta, apply_delta
        assert StateDelta is not None
        assert apply_delta is not None

    def test_executor_symbols_importable(self) -> None:
        from arnold.pipeline import run_pipeline
        assert run_pipeline is not None

    def test_step_invocation_symbols_importable(self) -> None:
        from arnold.pipeline import (
            ModelAdapterNotImplementedError,
            StepInvocation,
            StepInvocationAdapter,
            StepInvocationAdapterRegistry,
        )
        assert StepInvocation is not None
        assert StepInvocationAdapter is not None
        assert StepInvocationAdapterRegistry is not None
        assert ModelAdapterNotImplementedError is not None

    def test_typed_port_symbols_importable(self) -> None:
        from arnold.pipeline import (
            CONTENT_TYPES,
            ContentValidatorRegistry,
            ContentTypeRegistry,
            Port,
            PortRef,
            RoutingKey,
            SeamId,
            register_schema,
        )
        assert Port is not None
        assert PortRef is not None
        assert RoutingKey is not None
        assert SeamId is not None
        assert ContentTypeRegistry is not None
        assert ContentValidatorRegistry is not None
        assert CONTENT_TYPES is not None
        assert register_schema is not None

    def test_reduce_selection_symbols_importable(self) -> None:
        from arnold.pipeline import ReduceResult, SelectionResult
        assert ReduceResult is not None
        assert SelectionResult is not None

    def test_profile_symbols_importable(self) -> None:
        from arnold.pipeline import (
            AgentSpecShape,
            ProfileLoadError,
            load_profile_metadata,
            load_profile_sources,
            load_profiles,
            merge_profile_layers,
            parse_agent_spec_shape,
            parse_profiles_doc,
            resolve_default_profile,
            validate_declared_stage_keys,
        )
        assert AgentSpecShape is not None
        assert ProfileLoadError is not None
        assert load_profile_metadata is not None
        assert load_profile_sources is not None
        assert load_profiles is not None
        assert merge_profile_layers is not None
        assert parse_agent_spec_shape is not None
        assert parse_profiles_doc is not None
        assert resolve_default_profile is not None
        assert validate_declared_stage_keys is not None

    def test_contract_result_symbols_importable(self) -> None:
        from arnold.pipeline import (
            AcceptedVersionRange,
            ContractSchemaRegistry,
            CONTRACT_RESULT_SCHEMA_VERSION,
            ContractResult,
            ContractStatus,
            EvidenceArtifactRef,
            Freshness,
            Provenance,
            ValidationResult,
            Suspension,
            select_audit_mode,
        )
        assert AcceptedVersionRange is not None
        assert ContractSchemaRegistry is not None
        assert ContractResult is not None
        assert ContractStatus is not None
        assert EvidenceArtifactRef is not None
        assert Freshness is not None
        assert Provenance is not None
        assert Suspension is not None
        assert ValidationResult is not None
        assert select_audit_mode is not None
        assert CONTRACT_RESULT_SCHEMA_VERSION is not None


class TestBridgeImports:
    """Bridge re-exports from megaplan must still resolve."""

    def test_megaplan_types_bridge_imports(self) -> None:
        """Symbols re-exported via megaplan._pipeline.types bridge from Arnold."""
        from arnold.pipelines.megaplan._pipeline.types import (
            CONTENT_TYPES,
            ContentTypeRegistry,
            Port,
            PortRef,
            ReduceResult,
            RoutingKey,
            SelectionResult,
            register_schema,
        )
        assert Port is not None
        assert PortRef is not None
        assert RoutingKey is not None
        assert ContentTypeRegistry is not None
        assert CONTENT_TYPES is not None
        assert register_schema is not None
        assert ReduceResult is not None
        assert SelectionResult is not None

    def test_megaplan_pipeline_bridge_imports(self) -> None:
        """Core types still importable from megaplan._pipeline."""
        from arnold.pipelines.megaplan._pipeline import (
            Edge,
            ParallelStage,
            Pipeline,
            PipelineVerdict,
            Stage,
            Step,
            StepContext,
            StepResult,
        )
        assert Edge is not None
        assert ParallelStage is not None
        assert Pipeline is not None
        assert PipelineVerdict is not None
        assert Stage is not None
        assert Step is not None
        assert StepContext is not None
        assert StepResult is not None

    def test_arnold_types_are_neutral_dataclasses(self) -> None:
        """Arnold's Port/RoutingKey/PortRef must be the concrete dataclass versions."""
        from arnold.pipeline.types import Port, RoutingKey, PortRef
        from dataclasses import is_dataclass
        # Arnold versions are concrete frozen dataclasses (not Protocols).
        assert is_dataclass(Port)
        assert is_dataclass(RoutingKey)
        assert is_dataclass(PortRef)


class TestDiscoveryStepsStubs:
    """The discovery/ and steps/ stub packages exist and are importable."""

    def test_discovery_stub_importable(self) -> None:
        import arnold.pipeline.discovery  # noqa: F401

    def test_steps_stub_importable(self) -> None:
        import arnold.pipeline.steps  # noqa: F401
