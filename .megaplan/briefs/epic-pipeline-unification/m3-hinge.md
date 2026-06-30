# M3 — THE HINGE: Activation + realized-graph + 2-axis drivers + Conveyance + R1 authority-flip + Governor

**Status:** Milestone brief (re-derived onto the eleven organs, 2026-05-29). Supersedes the
pre-architecture `m3-drivers-state.md` (which this re-aims). Authoritative scope:
`briefs/validation/sequencing/PROGRAM.md` **M3 entry (L141-177)** + the critical-path apex
note (L340-346) + open risks 1,2,4 (L419-446); `briefs/pipeline-unification-EPIC.md` **the
eleven organs (L29-49), the data model (L51-67), the seven reshapers (L69-75)**; and the
organ specs in `briefs/validation/committed-uu/SYNTHESIS.md` (Activation L222-231; Conveyance
L235-245; Governor/Capacity-Lease L247-256; Reshapers #1,#2,#4 L343-371; principles 1,2,8 of
Part 5). Open questions resolved to their pre-made defaults in
`briefs/validation/human-blockers/REGISTER.md` §3 (M3 line) + §2.

**M3 is the apex of the critical rope.** It is the single most dangerous engine-half-swapped
moment in the program: it removes the only version-isolation seam (the subprocess boundary) AND
flips the highest-blast-radius foundation (R1: the event log becomes authoritative,
`state.json` a derived cache) WHILE the chain self-hosts. Position 4 on the longest chain,
un-relocatable. Everything lands behind default-OFF `MEGAPLAN_UNIFIED_DISPATCH`; the epic
driving the build runs the toggle OFF on the pinned/frozen subprocess engine; the in-process
path soaks on THROWAWAY plans only. **The subprocess seam is NOT deleted here** — it survives
dormant behind the flag for ≥1 dual-green milestone, retired only at M6.

---

## Outcome

Six organ-pieces land as `{old-path default-ON, new-path default-OFF behind a flag}`, plus the
hinge gate:

1. **The Activation primitive** — a persisted, supervised record of a node firing, carrying a
   **pluggable readiness rule** (today only `upstream-done`; the field is named now for
   `fixpoint`/`standing`/`market`/`emergent`) + a lifecycle (transitions ARE log events) +
   identity = `hash(node + input-Ports + profile)`. Subsumes the implicit
   program-counter-plus-thread that exists today.
2. **THE realized-graph / topology-realizer** — `build_topology(run_config) -> Graph`: the
   SINGLE source for both `next_step` projection and reverse-recovery (`predecessors()`),
   re-invocable mid-run with a **cursor-survival invariant**.
3. **2-axis drivers** — substrate (`in_process` | `subprocess_isolated`) × topology (`graph`,
   loop-control as a node). `oneshot` is DELETED.
4. **The Conveyance / Work-Envelope** — `StepContext`/`StepResult` carry a typed `RunEnvelope`
   (taint-lattice joined-at-every-merge + cost-ledger + lineage + deadline + cancellation-token
   + error-class + retry-budget). The temporal face of the Port. *Nothing crosses a seam naked.*
5. **THE R1 AUTHORITY FLIP** — the shadow WAL (seeded M1, fold-equivalent since) becomes
   authoritative; `state.json` becomes a rebuilt cache; resume = replay.
6. **The Governor + Capacity-Lease** — tree-scoped recursion/cost budget + a linearizable
   `fcntl.flock`'d cross-tenant arbiter with **fencing tokens that fail the NEXT write**, homed
   in the key/rate broker, pulled forward to land directly under the Activation it scopes.
7. **THE HINGE GATE (must pass IN M3):** fold-equivalence vs the M2.5 recovery/blocked corpus +
   the substrate-swap oracle (replay a recorded **blocked-retry-then-resume** trace across the
   version boundary; crash-isolation; version-skew), behind default-OFF flag.

---

## Scope (in) — work items tied to current file:line

- **Conveyance FIRST (the first sub-PR).** Introduce a typed `RunEnvelope` carried on
  `StepContext`/`StepResult` (referenced throughout `megaplan/_pipeline/` but not yet a typed
  carrier — see `pattern_types.py`, `pattern_dynamic.py`). It reuses the M2 taint lattice (do
  NOT invent taint twice) and carries cost-ledger + lineage + deadline + cancellation-token +
  error-class + retry-budget. Today these leak through `state.json` and `repr(exc)` (SYNTHESIS
  Part 5 #2). Lands BEFORE the Activation that carries it and the Governor that charges it.
- **The Activation record.** A persisted+supervised firing record with `readiness_rule` (enum,
  today only `upstream-done`, the rest named-inert) + lifecycle states emitted as log events +
  identity `hash(node + input-Ports + profile)`. The in-process walk in
  `executor.run_pipeline` (`megaplan/_pipeline/executor.py:212`) gains an Activation per step;
  the implicit thread/program-counter becomes the explicit record (SYNTHESIS Activation spec,
  Reshaper #2).
- **Topology-realizer `build_topology(run_config) -> Graph`.** Performs on graph edges the
  ordered cumulative fold today done over the `WORKFLOW` dict by `_workflow_for_robustness`
  (`megaplan/_core/workflow.py:184-209`) driven by `_ROBUSTNESS_WORKFLOW_LEVELS`
  (`megaplan/_core/workflow_data.py:116-122`). Must reproduce the node/edge REWRITING in
  `_ROBUSTNESS_OVERRIDES` (`workflow_data.py:91-113`). Re-invocable mid-run: `set-robustness`
  rebuilds the live graph and the resume cursor stays valid (the cursor-survival invariant).
- **`workflow_next` becomes a thin projection over the realized graph** — *signature unchanged*
  (`workflow.py:282-302`; `infer_next_steps` alias L302, ~15 callers). Must still filter edges
  by the 7 `_transition_matches` predicates (`workflow.py:212-242`) and re-append the synthetic
  `"step"` target for `_STEP_CONTEXT_STATES` (`workflow.py:49`, projection at `:297`). The 7
  conditions survive as edge metadata, NOT flattened to the 3 coarse `kind="gate"` edges
  (`executor.py:42-52, 268-271`).
- **Reverse-recovery derived on demand.** `_BLOCKED_RECOVERY_STATES` (`handlers/override.py`)
  and `_RESUME_ACTIVE_STATES` (workflow resume) become `predecessors(stage)` queries on the
  single graph (no persisted 4th copy), exposed as a queryable API the recovery handlers call.
- **Substrate axis — the `subprocess_isolated` driver.** Extract the reusable substrate of
  `auto.py`'s subprocess loop into a driver: `spawn` (`runtime/process.py:69`,
  `start_new_session=True`), the idle+wall watcher in `_run_megaplan`
  (`megaplan/auto.py:238-368`), `kill_group` on stall (`auto.py:362`), plan-mtime liveness
  (`_plan_liveness_mtime`, `auto.py:377`), and `PHASE_TIMEOUT_EXIT_CODE=124` (`auto.py:125`)
  surfaced as a containable per-step failure. `in_process` is today's `executor.run_pipeline`
  (`executor.py:212`). **Two substrates, not one driver with a flag.**
- **Topology axis — loop-control as a node.** A control node on the walk (NOT a peer driver):
  owns the iteration count, reads a `Callable[[LoopContext], bool]` over
  `{state, last_fanout_results, budget, iteration}`, mandatory `max_iterations` cap +
  teardown-on-all-paths. Wire the predicate `iterate_until` currently `del`s
  (`megaplan/_pipeline/pattern_topology.py:288`).
- **THE R1 AUTHORITY FLIP.** The shadow WAL (seeded M1, fold-equivalent every milestone since)
  becomes authoritative behind `MEGAPLAN_UNIFIED_DISPATCH`. `state.json` is rebuilt from the
  fold (resume = replay). Folds through `write_plan_state` (`megaplan/_core/state.py:329`) under
  the existing `plan_state_lock` (`state.py:235`, `fcntl.flock`). Reshaper #1. **Gated on the
  hinge gate; never flips on a green happy-path parity alone.**
- **The Governor + Capacity-Lease.** Homed in `runtime/key_pool.py` (`KeyPool` at
  `key_pool.py:66`; `acquire` at `:158`; `report_429` at `:171` — the non-atomic LRU that
  stampedes today, SYNTHESIS Reshaper #4). Add: a tree-scoped recursion/cost/concurrency/fan-out
  budget charged per-subgraph against a fixed pool; and a linearizable `fcntl.flock`'d on-disk
  Capacity-Lease with **fencing tokens** so a stolen/expired lease fails its NEXT write. A
  byte-identical in-process fallback exists when the flock path is unavailable (REGISTER M4
  pattern, applied here).
- **State-evolution = two honest values** behind the Store (`state.py:214-220`,
  `PlanStateWriteMode`): `forward-only` (default) + `reversible` (= forward + `snapshot`/
  `restore` under `plan_state_lock`, sidecar `.state-versions/<id>.json`). `restorable_boundary`
  **fails LOUD** when `reversible` composes with `subprocess_isolated`/fan-out. Event-sourced is
  declared on the axis enum + scaffolded behind the interface, **no real backend here**.
- **Cloud `_phase_command` shim.** The cloud→auto coupling (`megaplan/cloud/cli.py:225-227`,
  `from megaplan.auto import _phase_command`) lands as a guarded shim born with the process
  driver, plus a cloud smoke oracle wired into the chain.
- **Acceptance toy.** One non-planning, non-forward-only package (tiny backtracking
  constraint-solver) exercising loop node + `restore` + `budget`, zero planning imports, all
  inter-step data crossing a declared Port.

## Locked decisions

- **The Activation, not the graph shape, is the scheduler primitive** (Reshaper #2). Named now
  while readiness = `upstream-done`; the other rules are inert fields, not switch-statement mush.
- **R1 flips HERE, not at the M1 seed.** Authority arrow inverts at the apex, gated on the M2.5
  oracle + fold-equivalence (green since M1) — never on the substrate-blind happy-path parity.
- **The realized graph is the SINGLE source** for `next_step` projection and reverse-recovery.
  No persisted 4th copy; recovery = `predecessors(stage)` on demand.
- **Two orthogonal driver axes, not a flat 4-value enum**; `oneshot` is DELETED (phantom).
- **Loop is a composable NODE on the walk**, not a peer driver; owns predicate/teardown/cap.
- **The Governor moves EARLIER than its DAG slot** (lands at M3, not M4): the moment R1 makes
  the log authoritative the reason-to-ban-concurrency dissolves (UU#6), and the first concurrent
  activation is a fork-bomb against the shared wallet without a tree budget (UU#8). You cannot
  safely demo the primitive subsuming loop/market without the Governor already under it.
- **Conveyance reuses the M2 taint lattice** — temporal face of the same law whose spatial face
  is the Port. Never invent taint twice.
- **Capacity-Lease uses fencing tokens, not wall clocks** — a stolen/expired lease fails its
  NEXT write (SYNTHESIS Governor spec; Reshaper #4).
- **Forward-only stays the DEFAULT** Store model; planning's hot path is unchanged.
- **Subprocess seam stays dormant ≥1 dual-green milestone**, retired only at M6 (strangler
  discipline; no organ-swap + old-path-deletion in one PR).
- **Reuse, do not fork:** `runtime/process.{spawn,kill_group}`, `_run_megaplan`'s watcher,
  `plan_state_lock`, `key_pool`, and the `_workflow_for_robustness` fold logic.

## Open questions (each RESOLVED to its default — zero human blockers)

- **Snapshot granularity** → whole-blob copy of `state.json` (cheap, matches LWW); BUT it rolls
  back the RECORD not the WORLD — hence the loud `restorable_boundary`. *(REGISTER M3.)*
- **Mid-run re-realization + live cursor** → Done-#2 cursor-survival invariant: rebuilt topology
  reproduces recovery/resume states + cursor on a live node, else a typed reject (never parks).
  *(REGISTER M3 + §2 set-robustness row.)*
- **Snapshot location** → sidecar `.state-versions/<id>.json` under the per-plan flock; confirm
  no collision with `_write_forensic_backup` (`executor.py:90-133`). *(REGISTER M3.)*
- **Cross-shard budget** → single-tenant in M3; cross-shard folding deferred to M4. *(REGISTER
  M3.)*
- **"One Store" vs "irreconcilable"** → interfaces-with-backends: event-sourced scaffolded
  behind the interface, no real backend in M3. *(REGISTER M3.)*
- **Cloud `_phase_command` shim** → land in M3; smoke oracle verifies. *(REGISTER M3.)*
- **Acceptance toy** → tiny backtracking constraint-solver. *(REGISTER M3.)*
- **R1 flip blocked by a red oracle** → auto-halt + the bounded escalation ladder (retry ×2 →
  bump profile/robustness one tier → `stop_chain` + auto-ticket); never a human wait. *(REGISTER
  §1, §4.)*

## Constraints

- **Crash-isolation is an explicit done-criterion, not a hoped-for property.** `in_process` runs
  steps in ONE interpreter (an OOM/segfault/wedge takes the run down); `subprocess_isolated` is
  the ONLY substrate that preserves auto.py's containment (`auto.py:352-368`). The flip removes
  this seam — so the substrate-swap oracle (crash-isolation) must be green before the flip.
- **The hinge gate guards a SUBSTRATE swap (the highest-risk class).** The happy-path parity gate
  is structurally blind to substrate swaps; its honest label is "control-flow/artifact parity on
  the happy path, NOT drift-provably-zero." The behavioral-replay + substrate-swap oracle is the
  **SOLE retirement authority** (PROGRAM L381-386).
- **The Capacity-Lease is built before a second real tenant exists.** Fork-bomb +
  simulated-clock-skew + two-tenant oracles stand in as a synthetic adversary; the alternative
  (unbanning concurrency at M3 with no Governor) is a fork-bomb against the live wallet.
- **No editable-install dogfood; separate external driver** (M0; MEMORY `dogfood_engine_shadow`). The epic
  runs the toggle OFF; the in-process path soaks on THROWAWAY plans only.
- **Back-compat.** `iterate_until`, `SubloopStep`, `write_plan_state` modes, executor edge
  dispatch, and `workflow_next`'s signature all keep working (`extra="ignore"`, no removed
  modes). All new pieces are additive behind the flag.

## Done criteria (testable, incl. the oracle gate)

1. **THE HINGE ORACLE GATE (must be green IN M3):** with `MEGAPLAN_UNIFIED_DISPATCH=on`,
   fold-equivalence holds vs the M2.5 recovery/escalate/**blocked** corpus, AND the
   substrate-swap oracle replays a recorded **blocked-retry-then-resume** trace across the
   version boundary byte-stably, AND crash-isolation + version-skew oracles pass. Red →
   auto-halt + the bounded ladder; the flip does NOT promote.
2. **R1 authority flip:** with the flag ON, `state.json` is rebuilt from the WAL fold; killing
   and resuming a run replays the log to the identical cursor; with the flag OFF the old
   `state.json`-authoritative path is byte-unchanged (regression).
3. **Realizer re-invocability:** `build_topology` rebuilt after a simulated `set-robustness`
   yields a graph whose `predecessors(stage)` reproduces `_BLOCKED_RECOVERY_STATES` /
   `_RESUME_ACTIVE_STATES` exactly, with a still-valid resume cursor and no persisted 4th copy.
4. **Parity GATE:** `workflow_next` over the realized graph equals the legacy dict-folded impl
   across `{5 robustness} × {with_prep, with_feedback} × {all states} × {all gate
   recommendations}`, including the synthetic `"step"` target and the
   `gate_proceed`/`gate_proceed_blocked`/`gate_proceed_agent_availability_blocked` distinctions.
5. **Crash-isolation (explicit):** under `subprocess_isolated`, a step that `sys.exit(1)` /
   sleeps past idle / is OOM-shaped is killed via `kill_group`, surfaced as a contained per-step
   failure, parent survives, process group reaped (no orphan). Under `in_process` the same step
   takes the run down — asserted as the documented trade.
6. **Activation:** each step fires a persisted Activation with identity `hash(node + input-Ports
   + profile)`; lifecycle transitions appear as log events; readiness `upstream-done` gates
   firing; the other readiness rules exist as inert enum values rejected loudly if selected.
7. **Conveyance:** `RunEnvelope` rides every `StepContext`→`StepResult`; taint joins at every
   merge; cost/deadline/cancellation/retry-budget/error-class are carried, not leaked through
   `state.json`/`repr(exc)`; a dropped envelope fails a unit assertion.
8. **Governor + Capacity-Lease:** a synthetic recursive fan-out is bounded by the tree budget
   (depth/fan-out/dollar/concurrency) and stopped at the cap; the two-tenant + fork-bomb +
   clock-skew oracle shows no double-issue, shared backoff, shared spend cap; a stolen/expired
   lease fails its NEXT write (fencing token); in-process fallback is byte-identical.
9. **Loop node:** runs N times data-dependently (predicate actually consulted, not `del`'d);
   `max_iterations` fires; teardown runs on every exit path (normal/cap/exception/budget).
10. **Store axis:** `snapshot()`→mutate→`restore()` returns exact prior state under the lock;
    `restorable_boundary` RAISES LOUD when `reversible` composes with `subprocess_isolated`/
    fan-out; forward-only default unchanged.
11. **Cloud `_phase_command` shim** + cloud smoke oracle pass.
12. **Non-planning acceptance package** (backtracking solver) green on loop + restore + budget,
    zero planning imports, all inter-step data crossing a declared Port.
13. **Strangler:** OLD subprocess engine still self-hosts a throwaway 1-milestone plan
    (flag-OFF, pinned, schema report-only); NEW path runs a planning-shaped throwaway behind the
    flag matching the replay corpus; subprocess seam present and dormant (NOT deleted).

## Touchpoints

- `megaplan/_core/workflow.py:184-209` (`_workflow_for_robustness` fold → onto edges),
  `:212-242` (`_transition_matches`, 7 predicates), `:49` (`_STEP_CONTEXT_STATES`),
  `:282-302` (`workflow_next`/`infer_next_steps` projection + synthetic `"step"`).
- `megaplan/_core/workflow_data.py:91-113` (`_ROBUSTNESS_OVERRIDES`), `:116-122`
  (`_ROBUSTNESS_WORKFLOW_LEVELS`).
- `megaplan/_core/state.py:214-220` (`PlanStateWriteMode`), `:235` (`plan_state_lock`),
  `:329` (`write_plan_state` — the WAL fold + snapshot/restore hang here).
- `megaplan/auto.py:238-368` (`_run_megaplan` watcher = the process substrate), `:362`
  (`kill_group`), `:377` (`_plan_liveness_mtime`), `:486-517` (`_phase_command`), `:125`
  (`PHASE_TIMEOUT_EXIT_CODE`), `:1390` (`STATE_AWAITING_HUMAN`).
- `megaplan/runtime/process.py:69` (`spawn`, `start_new_session`), `kill_group`.
- `megaplan/runtime/key_pool.py:66` (`KeyPool`), `:158` (`acquire` — the non-atomic LRU),
  `:171` (`report_429`) — the Governor/Capacity-Lease home.
- `megaplan/_pipeline/executor.py:212` (`run_pipeline` in-process walk + per-step Activation),
  `:42-52, 268-271` (gate edge dispatch), `:90-133` (`_write_forensic_backup` — collision
  check), `:308-403` (`run_pipeline_with_policy`, escalate `:387-389`).
- `megaplan/_pipeline/pattern_topology.py:288` (`iterate_until` — stop `del`-ing the predicate).
- `megaplan/_pipeline/pattern_types.py`, `pattern_dynamic.py` (`StepContext`/`StepResult` — the
  Conveyance carrier).
- `megaplan/_pipeline/subloop.py` (child-on-copy state; budget-not-crossing-shards constraint).
- `megaplan/cloud/cli.py:225-227` (`_phase_command` shim born here).

## Anti-scope

- NOT the `dispatch`/`emit`/`evidence` services, config-precedence resolver, the RecoveryPolicy
  spine, the Effect Ledger, or the Evaluand — those are **M4**. M3 builds substrate mechanism +
  the Activation/Conveyance/Governor organs + the R1 flip; M4 builds the policy spine on top.
- NOT cross-shard / nested-fan-out budget folding — the Governor's budget is tree-scoped but
  single-tenant in M3; cross-shard folding is M4 (REGISTER M3).
- NOT a real event-sourced backend — the axis is declared + scaffolded behind the interface;
  only forward-only + reversible get real backends with real users.
- NOT the control/override plane, human-gate service, or supervisor tier — **M5**. M3 only
  ensures recovery handlers can query the realized graph's reverse maps.
- NOT relocating planning, dropping `_BUILTIN_NAMES`, deleting the subprocess seam, or collapsing
  the next-step encodings — that is **M6** (now safe because M3's parity gate proved the
  projection faithful). The subprocess seam stays dormant ≥1 dual-green milestone.
- NOT the Calibration/eval ledgers, Manifest, Capsule, or Warrant — later milestones / sinks.
