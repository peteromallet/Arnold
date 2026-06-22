from __future__ import annotations

import pytest

from arnold.agent.contracts import AgentRequest, AgentResult
from arnold.execution.registries import (
    AgentCapabilityHandler,
    AgentEffectHandler,
    AgentReducerHandler,
    AuthorityRegistry,
    CapabilityHandler,
    CapabilityRegistry,
    ControlRegistry,
    EffectHandler,
    EffectRegistry,
    ExecutionRegistries,
    ReducerHandler,
    ReducerRegistry,
    build_agent_adapter_bridge,
)
from arnold.kernel import CapabilityCheck, CapabilityId, ControlBinding, ControlTarget, ControlTransitionType


class FakeCapabilityHandler:
    def check(self, requirement_id: str, *, route: str, context: dict) -> CapabilityCheck:
        return CapabilityCheck(
            capability_id=CapabilityId(namespace="test", name=requirement_id),
            allowed=True,
        )


class FakeEffectHandler:
    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: dict,
        idempotency_key: str,
        context: dict,
    ) -> dict:
        return {"effect_id": effect_id, "route": route, "payload": payload}


class FakeReducerHandler:
    def reduce(self, reducer_id: str, *, inputs: tuple[dict, ...], context: dict) -> dict:
        return {"reducer_id": reducer_id, "count": len(inputs)}


class FakeControlHandler:
    def apply(
        self,
        transition_id: str,
        *,
        transition_type: str,
        binding: ControlBinding,
        context: dict,
    ):
        from arnold.kernel import ControlTransition

        return ControlTransition(
            transition_type=ControlTransitionType.OVERRIDE,
            source=binding.target,
            target=binding.target,
            trigger=transition_id,
            payload_schema_hash="sha256:" + "0" * 64,
            policy_ref=binding.policy_ref,
            idempotency_key="idem-1",
        )


class FakeAuthorityHandler:
    def verify(self, authority_id: str, *, action: str, evidence: dict, context: dict) -> bool:
        return evidence.get("approved", False)


def test_capability_registry_fails_closed_on_unregistered_key() -> None:
    registry = CapabilityRegistry()
    with pytest.raises(LookupError, match="unregistered"):
        registry.check("unknown")


def test_effect_registry_fails_closed_on_unregistered_key() -> None:
    registry = EffectRegistry()
    with pytest.raises(LookupError, match="unregistered"):
        registry.execute("unknown", idempotency_key="k")


def test_reducer_registry_fails_closed_on_unregistered_key() -> None:
    registry = ReducerRegistry()
    with pytest.raises(LookupError, match="unregistered"):
        registry.reduce("unknown", inputs=())


def test_control_registry_fails_closed_on_unregistered_key() -> None:
    registry = ControlRegistry()
    binding = ControlBinding(binding_id="b1", target=ControlTarget("n1"))
    with pytest.raises(LookupError, match="unregistered"):
        registry.apply("unknown", transition_type="override", binding=binding)


def test_authority_registry_fails_closed_on_unregistered_key() -> None:
    registry = AuthorityRegistry()
    with pytest.raises(LookupError, match="unregistered"):
        registry.verify("unknown", action="resume", evidence={})


def test_registry_rejects_handler_that_does_not_satisfy_protocol() -> None:
    registry = CapabilityRegistry()
    with pytest.raises(TypeError, match="CapabilityHandler"):
        registry.register("bad", object())


def test_capability_registry_routes_to_registered_handler() -> None:
    registry = CapabilityRegistry()
    registry.register("cap.read", FakeCapabilityHandler())
    result = registry.check("cap.read", route="default", context={"x": 1})
    assert result.allowed is True


def test_effect_registry_requires_idempotency_key() -> None:
    registry = EffectRegistry()
    registry.register("fx.write", FakeEffectHandler())
    with pytest.raises(ValueError, match="idempotency_key"):
        registry.execute("fx.write", route="default", payload={})


def test_effect_registry_routes_to_registered_handler() -> None:
    registry = EffectRegistry()
    registry.register("fx.write", FakeEffectHandler())
    result = registry.execute(
        "fx.write",
        route="default",
        payload={"value": 1},
        idempotency_key="idem-1",
    )
    assert result["effect_id"] == "fx.write"


def test_reducer_registry_routes_to_registered_handler() -> None:
    registry = ReducerRegistry()
    registry.register("reducer.sum", FakeReducerHandler())
    result = registry.reduce(
        "reducer.sum",
        inputs=({"v": 1}, {"v": 2}),
        context={},
    )
    assert result["count"] == 2


def test_control_registry_routes_to_registered_handler() -> None:
    registry = ControlRegistry()
    registry.register("ctrl.override", FakeControlHandler())
    binding = ControlBinding(binding_id="b1", target=ControlTarget("n1"))
    result = registry.apply(
        "ctrl.override",
        transition_type="override",
        binding=binding,
    )
    assert result is not None
    assert result.trigger == "ctrl.override"


def test_authority_registry_routes_to_registered_handler() -> None:
    registry = AuthorityRegistry()
    registry.register("auth.operator", FakeAuthorityHandler())
    assert registry.verify("auth.operator", action="resume", evidence={"approved": True})
    assert not registry.verify("auth.operator", action="resume", evidence={"approved": False})


def test_manifest_fields_are_never_treated_as_import_paths() -> None:
    """Registry keys are opaque strings; no dynamic import is performed."""

    registry = CapabilityRegistry()
    registry.register("arnold.pipelines.megaplan:capability", FakeCapabilityHandler())
    # The handler is still found by the opaque string key.
    assert registry.check("arnold.pipelines.megaplan:capability").allowed is True

    effect_registry = EffectRegistry()
    effect_registry.register("python:os.system", FakeEffectHandler())
    result = effect_registry.execute(
        "python:os.system",
        idempotency_key="idem",
        payload={"cmd": "echo"},
    )
    assert result["effect_id"] == "python:os.system"


def test_agent_adapter_bridge_satisfies_protocols_without_product_imports() -> None:
    """The bridge wraps an arnold.agent dispatcher; no megaplan pipeline import."""

    class FakeDispatcher:
        def dispatch(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                payload={"agent": request.agent},
                raw_output=f"ok:{request.agent}",
                duration_ms=1,
                cost_usd=0.0,
            )

    registries = build_agent_adapter_bridge(FakeDispatcher())

    assert isinstance(registries.capabilities, CapabilityRegistry)
    assert isinstance(registries.effects, EffectRegistry)
    assert isinstance(registries.reducers, ReducerRegistry)

    cap_result = registries.capabilities.check("agent.default")
    assert cap_result.allowed is True

    effect_result = registries.effects.execute(
        "agent.default",
        idempotency_key="idem-1",
        payload={"task": "hello"},
    )
    assert "ok:agent.default" in effect_result["output"]

    reducer_result = registries.reducers.reduce(
        "agent.default",
        inputs=({"a": 1}, {"b": 2}),
    )
    assert reducer_result["output"].startswith("ok:")


def test_execution_registries_wraps_plain_mappings_for_compat() -> None:
    registries = ExecutionRegistries(capabilities={"agent.default": object()})
    assert isinstance(registries.capabilities, CapabilityRegistry)


def test_execution_registries_defaults_are_empty_typed_registries() -> None:
    registries = ExecutionRegistries()
    assert isinstance(registries.capabilities, CapabilityRegistry)
    assert isinstance(registries.effects, EffectRegistry)
    assert isinstance(registries.reducers, ReducerRegistry)
    assert isinstance(registries.controls, ControlRegistry)
    assert isinstance(registries.authorities, AuthorityRegistry)
