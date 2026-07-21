"""Shared WBC adapter for the common worker-dispatch path."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, TypeVar

from arnold.workflow.execution_attempt_ledger import LedgerEvent

from .action_validator import ActionBoundaryContext
from .wbc_runtime import ImmutableAttemptArtifacts, RuntimeProducerResult, WbcRuntimeProducerFacade

COMMON_WORKER_DISPATCH_WRITER_ID = "megaplan.common_worker_dispatch"
COMMON_WORKER_DISPATCH_SURFACE = "megaplan.common_worker_dispatch"
COMMON_WORKER_DISPATCH_START_SOURCE_LOOKUP_KEY = "common_worker_dispatch:start"
COMMON_WORKER_DISPATCH_COMPLETE_SOURCE_LOOKUP_KEY = "common_worker_dispatch:complete"
COMMON_WORKER_DISPATCH_FAILURE_SOURCE_LOOKUP_KEY = "common_worker_dispatch:failure"

_ResultT = TypeVar("_ResultT")


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({str(key): _freeze_json(item) for key, item in sorted(value.items())})


class PostLaunchIndeterminateError(RuntimeError):
    """Raised when post-launch certification fails after worker code already ran."""

    def __init__(
        self,
        message: str,
        *,
        worker_result: Any,
        terminal_result: RuntimeProducerResult,
    ) -> None:
        super().__init__(message)
        self.worker_result = worker_result
        self.terminal_result = terminal_result


@dataclass(frozen=True)
class CommonWorkerDispatchResult:
    reserve: RuntimeProducerResult
    start: RuntimeProducerResult
    terminal: RuntimeProducerResult
    worker_result: Any
    diagnostics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", _freeze_mapping(self.diagnostics))


@dataclass(frozen=True)
class CommonWorkerDispatchSpec:
    facade: WbcRuntimeProducerFacade
    attempt_id: str
    start_event: LedgerEvent
    success_event_factory: Callable[[Any], LedgerEvent]
    failure_event_factory: Callable[[BaseException], LedgerEvent]
    start_action_context: ActionBoundaryContext
    success_action_context: ActionBoundaryContext
    failure_action_context: ActionBoundaryContext
    artifacts: ImmutableAttemptArtifacts | None = None
    post_dispatch_certificate: Callable[[Any], None] | None = None
    indeterminate_event_factory: Callable[[BaseException], LedgerEvent] | None = None
    writer_id: str = COMMON_WORKER_DISPATCH_WRITER_ID
    surface_name: str = COMMON_WORKER_DISPATCH_SURFACE
    expected_source_version: str = "source.v1"
    start_source_lookup_key: str = COMMON_WORKER_DISPATCH_START_SOURCE_LOOKUP_KEY
    success_source_lookup_key: str = COMMON_WORKER_DISPATCH_COMPLETE_SOURCE_LOOKUP_KEY
    failure_source_lookup_key: str = COMMON_WORKER_DISPATCH_FAILURE_SOURCE_LOOKUP_KEY

    def run(self, dispatch: Callable[[RuntimeProducerResult], _ResultT]) -> CommonWorkerDispatchResult:
        reserve = self.facade.reserve_attempt(
            attempt_id=self.attempt_id,
            writer_id=self.writer_id,
            surface_name=self.surface_name,
            source_lookup_key=self.start_source_lookup_key,
            expected_source_version=self.expected_source_version,
            action_context=self.start_action_context,
            artifacts=self.artifacts,
        )
        start = self.facade.start_attempt(
            attempt_id=self.attempt_id,
            event=self.start_event,
            writer_id=self.writer_id,
            surface_name=self.surface_name,
            source_lookup_key=self.start_source_lookup_key,
            expected_source_version=self.expected_source_version,
            action_context=self.start_action_context,
            artifacts=self.artifacts,
        )
        try:
            worker_result = dispatch(start)
        except BaseException as exc:
            terminal = self.facade.fail_attempt(
                attempt_id=self.attempt_id,
                event=self.failure_event_factory(exc),
                writer_id=self.writer_id,
                surface_name=self.surface_name,
                source_lookup_key=self.failure_source_lookup_key,
                expected_source_version=self.expected_source_version,
                action_context=self.failure_action_context,
                artifacts=self.artifacts,
            )
            raise exc from _FailureEvidenceRecorded(terminal)

        if self.post_dispatch_certificate is not None:
            try:
                self.post_dispatch_certificate(worker_result)
            except BaseException as exc:
                terminal = self.facade.fail_attempt(
                    attempt_id=self.attempt_id,
                    event=(self.indeterminate_event_factory or self.failure_event_factory)(exc),
                    writer_id=self.writer_id,
                    surface_name=self.surface_name,
                    source_lookup_key=self.failure_source_lookup_key,
                    expected_source_version=self.expected_source_version,
                    action_context=self.failure_action_context,
                    artifacts=self.artifacts,
                )
                raise PostLaunchIndeterminateError(
                    "post-launch certification failed after worker dispatch",
                    worker_result=worker_result,
                    terminal_result=terminal,
                ) from exc

        terminal = self.facade.complete_attempt(
            attempt_id=self.attempt_id,
            event=self.success_event_factory(worker_result),
            writer_id=self.writer_id,
            surface_name=self.surface_name,
            source_lookup_key=self.success_source_lookup_key,
            expected_source_version=self.expected_source_version,
            action_context=self.success_action_context,
            artifacts=self.artifacts,
        )
        return CommonWorkerDispatchResult(
            reserve=reserve,
            start=start,
            terminal=terminal,
            worker_result=worker_result,
            diagnostics={
                "writer_id": self.writer_id,
                "surface_name": self.surface_name,
                "attempt_id": self.attempt_id,
            },
        )


class _FailureEvidenceRecorded(Exception):
    """Internal marker used only to preserve the original failure cause."""

    def __init__(self, terminal_result: RuntimeProducerResult) -> None:
        super().__init__("failure evidence recorded")
        self.terminal_result = terminal_result


__all__ = [
    "COMMON_WORKER_DISPATCH_COMPLETE_SOURCE_LOOKUP_KEY",
    "COMMON_WORKER_DISPATCH_FAILURE_SOURCE_LOOKUP_KEY",
    "COMMON_WORKER_DISPATCH_START_SOURCE_LOOKUP_KEY",
    "COMMON_WORKER_DISPATCH_SURFACE",
    "COMMON_WORKER_DISPATCH_WRITER_ID",
    "CommonWorkerDispatchResult",
    "CommonWorkerDispatchSpec",
    "PostLaunchIndeterminateError",
]
