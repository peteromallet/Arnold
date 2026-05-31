# m4 — Shared substrate: emission · evidence · RunConfig+services

**Epic:** Pipeline Unification (`.megaplan/briefs/pipeline-unification-EPIC.md`, m4 §89–102; Guiding principle §7–17).
**Tier/robustness:** premium · thorough/high.
**Depends on:** m3 (planning is a discovered pack; ONE clean routing source via graph edges) **and**
m2 (pack-agnostic dispatch — the dispatch service is one of the shared kernels this milestone composes).
**Grounded:** 2026-05-28 against current main. **Findings:** `.megaplan/briefs/validation/{c3-emission,c4-handlercontext,c5-realizer}.md`,
`.megaplan/briefs/validation/premortem/{p1-blast-radius,p5-overengineering}.md`.

> This brief MERGES the shared kernels of the two deferred v1 drafts (`deferred/m5-config-substrate.md`,
> `deferred/m6-realizer.md`) and DROPS their planning-only generality. Every piece below is justified by
> the guiding principle: **another tool (Arnold) actually uses it.** Anything that only makes planning's
> internals prettier is explicitly deferred, not built.

---

## Outcome

The three genuinely-shared capabilities a non-planning tool needs become a reusable substrate:

1. **Emission** — a non-planning tool can emit observability (`phase_result.json` + receipts) without
   being a planning pipeline. Today three live emitters hand-roll this inline and four raw consumers read
   `state.json` directly; they converge on ONE post-step emission hook + ONE validated read source.
2. **Evidence-of-work** — "how a step proves it happened" becomes a mode-keyed strategy injected once per
   run (code → git-evidence, no assemble; prose → assemble, no git), so `finalize` stops branching on the
   mode string and the pure DAG scheduler (`compute_task_batches`) is the shared scheduler under both.
3. **Config** — a typed `RunConfig` + a `services` bag passed as an **added kwarg** to handlers (no
   signature break), absorbing the ambient reads (26 `MEGAPLAN_*` env, `~/.megaplan/config.json`, the
   in-place `apply_profile_expansion` mutation) so a second tool populates config typed-ly instead of
   reverse-engineering an `argparse.Namespace`.

**Honest about the ceiling.** This does NOT make handlers pure. `handle_gate` keeps its tiebreaker /
reprompt / auto-downgrade cascade and 2–3 worker spawns (`gate.py:448`); `handle_execute` stays a
multi-batch driver with embedded approval/session policy (`execute.py:96`). m4 makes their *config typed*
and their *service + emission + evidence dependencies injected* — the control flow, the loops, and the
worker fan-out stay exactly where they are. "RunConfig + services," not "pure handlers."

**Handoff:** one emission hook + one validated state read source; a mode-keyed evidence strategy with a
mode-agnostic `finalize`; a `RunConfig`+`services` substrate consumable by a non-planning tool.

---

## Scope (tied to current file:line)

### 1. ONE shared post-step emission hook (consolidate 3 live emitters + route the raw readers)

c3 verified the brief premise "the executor emits nothing" is **FALSE** — emission already fires on every
production path. This is a **dedup/consolidation**, not a from-zero foundation. The three live
`_emit_phase_result` emitters:
- `handlers/shared.py:453` — `_finish_step`, the generic planning path (prep/critique/gate/finalize/revise).
  Note it **skips** execute/review (`shared.py:421` `if step not in {"execute","review"}`) because those
  emit their own.
- `handlers/execute.py:306` — execute hand-rolls outcome→exit_kind off `response["_phase_outcome"]`.
- `handlers/review.py:469` — review hand-rolls its own.
- (Fourth, outside the executor: `cli/feedback.py:432,477` — note as a touchpoint; do not force it through
  the hook unless it falls out cleanly.)

`_emit_phase_result` is defined at `orchestration/phase_result.py:504`; it reads
`state["meta"]["current_invocation_id"]` (set by `set_active_step`, `_core/state.py:677`) and **degrades
gracefully** (warns + skips, does NOT raise) when absent (`phase_result.py:528–539`). The receipt half
runs inline at `shared.py:347` (`_emit_receipt`) and `execute/batch.py:711/724,1445/1458`.

**Action:** extract a single `emit_step_outcome(...)` hook owning both `phase_result.json` and the receipt,
honoring the execute/review divergence (their `_phase_outcome`→exit_kind + drift/metrics receipt logic must
survive — c3 names this as the silent-loss risk if the generic path naively became the only emitter). All
three live sites call it; the execute/review carve-out becomes a parameter, not a duplicated body.

**Route the raw readers through ONE validated state read source.** doctor (`observability/doctor.py`) and
introspect (`observability/introspect.py`) `json.loads` `state.json` raw; `list` and `feedback search` read
raw too (p1 §6). They consume state/next_step without going through a validated loader. m4 routes these so a
non-planning tool emits and is read uniformly — **a tool emits observability without being planning.**

**HONEST limit:** m4 consolidates the *emit* contract and the *read* source. It does **not** redefine
liveness/timeout against in-process cursors — that is m3's job (p1 §1) and m3 is a dependency, so by m4 the
subprocess-PID basis is already resolved. m4 must only ensure in-process emission keeps tagging events with
a stable `phase` label (cost-by-phase `cost.py:98` and `next_step_runtime` depend on it — p1 §5).

### 2. Injected evidence strategy (mode-keyed, NOT a symmetric Protocol)

c5 confirmed two evidence shapes exist and they are **asymmetric**: prose has an `assemble` step
(`runtime/doc_assembly.py:199`, a registered pipeline stage) and NO git evidence; code has git evidence and
NO assemble (git IS the artifact). A symmetric 5-method `Realizer` Protocol would force code to stub
`assemble`. **DROPPED** (see Deferred). What ships is a mode-keyed strategy whose surface is the *union of
what the existing branches actually call*; absent methods for a mode are no-ops, not forced stubs.

Consolidate the ~20 `is_prose_mode` evidence branches (c5 §36–48, re-verified):
- `execute/batch.py` L289 (skip git snapshot + before-line-counts), L322 (skip `_collect_quality_deviations`),
  L344 (skip `_auto_attribute_unclaimed_paths` + `_observe_git_changes`), L371 (evidence check →
  `sections_written`), L1348.
- `execute/timeout.py` L55, L75, L82, L143, L304 (skip git-based timeout reconciliation / execution-audit).
- `execute/aggregation.py` L51, L57, L97 (prose payload shape `sections_written` vs `files_changed`).
- `execute/merge.py` L390 (`required_fields` fork: code = `(task_id,status,executor_notes,files_changed,
  commands_run)`, prose = `…sections_written`, creative adds `stance,stop_signal` L394–397).

**Reuse already-pluggable hooks; do NOT re-erect them.** `quality.py:150`
(`_check_done_task_evidence_by_kind`, kind-keyed with `code_*` overrides) is *consumed* by the strategy, not
replaced; `merge.py:390`'s fork becomes `strategy.required_fields(state)`. Creative is a 3-way sub-mode of
prose (`_core/modes.py:38` `is_prose_mode = {doc,joke,creative}`) — the prose strategy handles the
`stance/stop_signal` variance internally (one nested branch), avoiding a 4th class.

**Make `finalize` mode-agnostic.** `handlers/finalize.py` has the code-only injection cluster:
`_validate_finalize_payload` (L220, requires a test-verification final task only when `mode=="code"`),
`_ensure_verification_task` (L308) + `_ensure_user_actions_pre_gate_task` (L379, early-returns unless
`mode=="code"`), invoked at L604–605 inside the `_write_finalize_artifacts` mode branch. These delegate to
the strategy (`strategy.finalize_tasks(payload, state)`) so finalize stops branching on the mode string.

**The DAG scheduler is shared and already exists.** `compute_task_batches` (`_core/io.py:58`) is a pure
Kahn topo-sort taking only `(tasks, completed_ids)`, zero mode awareness, raises on cycles (`io.py:99`);
`split_oversized_batches` (`io.py:107`) is likewise mode-free. c5 §80–86: ~done. **Action = document the
boundary + ensure the strategy never re-implements scheduling. Do NOT extract or move it.**

**Selection.** Strategy is resolved once at execute entry from `mode` (`_core/modes.py:38`); `is_prose_mode`
→ ProseStrategy, else CodeStrategy. (No `capabilities` tuple — it would be a 1:1 indirection over `mode`;
DROPPED, see Deferred.) The strategy's home is `hctx.services` (scope item 3); if that home isn't ready it
is selected at execute entry and threaded down the existing call chain as a stopgap.

### 3. `RunConfig` + `services` bag as an added kwarg (NO signature break, NO 81-field typing)

c4 measured **81 distinct fields** read in `handlers/*.py` (35 via `args.<f>`, 55 via `getattr`); the
"~17 stable" framing is at best the per-command threaded core. The handler bus is dispatched
`handle_X(root, args)` at `cli/__init__.py:1561,1566`; `progress_emitter` is already stapled on at
`cli/__init__.py:1574` (`args.progress_emitter = ProgressEmitter.from_env()`).

**Action:**
- Define `RunConfig` (frozen value object over the *threaded-core* read surface — the fields that flow
  handler → `_run_worker` (`shared.py:204`) → `apply_profile_expansion`/`resolve_agent_mode` (`shared.py:219,
  220`) → `run_step_with_worker` (`shared.py:239`), and → `_finish_step` → `_emit_receipt` (`shared.py:347`)
  → `build_receipt(args=...)` (`receipts/__init__.py:31`, reads only `getattr(args,"profile")`)). Type the
  threaded core; keep a typed pass-through for command-specific fields. **Do NOT enumerate all 81.**
- Define `services` = `{worker_runner, progress_emitter, event_sink, evidence_strategy}`. `worker_runner`
  injects the entry point handlers call directly today (`shared.py:239`); `progress_emitter` moves off the
  namespace (`cli/__init__.py:1574`) into `services`; `evidence_strategy` (scope 2) lives here.
- **Pass `(root, args, *, ctx=...)` as an ADDED KWARG** — NOT `(root, state, hctx)`. This avoids the
  public-API break c4 §4 flagged (handlers are in two `__all__`s: `handlers/__init__.py:75–90`,
  `__init__.py:48–72`) and the deprecation-shim dance. Existing `(root, args)` callers keep working
  untouched; the kwarg is optional and, when absent, built from `args` at the dispatch boundary.
- **Hoist the handler-facing ambient reads** onto `RunConfig`: `finalize.py:31`
  (`MEGAPLAN_FINALIZE_STRICT_VALIDATION`), `finalize.py:496` / `plan.py:117` / `review.py:527` (`MOCK_ENV_VAR`);
  the `~/.megaplan/config.json` read in `resolve_agent_mode` (`workers/_impl.py:2313`, reads `config.get
  ("agents",{}).get(step)` via `load_config`, `_core/io.py:743`); and the in-place `apply_profile_expansion`
  mutation (`profiles/__init__.py:1506–1540`, guarded by `_profile_applied`, writes `args.profile` /
  `_live_phase_model_steps` / `phase_model`) — model it as a function that *produces* the expanded config
  into typed fields. **The 26-env count is the repo total; m4 hoists only the handler-facing reads.** The
  ~22 worker/core/cloud reads (NARROW_SANDBOX, TRUSTED_CONTAINER, Shannon timeouts, etc.) stay put.

**HONEST limit / the killer (c4 Unknown-unknown, p5 §3):** even after m3 goes in-process, config is still
reconstituted from `state["config"]` per stage. So "build once, thread it" is partly fiction — `RunConfig`
is a *typed view built from `state["config"]` + the hoisted ambient reads*, not a single long-lived object.
`state["config"]` stays the single serialized source of truth; `RunConfig` is the typed lens over it, NOT a
parallel truth. And p1 §7: `state["config"]` is read raw in ~48 files (receipts/, forms/, `_core/modes.py`,
`workers/shannon.py`, every creative/doc prompt module). m4 scopes `RunConfig` to the **handler layer only**
and documents the raw readers as deliberately out of scope — they keep reading `state["config"]`.

---

## Locked decisions (incl. what's deferred and WHY — the principle)

1. **Each piece is justified by "Arnold or another tool uses it."** Emission → Arnold emits progress.
   Evidence strategy → Arnold proves work differently (resident loop, not a code diff). RunConfig+services →
   Arnold populates config typed-ly and injects a fake `worker_runner`. The shared DAG scheduler already
   serves both. Anything failing this test is deferred below.
2. **Emission is consolidation, not foundation** (c3). The execute/review inline `_phase_outcome`→exit_kind +
   drift/metrics receipt logic is load-bearing and must survive the merge; the silent-loss risk if it didn't
   is c3's named hazard.
3. **Mode-keyed evidence strategy, asymmetric by design** (c5). Union-of-what-branches-call surface; absent
   methods are no-ops. Resolved once from `mode`.
4. **RunConfig+services as an added kwarg — no signature break, no shim dance** (p5 §3, c4 §4). Type the
   threaded core, escape-hatch the rest. `state["config"]` stays the serialized source.
5. **DEFERRED — full `HandlerContext` purity + 81-field typing.** WHY: planning-shaped. Handlers stay
   effectful (c4 §2); typing 64 escape-hatch fields is "the getattr bag with a new name" (p5 §3). No second
   tool needs pure handlers — it needs typed config it can populate, which the threaded-core subset gives.
6. **DEFERRED — symmetric 5-method Realizer Protocol.** WHY: only two asymmetric modes exist, no third on the
   roadmap (c5 §133); a Protocol forces code to stub `assemble` (c5 §136). Revive only when a real third
   evidence shape (data/notebook, infra/apply) appears.
7. **DEFERRED — `capabilities` tuple pack metadata.** WHY: its only reader is the realizer selector, and
   `mode` already binds the strategy 1:1 (p5 §1). A one-key addition to `_module_metadata` is demonstrably
   cheap to add later; building it now is speculative indirection.
8. **DEFERRED — PR #43 (`worktrees/`) re-home + CodeRealizer-as-a-class + auto.py in-process port.** WHY:
   relevant only to a code-evidence *second tool* / in-process driving that no tenant has asked for; recoverable
   at `4ef36402`. m4 needs none of it — it needs m1's executor merge (have it) + m3's clean routing (dependency).

## Open questions

1. **Does `feedback`'s emission (`feedback.py:432,477`) fold into the hook?** It's outside the executor and
   hard-asserts `STATE_REVIEWED`→`STATE_DONE` (`feedback.py:406`, p1 §5). Lean: route it through the hook only
   if it falls out cleanly; otherwise note it as a separate emitter and leave it.
2. **`worker_runner` interface shape** — minimal callable matching `run_step_with_worker`'s signature, or a
   richer protocol? Lean: minimal callable now; widen only on a real need.
3. **Does the evidence strategy live in `services` from day one, or selected at execute entry?** Lean: home is
   `services`; execute-entry selection is the stopgap if the bag isn't threaded everywhere yet.
4. **Frozen `RunConfig` vs the `_agent_fallback` mid-run write** (`workers/_impl.py:2432,2640`, read via
   `hasattr(args,"_agent_fallback")` at `shared.py:128–130`) — does it become a typed field or a service-side
   cache? Decide in plan.

## Constraints

- **m1 parity gate stays green throughout** (epic §134). This is a pure refactor: code and prose runs are
  byte-identical before/after. `apply_profile_expansion` precedence (live CLI > persisted CLI > profile,
  `profiles/__init__.py:1520–1529`) preserved exactly. No golden expectation edited unless a behavior change
  is deliberate and lands in its own commit.
- **No public-API break.** Both `__all__`s import unchanged; the added kwarg is optional; the import-surface
  characterization test (`tests/characterization/test_import_surface.py`) stays green.
- **`state["config"]` stays the single serialized source** RunConfig is built from — not a parallel truth.
- **In-process emission must keep stable `phase` tags** (p1 §5: cost-by-phase, `next_step_runtime`).
- **Don't churn freshly-stabilized execute code beyond the seam** (c5 §138–145). The May 24–28 refactor split
  `core.py` → `batch/merge/aggregation/quality/timeout`; consolidate the branches *in place* into a strategy
  the existing modules consume — do NOT re-org by mode.

## Done criteria (testable)

1. **One emission hook.** A single `emit_step_outcome(...)` is the sole writer of `phase_result.json` +
   receipts; all three live sites (`shared.py:453`, `execute.py:306`, `review.py:469`) call it; execute/review's
   `_phase_outcome`→exit_kind + drift receipt logic produces byte-identical output vs pre-m4 (parity test).
   A non-planning caller can invoke it and produce a valid `phase_result.json` + receipt without a Pipeline.
2. **One validated read source.** doctor/introspect/`list`/`feedback search` read state through one validated
   loader; a test asserts a non-planning state shape is read without error.
3. **Zero evidence `is_prose_mode` branches remain** in `execute/batch.py`, `timeout.py`, `aggregation.py`,
   `merge.py`, and `finalize.py` (grep is the gate). CLI-policy branches in `handlers/execute.py` (L106, L204)
   may remain, documented. `finalize` no longer reads the mode string for task injection.
4. **Strategy selection unit test:** `mode=code` → CodeStrategy, `mode in {doc,joke,creative}` → ProseStrategy;
   a full code run and a full doc run produce byte-identical artifacts vs pre-m4 main.
5. **`compute_task_batches` untouched** and documented as the shared scheduler; the strategy never
   re-implements scheduling (grep: no Kahn/topo logic inside the strategy).
6. **RunConfig+services injected as a kwarg:** a fake `worker_runner` injected via `services` is the one
   invoked; `progress_emitter` and `evidence_strategy` resolve from `services`, not module globals, on the new
   path. Existing `(root, args)` callers still work (no kwarg) — import-surface test green.
7. **Handler-facing ambient reads hoisted:** `finalize.py:31,496`, `plan.py:117`, `review.py:527`, and
   `resolve_agent_mode`'s `load_config` read source from `RunConfig`; a test injects values and confirms no
   `os.getenv`/`load_config` disk read fires mid-handler. Profile expansion is compute-once; expanded
   `phase_model`/`_live_phase_model_steps`/inferred `profile` match the old in-place result field-for-field.
8. **No behavior change elsewhere:** full suite green; parity gate green on both code and prose.

## Touchpoints

- `megaplan/handlers/shared.py:347` (`_emit_receipt`), `:380–463` (`_finish_step`, the `:421` execute/review
  skip, the `:453` `_emit_phase_result`), `:204` (`_run_worker`), `:219,220,239` (expand/resolve/dispatch),
  `:128–130` (`attach_agent_fallback`).
- `megaplan/handlers/execute.py:306` (emit), `:96` (handler, stays impure), `:106,204` (CLI-policy prose branches, retained).
- `megaplan/handlers/review.py:469` (emit).
- `megaplan/orchestration/phase_result.py:504` (`_emit_phase_result`), `:528–539` (graceful-skip).
- `megaplan/handlers/finalize.py:220,308,379,604–605` (mode→strategy delegation), `:31,496` (env hoist).
- `megaplan/execute/batch.py` (L289,322,344,371,1348), `timeout.py` (L55,75,82,143,304),
  `aggregation.py` (L51,57,97), `merge.py` (L390–405), `quality.py:150` (consumed, not rewritten).
- `megaplan/_core/io.py:58` (`compute_task_batches` — documented boundary, untouched), `_core/modes.py:38` (mode→strategy).
- `megaplan/runtime/doc_assembly.py:199` (`assemble_doc` — prose strategy's `assemble`).
- `megaplan/cli/__init__.py:1561,1566` (dispatch), `:1574` (progress_emitter → services).
- `megaplan/profiles/__init__.py:1506–1540` (`apply_profile_expansion`), `megaplan/workers/_impl.py:2313`
  (`resolve_agent_mode` config.json), `:2432,2640` (`_agent_fallback`).
- `megaplan/_core/io.py:743` (`load_config`), `megaplan/receipts/__init__.py:31,39` (`build_receipt(args=...)`).
- `megaplan/observability/doctor.py`, `observability/introspect.py`, `cli/feedback.py:432,477` (raw readers / 4th emitter).
- Tests: `tests/characterization/test_import_surface.py`; m1 parity gate.

## Anti-scope

- **No full `HandlerContext` purity, no 81-field typing, no "pure handlers" claim** (Locked #5). Handlers
  still loop + spawn workers.
- **No symmetric 5-method Realizer Protocol; no `capabilities` tuple** (Locked #6, #7).
- **No PR #43 / `worktrees/` re-home; no CodeRealizer-as-class beyond the mode-keyed strategy seam** (Locked #8).
- **No auto.py in-process port** (Locked #8 / epic §102) and no execution-model change — m3 owns that.
- **No DAG-runner extraction** — `compute_task_batches` is already pure and mode-free; document, don't move.
- **No raw `state["config"]` reader migration** outside the handler layer (~48 files stay raw, p1 §7).
- **No worker/core/cloud env hoist** (~22 reads stay where they are).
- **No liveness/timeout redefinition** (m3) and **no routing-source collapse** (m3) — m4 consumes those handoffs.
- **No `megaplan status` JSON contract change** (pinned in m1).
