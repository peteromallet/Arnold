"""Protocol registries for the manifest runtime.

All runtime dispatch is keyed by explicit string identifiers. Manifest fields
are never treated as dynamic import paths. Unregistered keys fail closed.

The ``arnold.agent`` adapter bridge proves that product agent contracts can
satisfy registry protocols without importing any product pipeline packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from arnold.agent.contracts import AgentDispatcher, AgentRequest, AgentResult
from arnold.kernel import CapabilityCheck, CapabilityId, ControlBinding, ControlTransition


# ---------------------------------------------------------------------------
# Neutral handler protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class CapabilityHandler(Protocol):
    """Evaluate whether a capability requirement is satisfied."""

    def check(
        self,
        requirement_id: str,
        *,
        route: str,
        context: Mapping[str, Any],
    ) -> CapabilityCheck: ...


@runtime_checkable
class EffectHandler(Protocol):
    """Execute an external effect and return a structured result."""

    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ReducerHandler(Protocol):
    """Fold a sequence of fanout child outputs into a single value."""

    def reduce(
        self,
        reducer_id: str,
        *,
        inputs: tuple[Mapping[str, Any], ...],
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ControlHandler(Protocol):
    """Project a control transition without mutating the manifest."""

    def apply(
        self,
        transition_id: str,
        *,
        transition_type: str,
        binding: ControlBinding,
        context: Mapping[str, Any],
    ) -> ControlTransition | None: ...


@runtime_checkable
class AuthorityHandler(Protocol):
    """Verify authority evidence before a mutation is accepted."""

    def verify(
        self,
        authority_id: str,
        *,
        action: str,
        evidence: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Registries (fail closed)
# ---------------------------------------------------------------------------


class _Registry:
    """Base registry that fails closed on unregistered keys."""

    def __init__(self, handlers: Mapping[str, Any] | None = None) -> None:
        self._handlers: dict[str, Any] = dict(handlers or {})

    def register(self, key: str, handler: Any) -> None:
        if not key:
            raise ValueError("registry key must be non-empty")
        self._handlers[key] = handler

    def get(self, key: str) -> Any:
        try:
            return self._handlers[key]
        except KeyError as exc:
            raise LookupError(f"unregistered handler: {key!r}") from exc

    def has(self, key: str) -> bool:
        return key in self._handlers


class CapabilityRegistry(_Registry):
    """String-keyed capability handler registry."""

    def register(self, key: str, handler: CapabilityHandler) -> None:
        if not isinstance(handler, CapabilityHandler):
            raise TypeError(f"capability handler for {key!r} must satisfy CapabilityHandler")
        super().register(key, handler)

    def check(
        self,
        key: str,
        *,
        route: str = "default",
        context: Mapping[str, Any] | None = None,
    ) -> CapabilityCheck:
        handler = self.get(key)
        return handler.check(key, route=route, context=context or {})


class EffectRegistry(_Registry):
    """String-keyed external effect handler registry."""

    def register(self, key: str, handler: EffectHandler) -> None:
        if not isinstance(handler, EffectHandler):
            raise TypeError(f"effect handler for {key!r} must satisfy EffectHandler")
        super().register(key, handler)

    def execute(
        self,
        key: str,
        *,
        route: str = "default",
        payload: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if not idempotency_key:
            raise ValueError("effect execution requires an idempotency_key")
        handler = self.get(key)
        return handler.execute(
            key,
            route=route,
            payload=payload or {},
            idempotency_key=idempotency_key,
            context=context or {},
        )


class ReducerRegistry(_Registry):
    """String-keyed reducer handler registry."""

    def register(self, key: str, handler: ReducerHandler) -> None:
        if not isinstance(handler, ReducerHandler):
            raise TypeError(f"reducer handler for {key!r} must satisfy ReducerHandler")
        super().register(key, handler)

    def reduce(
        self,
        key: str,
        *,
        inputs: tuple[Mapping[str, Any], ...],
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        handler = self.get(key)
        return handler.reduce(key, inputs=inputs, context=context or {})


class ControlRegistry(_Registry):
    """String-keyed control transition handler registry."""

    def register(self, key: str, handler: ControlHandler) -> None:
        if not isinstance(handler, ControlHandler):
            raise TypeError(f"control handler for {key!r} must satisfy ControlHandler")
        super().register(key, handler)

    def apply(
        self,
        key: str,
        *,
        transition_type: str,
        binding: ControlBinding,
        context: Mapping[str, Any] | None = None,
    ) -> ControlTransition | None:
        handler = self.get(key)
        return handler.apply(
            key,
            transition_type=transition_type,
            binding=binding,
            context=context or {},
        )


class AuthorityRegistry(_Registry):
    """String-keyed authority verification registry."""

    def register(self, key: str, handler: AuthorityHandler) -> None:
        if not isinstance(handler, AuthorityHandler):
            raise TypeError(f"authority handler for {key!r} must satisfy AuthorityHandler")
        super().register(key, handler)

    def verify(
        self,
        key: str,
        *,
        action: str,
        evidence: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        handler = self.get(key)
        return handler.verify(
            key,
            action=action,
            evidence=evidence or {},
            context=context or {},
        )


# ---------------------------------------------------------------------------
# Aggregate registries container
# ---------------------------------------------------------------------------


@dataclass
class ExecutionRegistries:
    """Process-local protocol registries supplied by product integrations.

    For backward compatibility with the T5 skeleton, plain ``Mapping[str, Any]``
    dictionaries are accepted and wrapped into the appropriate typed registry
    without validating their values until a registry method is invoked.
    """

    capabilities: CapabilityRegistry | Mapping[str, Any] = field(
        default_factory=CapabilityRegistry
    )
    effects: EffectRegistry | Mapping[str, Any] = field(default_factory=EffectRegistry)
    reducers: ReducerRegistry | Mapping[str, Any] = field(default_factory=ReducerRegistry)
    controls: ControlRegistry | Mapping[str, Any] = field(default_factory=ControlRegistry)
    authorities: AuthorityRegistry | Mapping[str, Any] = field(
        default_factory=AuthorityRegistry
    )

    def __post_init__(self) -> None:
        if isinstance(self.capabilities, dict):
            object.__setattr__(
                self, "capabilities", CapabilityRegistry(self.capabilities)
            )
        if isinstance(self.effects, dict):
            object.__setattr__(self, "effects", EffectRegistry(self.effects))
        if isinstance(self.reducers, dict):
            object.__setattr__(self, "reducers", ReducerRegistry(self.reducers))
        if isinstance(self.controls, dict):
            object.__setattr__(self, "controls", ControlRegistry(self.controls))
        if isinstance(self.authorities, dict):
            object.__setattr__(self, "authorities", AuthorityRegistry(self.authorities))


# ---------------------------------------------------------------------------
# arnold.agent adapter bridge (product-neutral)
# ---------------------------------------------------------------------------


class AgentCapabilityHandler:
    """Wrap an ``arnold.agent`` dispatcher as a capability handler.

    The manifest's capability_id is mapped to an agent name; the handler
    dispatches a read-only agent request and returns allowed=True when the
    agent produces a non-empty raw output. No product pipeline imports are
    required.
    """

    def __init__(
        self,
        dispatcher: AgentDispatcher,
        *,
        mode: str = "unit",
        prompt_template: str = "{requirement_id}",
    ) -> None:
        self.dispatcher = dispatcher
        self.mode = mode
        self.prompt_template = prompt_template

    def check(
        self,
        requirement_id: str,
        *,
        route: str,
        context: Mapping[str, Any],
    ) -> CapabilityCheck:
        del route
        prompt = self.prompt_template.format(requirement_id=requirement_id, **context)
        request = AgentRequest(agent=requirement_id, mode=self.mode, prompt=prompt)
        result = self.dispatcher.dispatch(request)
        allowed = bool(result.raw_output.strip())
        return CapabilityCheck(
            capability_id=CapabilityId(namespace="agent", name=requirement_id),
            allowed=allowed,
            reason="agent returned output" if allowed else "agent returned empty output",
        )


class AgentEffectHandler:
    """Wrap an ``arnold.agent`` dispatcher as an effect handler.

    The manifest's effect_id is mapped to an agent name; payload fields are
    passed through the agent prompt. This is a neutral bridge: the runtime
    never imports a product pipeline package.
    """

    def __init__(
        self,
        dispatcher: AgentDispatcher,
        *,
        mode: str = "unit",
        prompt_template: str = "{effect_id}: {payload}",
    ) -> None:
        self.dispatcher = dispatcher
        self.mode = mode
        self.prompt_template = prompt_template

    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del route, idempotency_key, context
        prompt = self.prompt_template.format(effect_id=effect_id, payload=payload)
        request = AgentRequest(agent=effect_id, mode=self.mode, prompt=prompt)
        result = self.dispatcher.dispatch(request)
        return {
            "output": result.raw_output,
            "payload": dict(result.payload),
        }


class AgentReducerHandler:
    """Wrap an ``arnold.agent`` dispatcher as a reducer handler."""

    def __init__(
        self,
        dispatcher: AgentDispatcher,
        *,
        mode: str = "unit",
        prompt_template: str = "Reduce: {inputs}",
    ) -> None:
        self.dispatcher = dispatcher
        self.mode = mode
        self.prompt_template = prompt_template

    def reduce(
        self,
        reducer_id: str,
        *,
        inputs: tuple[Mapping[str, Any], ...],
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context
        prompt = self.prompt_template.format(reducer_id=reducer_id, inputs=inputs)
        request = AgentRequest(agent=reducer_id, mode=self.mode, prompt=prompt)
        result = self.dispatcher.dispatch(request)
        return {"output": result.raw_output, "payload": dict(result.payload)}


AgentHandlerFactory = Callable[[AgentDispatcher], Any]


def build_agent_adapter_bridge(
    dispatcher: AgentDispatcher,
    *,
    mode: str = "unit",
) -> ExecutionRegistries:
    """Return execution registries backed by an ``arnold.agent`` dispatcher."""

    return ExecutionRegistries(
        capabilities=CapabilityRegistry(
            {"agent.default": AgentCapabilityHandler(dispatcher, mode=mode)}
        ),
        effects=EffectRegistry(
            {"agent.default": AgentEffectHandler(dispatcher, mode=mode)}
        ),
        reducers=ReducerRegistry(
            {"agent.default": AgentReducerHandler(dispatcher, mode=mode)}
        ),
    )


__all__ = [
    "AgentCapabilityHandler",
    "AgentEffectHandler",
    "AgentReducerHandler",
    "AuthorityHandler",
    "AuthorityRegistry",
    "CapabilityHandler",
    "CapabilityRegistry",
    "ControlHandler",
    "ControlRegistry",
    "EffectHandler",
    "EffectRegistry",
    "ExecutionRegistries",
    "ReducerHandler",
    "ReducerRegistry",
    "build_agent_adapter_bridge",
]
