"""In-process driver for pipeline steps.

``InProcessDriver`` runs a step callable directly in the current process —
there is **no** subprocess isolation.  This is the simplest driver and the
one used when the step is a pure-Python function that the caller trusts
not to corrupt process state.

Crash-isolation trade (documented, deliberate)
----------------------------------------------
Unlike :class:`SubprocessIsolatedDriver`, this driver runs the step in the
same OS process.  Two consequences follow:

1. ``sys.exit(1)`` inside the step **propagates** ``SystemExit`` to the
   caller.  The driver does **not** catch it — the whole process terminates
   unless the caller has installed its own ``sys.exit`` hook.  This is the
   defining crash-isolation gap.

2. A regular exception (``ValueError``, ``RuntimeError``, …) is **caught**
   by the driver and surfaced as a :class:`StepResult` whose
   ``state_patch`` carries ``{"failed": True, "error": …, "error_type": …}``.
   The step is marked ``next="halt"`` so the pipeline terminates cleanly
   rather than raising through the executor main loop.

When the pipeline executor (:func:`megaplan._pipeline.executor.run_pipeline`)
is the intended consumer, the driver can delegate to it for single-step
execution by constructing a minimal ``Pipeline`` wrapping the callable.
The direct-call path used here is equivalent for the single-step case and
avoids the executor's iteration machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult


@dataclass
class InProcessDriver:
    """Runs a pipeline step **in-process** (no subprocess isolation).

    Attributes:
        name: Step identifier forwarded to the pipeline registry.
        kind: Step kind (default ``"produce"``).
        step_func: The callable that implements the step.  Receives a
            ``StepContext`` and must return a ``StepResult`` on success.
    """

    name: str = "in_process"
    kind: Literal["produce", "judge", "decide", "subloop", "override"] = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple[Any, ...] = ()
    consumes: tuple[Any, ...] = ()

    step_func: Callable[[StepContext], StepResult] | None = None

    def run_step(self, ctx: StepContext) -> StepResult:
        """Execute *step_func(ctx)* in the current process.

        Returns:
            The ``StepResult`` produced by *step_func* on success.

            On a regular exception the driver catches it and returns a
            ``StepResult`` with ``next="halt"`` and ``state_patch``
            carrying ``failed=True`` plus the exception details.

        Raises:
            SystemExit: **Propagated deliberately** — the driver does not
                intercept ``sys.exit()``.  This is the documented
                crash-isolation trade.
        """
        if self.step_func is None:
            return StepResult(
                next="halt",
                state_patch={"failed": True, "error": "step_func is None"},
            )

        try:
            return self.step_func(ctx)
        except SystemExit:
            # Deliberately propagate — no crash isolation.
            # Documented trade: in-process driver cannot contain a
            # sys.exit() the way a subprocess can.
            raise
        except BaseException as exc:
            return StepResult(
                next="halt",
                state_patch={
                    "failed": True,
                    "error": repr(exc),
                    "error_type": type(exc).__name__,
                },
            )
