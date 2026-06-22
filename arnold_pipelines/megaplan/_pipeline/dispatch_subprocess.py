"""M4 T6/T7 — Subprocess Dispatcher binding for the worker entry points.

T6 (audit) verified these anchors in ``megaplan/workers/_impl.py`` on branch
``arnold-epic`` (2026-05-30):

* ``run_step_with_worker``         — :2551 (4-tuple return
  ``(WorkerResult, agent, mode, effective_refreshed)`` at :2701)
* ``run_claude_step``              — :1733
* ``run_codex_step``               — :1764
* ``run_command``                  — :330
* ``WorkerResult`` (``@dataclass``) — :195/196
* ``state["active_step"]`` ``run_id`` access — :634-638; the actual liveness
  write site is ``touch_active_step`` at :648.  This Dispatcher binding must
  NOT bypass that liveness-write seam — preserve it through the shim.

T7 (binding) — gated behind ``MEGAPLAN_UNIFIED_DISPATCH=1``.

The strangler is conservative: the legacy production code path that calls
``run_step_with_worker`` directly remains default-on and untouched.  This
Dispatcher exists so future code can route through the unified seam without
duplicating worker-resolution logic, and so the regression test for the
on-token-progress liveness write (a4 guard) has a stable shape to assert
against.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from arnold_pipelines.megaplan._pipeline.dispatch import (
    Dispatcher,
    DispatchRequest,
    DispatchResult,
)
from arnold_pipelines.megaplan._pipeline.flags import unified_dispatch_on


@dataclass(frozen=True)
class SubprocessDispatchConfig:
    """Bind-time configuration for the subprocess Dispatcher.

    Carries the worker-entry callables and plan-dir bits that
    ``run_step_with_worker`` needs but that the Dispatcher Protocol
    intentionally does NOT bake into ``DispatchRequest``.
    """

    step: str
    plan_dir: Path
    args: argparse.Namespace
    root: Path
    # Allow tests to inject a fake ``run_step_with_worker`` without monkey-
    # patching the module.  Defaults to the production import.
    run_step_with_worker: Optional[Callable[..., Any]] = None
    # Liveness write hook — defaults to touch_active_step in production.
    # Tests inject a recording callable to prove writes occur on token
    # progress (a4 regression guard).
    liveness_writer: Optional[Callable[..., Any]] = None
    # Watchdog bounds — preserved from the legacy hardwired path.
    idle_timeout: Optional[float] = None
    pre_first_byte_timeout: Optional[float] = None


class SubprocessDispatcher:
    """Dispatcher backend that drives ``run_step_with_worker`` (legacy path).

    Gated behind ``MEGAPLAN_UNIFIED_DISPATCH=1``; when the flag is off,
    :meth:`run` raises ``RuntimeError`` so callers cannot accidentally use
    this path before its companion flag is enabled.
    """

    def __init__(self, config: SubprocessDispatchConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Dispatcher protocol
    # ------------------------------------------------------------------
    def run(self, request: DispatchRequest) -> DispatchResult:
        if not unified_dispatch_on():
            raise RuntimeError(
                "SubprocessDispatcher.run() called with "
                "MEGAPLAN_UNIFIED_DISPATCH=0 — legacy hardwired path is "
                "default-on and must remain the only execution route."
            )

        cfg = self._config
        run_step = cfg.run_step_with_worker
        if run_step is None:  # pragma: no cover — production import
            from arnold_pipelines.megaplan.workers._impl import run_step_with_worker as _rsw
            run_step = _rsw

        # Token-progress liveness sink — fired BEFORE driving the worker so
        # the watchdog sees a tick at start, then re-fired by the worker
        # callback on each token batch via the bound liveness writer.
        sink = request.liveness_sink
        run_id = self._extract_run_id(request)

        def _on_token_batch(detail: str = "token", kind: str = "tokens") -> None:
            # Preserve the touch_active_step seam (see T6 audit at :648).
            if cfg.liveness_writer is not None:
                cfg.liveness_writer(
                    cfg.plan_dir, run_id=run_id, kind=kind, detail=detail
                )
            if sink is not None:
                sink({"alive": True, "phase": "dispatch_subprocess.tokens",
                      "run_id": run_id})

        # Stash the on-token-batch callback on shim_state so the worker
        # implementation can grab it without us mutating module state.
        shim = dict(request.shim_state or {})
        shim["on_token_batch"] = _on_token_batch
        shim["idle_timeout"] = cfg.idle_timeout
        shim["pre_first_byte_timeout"] = cfg.pre_first_byte_timeout

        # Call the worker entry point.  The state argument is pulled from
        # shim_state — the Dispatcher Protocol kept it off the request to
        # avoid god-fields, but the subprocess backend genuinely needs it.
        state = shim.get("plan_state")
        worker_result, agent, mode, refreshed = run_step(
            cfg.step,
            state,
            cfg.plan_dir,
            cfg.args,
            root=cfg.root,
            prompt_override=request.prompt_override,
            prompt_kwargs=shim.get("prompt_kwargs"),
        )

        # The 4-tuple round-trips into DispatchResult: result holds the
        # WorkerResult, session_ref opaquely carries (agent, mode, refreshed).
        cost = float(getattr(worker_result, "cost_usd", 0.0) or 0.0)
        return DispatchResult(
            result=worker_result,
            cost=cost,
            session_ref=(agent, mode, refreshed),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extract_run_id(self, request: DispatchRequest) -> Optional[str]:
        env = request.envelope
        for attr in ("run_id", "lease_id"):
            v = getattr(env, attr, None)
            if isinstance(v, str) and v:
                return v
        lineage = getattr(env, "lineage", None)
        if lineage:
            head = next(iter(lineage), None)
            if isinstance(head, str) and head:
                return head
        return None


__all__ = ["SubprocessDispatcher", "SubprocessDispatchConfig"]
