# Foundation audit — what must be hardened BEFORE the planning-unification epic

**Method:** 10 independent DeepSeek-V4-Pro agents, one per foundational subsystem, each told to
*assume the unification refactor happens* and hunt only for **pre-existing structural rot the
refactor will be built on top of** — with `path:line` evidence, severity, and a fix-first call.
Companion to `briefs/pipeline-unification-planning-as-pack.md`. Date: 2026-05-24.

**Headline:** the refactor's own brief is sound, but it rests on **five foundations that are weaker
than it assumes**. Two of them (the state/persistence/lifecycle layer, and the executor that is
*supposed to be* the single path) are genuine blockers — the unified path **cannot correctly run
planning today** and the state layer can **silently corrupt to `{}`**. Fix the convergent items
below as a pre-Phase-0 hardening pass; they are cheap, decoupled, and de-risk everything after.

---

## The 5 convergent foundations (ranked by risk; convergence = how many agents independently hit it)

### F1. State / persistence layer — **the rotten foundation** (agents 01, 02, 04, 08, 09, 10)
The single most-cited substrate. The refactor's "executor owns one write model" is poured on top of:
- **No `schema_version`** on `state.json` *or* `chain_state.json` (01, 09, 10). No way to tell legacy
  vs unified shape; cloud version-skew unguarded.
- **`PlanState` TypedDict is incomplete** — omits `last_gate` (a core routing key written at init,
  read by the bridge, mutated by 7+ handlers); `PlanMeta` misses `tiebreaker_count`,
  `current_invocation_id`, `worktree`, `epic_id`. No load/save validation. (`types.py:149-163,61-70`) (01)
- **Non-atomic writers** that corrupt on a mid-write crash: `chain.py:1646`, `auto.py:771`
  (`_recover_execute_callback_failure_state` — a **FOURTH** external writer the brief never named).
  Everything else uses `atomic_write_json`. (01, 10)
- **Silent total-state loss:** `read_json` returns `{}` on `JSONDecodeError`, so a truncated
  `state.json` from those non-atomic writes = plan state vanishes, no error. (`plan_repository.py:174`) (10)
- **Four divergent write strategies with opposite merge defaults** (`save_state_merge_meta` = in-memory
  wins; `_merge_state_to_disk` = disk wins; `touch_active_step` = no merge; `save_state` = blind
  overwrite). Races are timing-dependent. (01)
- **In-memory staleness breaks policy hooks:** `StallDetector`/`CostTracker` read the executor's stale
  in-memory `state`, so stall detection can falsely fire after ~5 iterations on handler-backed steps.
  (`runtime.py:38-48`) (01, 02, 08)

### F2. The executor is NOT ready to be the single path (agent 02 — standout)
The brief says "everything runs through `run_pipeline_with_policy`." That function **cannot run
planning's topology today**:
- **`run_pipeline_with_policy` drops override-edge dispatch entirely** — `run_pipeline` has the
  `find_override_edge` block (`executor.py:268-273`); the policy variant (`:377-397`) has none. Planning's
  human-override escape hatch **silently fails** on the designated unified path. **BLOCKER.** (02)
- **EscalatePolicy `"abort"` has no edge dispatch** — the policy's own docstring promises it; the
  executor only handles `"force_proceed"`, else `LookupError`. (`executor.py:386-392`) (02)
- **`ContextRetry` / `BlockedRetry` are dead code** — defined, wired into `RuntimePolicy`, never called
  by either executor. The retry logic lives only in `auto.py`'s loop. (`runtime.py:105-143`) (02)
- **No mid-graph crash resilience** — `ResumeCursor` exists but the executor never persists it between
  stages; a crash always restarts at `pipeline.entry`. (02, 10)
- **First-match edge dispatch** can't disambiguate planning's gate-loop self-loops; a test admits it and
  re-enters on `LookupError`. (`executor.py:276-291`) (02)

### F3. Profiles is a half-built migration, not "a quirk to clean up" (agent 07 — standout)
The brief lists `profiles/` under "shared infrastructure that already needs no change." That is wrong:
- **`VALID_PHASE_KEYS` rejects any non-planning step name** — system-profile + tier_models validation
  `raise CliError` for `synth`/`outline`/`section_draft`. "Any pack, same contract" is impossible while
  the profile system only knows planning's 13 phase names. (`profiles/__init__.py:24,178-183,271-276`) **BLOCKER.** (07)
- **`resolve_agent_mode` crashes on unknown steps** — `DEFAULT_AGENT_ROUTING[step]` is a bare
  `__getitem__`, called from ~30 sites. (`workers/_impl.py:2682`) (07, 04)
- **The clean fix already exists as dead code** — `_pipeline/profile.py`'s slot-agnostic `Profile.model_for()`
  is imported only by tests. Someone built the pack-agnostic profile system and never wired it in. (07)
- **creative/doc steps are stubs that never call workers** — they "work" with profiles only because they
  never resolve a model; the moment Body 3 gives them real realizers, they crash. (07)

### F4. Observability emits nothing on the pipeline path — and the receipts story is backwards (agents 01, 08)
- **The executor emits zero observability** — no `phase_result.json`, receipts, history, or events. Today
  `megaplan run planning` only emits because `InProcessHandlerStep` delegates to `_finish_step`; Body 2
  retires that wrapper → all emission silently vanishes unless a shared post-step hook lands first. **BLOCKER.** (01, 08)
- **The brief's "receipts/ currently unused" is FALSE** — `megaplan/receipts/` is wired and load-bearing
  (called from `_finish_step`, execute, review; has its own `schema_version`). The *dormant* one is
  `_pipeline/receipt.py`. Two receipt systems will collide when the pipeline path gets a hook. (08)
- **`_emit_phase_result` depends on `meta.current_invocation_id`**, set by `set_active_step`, which the
  executor path never calls — so a naively bolted-on hook silently skips emission. (`phase_result.py:567`) (01)
- **status JSON is unversioned** (~20 keys; consumers `json.loads` with no shape assert) and
  **`upstream_artifact_hashes` hardcodes planning artifact filenames** — renaming artifacts silently
  breaks audit hashes for every pack. (08, 09)

### F5. Consumers reach PAST the CLI into internals — "thin front doors" is already false (agent 09 — standout)
- **Cloud supervisor shells `python3 -c "from megaplan.chain import ..."` over SSH** — it imports internal
  chain symbols and mutates `ChainState` by name, NOT the CLI. The brief only saw the `status_payload`
  path; this `sync-refresh` path (`cloud/supervise.py:53-80`) is a raw internal-API call with zero version
  negotiation. **BLOCKER for the CLI-boundary promise.** (09)
- **chain.py reads `execution_batch_*.json` / `finalize.json` by glob and writes `state.json` directly**
  (09, 10); **bakeoff imports `_core.state.load_plan`** and reads internal artifacts (09). The DAG-runner
  renaming any of these silently breaks consumers.

---

## Two more, lower but real

- **F6 — Handler config bus has ambient inputs the brief didn't count (agent 04):** `args` is **mutated
  in-place** by `apply_profile_expansion` (sentinel flags `_profile_applied`, `_live_phase_model_steps`),
  so a frozen `HandlerContext` built once at dispatch can't model it; **14 `MEGAPLAN_*` env vars** read
  directly; `resolve_agent_mode` reads `~/.megaplan/config.json` from disk; handlers spawn pytest
  subprocesses, emit events, scan PATH, mutate the debt registry. "Pure-ish `(root, state, hctx)`" leaks
  unless all of these are captured.
- **F7 — Registry discovery is silently best-effort (agent 03):** three `except → return None` paths
  swallow pack import errors with no log; `build_pipeline()` is not called at discovery (fails deep in a
  run); **prompt registration is a second independent import that can fail separately**, so the brief's §8
  discovery guard ("discoverable + compiles") is insufficient — it must also `get_pipeline()` AND resolve a
  canonical prompt key.

## What's actually solid (don't re-solve)
- **execute/ DAG/batch/merge/blocked core is genuinely mode-agnostic** (`compute_task_batches` is pure
  topo-sort) — the §5 DAG-runner extraction is supported by the code (agent 06).
- **FaultRegistry is clean**, one planning-specific method to strip — matches brief §4 (agent 10).
- **PR #43 is NOT extractable as a subset and must NOT merge first** — keep as reference spike, land
  Body 1+2, re-home into Body 3's CodeRealizer. Confirms brief §14 (agent 06).

---

## Recommended PRE-PHASE-0 hardening sprint (cheap, decoupled, de-risks everything)

Ordered. None of these require committing to the full epic; all are defensible on their own merits.

1. **State write discipline + schema marker (F1).** Route *all* `state.json`/`chain_state.json` writes
   through `atomic_write_json`; kill the 2 non-atomic writers (`chain.py:1646`, `auto.py:771`); stop
   `read_json` returning `{}` on decode error (raise/quarantine instead); add `schema_version` stamped on
   every write; complete + validate the `PlanState`/`PlanMeta` TypedDicts. **The corruption bomb.**
2. **Define the plan lifecycle state machine (F1/10).** Extend `WORKFLOW` to cover `failed`/`blocked`/
   recovery transitions; add one `transition(state, event) -> state`; route the **four** external writers
   through it. The brief's `mark_plan_executed()` API has no legal-transition definition to enforce without this.
3. **Fix the executor so it can actually run planning (F2).** Port override-edge + escalate-abort dispatch
   into `run_pipeline_with_policy`; wire `ContextRetry`/`BlockedRetry`; persist `ResumeCursor` per stage.
   This is prerequisite to *any* "unified path" claim.
4. **Land the shared post-step emission hook (F4) — brief Body 1a, but do it first.** One
   `_emit_post_step()` calling phase_result + receipt + history + `emit(PHASE_END)` + state save, invoked
   by both `_finish_step` and the executor; wire the `current_invocation_id` lifecycle; deprecate
   `_pipeline/receipt.py`; version the status JSON.
5. **Make the profile system pack-agnostic (F3).** `DEFAULT_AGENT_ROUTING.get(step)` with loud-fail; wire
   the existing `_pipeline/profile.py` `Profile.model_for()` into Step dispatch; replace `VALID_PHASE_KEYS`
   with per-pipeline stage validation. ~20 LOC, unblocks "any pack, same contract."
6. **Harden discovery (F7).** Log/raise on pack import failure; make the §8 guard `get_pipeline("planning")`
   + resolve a canonical prompt key, not just a name-in-list check.
7. **Inventory + version the consumer bypasses (F5).** A versioned `megaplan cloud sync-refresh`
   subcommand to replace the `python3 -c "from megaplan.chain import ..."` SSH call; a CI smoke test
   diffing in-process status JSON vs real-subprocess `megaplan status`.

## Verification pass (Claude direct code-read, 2026-05-24)
Spot-checked the decision-critical claims against the source. **10 of 11 verified true; 1 overstated.**
- **F2a — `run_pipeline_with_policy` drops override-edge dispatch: TRUE.** `run_pipeline`
  (`executor.py:268-273`) imports `find_override_edge` + branches on `verdict.override`; the policy
  variant (`:379-401`) has only the `verdict.recommendation`→gate-edge branch. No override dispatch. BLOCKER confirmed.
- **F2b — `ContextRetry`/`BlockedRetry` dead in executor: TRUE.** Zero references in `executor.py`; defined only in `runtime.py`.
- **F1a — two non-atomic writers: TRUE.** `chain.py:1646` and `auto.py:771` both raw `state_path.write_text(json.dumps(...))`.
- **F1c — no `schema_version`: TRUE.** Absent from `state.py`/`types.py`.
- **F1d — `last_gate` not in `PlanState` TypedDict: TRUE.**
- **F3a — `VALID_PHASE_KEYS` rejects non-planning keys: TRUE** (`profiles/__init__.py:24,178-183,271-276`).
- **F3b — `resolve_agent_mode` bare `DEFAULT_AGENT_ROUTING[step]`: TRUE** (`workers/_impl.py:2682`).
- **F3c — `_pipeline/profile.py` is prod-dead: TRUE.** Imported only by 3 test files.
- **F4 — `receipts/` is load-bearing, brief's "unused" inverted: TRUE.** Called from `shared.py:340-352`, `execute/core.py:1001,1696`.
- **F5 — cloud `sync-refresh` shells `python3 -c "from megaplan.chain import …"`: TRUE** (`cloud/supervise.py:54`).
- **CORRECTED — F1b "silent total state loss": OVERSTATED.** `read_json` (`_core/io.py:262`) *raises*
  `JSONDecodeError`; `load_state` (`plan_repository.py:174`) passes it through. A corrupt `state.json`
  fails **loud at next load**, not silently `{}`. The non-atomic-write corruption risk stands; the
  *silent* consequence does not. (Same over-dramatization the brief's §13 ledger repeatedly caught.)

**Net: the audit is trustworthy.** The two reframing blockers (F2 executor, F3 profiles) are real.

## Top things the brief's own 3 waves MISSED (the new signal from this audit)
- `run_pipeline_with_policy` — the **designated unified target** — cannot dispatch override/abort edges
  and never calls the retry hooks (F2). This is the sharpest finding: the destination path is broken.
- Profiles is a **half-built migration with the fix sitting as dead code**, not "a quirk" (F3).
- The cloud **sync-refresh SSH path imports internal symbols** — the CLI-boundary promise is already
  false there (F5).
- A **fourth** non-atomic external state writer (`auto.py:771`) beyond the three the brief named (F1).
- `receipts/` is **load-bearing, not unused** — the brief's premise for that subsystem is inverted (F4).
- `read_json → {}` turns the non-atomic-write corruption risk into **silent total state loss** (F1).
