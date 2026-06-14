"""Tests for ``arnold.runtime.operations`` (T4 / SC4)."""

from __future__ import annotations

from arnold.runtime.operations import (
    NullOperationRegistry,
    OperationKind,
    OperationRegistry,
    OperationRequest,
    OperationResult,
)


class TestOperationKindEnumeration:
    def test_six_neutral_operation_kinds_exist(self) -> None:
        # The brief mandates carriers for: run phase, status/control
        # projection, resume, override list/apply, profile validation.
        kinds = {k for k in OperationKind}
        assert kinds == {
            OperationKind.EXECUTE,
            OperationKind.STATUS_PROJECTION,
            OperationKind.RESUME,
            OperationKind.OVERRIDE_LIST,
            OperationKind.OVERRIDE_APPLY,
            OperationKind.PROFILE_VALIDATE,
        }
        assert len(kinds) == 6

    def test_kind_values_are_runtime_neutral_strings(self) -> None:
        # No forbidden Megaplan vocabulary in the kind values themselves.
        forbidden = {
            "planning",
            "critique",
            "finalize",
            "tiebreaker",
            "escalate",
            "force_proceed",
            "abort",
            "replan",
            "add_note",
        }
        for kind in OperationKind:
            assert kind.value not in forbidden


class TestNullOperationRegistry:
    def test_supported_operations_returns_empty_frozenset(self) -> None:
        registry = NullOperationRegistry()
        supported = registry.supported_operations()
        assert supported == frozenset()
        assert isinstance(supported, frozenset)
        assert len(supported) == 0

    def test_dispatch_returns_unsupported_result_for_every_kind(self) -> None:
        registry = NullOperationRegistry()
        for kind in OperationKind:
            req = OperationRequest(kind=kind, payload={"opaque": "data"})
            result = registry.dispatch(req)
            assert isinstance(result, OperationResult)
            assert result.ok is False
            assert result.payload == {}
            assert result.errors == ("unsupported", kind.value)

    def test_dispatch_does_not_raise_for_any_kind(self) -> None:
        registry = NullOperationRegistry()
        for kind in OperationKind:
            # If this raises pytest will fail the test.
            registry.dispatch(OperationRequest(kind=kind))

    def test_dispatch_does_not_raise_on_unknown_kind_string(self) -> None:
        # Defensive: callers that hand-construct a request with a bare
        # string (rather than an enum value) must still get a structured
        # unsupported result, not an unhandled exception.
        registry = NullOperationRegistry()

        class _Fake:
            value = "made_up_kind"

        # Bypass the dataclass type by going through the runtime path
        req = OperationRequest.__new__(OperationRequest)
        object.__setattr__(req, "kind", _Fake())
        object.__setattr__(req, "payload", {})
        result = registry.dispatch(req)
        assert result.ok is False
        assert result.errors[0] == "unsupported"


class TestOperationRegistryProtocol:
    def test_null_registry_satisfies_protocol(self) -> None:
        # ``OperationRegistry`` is a ``runtime_checkable`` Protocol — the
        # null registry must structurally satisfy it.
        registry = NullOperationRegistry()
        assert isinstance(registry, OperationRegistry)
