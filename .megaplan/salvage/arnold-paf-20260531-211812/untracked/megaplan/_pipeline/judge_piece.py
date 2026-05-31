"""JudgePiece — Step protocol implementation for the Evaluand Ledger (M5-eval).

Five load-bearing invariants:

1. ``isinstance(JudgePiece(...), Step)`` is True — full Step Protocol surface.
2. ``verdict.payload['evaluand']`` is ALWAYS attached regardless of feature
   flag; ``_attributable`` joins consume that without a journal round-trip.
3. When ``MEGAPLAN_UNIFIED_DISPATCH=1``, exactly one ``emit_evaluand`` AND
   one ``write_prompt_bytes`` is performed per ``run`` call; when the flag is
   off both are no-ops.
4. ``judge_version`` is byte-stable for identical inputs and changes when
   the model identity (name@version) changes.
5. ``dispatch_judge`` is the single counted model-call entry: invoked exactly
   once per ``run`` (mock counter enforces in tests).

NOTE: ``register_node('judge.default', ...)`` lives in ``identity.py``, NOT
here — ``pipelines check`` populates NODE_REGISTRY without importing this
module.
"""

from __future__ import annotations

import hashlib
import inspect
import os
from datetime import datetime, timezone
from typing import Any, Final, Literal

from megaplan._pipeline.identity import (
    ARNOLD_API_VERSION,
    manifest_hash,
)
from megaplan._pipeline.types import Port, PipelineVerdict, StepContext, StepResult
from megaplan.observability.events import compute_model_identity


_JUDGE_PORT_SET: tuple[Port, ...] = (
    Port(name="judged-artifact", content_type="text/markdown"),
)


class JudgePiece:
    """A Step that judges an artifact and records an :class:`EvaluandRecord`."""

    kind: Final[Literal["judge"]] = "judge"
    prompt_key: str | None = None
    slot: str | None = None

    def __init__(
        self,
        *,
        name: str,
        rubric_body: str,
        judge_model: str,
        rubric_version: str,
    ) -> None:
        if rubric_body == "":
            raise ValueError("rubric_body must not be empty")
        self.name = name
        self.rubric_body = rubric_body
        self.judge_model = judge_model
        self.rubric_version = rubric_version

    def run(self, ctx: StepContext) -> StepResult:
        from megaplan.workers.hermes import dispatch_judge
        from megaplan.observability.evaluand import EvaluandRecord, emit_evaluand
        from megaplan.observability.prompt_cache import write_prompt_bytes
        from megaplan.receipts.canonical import canonicalize_prompt

        # (a) model identity
        model_identity = compute_model_identity(self.judge_model, reported_version=None)

        # (b) build prompt + INLINE two-hash recipe
        prompt = self.rubric_body
        prompt_hash_raw = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        try:
            state = getattr(ctx, "state", None) or {}
            cfg = state.get("config", {}) if isinstance(state, dict) else {}
            project_dir = cfg.get("project_dir", "")
            plan_id = cfg.get("plan_id", state.get("plan_id", "") if isinstance(state, dict) else "")
            canonical_prompt = canonicalize_prompt(
                prompt,
                project_dir=project_dir,
                plan_dir=ctx.plan_dir,
                plan_id=str(plan_id or ""),
            )
        except Exception:
            canonical_prompt = prompt
        prompt_hash_canonical = hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest()

        # (c) judge_version via manifest_hash
        try:
            step_code_source = inspect.getsource(self.__class__)
        except (OSError, TypeError):
            step_code_source = f"{self.__class__.__module__}.{self.__class__.__qualname__}"
        judge_version = manifest_hash(
            step_code_source=step_code_source,
            resolved_rubric_body=self.rubric_body,
            model_identity=model_identity,
            port_set=_JUDGE_PORT_SET,
            abi_version=ARNOLD_API_VERSION,
        )

        # (d) invoke model (counted dispatch)
        dispatch_result = dispatch_judge(
            prompt=prompt, model=self.judge_model, effort=None
        )

        # (e) provenance/taint — read, never re-derive
        provenance = getattr(ctx, "provenance", None)
        if provenance is None:
            state = getattr(ctx, "state", None) or {}
            provenance = state.get("provenance", {}) if isinstance(state, dict) else {}
        taint = "trusted"
        state = getattr(ctx, "state", None) or {}
        if isinstance(state, dict):
            taint = state.get("taint", "trusted")

        # input_set_hash — best-effort from inputs map or empty
        input_set_hash = ""
        inputs = getattr(ctx, "inputs", {}) or {}
        if inputs:
            joined = "\x00".join(f"{k}:{v}" for k, v in sorted(inputs.items()))
            input_set_hash = hashlib.sha256(joined.encode("utf-8")).hexdigest()

        record: EvaluandRecord = {
            "piece_version": None,
            "judge_version": judge_version,
            "rubric_version": self.rubric_version,
            "input_set_hash": input_set_hash,
            "score": 0.0,
            "provenance": dict(provenance) if provenance else {},
            "taint": taint,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "model_identity": model_identity,
            "prompt_hash_canonical": prompt_hash_canonical,
            "prompt_hash_raw": prompt_hash_raw,
        }

        # (f) flag-gated dual emission
        if os.getenv("MEGAPLAN_UNIFIED_DISPATCH") == "1":
            params = dict(provenance.get("params", {})) if isinstance(provenance, dict) else {}
            write_prompt_bytes(
                ctx.plan_dir,
                prompt_hash_canonical or prompt_hash_raw,
                raw=prompt.encode("utf-8"),
                canonical=canonical_prompt.encode("utf-8"),
                model_identity=model_identity,
                params=params,
            )
            emit_evaluand(ctx.plan_dir, record)

        # (g) ALWAYS attach evaluand to verdict.payload
        verdict = PipelineVerdict(
            score=0.0,
            payload={
                "evaluand": dict(record),
                "dispatch_result": dispatch_result,
            },
            recommendation="proceed",
        )
        return StepResult(verdict=verdict, next="halt")
