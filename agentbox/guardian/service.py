"""Guardian service wiring and lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arnold.runtime.durable_ops import FileBackedDurableOpsStore

from agentbox.config import AgentBoxConfig
from agentbox.guardian.handlers import GuardianHandlerRegistry, default_guardian_handler_registry
from agentbox.guardian.notifications import GuardianNotifier, OutboundSink
from agentbox.guardian.scheduler import ensure_guardian_tasks
from agentbox.guardian.state import GuardianStateStore
from agentbox.guardian.worker import GuardianWorker


@dataclass
class GuardianService:
    """Top-level Guardian lifecycle owner."""

    config: AgentBoxConfig
    operation_store: FileBackedDurableOpsStore
    resident_store: Any | None = None
    outbound: OutboundSink | None = None
    handler_registry: GuardianHandlerRegistry = field(
        default_factory=default_guardian_handler_registry
    )
    notifier: GuardianNotifier | None = None
    state_store: GuardianStateStore | None = None
    clock: Any | None = None
    poll_interval_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.state_store is None:
            self.state_store = GuardianStateStore(self.config)
        if self.notifier is None and (self.resident_store is not None or self.config is not None):
            self.notifier = GuardianNotifier(
                store=self.resident_store,
                outbound=self.outbound,
                operation_store=self.operation_store,
                config=self.config,
                state_store=self.state_store,
            )
        if self.clock is None:
            self.clock = _SystemClock()

    async def run_once(self, *, max_operations: int = 50) -> dict[str, Any]:
        """Run a single Guardian tick if not globally paused."""

        if self.is_paused():
            return {"paused": True, "tasks_run": 0, "operations_supervised": 0}

        ensure_guardian_tasks(self.config, now=self.clock.now())
        worker = GuardianWorker(
            config=self.config,
            operation_store=self.operation_store,
            handler_registry=self.handler_registry,
            notifier=self.notifier,
            state_store=self.state_store,
        )
        return await worker.run_due_once(
            now=self.clock.now(),
            max_operations=max_operations,
        )

    async def run_forever(self) -> None:
        """Poll and run Guardian ticks until cancelled."""

        while True:
            await self.run_once()
            await asyncio.sleep(self.poll_interval_seconds)

    def pause(self, reason: str | None = None) -> dict[str, Any]:
        """Pause the Guardian without touching operations or leases."""

        return self.state_store.set_global_pause(
            True,
            reason=reason or "operator",
            now=self.clock.now(),
        )["global_pause"]

    def resume(self) -> dict[str, Any]:
        """Resume normal Guardian operation."""

        return self.state_store.set_global_pause(
            False,
            reason=None,
            now=self.clock.now(),
        )["global_pause"]

    def is_paused(self) -> bool:
        return bool(self.state_store.read().get("global_pause", {}).get("paused"))

    def status(self) -> dict[str, Any]:
        state = self.state_store.read()
        pause = state.get("global_pause", {})
        return {
            "paused": bool(pause.get("paused")),
            "reason": pause.get("reason"),
            "updated_at": pause.get("updated_at"),
            "scheduled_task_count": len(self.operation_store.list_scheduled_tasks()),
            "operation_notification_dedupe_count": len(
                state.get("operation_notification_dedupe", {})
            ),
        }

    @classmethod
    def default(cls, config: AgentBoxConfig | None = None) -> "GuardianService":
        """Factory for CLI usage using file-backed stores."""

        config = config or AgentBoxConfig()
        operation_store = FileBackedDurableOpsStore(config.ops_store_root)
        resident_store = None
        try:
            from arnold_pipelines.megaplan.store import FileStore

            resident_store = FileStore(_resident_store_root(config))
        except Exception:
            resident_store = None
        return cls(
            config=config,
            operation_store=operation_store,
            resident_store=resident_store,
        )


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _resident_store_root(config: AgentBoxConfig) -> Path:
    root = config.workspace_root / "resident_store"
    root.mkdir(parents=True, exist_ok=True)
    return root


__all__ = [
    "GuardianService",
]
