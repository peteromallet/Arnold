"""ReceiptDecorator — Sprint 5 Chunk D.

Wraps any :class:`Step` so a JSON receipt is written next to its
artifacts on every invocation: timestamps, duration, the step name,
the kind, the resolved slot, the verdict (if any), and the
output-path manifest. Receipts plug into the cohesion brief's
"plan-mode features as primitives" — what handle_<phase> writes
internally to ``step_receipt_*.json`` becomes a Step-side
decoration any user can opt in to.

Usage::

    step = ReceiptDecorator(CritiqueStep())
    # OR
    pipeline = Pipeline(
        stages={
            "critique": Stage(
                "critique", ReceiptDecorator(CritiqueStep()),
                edges=(Edge("gate", "gate"),),
            ),
        },
        entry="critique",
    )

After ``step.run(ctx)`` returns, the executor finds
``<plan_dir>/<step_name>/receipt.json`` alongside whatever the
wrapped Step wrote.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from megaplan._pipeline.types import Step, StepContext, StepMixinProperty, StepResult


@dataclass
class ReceiptDecorator(StepMixinProperty):
    """A Step that wraps another Step and writes a JSON receipt.

    The wrapped Step's protocol attributes are exposed verbatim so
    introspection (``isinstance(d, Step)``) keeps working.
    """

    inner: Step
    receipt_filename: str = "receipt.json"

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def kind(self) -> str:
        return self.inner.kind

    @property
    def prompt_key(self) -> str | None:
        return getattr(self.inner, "prompt_key", None)

    @property
    def slot(self) -> str | None:
        return getattr(self.inner, "slot", None)

    def run(self, ctx: StepContext) -> StepResult:
        started = time.time()
        try:
            result = self.inner.run(ctx)
            outcome = "success"
            err: str | None = None
        except BaseException as exc:
            outcome = "error"
            err = repr(exc)
            self._write_receipt(ctx, started, outcome, err, result=None)
            raise
        self._write_receipt(ctx, started, outcome, err, result=result)
        return result

    def _write_receipt(
        self,
        ctx: StepContext,
        started_at: float,
        outcome: str,
        error: str | None,
        result: StepResult | None,
    ) -> None:
        finished = time.time()
        receipt = {
            "step_name": self.name,
            "step_kind": self.kind,
            "slot": self.slot,
            "prompt_key": self.prompt_key,
            "mode": getattr(ctx, "mode", None),
            "started_at": started_at,
            "finished_at": finished,
            "duration_ms": int((finished - started_at) * 1000),
            "outcome": outcome,
            "error": error,
        }
        if result is not None:
            receipt["next"] = result.next
            receipt["outputs"] = {k: str(v) for k, v in result.outputs.items()}
            if result.verdict is not None:
                receipt["verdict"] = {
                    "score": result.verdict.score,
                    "flags": list(result.verdict.flags),
                    "recommendation": result.verdict.recommendation,
                    "override": result.verdict.override,
                }
            receipt["state_patch_keys"] = sorted(dict(result.state_patch).keys())

        out_dir = Path(ctx.plan_dir) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / self.receipt_filename
        out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str))
