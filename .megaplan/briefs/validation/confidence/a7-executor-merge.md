# A7 — CONFIDENCE: merge `run_pipeline` + `run_pipeline_with_policy`

Validated against current code 2026-05-28. Files read: `megaplan/_pipeline/executor.py`,
`override.py`, `runtime.py`, `registry.py`, `run_cli.py`, `resume.py`, `subloop.py`, `types.py`,
`megaplan/cli/__init__.py`; grepped all callers across `megaplan/` + `tests/`. Cross-checked
prior brief `.megaplan/briefs/validation/c1-executor.md` (claims independently re-verified — all hold).

## Verdict: LOW-MEDIUM risk, ~1 day. c1's "clean low-risk" framing is essentially correct,
but only if the merge is done as a **superset** (policy variant absorbed into `run_pipeline`),
NOT a swap to the policy variant. The trap is direction, not difficulty.

---

## 1. Caller census (definitive)

**`run_pipeline` (bare) — the production path. Many real callers:**
- `run_cli.py:335` (`megaplan run <name>`) — production.
- `cli/__init__.py:960` (human-gate resume) — production.
- `subloop.py:84` (`SubloopStep.run` runs child pipelines) — production.
- `resume.py:12,14` (docstring example only — not live).
- `demo_judges.py:264`, `demos/doc_critique.py:225` — demos.
- `registry.py:243` (`run_pipeline_by_name`, when `policy is None`).
- Tests: composability, override, typed_edges, subloop, mode_e2e, compose, human_gate,
  writing_panel_e2e, epic_blitz_e2e, doc_pipeline, run_cli (monkeypatches by name).

**`run_pipeline_with_policy` — ZERO production callers.**
- `registry.py:244` (`run_pipeline_by_name`, only when `policy=` passed) — but
  `run_pipeline_by_name` itself has **no production callers** (only tests
  `test_pipeline_registry.py`, `test_pipeline_scoped_prompts.py`, neither passes a policy).
- Everything else is tests: `test_pipeline_runtime_e2e`, `test_auto_pipeline_runtime`,
  `test_pipeline_runnable_e2e`, `test_pipeline_planning_parity`, `test_pipeline_composability`,
  `characterization/test_pipeline_golden`.
- `megaplan auto` does **not** touch any of this — it runs its own legacy `while True` phase
  loop in `auto.py`. `pipeline_runtime_enabled()` / `MEGAPLAN_PIPELINE_AUTO` has **no callers**;
  the docstring claim that the env var flips dispatch is stale/aspirational.

So: bare `run_pipeline` is the only thing production depends on. The policy variant is a
test-only artifact built ahead of an auto.py migration that never landed.

## 2. Line-by-line semantic delta (what each has that the other lacks)

Shared spine is identical: artifact_root mkdir, state seed, per-iteration `ctx` refresh,
ParallelStage/Stage dispatch, `_verify_outputs`, state_patch merge + `_merge_state_to_disk`,
`_record_error`, `result.next=="halt"` (+ `_pipeline_paused` → `awaiting_user`).

**`run_pipeline` HAS, policy LACKS (the lossy subset — F2 blocker if you merge the wrong way):**
- `verdict.override` → `find_override_edge` (kind=="override") dispatch (executor.py:277-278).
  The policy variant never imports `find_override_edge`, so first-class override edges
  (`override force_proceed/abort/replan/add_note`) are silently dropped → falls through to
  recommendation/normal, raising `LookupError` if nothing matches. Used by override-edge tests.

**Policy HAS, `run_pipeline` LACKS:**
- `max_iterations` guard → `halt_reason="max_iterations"` (343-344).
- `policy.stall.observe` / `is_stalled` → `halt_reason="stalled"` (368-370).
- `policy.cost.should_abort` → `halt_reason="cost_cap"` (371-372).
- escalate handling: on `recommendation=="escalate"` with no matching gate edge,
  `policy.escalate.resolve()`; only `"force_proceed"` is consumed (re-targets to the `proceed`
  gate edge). **`"abort"`/`"fail"` resolutions are dead** — `resolve()` returns `"abort"` which
  is never compared; `"fail"` raises inside resolve but no test covers it.

These guards are **purely additive halts**. They cannot change behavior for `run_pipeline`'s
existing callers as long as they're disabled-by-default (no policy = no stall/cost/iteration cap,
no escalate resolution). That is the whole game.

## 3. Is the policy-hook path live? NO.

StallDetector / CostTracker / EscalatePolicy are exercised only in tests. ContextRetry and
BlockedRetry are **never dispatched at all** — `should_retry` has zero callers anywhere
(the `context_retry_count`/`blocked_retry_count` in auto.py are unrelated local ints in the
legacy loop). EscalatePolicy abort/fail are dead branches. So merging-by-superset does **not**
oblige you to make this code correct in production — it stays behind the optional `policy` arg,
same as today. You are NOT reviving dead code into the hot path unless you also wire
`run_pipeline_by_name(policy=...)` or auto.py to it, which is out of scope for m1.

## 4. Position: genuinely low-medium-risk IF merged as a superset.

The real risk is doing it backwards. If m1 keeps the policy variant and routes production
through it, override-edge dispatch silently breaks (`subloop`, human-gate resume, `megaplan run`
all on bare `run_pipeline` today depend on the full dispatch ladder). That would be a real,
test-passing-but-prod-broken regression because no production override-edge test runs through
the policy variant.

### CONCRETE approach for m1
1. Keep the public name **`run_pipeline`**. Add an optional `policy: RuntimePolicy | None = None`
   kwarg (default None). This preserves every existing call site and the by-name monkeypatch in
   `test_pipeline_run_cli.py` (patches `executor_module.run_pipeline`).
2. Take `run_pipeline`'s body (the **full** dispatch ladder incl. `find_override_edge`) as the
   base. Wrap the loop guards conditionally:
   - top of loop: `if policy is not None and iterations >= policy.max_iterations: return …`
   - after `_merge_state_to_disk`: `if policy is not None:` → stall.observe / is_stalled /
     cost.should_abort halts.
   - in the recommendation branch: after the gate-edge lookup, `if policy is not None and
     rec == "escalate" and edge is None:` apply escalate.resolve force_proceed. Order:
     override → recommendation(+escalate) → normal/result.next. Override must stay first.
3. Make `run_pipeline_with_policy` a thin shim: `def run_pipeline_with_policy(pipeline, ctx, *,
   artifact_root, policy): if not isinstance(policy, RuntimePolicy): raise TypeError(...);
   return run_pipeline(pipeline, ctx, artifact_root=artifact_root, policy=policy)`. Keep the
   TypeError so `test_run_pipeline_with_policy_requires_runtimepolicy` passes. This keeps all
   six test modules green with zero edits. (Optionally inline-deprecate later; not for m1.)
4. Do NOT touch `run_pipeline_by_name`, auto.py, or the env flag.

### Residual uncertainty / watch-items
- **Escalate semantics under merge:** the merged escalate block must only fire when
  `policy is not None`. With `policy is None` (all prod), an `escalate` recommendation with no
  gate edge raises `LookupError` exactly as bare `run_pipeline` does today — preserved. Confirm
  no production planning pipeline emits `escalate` expecting silent force-proceed (it doesn't —
  prod goes through bare `run_pipeline` with no escalate handling today, so behavior is
  unchanged by definition).
- **Golden/parity tests** (`test_pipeline_golden`, `test_pipeline_planning_parity`) run the
  planning pipeline through the policy path with `stall_threshold=999`, `on_escalate=force-proceed`.
  The planning pipeline uses gate `recommendation` edges, not `verdict.override` edges
  (the `override_action:add-note` in those tests is `handle_override` writing state.json
  out-of-band, NOT executor override-edge dispatch). So adding override-edge handling to the
  shared path does not perturb them. Low risk but re-run these two to confirm snapshot stability.
- **dead retry classes:** leave ContextRetry/BlockedRetry untouched; merging doesn't activate
  them. If a reviewer flags them, that's a separate dead-code cleanup, not m1.
- One real behavioral nuance to verify in tests: bare `run_pipeline` has NO `max_iterations`
  cap; an accidental infinite gate self-loop currently spins forever. The merge keeps that
  (policy=None ⇒ no cap). If m1 wants a safety cap for prod, that's a *new* behavior change —
  flag it explicitly, don't smuggle it in.
