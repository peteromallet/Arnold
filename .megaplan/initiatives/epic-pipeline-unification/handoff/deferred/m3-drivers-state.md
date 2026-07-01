# M3 — Drivers + realized-graph + state-evolution

**Status:** Milestone brief (regenerated 2026-05-29). Authoritative scope:
`briefs/pipeline-unification-EPIC.md` — the **M3 entry** (L143-145), **Structural piece #2**
the realized-graph / topology-realizer (L102-105), and the **Resolved over-builds** paragraph
(L123-131: 2-axis drivers, `oneshot` deleted, two honest state values). Grounded in
`briefs/validation/interrogation/SYNTHESIS.md` (**Theme B** — *both* criticals, the
topology-realizer spec in CONFIRMED MISSING ABSTRACTIONS #2, the over-complication "flat
4-value driver enum", the over-simplifications "State-evolution axis behind ONE Store" and
"snapshot = copy the whole blob"), `briefs/validation/decision/{migration-fit,
interface-feasibility}.md`, `briefs/validation/confidence/a2-concurrency.md`, and
`briefs/validation/confidence/a3-human-recovery.md` **§4.4 (the parity test)**.

M3 is the **mechanism + faithful-projection** milestone. M2 decoupled the *types*; M3 makes
the SDK express pipelines that are NOT a single static topology, NOT single-substrate
in-process, and NOT forward-only — **and proves the dynamic graph projection is faithful before
M6 is allowed to collapse the next-step encodings onto it.** Theme B's verdict is load-bearing:
the root cause of the "3 next-step encodings" problem is **not three encodings — it is that
there is no realized graph to project from.** M3 builds that graph; the parity gate proves the
projection over it equals today's behaviour across the full cross-product.

---

## Outcome

Three real, separately-testable SDK pieces, plus a gate:

1. **A 2-axis driver model** — substrate (`in_process` | `subprocess_isolated`) × topology
   (a `graph` with **loop-control as a composable node**, not a peer driver). `oneshot` is
   DELETED (a phantom — named in briefs, zero spec/acceptance/user; SYNTHESIS over-complications).
2. **THE realized-graph / topology-realizer** — `build_topology(run_config) -> Graph`: an
   ordered rewrite fold matching `_ROBUSTNESS_WORKFLOW_LEVELS`, re-invocable mid-run
   (`set-robustness` mutates the live graph). It is the **SINGLE source** both the `next_step`
   projection AND the reverse-recovery maps query — recovery = `predecessors(stage)` computed on
   demand, **no persisted 4th copy**.
3. **State-evolution = two honest values** behind ONE Store: `forward-only` (default, today's
   behaviour) and `reversible` (= forward + `snapshot`/`restore`), plus an explicit
   `restorable_boundary` that **fails LOUD** when composed with process/fan-out. Event-sourced is
   a SEPARATE backend with its own contract — *declared on the axis, not shipped here.*
4. **GATE (must pass IN M3):** the `{5 robustness} × {with_prep, with_feedback} × {states} ×
   {verdicts}` parity test (a3 §4.4) proving the dynamic projection over the realized graph
   equals the legacy `_workflow_for_robustness`-folded `workflow_next`. **The single-source
   collapse is unsafe until this is green.**

---

## Scope (in) — file:line

- **Topology-realizer.** New `build_topology(run_config) -> Graph` that performs, *on graph
  edges*, the ordered cumulative fold today done over the `WORKFLOW` dict by
  `_workflow_for_robustness` (`_core/workflow.py:184-209`) driven by `_ROBUSTNESS_WORKFLOW_LEVELS`
  (`_core/workflow_data.py:116-122`). It must reproduce the **node/edge REWRITING** in
  `_ROBUSTNESS_OVERRIDES` (`_core/workflow_data.py:91-113`) — not parameter binding: `bare`
  collapses `plan→finalize`, `light` rewrites `critiqued→revise→GATED` and drops review
  (`STATE_EXECUTED: []`), `full` rewrites `initialized→plan`; `with_prep`/`with_feedback` then
  *undo* parts of that fold (`workflow.py:199-208`). Re-invocable mid-run: a `set-robustness`
  override rebuilds the live graph and the resume cursor stays valid.
- **`workflow_next` becomes a thin projection over the realized graph** (a3 §4.4 item 1),
  *signature unchanged* (`_core/workflow.py:282-299`; `infer_next_steps` alias L302). It must
  still: (a) filter edges by the 7 gate-predicate conditions `_transition_matches`
  (`workflow.py:212-242` — `gate_unset/iterate/escalate/tiebreaker/proceed/proceed_blocked/
  proceed_agent_availability_blocked`); (b) **re-append the synthetic `"step"` target** for
  `_STEP_CONTEXT_STATES` (`workflow.py:297-298`) — a target that **exists in no edge** and must
  remain a synthetic projection, not a graph node; (c) keep `_gate_next_step`'s escalate routing
  *out* of the graph into the control plane intact (the graph dereferences out of itself — a3
  §2.5, SYNTHESIS Theme B). The 7 conditions survive as edge metadata or as the resolver the
  projection invokes — they are **not** flattened to the 3 coarse `kind="gate"` edges
  (`executor.py:42-52, 279-301`).
- **Reverse-recovery maps derived on demand** from the realized graph (a3 §4.4 item 3): the three
  hand-maintained copies — `_BLOCKED_RECOVERY_STATES` (override.py), `_RESUME_ACTIVE_STATES`
  (`workflow.py` resume), and the implicit forward edges — become `predecessors(stage)` queries on
  the single graph. Persisting a derived 4th copy is an over-build (SYNTHESIS over-complications);
  but the derived maps **must remain a queryable API** the recovery handlers call (a3 §3:
  recover-blocked is a reverse projection; the graph returns `[]` for blocked).
- **Substrate axis: the `subprocess_isolated` (process) driver.** Extract the reusable substrate
  of `auto.py`'s subprocess loop into a driver. The mechanism already exists: `spawn`
  (`runtime/process.py:69`, `start_new_session=True` → setsid pgroup L86), the idle+wall watcher
  in `_run_megaplan` (`auto.py:238-368`), `kill_group` on stall (`process.py`; SIGTERM→SIGKILL,
  `auto.py:362`), plan-artifact-mtime liveness (`_plan_liveness_mtime`, `auto.py:377`), and a
  non-zero/`124` exit (`PHASE_TIMEOUT_EXIT_CODE`, `auto.py:125`) surfaced as a *containable*
  per-step failure. The `in_process` substrate is today's `executor.run_pipeline`
  (`executor.py:212`) — steps share one interpreter. **These are two substrates, not one driver
  with a flag** (migration-fit e2).
- **Topology axis: loop-control as a composable node.** The data-predicate loop is a **control
  node on the graph walk**, NOT a peer driver in a 4-way enum. It owns the iteration count, reads
  a `Callable[[LoopContext], bool]` over `{state, last_fanout_results, budget, iteration}`, has a
  mandatory `max_iterations` cap and a `finally`/teardown hook on every exit path. Wire the
  predicate that `iterate_until` currently `del`s (`_pipeline/pattern_topology.py:269-298`) so the
  loop node consumes it. (`last_fanout_results` is the typed Port the M2 fan-out join writes — do
  not re-introduce it as an untyped key here; SYNTHESIS Theme A.)
- **Store evolution axis — two honest values.** Behind `write_plan_state` (`_core/state.py:329`),
  under the existing cross-process `plan_state_lock` (`state.py:234-245`, `fcntl.flock`).
  `forward-only` IS today's `PlanStateWriteMode` set (`state.py:214-220`: replace / patch-key /
  patch-many / active-step-heartbeat / merge-meta-list — all forward, no restore). `reversible` =
  forward + `snapshot(store) -> version_id` and `restore(version_id)`, both writing under the same
  lock. Add a `restorable_boundary` declared on the axis that **fails LOUD** under process/fan-out
  composition (see Constraints). **Event-sourced is declared on the axis enum and scaffolded behind
  the interface but gets NO real backend here** (SYNTHESIS: it is a fundamentally different
  contract — write=append(event), read=projection — that M4:39 calls *irreconcilable* with LWW
  `state.json`; resolved toward interfaces-with-backends).
- **Cloud `_phase_command` shim — born here.** The cloud→auto coupling
  (`cloud/cli.py:225-227`, `from megaplan.auto import _phase_command`) is the second cloud→auto
  coupling (EPIC cross-cutting). It is assigned to M3 — landed as a guarded shim when the process
  driver is born — plus a cloud smoke oracle wired into the chain, not left implicit in the M5/M6
  seam (SYNTHESIS re-sequence; top-risk #9).
- **Acceptance: one non-planning, non-forward-only package** exercising the loop node + `restore`
  + `budget` — e.g. a tiny backtracking constraint-solver, with **NO planning imports** and **NO
  hand-rolled inter-step plumbing** (all data crosses a declared Port; SYNTHESIS over-simplification
  + acceptance check). This is EPIC acceptance #1: the existing apps and jokes are all forward-only
  and would never surface a regression on these axes.

## Locked decisions

- **Two orthogonal axes, not a flat 4-value enum.** substrate (`in_process` |
  `subprocess_isolated`) × topology (`graph` + loop-control node). This kills the M6
  "one driver or compose process+graph?" open question — it only existed because the taxonomy
  flattened an isolation axis and a topology axis into one list (SYNTHESIS over-complications).
- **`oneshot` is DELETED.** Phantom with no contract/acceptance/user.
- **Loop is a composable NODE on the walk, not a peer driver.** Driver selection picks substrate +
  topology; the loop predicate/teardown/cap is control *on* the graph, not a fourth runtime.
- **The realized graph is the SINGLE source of truth** for both `next_step` projection and
  reverse-recovery. No persisted 4th copy; recovery = `predecessors(stage)` on demand.
- **`workflow_next` keeps its signature and ~15 callers unchanged** — only its body re-implements
  over the graph (a3 §4.4). The 7 gate predicates and the synthetic `"step"` target survive.
- **Forward-only stays the DEFAULT** Store model; planning's hot path contract is unchanged.
- **Event-sourced is a separate backend, not shipped in M3.** Resolve the EPIC L33 "one Store" vs
  M4:39 "irreconcilable" contradiction in writing toward interfaces-with-backends (done above).
- **Routing stays ONE model** (settled by M2/the EPIC): a Step emits a routing key; a binding maps
  key→consequence; edges declared by key. `restore_and_diverge` is ONE new `kind='restore'` edge
  peer (it needs `reversible`), NOT a parallel consequence map. M3 must not re-introduce a third
  routing vocabulary (SYNTHESIS over-complications).
- **Reuse, do not fork:** `runtime/process.{spawn,kill_group}`, `_run_megaplan`'s watcher,
  `plan_state_lock`, and the existing `_workflow_for_robustness` fold logic (moved to operate on
  graph edges) are the substrate the new pieces build on.

## Open questions

- **Snapshot granularity / cost.** Whole-blob copy of `state.json` (cheap, matches LWW) vs diff?
  Whole-blob is the honest first cut given `write_plan_state` is blob surgery. *Non-blocking —
  pick whole-blob.* BUT see the boundary constraint: whole-blob rolls back the RECORD, not the
  WORLD.
- **Mid-run re-realization + live cursor.** When `set-robustness` rebuilds the graph mid-run, the
  resume cursor (`state.current_state`) must still resolve to a valid stage in the new topology.
  Confirm the fold is deterministic and the cursor never points at a deleted node. *(This is the
  biggest design unknown — see the realizer's re-invocability requirement.)*
- **Where the reversible backend persists snapshots.** Sidecar dir under `plan_dir`
  (`.state-versions/<id>.json`) inside the per-plan flock; confirm no collision with the
  executor's forensic-backup naming (`executor.py:90-133`, `_write_forensic_backup`).
- **Budget across fan-out shards.** `SubloopStep` runs children on a *copy* of parent state and
  promotes only namespaced keys, so a shared depletable budget cannot accumulate across siblings
  without a fold channel (abstraction-stress-test §2). M3 ships budget single-tenant; cross-shard
  folding is M4/M-fanout. **Flag, don't solve.**

## Constraints

- **In-process loop vs subprocess isolation — the central, explicit done-criterion.** The
  `in_process` substrate (graph + loop node) runs steps in ONE Python interpreter: a step that
  OOMs, segfaults, or wedges takes the whole run with it. `subprocess_isolated` is the ONLY
  substrate that preserves auto.py's containment — each step a separate session-group process,
  killable on idle/wall timeout without touching the parent (`auto.py:352-368`), non-zero/`124`
  exit surfaced as recoverable. **Crash-isolation is an explicit done-criterion, not a property
  we hope for** (SYNTHESIS substrate-swap oracle (b); migration-fit e2). The two are different
  substrates, not one driver with a flag.
- **The snapshot BOUNDARY must be declared.** The acceptance toys mutate a world OUTSIDE the blob
  (file edits, git checkout); whole-blob `restore` rolls back the RECORD but NOT the WORLD, and
  M3 defers oracle/`run(cmd)` (the only world-undo mechanism) to M4. So `restorable_boundary`
  must **fail LOUD** the instant `reversible` is composed with `subprocess_isolated` or fan-out —
  a green pure-in-memory rollback is precisely the case that hides the gap (SYNTHESIS
  over-simplification + Theme G).
- **The parity gate guards a SUBSTRATE swap (Theme G).** Identical happy-path artifacts say
  nothing about the projection's fidelity across robustness/flags/states/verdicts — which is
  exactly why the parity test is the *cross-product*, not a single-path SHA compare. The
  gate→TIEBREAKER→ITERATE silent downgrade (memory; migration-fit e7) is this class already
  biting: a faithless projection silently routes wrong.
- **State concurrency stays single-process for the new bits.** Per-plan `state.json` is
  cross-process safe via `fcntl.flock` (a2 §4); snapshot/restore write under that same
  `plan_state_lock`. The `budget` is a per-RUN resource, in-process only (a2 §1-2) — NOT a
  cross-tenant quota broker (that is M4's `key_broker`/`rate_broker`). Do not over-claim it.
- **No editable-install dogfood; separate external driver** (EPIC cross-cutting + MEMORY).
- **Back-compat.** `iterate_until`, `SubloopStep`, `write_plan_state` modes, the executor edge
  dispatch, and `workflow_next`'s signature all keep working for existing callers
  (`extra="ignore"`, no removed modes). The realizer, loop node, process substrate, and reversible
  Store are *additive*.

## Done criteria (testable)

1. **THE GATE (a3 §4.4):** `workflow_next(state)` over the realized-graph impl equals the legacy
   dict-folded impl across the full cross-product `{5 robustness} × {with_prep, with_feedback} ×
   {all states} × {all gate recommendations}`, **including** the synthetic `"step"` target and the
   `gate_proceed` / `gate_proceed_blocked` / `gate_proceed_agent_availability_blocked`
   distinctions. **This gate must be green in M3** — M6's collapse is blocked on it.
2. **Realizer mid-run re-invocability:** `build_topology` rebuilt after a simulated `set-robustness`
   yields a graph whose `predecessors(stage)` reproduces `_BLOCKED_RECOVERY_STATES` /
   `_RESUME_ACTIVE_STATES` exactly, with no persisted 4th copy and a still-valid resume cursor.
3. **Crash-isolation (explicit):** under `subprocess_isolated`, a step that `sys.exit(1)` / sleeps
   past idle timeout / is OOM-shaped is killed via `kill_group` and surfaced as a contained
   per-step failure; the parent survives and the process group is reaped (no orphan), mirroring
   `auto.py`. Under `in_process`, the same step **takes the run down** — asserted as the documented
   trade, not a regression.
4. **Loop node:** a sub-pipeline runs N times where N is data-dependent (predicate reads
   `state`/`budget`/`iteration`, actually consulted, not `del`'d), `max_iterations` fires when the
   predicate never satisfies, and the teardown hook runs on every exit path (normal / cap /
   exception / budget-exhausted).
5. **Store axis:** `snapshot()` → mutate → `restore()` returns exact prior state under the
   per-plan lock; `restorable_boundary` **raises LOUD** when `reversible` is composed with
   `subprocess_isolated` or fan-out; forward-only default behaviour is unchanged (regression).
6. **Non-planning acceptance package** (backtracking solver) runs green on loop + restore +
   budget with **zero planning imports** and **all inter-step data crossing a declared Port** (no
   hand-rolled string channels).
7. **Cloud `_phase_command` shim** + cloud smoke oracle: `cloud/cli.py` resume resolves a phase
   command through the M3 shim and a smoke run passes.
8. Parity gate green on planning's forward-only happy path — honest label (control-flow/artifact
   parity on the happy path, *not* "drift provably zero").

## Touchpoints

- `megaplan/_core/workflow.py:184-209` (`_workflow_for_robustness` — the fold to move onto edges),
  `:212-242` (`_transition_matches`, 7 predicates), `:245-263` (`workflow_includes_step`),
  `:282-302` (`workflow_next` / `infer_next_steps` projection + synthetic `"step"`).
- `megaplan/_core/workflow_data.py:91-113` (`_ROBUSTNESS_OVERRIDES` — node/edge REWRITING),
  `:116-122` (`_ROBUSTNESS_WORKFLOW_LEVELS` — the ordered cumulative fold the realizer matches).
- `megaplan/handlers/override.py` — `_BLOCKED_RECOVERY_STATES` + the 9 override actions; recovery
  handlers must keep a queryable reverse-map API derived from the realized graph (a3 §1, §3).
- `megaplan/_pipeline/executor.py:42-52, 212, 255, 267-305` (in-process walk + gate edge dispatch),
  `:90-133` (forensic backup — snapshot-dir collision check), `:308-403` (`run_pipeline_with_policy`,
  escalate at `:388-403`).
- `megaplan/_pipeline/pattern_topology.py:269-298` (`iterate_until` — stop `del`-ing the predicate;
  loop node consumes it).
- `megaplan/_pipeline/subloop.py` — child-on-copy state contract; the budget-not-crossing-shards
  constraint lives here.
- `megaplan/auto.py:238-368` (`_run_megaplan` watcher = the process substrate),
  `:377` (`_plan_liveness_mtime`), `:486-517` (`_phase_command`), `:125` (`PHASE_TIMEOUT_EXIT_CODE`).
- `megaplan/runtime/process.py:69` (`spawn`, `start_new_session`), `kill_group` (SIGTERM→SIGKILL) —
  the isolation substrate (reuse, do not fork).
- `megaplan/_core/state.py:214-220` (`PlanStateWriteMode`, all forward), `:234-245`
  (`plan_state_lock`), `:329` (`write_plan_state`) — the Store surface the evolution axis hangs off;
  snapshot/restore added behind it under the existing lock.
- `megaplan/cloud/cli.py:225-227` (`from megaplan.auto import _phase_command`) — the shim born here.

## Anti-scope

- NOT the `dispatch` service, `emit` unification, `evidence`/oracle/`run(cmd)` split, the
  config-precedence resolver, or the **driver policy spine** (`RecoveryPolicy` / budget authority /
  observability contract) — those are **M4** (SYNTHESIS Theme C: M3 builds substrate *mechanism*,
  M4 builds the *policy spine*). The M3 acceptance toy may shell out locally for its own test, but
  the sanctioned `run` step + oracle evidence are M4.
- NOT a cross-tenant key/rate/quota broker — M4 (a2 §1-2). M3 `budget` is per-run, in-process.
- NOT cross-shard / nested-fan-out budget folding, `fanout_per_item`, or parallel-isolated
  `dynamic_fanout` — fan-out work, deferred.
- NOT full event-sourcing — the axis is declared + scaffolded; only forward-only + reversible get
  real backends with real users in M3.
- NOT relocating planning to a discovered module, dropping `_BUILTIN_NAMES`, or
  **actually collapsing the next-step encodings** — that is M6, *and it is now safe because M3's
  parity gate proved the projection faithful* (EPIC L158). M3 builds the realized graph and proves
  the projection; M6 deletes the redundant encodings.
- NOT the control/override plane, human-gate service, or supervisor tier (F7/F8) — M5. M3 only
  ensures recovery handlers can query the realized graph's reverse maps; it does not re-home the
  control plane (SYNTHESIS Theme D: that binding is mechanism, not content — M5's job).
