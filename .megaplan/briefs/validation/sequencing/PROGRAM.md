# Arnold Build — THE Sequenced Milestone Program (reconciled)

**Status:** Re-derived epic of record (2026-05-29). Reconciles the three independent build
orderings — `dependency-dag.md` (what is technically possible), `strangler-keep-alive.md`
(the hard self-hosting constraint), `risk-value-first.md` (what to front-load to fail fast
and deliver provable increments) — into ONE dependency-ordered program. Supersedes the
pre-architecture m1..m7 briefs in `.megaplan/briefs/epic-pipeline-unification/`, which are re-aimed onto
the eleven organs and seven reshapers of `committed-uu/SYNTHESIS.md`.

How the three lenses combine, in one sentence each:
- **The DAG is the skeleton** — it fixes the forced edges (Port⇐R1, Conveyance⇐Port,
  Activation⇐Port+Conveyance, Governor⇐Activation, services⇐Governor, F4⇐F5, **Evaluand⇐Calibration**,
  the strangler swap last). No reconciliation may violate a hard DAG edge.
- **The strangler lens is the binding constraint** — it adds the floor the DAG omits (a pinned
  external engine + report-only schema + flag-gated dual-run + replay/substrate oracles), forces
  every organ to land as `{old-path default-on, new-path default-off-behind-flag}`, and defers the
  single system-flipping deletion (`_BUILTIN_NAMES` + relocate planning) to the LAST load-bearing
  milestone so there is never a multi-week broken window.
- **The risk-value lens re-shapes WITHIN the strangler envelope** — it pulls the auto.py
  behavioral oracle forward as its own cheap spike (the DAG itself flagged this as the one
  mitigation its skeleton needs), brings the Governor up to land with the Activation (the moment
  the log is authoritative the reason-to-ban-concurrency dissolves, and the first concurrent
  activation is a fork-bomb without a tree budget), and parallelizes the value half (node-lib /
  execute / eval) off the service base so a slow foundation never serializes everything.

---

## Reshaper #1 is the floor — CONFIRMED, with one correction

**Confirmed.** Reshaper #1 (state = a deterministic fold over an append-only, effect-typed,
taint-carrying event log; WAL authoritative, `state.json` a rebuilt cache) is the universal root.
All eleven organs either record INTO the log or are folded FROM it; every other reshaper assumes
it (Port's `artifact` kind is a by-content-hash ref into the log/blob store and its `value` kind is
inline-in-log; the Activation's lifecycle transitions ARE log events; the Governor's lease/spend are
folded from the log with fencing-tokens-fail-next-write; the one Ledger IS the log; the Manifest is
what the content-hash points AT). Built late, every prior organ is a retrofit against a substrate
whose authority arrow points the wrong way — and SYNTHESIS Tier-S UU#6 is explicit that this
retrofit "silently corrupts in-flight runs." Nothing technically precedes it.

**The correction the strangler lens forces:** the *organ* R1 is the floor, but it is NOT milestone
zero, and its authority flip is NOT a single PR. Two refinements, both load-bearing:

1. **A harness milestone (M0) precedes even R1.** R1 is the first behavior-changing merge, and the
   strangler edge is *currently violated* (we dogfood off an editable install — MEMORY:
   `dogfood_engine_shadow`). Without a pinned external engine + report-only schema validator, the
   very first R1 commit deadlocks the chain that is driving the build. So the true floor is M0; R1
   is the first organ built ON the floor.

2. **R1 is seeded-then-flipped, not built-at-once.** The log is written as a *shadow* from M1, with
   fold-equivalence asserted against `state.json` every milestone while `state.json` stays
   authoritative; the *authority flip* happens at M3 gated on the substrate-swap oracle. This is the
   only way to introduce R1 without the p3-H1 deadlock (a fail-closed validator deadlocking the old
   writer that is driving the build). The accepted residual risk of this deferral is named in the
   open risks below and is mitigated by making the shadow load-bearing from the M2.5 spike onward.

So: **R1 is the floor among the organs; M0 (harness) is the floor among the milestones; the R1
authority flip is the critical-path apex (M3), not its seed (M1).**

---

## The program — ordered milestones

Tiers: **T0 = keep-alive floor**, **T1 = foundation/critical-path**, **T2 = service + value layer**,
**T3 = the strangler swap + cross-cutting organs**, **T4 = sinks (projections, no new substrate)**.
Each milestone lands the new organ behind a default-OFF flag beside the live old path; the
per-milestone gate is in "Strangler discipline" below. Labels map to the prior vehicle (M1..M7) so
the chain.yaml regenerates onto this triple.

### M0 — Keep-alive floor: pinned engine + report-only schema + dual-run rig + oracle skeleton  `[T0]`
- **Delivers:** (1) a pinned external megaplan engine in its own venv from a tag, driving the epic
  against the working tree as target — the auto/chain/state code that EXECUTES the build never
  changes mid-flight (`--no-git-refresh`); (2) the schema-version validator in
  report-only / accept-missing-as-v0 mode so an old writer can never deadlock a new reader; (3) the
  standing dual-run rig (OLD engine boots+drives a throwaway plan AND a planning-shaped plan runs on
  whatever NEW pieces exist) + the behavioral-replay oracle harness + the substrate-swap oracle
  skeleton.
- **Hard prerequisites:** none (this IS the root the DAG omitted).
- **Organs/reshapers landed:** none yet — it is the *scaffold that makes R1 landable* without the
  deadlock. (This is `W0` from the strangler lens, folded in as a real milestone.)
- **Why first:** the DAG starts at R1 because nothing technically precedes it; the strangler lens
  proves R1's first commit deadlocks the live driver without this floor. Cheap, no organ, pure
  risk-removal — exactly the risk-value lens's "lowest invalidation risk, highest leverage" test.

### M1 — Foundation, hygiene, contract-checker + R1 shadow-WAL seed + seeded facts  `[T1]`
- **Delivers:** CI marker-switch; executor-merge superset (override-complete); `extra="ignore"`
  state back-compat + fixture corpus; pinned status/chain contracts; discovery-integrity guard;
  sandbox fail-open fix; the degenerate `pipelines check`/`doctor` linter (edges / reachability /
  gate-coverage only — no typed Port resolution yet); the `chain.yaml↔EPIC↔briefs` anti-drift lint
  (makes the STALE-program-execution bug un-shippable); **the R1 SHADOW-WAL writer** appending every
  event to an append-only effect-typed taint-carrying log with fold-equivalence asserted against
  `state.json` every milestone (state.json still authoritative); plus the *un-retrofittable seeds*
  the value lens demands now while there is one author/tenant: model-identity as a hash-pinned
  receipt field (R7 seed), per-phase prefix-cache-hit-rate + monoculture-index sensors, and the
  ZERO-`GateRecommendation`-in-SDK grep-gate scaffold.
- **Hard prerequisites:** M0.
- **Organs/reshapers landed:** R1 (SEED only — shadow log, schema_version stamp,
  migrate-before-validate); R7 (seed field, no consumer); Effect-Ledger TYPE SKELETON (replay-class
  enum + idempotency-key field, not yet enforced) — these three seeds ride along per the DAG's
  S0/S1 parallel notes.
- **Why here:** lands each piece as its own PR to main the day it is green, so the repo's
  ~80–900 commits/wk test the gates continuously instead of discovering rot at integration. WAL is
  shadow-only — retires nothing — exactly the read-side-shadow-before-authoritative move all three
  lenses converge on. The grep-gate scaffold enforces de-planning from line one.

### M2 — De-planning types + the Port + Contract Ledger + StateDelta(CAS) + R3 taint-in-hash  `[T1]`
- **Delivers:** `reduce`/`JoinFn` → structured data under the ZERO-`GateRecommendation` grep gate;
  `select()` / `Reduce[T]`; wire the dropped `iterate_until` predicate + stop-predicate library;
  the **typed Port** = `(kind∈{value,artifact,stream} × content-type[open MIME registry] × schema)`
  — artifact = by-content-hash-ref, value = inline-in-log; **taint enters the content-hash (R3)**;
  the **Contract Ledger** = content-hashed registry of Port contracts + legal coercions + binder
  that resolves `consumes`↔`produces` at build time (kills the `step_helpers.py:104` silent `v1.md`
  fallback — a missing dep becomes a loud `build()` failure); **StateDelta CAS** replaces flat-key
  LWW; the dropped predicate wired.
- **Hard prerequisites:** M1 (Port's `artifact` kind refs the log; taint enters the *log's* hash).
- **Parallel:** runs as a branch BESIDE the old string/state-dict plumbing — types do NOT depend on
  the executor merge, so serializing them behind M1 internals is pure tax. The 4-verdict enum moves
  to the planning binding; the grep gate proves zero leakage.
- **Organs/reshapers landed:** Port, Contract Ledger (R3); StateDelta(CAS).
- **Why here:** taint MUST enter the content-hash *before* any untrusted value shares the store —
  cache-collision-launders-taint is unrecoverable retrofit (SYNTHESIS UU#4). Partial enum conversion
  is worse than none: a half-converted `GateRecommendation` re-planning-izes every downstream driver.
  **Merge gate: grep=0 AND all consumers green together** — never a partial merge.

### M2.5 — Auto.py characterization spike + resume-model decision  `[T1, parallel with M2]`
- **Delivers:** `test_auto_drive.py` written against TODAY's subprocess `auto.py`, merged to main as
  permanent CI — the real behavioral oracle, **including recovery / escalate / blocked-retry traces,
  not just the happy path**; a one-page written decision on the SINGLE resume model (reconciling
  `_pipeline_paused_stage` vs `current_state`/`next_step`/`resume_cursor` vs `STATE_AWAITING_HUMAN`).
- **Hard prerequisites:** M1 (needs the shadow log + today's subprocess engine — depends on nothing
  M2 produces).
- **Parallel:** with M2 (off the M1 base).
- **Organs/reshapers landed:** none — it is the spike that DE-RISKS M3.
- **Why here (the cross-lens reconciliation):** the DAG explicitly names this as *the one mitigation
  its brittle skeleton needs* — splitting S3 at its seam and pulling the oracle forward turns M3 from
  "discover-and-port-at-once" into "port against a green pre-merged oracle." The risk-value lens
  independently demands the same spike ("highest-uncertainty discovery on a cheap spike, not inside
  the apex"). This oracle BECOMES the behavioral-replay corpus every later retirement is authorized
  against — making the shadow WAL load-bearing from here on (the key mitigation for the seed-early
  /enforce-late risk).

### M3 — THE HINGE: Activation primitive + realized-graph + 2-axis drivers + R1 authority flip + Governor  `[T1]`
- **Delivers:** the **2-axis driver** (substrate `in_process`|`subprocess_isolated` × topology
  `graph`, loop-as-node); the **topology-realizer** `build_topology(run_config)->Graph` as the SINGLE
  source for both `next_step` projection and reverse-recovery (`predecessors()`), re-invocable mid-run,
  with the `{5 robustness}×{prep,feedback}×{states}×{verdicts}` **parity test as a hard GATE**; the
  **Activation** = persisted/supervised firing record with a pluggable readiness rule (today only
  `upstream-done`, named now for loop/standing/market/emergent) + identity = `hash(node + input-Ports
  + profile)`; loop-control as a node with mandatory `max_iterations` + teardown-on-all-paths;
  **state-evolution** = `forward-only` | `reversible`(snapshot/restore + `restorable_boundary` fails
  LOUD under process/fan-out) | `event-sourced-separate-backend`; the cloud `_phase_command` shim;
  **the R1 AUTHORITY FLIP** — WAL becomes authoritative, `state.json` becomes a rebuilt cache, gated
  on the fold-equivalence oracle (green since M1) AND the substrate-swap oracle (resume-across-version,
  crash-isolation); **the tree-scoped Governor + linearizable `fcntl.flock`'d Capacity-Lease** (fencing
  tokens that fail the NEXT write) homed in the key/rate broker, pulled forward to land directly under
  the Activation it scopes.
- **Hard prerequisites:** M1 (log), M2 (Port + Contract Ledger — readiness consumes input Ports and
  hashes them), M2.5 (the oracle + the resume decision). Governor additionally needs the Conveyance
  envelope it charges against — see note below.
- **Conveyance fold-in:** the DAG broke Conveyance/Work-Envelope out as its own node (S2) between
  Port and Activation. Reconciled, it lands as the *first sub-PR of M3*: `StepContext`/`StepResult`
  carry a typed `RunEnvelope` (taint-lattice joined-at-every-merge + cost-ledger + lineage + deadline
  + cancellation-token + error-class + retry-budget) BEFORE the Activation that carries it and the
  Governor that charges it. It is the temporal face of the same law whose spatial face is the Port
  (built at M2) — reusing M2's taint lattice, never inventing it twice.
- **Organs/reshapers landed:** Activation (R2); Conveyance/Work-Envelope; R1 made authoritative;
  Governor + Capacity-Lease (R4) — the value lens's "pull R4 forward" reconciled into the hinge.
- **Why here / why the Governor moves up:** Activation cannot move earlier (needs Port + Conveyance)
  nor later (everything below depends on it) — position 4 on the longest chain, un-relocatable. The
  Governor moves EARLIER than the DAG's S4 slot because the moment R1 makes the log authoritative the
  reason-to-ban-concurrency dissolves (UU#6), and the FIRST concurrent / market activation is a
  fork-bomb against the shared wallet without a tree budget (UU#8) — you cannot safely demo the
  primitive subsuming loop/market without the Governor already under it. This is the single most
  dangerous engine-half-swapped moment: it removes the only version-isolation seam AND flips the
  highest-blast-radius foundation while the chain self-hosts — hence it lands STRICTLY behind
  default-OFF `MEGAPLAN_UNIFIED_DISPATCH`; the epic driving the build runs the toggle OFF (old
  subprocess auto); the in-process path soaks on THROWAWAY plans only; **the subprocess seam is NOT
  deleted** (it survives dormant behind the flag for ≥1 dual-green milestone, retired only at M6).

### M4 — Services + Effect Ledger + RecoveryPolicy spine + R5 one-log + Evaluand scaffold  `[T2]`
- **Delivers:** `dispatch` (2 backends) with watchdog/liveness on token-progress (not silence);
  `emit` = the single `EventSink.emit(kind,payload,scope)` write path resolving the two-disjoint-
  journals problem (**R5 made real**); `evidence` (attestation + oracle/`run(cmd)→{exit,stdout,stderr}`);
  config-precedence resolver; the **RecoveryPolicy spine** `classify(error)->{retry_fresh|
  retry_transient|escalate|halt(kind)}` (extracts auto.py's brain); the Run/Composition transaction
  boundary on the Envelope (UU#8); **the Effect Ledger enforced HERE** — every world-act carries
  replay-class + external idempotency-key(≠content-hash) + declared compensation — BEFORE the first
  real money/merge/PR is journaled on the new substrate; **the Evaluand + one-Ledger record**
  (versioned attributable judgment scaffold); `introspect`/`doctor`/`trace`/`cost` re-homed onto the
  composition-observability contract. (The Governor/Capacity-Lease landed at M3, ahead of its DAG
  slot.)
- **Hard prerequisites:** M3 (services carry the Envelope, dispatch acquires under the Lease, the
  Activation drives them). Effect/Evaluand records into the now-authoritative log.
- **Organs/reshapers landed:** Effect Ledger; R5 (one-log); the Evaluand record (scaffold —
  attribution lands fully at M5-eval). Internally 5 parallel PRs (dispatch ∥ emit ∥ evidence ∥
  config ∥ recovery-policy).
- **Why here:** the Effect Ledger MUST be load-bearing before any world-act runs on the new
  substrate — content-hashing the artifact does NOT make the ACT idempotent (SYNTHESIS UU#3). Services
  run as injected backends beside the old hard-wired calls; the OLD key-pool/cost-tracker stays live
  until the Capacity-Lease two-tenant oracle is green; journal unification stays report-only until M6.

### M5a — Node library + Behavioral Identity Manifest (R6)  `[T2, parallel with M5b/M5-eval]`
- **Delivers:** formalized `produce/judge/gate/revise/fan_out/escalate/clarify/verify/loop_until +
  select/reduce` as the composition vocabulary (provisional tier, checker-readable registry); reserve
  `arnold_api_version`; the **Behavioral Identity Manifest (R6)** — content-hash the behavioral
  closure (topology + step-code hashes + resolved prompt BODIES + routing-taken + Port set + ABI
  version + resolved dep-closure). M3's resume policy now keys on the Manifest hash (pin / refuse /
  migrate-via-codemod).
- **Hard prerequisites:** M2 (nodes are Port-typed), M3 (Manifest hashes the realized graph; resume
  keys on it).
- **Parallel:** with M5b and M5-eval off the M4 service base.
- **Organs/reshapers landed:** the node-library vocabulary; the Manifest (R6).
- **Why here:** patterns are Port-typed compositions that call emit/dispatch (M4). The Manifest is
  what makes resume version-aware (chimera defense, UU#9) and is what M6's relocated planning will be
  *identified by* — so it must land before the relocation tail. Additive; nothing retired.

### M5b — Execute realm: F4 complexity-tiering → F5 task-DAG scheduler  `[T2, parallel with M5-eval]`
- **Delivers:** F4 tier-resolution capability; F5 batch/task-DAG scheduler whose reducer returns
  app-defined typed outcomes (`Reduce[T]`, binding maps to phase_outcome); merge stays mechanical,
  classification moves to the reducer. Hard internal edge **F4-before-F5** (F5's per-batch
  tier→model resolution consumes F4's capability — `execute/batch.py:79,18`).
- **Hard prerequisites:** M5a (nodes), M3 (the scheduler), M4 (the Governor bounds task fan-out; the
  service dispatch).
- **Parallel:** with M5-eval.
- **Organs/reshapers landed:** the execute realm as a composition of the now-real primitives.
- **Why here:** new execute realm runs behind the same dispatch flag; the old execute path is retired
  only after its replay oracle is green.

### M5-eval — Evaluand + one Ledger: versioned attributable judgments  `[T2, parallel with M5a/M5b]`
- **Delivers:** the judge becomes a Port-typed, content-hashed, versioned PIECE; a score = a join over
  `(piece-version × rubric-version × judge-version × input-set)`, never a bare float; recorded into
  the one Ledger.
- **Hard prerequisites:** M4 (recorded into the one Ledger via verify/judge nodes), M5a (the
  verify/judge node verbs), M2 (a judge is a Port piece).
- **Parallel:** with M5a, M5b.
- **Organs/reshapers landed:** the Evaluand + one-Ledger attribution (completes the M4 scaffold).
- **Why here, and why it is GATED before Calibration:** for the self-improving heart this IS the
  spine. It is a HARD prerequisite of Calibration — calibrating against bare floats is the
  Goodhart / co-degradation failure (SYNTHESIS UU#2,#10), a regression that reads BETTER as quality
  rots, invisible by construction. **The Evaluand→Calibration edge is the single most order-sensitive
  in the whole program and is treated as non-negotiable by all three lenses.**

### M5-cal — Calibration Ledger: CapabilityClaims + decay/exploration; routing = a query  `[T2]`
- **Delivers:** the 1–5 tier score and `tier_models` become PROJECTIONS; routing = a query.
  DECAY/CHURN (new models seed from a capability-class prior, not cold-start) + EXPLORATION BUDGET
  (an off-policy fraction so the loop can't ratchet) + TAINT-AWARE AGGREGATION (Port taint governs
  shared-vs-tenant-local claims). The cheapest-routing-vs-prompt-caching (UU#12) and monoculture
  /co-degradation (UU#7/#10) tensions become gated experiments on the M1-seeded sensors.
- **Hard prerequisites:** M5-eval (a CapabilityClaim's outcome IS an Evaluand), M4 (over dispatches
  that must already route; the Calibration record is in the one Ledger), M3 (reads the taint lattice
  on the Envelope), R7 (keyed on hash-pinned model-identity, seeded at M1).
- **Organs/reshapers landed:** Calibration Ledger.
- **Why here:** build routing first and the loop Goodharts on an unversioned float — invisible by
  construction. The data it needs (M1 sensors, M3/M4 log, the M5-eval ruler) finally exists.

### M5c — Control plane: run-outcome vocabulary + control interface  `[T2, last/hardest of the value layer]`
- **Delivers:** `{succeeded, failed, escalated, blocked, awaiting_human}` + `valid_targets(state)` /
  `recover_targets(state)`; the control trio (`read_valid_targets`, `apply_transition`,
  `synthesize_artifacts`) the binding IMPLEMENTS; planning's `STATE_*` binds ONTO it (evicted from
  the SDK as mechanism, exactly as the 4-verdict enum was evicted from `JoinFn`); the override/auto
  split along the control/planning seam.
- **Hard prerequisites:** M4 (fires the RecoveryPolicy spine), M5b (maps execute outcomes into the
  run-outcome vocabulary), M3 (set-robustness mid-run re-realizes the topology).
- **Organs/reshapers landed:** the control vocabulary + interface; the SDK-vs-app `STATE_*` eviction
  (the most-violated edge made crisp).
- **Why here:** last and hardest de-planning; the new control interface runs BESIDE the old `STATE_*`
  state machine with back-compat aliases; the grep gate now also forbids `STATE_*` as mechanism in
  SDK modules; the old state machine is retired only after the full recovery/escalate matrix oracle
  is green.

### M6 — THE STRANGLER SWAP: megaplan as a discovered module + arnold namespace + trust boundary + journal unification + R7 load-bearing  `[T3]`
- **Delivers:** relocate planning; **drop `_BUILTIN_NAMES`**; manifest + driver + bindings +
  SKILL.md; **manifest-first NON-EXECUTING discovery** + path-derived trust tier (in-tree=trusted,
  out-of-tree=quarantined, blessed=explicit-allowlist-default-empty) + `arnold_api_version` range
  check without importing; collapse the next-step encodings (now safe — M3 proved the projection);
  the CLI/namespace migration (`arnold <verb>` umbrella + `arnold <module> <verb>`); **unify the two
  disjoint journals into ONE Ledger** (R5 completion); R7 made load-bearing (routing consumes the
  hash-pinned model-identity); resident adopts the pieces. **RETIRE the OLD subprocess seam HERE.**
- **Hard prerequisites:** M3 (reads the realized graph for next-step projection), M4 (services + the
  one-log), M5b (execute), M5c (planning's `STATE_*` binds onto the de-planned control interface),
  M5a (the Manifest is the discovery identity).
- **Parallel:** with M5d.
- **Organs/reshapers landed:** the relocation + trust boundary; R5 fully unified; R7 load-bearing.
- **Why LAST among load-bearing nodes:** this is the deferred strangler SWAP — the single deletion
  that removes the old path's root and the one irreversible self-reference change (the
  ship-of-Theseus killzone, B2). Placed last so the flagship/dogfood engine stays intact until
  everything underneath (driver, services, execute, control plane, eval, calibration) is proven; the
  swap is one atomic, oracle-gated cutover, not a creeping half-deletion across M1–M5c, so there is
  **no multi-week broken window**. The `megaplan <x>` aliases stay as fallback until discovered
  planning passes a full dual-run milestone.

### M5d — Supervisor tier: general cross-run orchestration  `[T3, parallel with M6 tail / after M6]`
- **Delivers:** chain/epic/bakeoff become bindings invoking general control ops (not "force-proceed"
  by name); binds onto M5c `awaiting_human` + auto-merge. Acceptance = a THROWAWAY canary epic
  (≥1 dep edge, ≥1 induced failure exercising escalate/recover) — never the epic driving the build.
- **Hard prerequisites:** M6 (orchestrates DISCOVERED modules — needs the relocation + namespace),
  M5c (general control ops), M3 (the single-planning-run process driver). `chain/__init__.py:65,73`
  imports `auto_drive` directly — it cannot be cleanly extracted until the thing it drives is a
  composed driver, which is M6's relocation, so it shares M6's prerequisite.
- **Organs/reshapers landed:** the supervisor tier on the general control ops.
- **Why here:** the supervisor IS the thing driving the epic, so extracting it is the purest
  swap-the-wings-mid-flight — it must be late and default-off, and its only honest acceptance is a
  deliberate canary epic since the frozen real epic structurally cannot exercise the new supervisor
  while it stays on the old engine.

### M7-capsule — Replayable Capsule  `[T4, sink]`
- **Delivers:** the portable exchange unit: Definition (Port-graph + intent + routing) + Contract
  (exported recipient-verifiable manifest, refuses-or-adapts LOUDLY) + Lineage (immutable parent
  edges) + Evidence (journal + diff + verify + cost). Registry / inspector / fork-with-back-edge are
  operations on it.
- **Hard prerequisites:** M5a (Definition = the Manifest), M2 (Contract = the exported Contract
  Ledger), M4 (Lineage + Evidence = the one Ledger).
- **Organs/reshapers landed:** the Capsule. Pure projection — adds no new substrate.

### M7-warrant — Warrant  `[T4, DAG sink]`
- **Delivers:** the outward atom: signed AUTHORITY (frozen policy envelope at action-time) + ACCOUNT
  (verified-work-units, durable, decoupled from provider dollars) + RATIONALE ANCHOR
  (captured-at-decision-time, pinned to the Manifest hash) + SHAPE-INDEPENDENCE (a one-shot action
  and a 200-turn graph yield identical Warrants).
- **Hard prerequisites:** M5a (rationale anchored to the Manifest hash), M5-eval (verified-work = an
  attributable Evaluand judgment), M4 (attests a recorded Effect).
- **Organs/reshapers landed:** the Warrant. The DAG sink — nothing internal depends on it, only
  external consumers (regulator / CISO / insurer).

### M7-docs — Builder docs & onboarding  `[T4, sink]`
- **Delivers:** the `docs/arnold/` set — authoring guide + generated-from-types reference (CI
  drift-gated) + package-contract + worked examples; the external-builder acceptance test (ship the
  `select`-tournament from docs + scaffold ALONE, a grep proving zero planning vocabulary).
- **Hard prerequisites:** M6 (documents the relocated, composition-shaped planning + the arnold
  namespace; the generated-from-types reference needs the types frozen, which the relocation
  completes).
- **Organs/reshapers landed:** none — the final proof the strangle completed (a fourth, non-planning
  tool ships on the same parts).

---

## The critical path

The longest forced chain (each hop a hard dependency edge, no dependency-legal way around it):

`M0` → `M1` → `M2.5` → `M3` → `M4` → `M5b` → `M5-eval` → `M5-cal` → `M5c` → `M6` → `M5d`

with the **R1 authority flip at M3** as the apex (highest blast radius × on the longest rope) and the
**M5-eval → M5-cal** edge as the most order-sensitive single edge in the program. M2 is on the
critical path's near-branch (M3 needs it) even though M2.5 is what M3 most uncertainly waits on, so
M2 ∥ M2.5 share the slot. The terminal sinks (M7-capsule / M7-warrant / M7-docs) hang off the chain
but extend it only by one projection hop.

## Parallel tracks (what proceeds off-critical-path)

- **M1 ∥ M2** — the foundation hygiene and the type/Port work are independent off the M0 base
  (types do not depend on the executor merge).
- **M2 ∥ M2.5** — the auto.py characterization spike depends only on M1 + today's subprocess engine,
  not on anything M2 produces; it runs beside M2 to de-risk M3.
- **M5a ∥ M5b ∥ M5-eval** — the node library, the execute realm, and the eval spine all fan out off
  the M4 service base; a slow foundation half never serializes the value-delivery half behind it.
- **M6 ∥ M5d** — the supervisor extraction overlaps the relocation tail (M5d still gates on M6's
  relocation completing).
- **M7-capsule ∥ M7-warrant ∥ M7-docs** — the three sinks are independent projections off the
  Manifest + Ledgers; only docs gates on M6's frozen type surface.

## Strangler discipline — the invariant gated EVERY milestone

At the close of EVERY milestone `M_i`, two conditions hold simultaneously and are machine-gated (one
t0 human "go", then no human in the loop):

1. **(OLD alive)** the OLD engine (subprocess state-machine: `auto.py` + `workflow.py` +
   `_run_megaplan`) still boots and drives a throwaway 1-milestone plan end-to-end — the load-bearing
   epic that is DRIVING the build runs on the FROZEN old engine via a PINNED external venv with the
   schema validator in REPORT-ONLY mode, flag-OFF, never on the half-built new pieces.
2. **(NEW alive)** a planning-SHAPED throwaway plan runs on whatever NEW organs exist through `M_i`,
   behind a default-OFF flag, with the **behavioral-replay oracle** confirming it matches recorded
   REAL-run traces (recovery/escalate/blocked included — NOT just mock parity).

Mechanics, in DAG terms: every organ is added as `{old-path default-on, new-path default-off-behind-
flag}`; an organ's old counterpart is deleted only after **≥1 full milestone of dual-run green AND
its substrate-swap oracle passing**; **no organ swap and its old-path deletion ever land in the same
PR**. The single deletion that flips the system — drop `_BUILTIN_NAMES` + relocate planning (M6) — is
deliberately the LAST load-bearing node, the only one that removes the old path's root; the swap is
one atomic, oracle-gated cutover, so there is no multi-week broken window.

The **sole retirement authority is the behavioral-replay + substrate-swap oracle, NEVER the happy-
path parity gate** — the parity gate's honest label is "happy-path control-flow/artifact parity, NOT
drift-provably-zero," which is structurally blind to substrate swaps. Per-milestone substrate-swap
oracles where the swap happens: resume-across-versions, crash-isolation, version-skew (M3), the
two-tenant Capacity-Lease + fork-bomb + clock-skew oracle (M4), the discovered-planning full dual-run
(M6). Autonomy: every `M_i` boundary is machine-gated by parity + the substrate oracles +
ZERO-`GateRecommendation`/`STATE_*` grep gates + binder assertions; red auto-halts+reverts or runs
the bounded escalation ladder (retry ×2 → bump profile/robustness one tier → `stop_chain` +
auto-ticket), never parks on a human.

## Why this order beats each alternative

- **vs pure dependency-DAG:** the DAG is correct but brittle — one long 13-hop rope with the heaviest,
  fastest-moving knot (the ~2,500-LOC auto.py Activation/driver port) un-relocatable at position 4 and
  NO parallel branch to make progress on if it slips. This program keeps the DAG's edges intact but
  adds the one mitigation the DAG itself named — the M2.5 spike that pulls the auto.py oracle forward
  so M3 ports against a green oracle instead of discovering-and-porting at once — and front-loads M0
  so R1's first commit doesn't deadlock the live driver (a floor the DAG omits because "nothing
  technically precedes R1").
- **vs pure strangler-keep-alive:** the strangler order is the binding constraint and is adopted
  wholesale (pinned engine, report-only schema, flag-gated dual-run, deferred atomic swap). But on its
  own it would seed-early/enforce-late on R1 across ~5 milestones, inheriting a fold validated mostly
  against the happy path the parity gate can see. This program imports the risk-value insight to make
  the shadow WAL **load-bearing from M2.5** (the recovery/escalate/blocked replay corpus) so a
  shadow-fold divergence on a recovery branch is caught continuously, not discovered at the M3 flip.
- **vs pure risk-value-first:** the value lens correctly fails-fast on the foundation and parallelizes
  the value half — both adopted (M3 as the bet-resolving hinge; M5a/M5b/M5-eval fan-out). But on its
  own it front-loads the event-sourced fold onto a REAL multi-day workload (a red M2 freezes the whole
  epic) and pulls the Governor forward before a second tenant exists. This program keeps the
  fail-fast/parallelize moves but wraps them in the strangler envelope: the fold is a read-side shadow
  before authoritative (a red oracle is "don't promote," not a broken live engine), the spike de-risks
  the bet, and the Governor's cross-tenant arbiter is gated by fork-bomb + simulated-clock-skew oracles
  (synthetic adversary now, real tenant later).

In short: **DAG edges + strangler envelope + risk-value front-loading inside the envelope.**

## Open sequencing risks

1. **The R1 authority flip (M3) is the single point of maximum danger** — it removes the only
   version-isolation seam AND flips the highest-blast-radius foundation while the chain self-hosts, on
   the longest rope. *Mitigation:* the M2.5 spike pre-merges the behavioral oracle; the flip is gated
   on fold-equivalence (green since M1) AND the substrate-swap oracle (resume-across-version,
   crash-isolation); it lands behind default-OFF `MEGAPLAN_UNIFIED_DISPATCH` with the subprocess seam
   kept dormant for ≥1 dual-green milestone. *Residual:* if M3 slips, the entire back two-thirds of
   the program is blocked with no parallel branch — accepted as the irreducible cost of an
   un-relocatable apex.

2. **Seed-early/enforce-late on R1** lets the shadow WAL run report-only for several milestones, so
   the flip can inherit a fold validated mainly against happy-path traces — and the recovery/retry/
   escalate/blocked-retry branches are exactly the class that recurs in this codebase's MEMORY log
   (execute-stall, shannon-stream-stall, chain-blocked-retry, tiebreaker-downgrade). *Mitigation
   (load-bearing):* the M2.5 corpus MUST include recorded recovery/escalate/blocked traces; the
   fold-equivalence oracle runs against THAT corpus every milestone from M2.5 on; the M3 substrate-swap
   oracle must replay a recorded blocked-retry-then-resume trace across the version boundary. *Residual:*
   the structural risk the keep-alive envelope accepts in exchange for never opening a broken window.

3. **The M5-eval → M5-cal edge is non-negotiable and tempting to invert** — Calibration "feels core"
   and a reconciliation tempted to build routing early would make the self-improvement loop Goodhart
   on an unversioned float, a regression invisible by construction (SYNTHESIS Tier-S UU#2,#10). *Guard:*
   M5-cal hard-depends on M5-eval; no routing query is admitted before the versioned-judgment ledger
   exists.

4. **The Governor's cross-tenant Capacity-Lease is built before a second real tenant exists to test
   it** (pulled forward to M3). *Mitigation:* fork-bomb + simulated-clock-skew + two-tenant oracles
   stand in as a synthetic adversary now; the alternative (unbanning concurrency at M3 with no
   Governor) is a fork-bomb against the live wallet, so the synthetic-adversary cost is accepted.

5. **The M6 atomic swap is irreversible** (drop `_BUILTIN_NAMES` + relocate the self-hosting engine).
   *Mitigation:* it is the LAST load-bearing node, gated on a full discovered-planning dual-run
   milestone, with `megaplan <x>` aliases as fallback; everything underneath is proven before the
   root is removed. *Residual:* a wrong-but-green relocation could auto-merge — contained by the union
   of parity + substrate oracle + grep gates + binder assertions (a partial/wrong conversion cannot go
   green) and the `stop_chain` + auto-ticket backstop.

6. **Substrate-swap blindness of the happy-path parity gate** is a standing structural risk, not a
   per-milestone one. *Mitigation:* the behavioral-replay + substrate-swap oracle is the SOLE
   retirement authority at every seam; the parity gate is honestly labelled and never trusted as the
   swap gate.
