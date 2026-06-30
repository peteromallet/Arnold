# m8 — State / Lifecycle Runtime Extraction (→ `arnold/runtime/`)

## Why this milestone exists
Two problems collapse into one. (1) Every pipeline needs durable, ordered, recoverable state + an event log; today that machinery lives under `arnold/pipelines/megaplan/` (event journal, atomic state-persistence engine, WAL fold), so the "second proof pipeline" cannot get **deterministic replay** without importing megaplan. (2) The deepest known engine defect — *no engine-owned ground-truth authority; state derived from claims across ≥5 drifting stores* — has a known proposed fix: **state-as-projection over an append-only event log + atomic reset**. Extracting a generic event-sourced state runtime into Arnold solves both at once: one authoritative store, replay built in, available to any pipeline.

## In scope — extract to `arnold/runtime/`
1. **Event journal engine** — `observability/events.py:262-393` (`EventWriter`: `fcntl.flock` monotonic seq on `.events.seq`, append-only NDJSON), `emit()` (:469), `read_events()` (:563) → `arnold/runtime/event_journal.py`. Make the **storage sink** and the **event-kind vocabulary** injected: define an `EventSink` protocol; split `EventKind` — generic kinds (state_written, phase_start/end, error) stay generic, planning-domain kinds (TIER_ESCALATED, PLAN_ABORTED, FLAG_RAISED, CAPABILITY_CLAIM, …) move to a megaplan-supplied vocab.
2. **State-persistence engine** — `_core/state.py:643-819` (`write_plan_state`: fcntl lock → read → modify → validate → atomic write → WAL emit; CAS version map; snapshot/restore) → `arnold/runtime/state_persistence.py`. Make `validate_state` a pluggable callback (today hard-wired to `validate_plan_current_state` over `CANONICAL_PLAN_STATES`) and the write-mode set a **mode registry** (megaplan registers heartbeat / legacy-migration / executor-key-merge modes; generic core ships lock+atomic-write+CAS+snapshot).
3. **WAL fold / projection** — `observability/fold.py:48-80` (`fold_events`, `rebuild_state_from_wal`: pure last-snapshot-wins fold over `state_written`) → `arnold/runtime/wal_fold.py`. Already pure; only disentangle the `read_events` import.
4. **Effect / replay type skeleton** — `observability/effect_ledger.py:1-84` (`Effect`, `ReplayClass` = pure/idempotent_keyed/at_most_once/pivot, `NONCOMPENSABLE`) → `arnold/runtime/effect.py`. Docstring-only coupling.

## Couplings to sever
- Event storage dispatch to `megaplan.store` (events.py:435-456) → behind the `EventSink` protocol; megaplan's `FileStore` becomes one sink impl.
- `_envelope_ctx: ContextVar[RunEnvelope]` reads → injected/optional.
- State-write modes carrying megaplan shapes (heartbeat `active_step`, legacy `STATE_INITIALIZED`/`STATE_CRITIQUED`, `apply_delta` merge) → registered by megaplan, not baked into the generic engine.

## Out of scope (stays megaplan / false positives)
The `CANONICAL_PLAN_STATES` token *set* and all planning-phase state machines (the engine is generic; the vocabulary is megaplan's); `_validate_plan_state_for_persist` as a concrete validator; `compute_task_batches` (operates on planning task records); `fold_equivalence_oracle`'s megaplan-specific default lift.

## Done criteria
- `arnold/runtime/{event_journal,state_persistence,wal_fold,effect}.py` import **zero `arnold.pipelines.megaplan`** (m0 leak gate extended).
- Megaplan's state/event writes route through the generic engine via registered vocab + sink; full suite green, byte-identical event/state output (golden test).
- A non-megaplan pipeline emits events, persists state, and `rebuild_state_from_wal` reconstructs it — deterministic replay demonstrated without megaplan.
- Ground-truth check: state for a sample run is reproducible as a pure fold over its event log (projection equals the live state.json).

## Locked decisions
- MOVE + dependency-inversion, not a rewrite. Preserve flock/seq/atomic-write semantics and on-disk NDJSON/state formats exactly (golden-file guarded).
- The generic engine owns the *mechanism* (append, lock, fold, atomic reset); megaplan owns the *vocabulary* (which states/kinds/modes exist) and registers it.

---

## Revision — post perspective-audit (2026-06-09)

The audit's contrarian lens is right that a naive "extract the engine" would extract
a hollow shell: `write_plan_state`'s real substance is its ~10 planning-shaped modes,
and `EventKind` is ~65% planning vocab. **Extract MECHANISMS, not megaplan-shaped
engines:**

- **State persistence:** the generic core is just `plan_state_lock()` +
  `atomic_write_json` (~30 lines) → `arnold/runtime/state_persistence.py`. The
  mode-laden writer (replace / executor-key-merge / active-step-heartbeat /
  legacy-migration / …) and `validate_state` STAY in megaplan and call the generic
  lock+write helper. (The "mode registry" is megaplan registering its modes onto the
  thin core — not the core shipping the modes.)
- **Event journal:** extract ONLY the `fcntl`-locked monotonic-seq NDJSON
  append/read mechanism with an **opaque `kind: str`** — do NOT ship an `EventKind`
  enum in the generic layer (it would have ~6 entries no second pipeline uses).
  Megaplan keeps its full `EventKind` vocabulary and passes kind strings in.
- **Fold:** ship a PURE combinator `fold_journal(events, *, kind_filter, projector)`
  → `arnold/runtime/wal_fold.py`. The specific fold that yields planning state
  (`current_state`/`next_step`/`valid_next`) stays in megaplan as a `projector`.

### NEW IN SCOPE — generic suspend / resume lifecycle (BLOCKER — lenses 1 & 8)
The audit found the substrate has NO generic pause/resume: the executor's
`should_suspend` hook returns only `(bool, reason)` and **discards the `Suspension`
object**; there is no resume entry point; the only human-gate impl is megaplan-owned
and welded to `ctx.plan_dir`. Every non-trivial pipeline (image-gen "pick best",
research-report "approve synthesis", ETL "anomaly review") needs this, and it is the
natural home of state/event runtime (resume IS persisted state). Add:
- `Suspension` as a **Protocol** (`kind: str`, `resume_cursor: str | None`, `to_json()`);
  move the human-interaction fields into a `HumanSuspension` impl. (Today `Suspension`
  in `arnold/pipeline/types.py` is all human-gate fields pretending to be generic.)
- A generic `HumanGateStep` in `arnold/pipeline/steps/` writing to `ctx.artifact_root`
  (not `plan_dir`).
- `run_pipeline_resume` + resume-cursor persistence in `arnold/runtime/`: `should_suspend`
  serializes a cursor; resume rebuilds state via `fold_journal` and re-enters the
  executor at the suspended stage. Megaplan's plan-dir human gate becomes a thin subclass.

### Ground-truth note unchanged
The event-sourced-state-as-projection payoff (durable fix for the no-ground-truth-authority
root) still holds — it is exactly `fold_journal` + the generic journal + atomic reset.

---

## Ground-truth validation (2026-06-09) — judgment-filtered

A neutral validator examined `write_plan_state`. It found the modes mutate `should_write`
inline and `legacy-migration` applies its mutation in-branch, and concluded a generic
`with_state_transaction(compute_fn)` helper would force refactoring every mode.

**My call — partially REJECT that scope.** That "teeth" only bites if we extract the WHOLE
`write_plan_state` as a transaction-with-compute-fn framework. We do not need that. The
lighter, correct extraction (confirmed by the same read: the lock cleanly wraps dispatch
at :668-815 and `atomic_write_json` is a clean one-liner at :811):

- Extract only the **primitives** — `plan_state_lock` + `atomic_write_json` (state) and the
  fcntl-NDJSON append/read (journal) — to `arnold/runtime/`. **`write_plan_state` with all
  its modes / `should_write` interleaving / `legacy-migration` quirk STAYS WHOLE in
  megaplan** and simply calls the generic primitives. No per-mode refactor.
- `fold_journal`: the validator confirmed `fold_events` is pure AND that
  `fold_equivalence_oracle` (fold.py:217-228) **already parameterizes the lift/fold/
  expected/observed seams** — so the generic combinator is partly realized; this is smaller
  than briefed, not larger.
- **Done-criteria add:** `import arnold.runtime` in a megaplan-absent venv must succeed
  (the m6 runtime boundary check); a non-megaplan pipeline persists state + journals events +
  `fold_journal`-reconstructs, all without importing megaplan.

Net: state/lifecycle extraction is LIGHTER than the validator implied — primitives + fold
combinator + the suspend/resume lifecycle, with the mode-laden writer left untouched in megaplan.
