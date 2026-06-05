"""Pipeline runtime policy modules — Sprint 4 Chunk C.

Extracts the cross-cutting concerns from ``megaplan/auto.py`` into
small, composable policy classes that the Pipeline executor can
consult between stage dispatches. Each policy has a single
responsibility and a clean dependency on per-stage events; the
executor wires them together via :class:`RuntimePolicy`.

The legacy ``auto.py`` phase loop is preserved as the default; the
``MEGAPLAN_PIPELINE_AUTO=1`` env var flips the dispatch to
:func:`run_pipeline_with_policy` (defined in
``megaplan/_pipeline/executor.py``).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass
class StallDetector:
    """Detects when the auto loop stops making progress.

    Mirrors the ``--stall-threshold`` semantics from auto.py: count
    consecutive iterations where neither ``current_state`` nor the
    review-rework counter advances. A separate threshold for the
    review→rework cycle is held by :class:`ReviewReworkLimiter`.
    """

    threshold: int = 5
    _prev_state: Optional[str] = None
    _prev_review_writes: int = 0
    _streak: int = 0

    def observe(self, state: Mapping[str, Any]) -> None:
        cur_state = state.get("current_state")
        review_writes = sum(
            1 for h in state.get("history", []) if h.get("step") == "review"
        )
        if cur_state != self._prev_state or review_writes != self._prev_review_writes:
            self._streak = 0
        else:
            self._streak += 1
        self._prev_state = cur_state
        self._prev_review_writes = review_writes

    def is_stalled(self) -> bool:
        return self._streak >= self.threshold

    def reset(self) -> None:
        self._streak = 0


@dataclass
class CostTracker:
    """Caps cumulative model spend.

    Reads ``state["meta"]["total_cost_usd"]`` after each phase and
    raises when the threshold is exceeded. ``None`` means no cap.
    """

    cap_usd: Optional[float] = None

    def _authority_total(self) -> Optional[float]:
        """Return the installed BudgetAuthority's live total when
        ``UNIFIED_BUDGET=1``, else ``None`` (legacy path)."""

        try:
            from arnold.pipelines.megaplan._pipeline.flags import unified_budget_on
            from arnold.pipelines.megaplan.runtime.budget_authority import current_authority
        except Exception:
            return None
        if not unified_budget_on():
            return None
        auth = current_authority()
        if auth is None:
            return None
        return float(auth.current_total())

    def should_abort(self, state: Mapping[str, Any]) -> bool:
        if self.cap_usd is None:
            return False
        auth_total = self._authority_total()
        if auth_total is not None:
            return auth_total > self.cap_usd
        meta = state.get("meta", {})
        cost = float(meta.get("total_cost_usd", 0.0) or 0.0)
        return cost > self.cap_usd

    def current_cost(self, state: Mapping[str, Any]) -> float:
        auth_total = self._authority_total()
        if auth_total is not None:
            return auth_total
        meta = state.get("meta", {})
        return float(meta.get("total_cost_usd", 0.0) or 0.0)


@dataclass
class EscalatePolicy:
    """Decides what to do when the gate emits an ESCALATE recommendation.

    Three modes match the legacy ``--on-escalate`` flag:
    ``force-proceed`` (default), ``abort``, or ``fail``. The
    Sprint-4 policy returns a string the executor uses to either
    follow the appropriate override edge (force-proceed → "proceed";
    abort → "escalate") or raise.
    """

    mode: str = "force-proceed"  # force-proceed | abort | fail

    def resolve(self, current_state: str) -> str:
        if self.mode == "force-proceed":
            return "force_proceed"
        if self.mode == "abort":
            return "abort"
        if self.mode == "fail":
            raise RuntimeError(
                f"EscalatePolicy=fail: gate escalated from state {current_state!r}"
            )
        raise ValueError(f"unknown EscalatePolicy mode: {self.mode}")


@dataclass
class ContextRetry:
    """Tracks fresh-execute retries after a Codex context-window exhaustion.

    Returns True from :meth:`should_retry` when a phase result reports
    a context-exhaustion signal AND the retry counter is below cap.
    """

    cap: int = 2
    _used: int = 0

    def should_retry(self, phase_result: Mapping[str, Any]) -> bool:
        if self._used >= self.cap:
            return False
        signal = (phase_result or {}).get("result") == "context_exhausted"
        if signal:
            self._used += 1
            return True
        return False


@dataclass
class BlockedRetry:
    """Retries execute when the worker reports result=blocked.

    Caps the retry count so a permanently-blocked task doesn't loop
    indefinitely. Mirrors ``--max-blocked-retries``.
    """

    cap: int = 1
    _used: int = 0

    def should_retry(self, phase_result: Mapping[str, Any]) -> bool:
        if self._used >= self.cap:
            return False
        if (phase_result or {}).get("result") == "blocked":
            self._used += 1
            return True
        return False


@dataclass
class RuntimePolicy:
    """Bundles every policy module the Pipeline runtime consults.

    Constructed once per ``megaplan auto`` invocation; mutated as
    side-effects by each phase event. Default values match the
    legacy CLI flag defaults.
    """

    stall: StallDetector = field(default_factory=StallDetector)
    cost: CostTracker = field(default_factory=CostTracker)
    escalate: EscalatePolicy = field(default_factory=EscalatePolicy)
    context_retry: ContextRetry = field(default_factory=ContextRetry)
    blocked_retry: BlockedRetry = field(default_factory=BlockedRetry)
    max_iterations: int = 200
    poll_sleep: float = 1.0
    started_at: float = field(default_factory=time.time)


def policy_from_cli_args(
    *,
    stall_threshold: int = 5,
    max_iterations: int = 200,
    max_cost_usd: Optional[float] = None,
    max_context_retries: int = 2,
    max_blocked_retries: int = 1,
    on_escalate: str = "force-proceed",
    poll_sleep: float = 1.0,
) -> RuntimePolicy:
    """Build a RuntimePolicy from auto.py's CLI flags.

    The flag names match ``megaplan auto`` exactly so wiring the
    runtime into auto.py is a one-line transformation.
    """

    return RuntimePolicy(
        stall=StallDetector(threshold=stall_threshold),
        cost=CostTracker(cap_usd=max_cost_usd),
        escalate=EscalatePolicy(mode=on_escalate),
        context_retry=ContextRetry(cap=max_context_retries),
        blocked_retry=BlockedRetry(cap=max_blocked_retries),
        max_iterations=max_iterations,
        poll_sleep=poll_sleep,
    )


def pipeline_runtime_enabled() -> bool:
    """Is the new Pipeline-walking runtime turned on?

    Defaults OFF in Chunk C (the legacy auto.py loop stays the
    default until parity holds for two chunks). Chunk E flips the
    default to ON.
    """

    return os.environ.get("MEGAPLAN_PIPELINE_AUTO", "0") == "1"
