# Arnold build sequence — STRANGLER / KEEP-MEGAPLAN-ALIVE order

**Lens:** Optimize the build order so planning ("megaplan") keeps working AND keeps self-hosting
(drives its own construction) at every milestone. We are replacing the engine while flying it. The
ordering principle is the strangler-fig: each new organ is **stood up beside** the old path, planning
is **migrated onto it behind a flag**, parity is **proven by a machine gate + behavioral-replay
oracle**, and only THEN is the old path retired. The OLD engine must always still boot and drive a
throwaway plan; a planning-shaped plan must always run on whatever NEW pieces exist so far.

This is one of three independent orderings (the others optimize for different lenses) that will be
reconciled. It is decisive and complete: every reshaper (#1–#7) and every organ is placed, with hard
prerequisites, parallelism, the critical path, the invariant maintained, and the single biggest risk.

Grounding read: `pipeline-unification-EPIC.md`, `committed-uu/SYNTHESIS.md`,
`human-blockers/REGISTER.md`, the m1–m7 briefs, and decisively `premortem/p3-self-reference.md`,
`premortem/p4-parity-illusion.md`, `premortem/p7-sequencing.md`, `decision/migration-fit.md`.

---

## The strangler-specific reframing the other lenses miss

Three findings from the evidence base force the SHAPE of a keep-alive order, independent of the
architecture's internal dependency graph:

1. **The deliverable IS the driver (p3-self-reference).** A `megaplan chain` built on this machinery
   drives the construction of this machinery. The driver loop is in-memory bytecode at process start;
   phase subprocesses re-import from disk. The instant a milestone merges driver/state code, the system
   is *split-version by accident*. The single most dangerous moment in the entire epic is **the removal
   of the subprocess seam (Reshaper-relevant: the event-log/Activation port-in-process)** — because that
   seam is the ONLY version-isolation boundary keeping the old in-memory driver from executing
   half-migrated new code in one address space. Until the engine driving the epic is a **pinned, frozen
   external engine** and the **state-schema validator is report-only**, no irreversible swap is safe.

2. **The happy-path parity gate is structurally blind to every substrate swap (p4).** Mock-worker,
   in-process-on-both-arms SHA256 parity proves "control-flow/artifact ordering on the fixtured happy
   path" — and NOTHING about subprocess→in-process isolation, routing, timing/liveness, recovery, cost,
   or emission. Under a strangler lens this means: **the parity gate is necessary but can never be the
   thing that authorizes retiring an old path.** Retirement is authorized only by a *behavioral-replay
   oracle* (recorded real-run traces vs the new path) + a *substrate-swap oracle* (resume-across-
   versions, crash-isolation, version-skew) at the exact milestone where the swap happens.

3. **The repo moves ~80–900 commits/week through the exact blast radius (p7).** A frozen-foundation-
   for-a-quarter plan loses to drift. Therefore **every new organ lands on main as its own PR the day
   it is green**, behind a default-OFF flag, so the river's velocity tests it continuously — instead of
   discovering integration rot at the end. The strangler order is *additive-on-main*, not a long-lived
   epic branch.

These three give the keep-alive discipline its concrete spine: **pinned engine + report-only schema +
flag-gated dual-run + replay/substrate oracle as the retirement authority + land-on-main-early.**

---

## The strangler invariant (held at EVERY milestone, non-negotiable)

> At the end of every milestone, BOTH of these are green in CI, on main:
> (A) the **OLD engine** (subprocess state-machine: `auto.py` + `workflow.py` + `_run_megaplan`)
>     still boots and drives a throwaway plan end-to-end; and
> (B) a **planning-shaped plan** runs through whatever NEW organs exist so far, behind a flag, and a
>     **behavioral-replay oracle** confirms it matches recorded real-run traces (not just mock parity).
> The flag controlling which path a real run takes defaults to OLD until the milestone's
> substrate-swap oracle is green; the epic that is *driving the build* always runs with the flag OFF
> (old path), on a **pinned external engine** with the **schema validator in report-only mode**.
> An organ's old counterpart is deleted ONLY after ≥1 full milestone of dual-run green AND its
> substrate-swap oracle passing. No organ swap and its old-path deletion land in the same PR.

The dual-run/flag/parity discipline, named per step, is the column "delivers" + "rationale" below.

---

## Why this order departs from the chain.yaml/STATUS order

The committed program is M1→M2→M3→M4→M5a→M5b→M5c→M6→M5d→M7. That order is correct on the *internal
dependency graph*. Under the keep-alive lens I make four surgical adjustments — all consistent with
the human-blocker register and p7's restructure, none relitigating the architecture:

- **Split M3 into M3-spike (characterize + freeze the resume model) and M3-port** (p7 Mode A/B). The
  in-process port is THE half-swapped moment; it must execute against an already-merged behavioral
  oracle and a settled resume model, not discover them inside the apex milestone.
- **M2 parallelizes off the M1 base** (p7 #4): de-planning types/Port don't depend on the executor
  merge; serializing them is pure tax and delays Arnold value.
- **The pinned-engine + report-only-schema + dual-run harness is M1 work, not a standing afterthought.**
  The strangler boundary (edges-map 9e) is currently VIOLATED (chain.yaml points at the stale map). For
  a keep-alive order this harness is the *first* deliverable — everything else stands on it, exactly as
  Reshaper #1 (the event log) stands under the organs.
- **The event-log foundation (Reshaper #1) is seeded report-only EARLY but made authoritative LATE.**
  This is the deepest keep-alive tension: Reshaper #1 says "everything stands on the event log," but
  flipping `state.json` from authority to cache is the highest-blast-radius swap (UU#6, p3-H1). So I
  seed the WAL as a *shadow writer* early (organ exists, fold verified against `state.json` every
  milestone) and flip authority only after the in-process port (M3) has proven the fold under the real
  driver. Seed early, enforce late — the design-principle the SYNTHESIS demands.

---

## The reshapers, mapped to milestones (so none is "built last")

- **Reshaper #1 (state = fold over append-only effect-typed taint-carrying log; WAL authoritative,
  state.json a cache):** SEEDED at M1 (shadow WAL writer + fold-equivalence oracle, report-only),
  FLIPPED to authoritative at M3-port (after the in-process driver proves the fold), hardened at M4
  (transaction boundary on the Envelope). This is the one reshaper whose *seeding* and *enforcement* are
  deliberately split across the timeline — that split IS the keep-alive strategy.
- **Reshaper #2 (Activation = the scheduler primitive):** named/typed at M2 (the readiness-rule field
  alongside Port), realized as the in-process scheduler at M3-port, generalized (loop/standing/market)
  at M5a/M5b. Seeded while the only rule is "upstream done."
- **Reshaper #3 (Port runtime-enforced, taint-lattice-in-the-hash):** M2. The keystone; binder fails
  build, taint hook is a no-op-then-enforce.
- **Reshaper #4 (tree-scoped Governor + Capacity-Lease):** M4 (under the scheduler M3 built, over the
  key pool). Seeded as the flock'd budget ledger.
- **Reshaper #5 (one Ledger, recorded-into never recomputed-from):** Effect Ledger + Evaluand/Ledger
  scaffolded at M4 (emit contract + replay-class + idempotency-key), unified at M6 (kills the two
  disjoint journals, UU#14).
- **Reshaper #6 (Manifest is what the content-hash points at):** M5a (behavioral-closure hash over the
  node library), enforced at resume in M3-port's resume policy and M6's discovery.
- **Reshaper #7 (model-identity hash-pinned):** seeded at M2/M4 as a recorded provenance fact on the
  Envelope; it is a typed field, cheap to seed, expensive to retrofit (p7/UU#7).

---

## The ordering

### W0 — Pinned-engine + dual-run + report-only-schema harness (inside M1, but FIRST)
**Delivers:** the keep-alive substrate itself: (1) a pinned external megaplan engine in its own venv
from a tag, driving the epic against the working tree as target — so the driver/auto/chain/state code
that *executes* the build never changes mid-flight (p3 #1); (2) the schema-version validator lands in
**report-only / accept-missing-as-v0** mode so an old writer can never deadlock a new reader (p3 #2,
H1); (3) the standing **dual-run rig**: a CI job that boots the OLD engine on a throwaway plan AND runs
a planning-shaped plan on the new pieces, plus the **behavioral-replay oracle** (recorded real-run
traces) and **substrate-swap oracle** skeleton. (4) `--no-git-refresh` discipline: never `git pull`
merged code into the live driver process (p3 #4, H4).
**Depends on:** nothing (this is the floor).
**Parallel with:** nothing — it gates everything.
**Why first:** without it, the very first behavior-changing merge (m1 schema, p3-H1) deadlocks the
chain that is driving the build. This is the literal embodiment of "keep megaplan self-hosting."

### M1 — Foundation, hygiene, contract-checker (additive, land each as its own PR to main)
**Delivers:** CI marker-switch; executor-merge superset (override-complete); `extra="ignore"` state
back-compat + fixture corpus; pinned status/chain contracts; discovery-integrity guard; sandbox
fail-open fix; `pipelines check`/`doctor` graph linter; chain.yaml↔EPIC↔briefs anti-drift lint; **the
shadow-WAL writer seeded report-only** (Reshaper #1 seed: every event also appended to an append-only
log, fold-equivalence asserted against `state.json` every milestone, but `state.json` stays
authoritative). Each deliverable merges to main the day it's green (p7 #3 drift armor).
**Depends on:** W0 (pinned engine, so merging m1 schema can't deadlock the driver).
**Parallel with:** M2 can start off the M1 base before M1 fully merges.
**Dual-run discipline:** the contract-checker + anti-drift lint ARE the first machine gates; the WAL is
shadow-only, retiring nothing.

### M2 — De-planning types + the Port + Activation/model-identity seeds (PARALLEL branch off M1 base)
**Delivers:** `reduce`/`JoinFn`→structured data with the ZERO-`GateRecommendation`-in-SDK grep gate;
`select()`/`Reduce[T]`; the **typed Port + binder + StateDelta(CAS)** (Reshaper #3); wire the dropped
`iterate_until` predicate; **seed the Activation readiness-rule field** (Reshaper #2, while the only
rule is upstream-done) and the **model-identity provenance field** on the Envelope (Reshaper #7). Delete
the silent `v1.md` fallback — turn a silent default into a loud `build()` failure.
**Depends on:** M1 base (for the linter to enforce the grep gate); does NOT depend on the executor merge.
**Parallel with:** M1's later PRs.
**Dual-run discipline:** the Port binder runs beside the old string/state-dict plumbing; planning's
4-verdict enum moves to the planning app binding; grep gate proves zero leakage. No old path retired —
types are additive. Partial conversion merges only when grep=0 AND all consumers green together.

### M2.5 — Auto.py characterization + resume-model decision (NEW spike; gates M3-port)
**Delivers:** `test_auto_drive.py` written against TODAY's subprocess `auto.py`, merged to main as
permanent CI (the behavioral oracle p4 demands as the real safety story); a one-page written decision
on the SINGLE resume model (reconcile `_pipeline_paused_stage` vs `current_state`/`next_step`/
`resume_cursor` vs `STATE_AWAITING_HUMAN`). This is pure discovery on a cheap spike, NOT inside the apex
milestone (p7 #2).
**Depends on:** M1 (status contract pinned so the oracle has a stable surface).
**Parallel with:** M2.
**Dual-run discipline:** the oracle records the OLD engine's real behavior — it BECOMES the
behavioral-replay corpus the rest of the epic's retirements are authorized against.

### M3-port — In-process port + realized-graph + WAL-authoritative flip (THE HINGE; behind default-OFF flag)
**Delivers:** the 2-axis driver (substrate × topology); the **topology-realizer** with the
{5 robustness}×{prep,feedback}×{states}×{verdicts} parity test as a hard GATE; Activation realized as
the in-process scheduler (Reshaper #2); loop-control as a node + mandatory `max_iterations` + teardown;
state-evolution two honest values + `restorable_boundary` (fails loud under process/fan-out); the cloud
`_phase_command` shim; **the Reshaper #1 flip: WAL becomes authoritative, `state.json` becomes a
rebuilt cache** — gated on the fold-equivalence oracle (seeded since M1) staying green AND the
substrate-swap oracle (resume-across-version, crash-isolation) passing.
**Depends on:** M1 (executor merge), M2 (Port — the scheduler binds ports), M2.5 (the oracle + resume
decision), W0 (the flip is unsafe without the pinned engine + report-only-until-now schema).
**Parallel with:** nothing — this is the critical-path apex.
**Dual-run discipline (the most important in the whole epic):** lands STRICTLY behind a default-OFF
`MEGAPLAN_UNIFIED_DISPATCH` toggle. The epic driving the build runs with the toggle OFF (old subprocess
auto). The in-process path soaks on THROWAWAY plans only. The subprocess seam is NOT deleted in this PR
— it survives, dormant, behind the flag, for ≥1 milestone of dual-run green before any retirement.
**This is the single most dangerous "engine half-swapped" moment** (see risk section).

### M4 — Services + policy spine + Governor/Capacity-Lease + Effect/Evaluand Ledger scaffold
**Delivers:** `dispatch` (2 backends) with a watchdog/liveness sink written on token-progress;
`emit` (ONE contract — begins killing the two disjoint journals, Reshaper #5); `evidence`
(attestation + oracle/`run(cmd)`); config-precedence resolver; the **RecoveryPolicy** spine
(classify→{retry,escalate,halt}); the **tree-scoped Governor + flock'd Capacity-Lease** under the
scheduler / over the key pool (Reshaper #4); the **Run/Composition transaction boundary on the
Envelope** (UU#8) so durability is a property of the RUN; Effect Ledger replay-class + external
idempotency-key≠hash + compensation; the Evaluand/Ledger record (versioned attributable judgment).
**Depends on:** M3-port (the scheduler the Governor sits under; the in-process dispatch the policy
spine drives).
**Parallel with:** M5a can begin once the node-library tier metadata is stable.
**Dual-run discipline:** services run as injected backends beside the old hard-wired calls; the OLD
key-pool/cost-tracker stays live until the Capacity-Lease two-tenant oracle is green. Schema/journal
unification stays report-only.

### M5a — Node library + Manifest (Reshaper #6)
**Delivers:** formalize `patterns.py` as the composition vocabulary (provisional tier); reserve
`arnold_api_version`; **the Behavioral Identity Manifest** — content-hash the behavioral closure
(topology + step-code hashes + prompt bodies + routing-taken + ABI + dep-closure), the object the
content-hash was always meant to point at (Reshaper #6). Resume policy (from M3) now keys on the
Manifest hash.
**Depends on:** M2 (the types the nodes are typed over), M3-port (the realized graph the Manifest
hashes).
**Parallel with:** M5b prep.
**Dual-run discipline:** node library is additive; Manifest is recorded beside runs, not yet enforced
on discovery (that's M6). Nothing retired.

### M5b — Execute realm
**Delivers:** the task-DAG scheduler; F5's reducer returns app-defined outcomes (not the 4-verdict
enum); merge stays mechanical, classification moves to the reducer.
**Depends on:** M5a (nodes), M3-port (scheduler), M4 (Governor bounds the task fan-out).
**Parallel with:** —.
**Dual-run discipline:** new execute realm runs behind the same dispatch flag; old execute path
retired only after its replay oracle is green.

### M5c — Control plane (evict STATE_*; hardest)
**Delivers:** the run-outcome vocabulary `{succeeded,failed,escalated,blocked,awaiting_human}` +
`valid_targets`/`recover_targets`; the control interface trio; planning's `STATE_*` binds ONTO it
(evicted from the SDK as mechanism, exactly as the 4-verdict enum was evicted from `JoinFn`).
**Depends on:** M5b (the outcomes the control plane routes), M4 (RecoveryPolicy it auto-fires).
**Parallel with:** —.
**Dual-run discipline:** the new control interface runs beside the old `STATE_*` state machine;
override/auto split along the control/planning seam; back-compat aliases keep old transitions valid.
The grep gate now also forbids `STATE_*` as mechanism in SDK modules. This is the last and hardest
de-planning; retirement of the old state machine only after the full recovery/escalate matrix oracle
is green.

### M6 — Megaplan as a discovered module + arnold namespace + trust boundary + journal unification
**Delivers:** relocate planning, drop `_BUILTIN_NAMES`, manifest+driver+bindings+SKILL.md;
**manifest-first NON-EXECUTING discovery** + trust tier (path-derived: in-tree=trusted,
out-of-tree=quarantined) + `arnold_api_version` range check WITHOUT importing; collapse the next-step
encodings (NOW safe — M3 proved the projection); resident adopts the pieces; the CLI migration
(`arnold <verb>` umbrella + `arnold <module> <verb>`); **unify the two disjoint journals into one
Ledger** (Reshaper #5 completion, UU#14) — recorded-into, never recomputed-from.
**Depends on:** M5c (control plane de-planned so the relocated module binds, not embeds), M3-port (the
realized graph the next-step projection reads), M5a (Manifest for discovery identity), W0 (the import
seam — `a5` re-opened: discovery is the ACE surface).
**Parallel with:** M5d prep.
**Dual-run discipline:** old `_BUILTIN_NAMES={"planning"}` path stays as a fallback until discovered
planning passes a full dual-run milestone; `megaplan <x>` aliases keep resolving until the rename
trigger. **The OLD subprocess seam is finally retired here** — only after M3→M5 have run dual-green
across multiple milestones.

### M5d — Supervisor tier (after M6)
**Delivers:** general cross-run orchestration invoking general control ops (not "force-proceed" by
name); chain/epic/bakeoff re-expressed; binds onto M5c awaiting_human + auto-merge.
**Depends on:** M6 (discovered module + namespace), M3-port (process driver), M5c (control ops).
**Parallel with:** M7 docs.
**Dual-run discipline:** acceptance is a **throwaway canary epic** (≥1 dep edge, ≥1 induced failure
exercising escalate/recover) — NOT the epic driving the build. The chain supervisor + override plane
were frozen the whole epic; this is where they're finally rebuilt on the general tier.

### M7 — Builder documentation & onboarding (gated on M6)
**Delivers:** the `docs/arnold/` set + generated-from-types reference (CI drift-gated) + worked
examples + the external-builder acceptance test (ship the select-tournament from docs+scaffold alone,
grep proves zero planning vocabulary).
**Depends on:** M6 (the surface is stable only after the namespace/discovery land).
**Parallel with:** M5d.
**Dual-run discipline:** none to retire; the acceptance test is the final proof the strangle completed
— a fourth, non-planning tool ships on the same parts.

---

## Critical path

W0 → M1 → M2.5 → M3-port → M4 → M5b → M5c → M6 → M5d → M7.
(M2 parallels M1→M2.5; M5a parallels M4→M5b; M7 parallels M5d.)

The path is dominated by the **M3-port hinge**: it is the only apex/extreme milestone, it cannot move
(M4+ depend on the in-process scheduler; it depends on M1's executor + M2's Port + M2.5's oracle), and
it carries the Reshaper #1 authority flip. Everything before it is "stand the organ up beside the old
path"; everything after it is "migrate onto and retire."

---

## The single most dangerous "engine half-swapped" moment

**M3-port — the in-process scheduler flip + WAL-authoritative flip, while the chain is driving the
build.** This moment uniquely combines all three keep-alive hazards at once (p3 H1+H2, p4 #1):

- It **removes the subprocess seam** — the only version-isolation boundary. Before M3, the driver loop
  (old in-memory bytecode) and phase subprocesses (fresh disk re-import) diverge harmlessly; after M3
  they execute in ONE address space, so any half-migrated state contract between driver-version and
  phase-version that the seam used to paper over now runs live (p3 H2).
- It **flips `state.json` from authority to cache** (Reshaper #1) — the single highest-blast-radius
  change in the architecture (UU#6); a wrong fold silently corrupts in-flight runs, and the happy-path
  parity gate is structurally blind to it (p4).
- A wedged in-process worker now **hangs the whole driver** with no SIGKILL-able child (p3 H2), and if
  the unproven in-process watchdog mis-fires while driving M3 ITSELF, the driver deadlocks.

The keep-alive containment is exactly: pinned external engine (driver never runs the code it's
building), schema validator report-only until after this milestone, the toggle default-OFF so the
DRIVING chain stays on the old subprocess path while the new path soaks on throwaway plans, the WAL
flip gated on the fold-equivalence oracle (green since M1) + the substrate-swap oracle, and the
subprocess seam NOT deleted until M6 after multiple dual-green milestones.

---

## The biggest sequencing risk THIS ordering carries

**Seed-early-enforce-late on Reshaper #1 lets the shadow WAL silently rot for the ~5 milestones it
runs report-only — so the M3-port authority flip inherits a fold that was never load-bearing and was
validated only against the mock-driven happy path the parity gate can see.** My order deliberately
defers the WAL authority flip to M3 to avoid the p3-H1 deadlock, but that deferral means the fold-
equivalence oracle is asserting against `state.json` writes from the OLD driver across all the recovery/
retry/escalate/blocked-retry branches that p4 proves the happy-path gate never exercises. If the shadow
fold has a divergence on a *recovery branch* (the exact class that recurs in this codebase's memory log:
execute-stall, shannon-stream-stall, chain-blocked-retry, tiebreaker-downgrade), it stays invisible
until the flip makes the WAL authoritative under the real driver — precisely the moment a divergence
corrupts an in-flight run with no subprocess seam to contain it.

**Mitigation owned by this order:** the M2.5 behavioral-replay corpus MUST include recorded
recovery/escalate/blocked traces (not just the happy path), and the fold-equivalence oracle must run
against THAT corpus every milestone — making the shadow WAL load-bearing from M2.5 onward, not just at
the flip. The substrate-swap oracle at M3 must specifically replay a recorded blocked-retry-then-resume
trace across the version boundary. This converts the risk from "discovered at the flip" to "gated
continuously," but it is the residual structural risk the keep-alive ordering accepts in exchange for
never opening a multi-week broken window.
