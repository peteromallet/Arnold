# Interrogation — SEQUENCING UNDER FULL AMBITION

**Lens:** the 6-milestone program order (m1 foundation → m2 deplanning-types → m3 drivers/state →
m4 services → m5 extract-features → m6 megaplan-as-module). I assume we WILL do all of it; I only
ask "what order will bite, and what must be ADDED / re-sequenced / parallelized to survive at full
ambition." No scope reduction.

Grounded against current `main` (`__version__ = "0.23.0"`, 2026-05-29).

---

## The single most likely program-staller (read this first)

**The execution driver (`briefs/epic-pipeline-unification/chain.yaml`) encodes the OLD 4-milestone
plan, not the 6-milestone EPIC.** The chain lists `m1-foundation, m2-dispatch-service,
m3-planning-as-pack, m4-shared-substrate` (chain.yaml:11-33) and the EPIC itself says so:
"*re-derive briefs to these; current m1-m4 briefs + chain.yaml are stale*" (EPIC §91). The dir still
carries both generations side by side: `m2-deplanning-types.md` AND `m2-dispatch-service.md`,
`m3-drivers-state.md` AND `m3-planning-as-pack.md`, `m4-services.md` AND `m4-shared-substrate.md`.
The stale `m3-planning-as-pack` is what is now **m6**, and the stale `m2-dispatch-service` is what is
now **m4**. If this program is driven via `megaplan chain`/epic with the present chain.yaml, it will
run the wrong decomposition in the wrong order — relocating planning to a pack (old m3) *before* the
drivers/state/services it must compose exist. **Before any milestone runs, chain.yaml must be
re-derived to the 6 new briefs and the stale m2/m3/m4 files deleted or archived** — otherwise the
harness silently executes the superseded plan. This is the highest-severity, lowest-cost fix.

---

## Top bites

### BITE 1 — M5 is 4 milestones wearing one label; its internal order is the real deadlock, not its position

M5's own brief admits it: "**This is the largest milestone in the program**" and ships a
"Sub-milestone candidates" section ranking F7/F8/F5/F2 as separable (m5-extract-features.md:285-300).
The EPIC bundles eight features (F1-F8) into one milestone, but they have a hard internal dependency
spine that the single-milestone framing hides:

- **F4 complexity-tiering** is the *input contract* to **F5 execute task-DAG**: F5's batch scheduler
  resolves per-batch tier→model via `_resolve_tier_spec`/`compute_batch_complexity`
  (`execute/batch.py:79,18`), which is literally F4's resolution capability. You cannot extract F5's
  scheduler as a general `produce`+`process` piece while the tier-resolution it calls is still
  planning-shaped. **F4 must land before F5.**
- **F7 control plane** depends on **F6 human-gate** ("F7 is the operator action that mutates and
  un-halts" vs F6 "halt-and-wait", m5:148-149) AND on **F1's** gate-consequence binding (force-proceed
  reads `last_gate.recommendation` and the `gate_proceed_agent_availability_blocked` predicate,
  `override.py:63`). F7 is also the brief's own "STRONGEST" split candidate with the seam declared
  "genuinely unresolved" (m5:222-229, 289-291).
- **F8 supervisor tier** (1,820-LOC `chain/__init__.py`) imports `auto_drive` directly
  (`chain/__init__.py:65,73,918`) — i.e. it sits *on top of* the very `process`-driver outcome that
  M3 produces and that planning's relocation (M6) consumes. F8 cannot be cleanly extracted until the
  thing it drives (a single planning run) is itself a composed driver, which is M6's job.

So the real internal order is roughly **{F1,F3,F9 node-lib} → F4 → F5 → F6 → F7**, with **F8 a
standalone tier that wants M6's process-driver settled first.** Shipping M5 as one milestone forces
all eight to land or revert together on a 9,350-LOC blast radius (`auto.py` 2468 + `chain` 1820 +
`batch.py` 1529 + `override.py` 919 + `cloud/cli.py` 1432 + others). **Forces:** re-decompose M5 into
explicit ordered sub-milestones (M5a node-lib formalization F1/F3/F9; M5b F4→F5 dispatch-scheduler;
M5c F6→F7 control/human-gate — last; M5d F8 supervisor — parallelizable after M6's process driver),
each its own chain entry with its own parity oracle.

### BITE 2 — Hidden ordering deadlock: M6 needs M3's `process` driver, but M5/M6 both punt the cloud→auto coupling

M6 must pick which driver the relocated planning package declares — its own open question:
"Does the relocated planning package declare ONE driver, or compose `process` (auto's per-phase
subprocess) + `graph`?" (m6:73-75). That `process` driver is M3's deliverable (M3 §2,
m3-drivers-state.md:47-54). Fine — M3 precedes M6. **But the coupling that actually breaks is below
the waterline:** `cloud/cli.py:225` imports `_phase_command` directly from `auto.py`, and
`cloud/supervise.py:54` reaches into `chain` internals over SSH. M5 explicitly declares cloud
anti-scope ("m5 defines the boundary, does not port it", m5:185, 215, 275). M6 also does not list
cloud porting in its 5 locked items — it only has resident adoption (m6:54-59). **So nobody owns
re-pointing `cloud/cli.py::_phase_command` and `cloud/supervise.py` off `auto.py`/`chain` internals
when M6 dissolves `auto.py` into the process driver and relocates planning.** The EPIC's own
cross-cutting list names "the 2nd cloud→auto coupling `cloud/cli.py::_phase_command`" as a guardrail
(EPIC §124) but no milestone is assigned it. When M6 drops `_BUILTIN_NAMES` and moves
`compile_planning_pipeline`, cloud's direct `from megaplan.auto import _phase_command` and the SSH
string in supervise.py break, and they are 1432 + 775 LOC of out-of-band integration with no parity
oracle. **Forces:** add an explicit cloud-recoupling work item — either a late sub-milestone after M6
or a guarded shim landed in M3 — and a cloud smoke oracle in the chain; do NOT leave it implicit
between two milestones that both say "not me."

### BITE 3 — M2 must finish the type decoupling completely or M3/M4/M5 all build on a leaky enum

M2 moves the 4-verdict `GateRecommendation` out of the SDK types. But that enum is woven through
**six** `_pipeline` modules today: `types.py`, `pattern_types.py`, `pattern_topology.py`,
`pattern_joins.py`, `subloop.py`, `stages/tiebreaker.py` (verified: `grep -rln GateRecommendation`).
`PromoteFn` returns it (`pattern_types.py:16`), `JoinFn` is typed around `StepResult` but the smoking
gun is `PromoteFn → GateRecommendation` and the join collation. Every downstream milestone consumes
these types: M3's gate-consequence map must NOT "re-import `GateRecommendation` semantics into the
driver layer" (m3:78-80); M4's dispatch result shape and M5's `fan_out`/`reduce` ALL sit on the M2
types. **If M2 leaves even one of the six modules half-converted, M3 and M4 inherit a type that
silently re-planning-izes the driver and dispatch layers**, and the leak is invisible until M5's
non-planning acceptance toy tries to `reduce`/`select` and is forced to inherit the verdict enum (the
exact failure the EPIC calls "a trap, not a teacher", §88). **Forces:** M2's done-criteria must assert
**zero** `GateRecommendation` references survive in the SDK-side modules (a grep gate in CI, not a
spot check), and `PromoteFn`/`JoinFn`/`Reduce[T]` must be re-typed to structured data in the SAME
milestone — partial conversion is worse than none because it hides the coupling behind a passing
parity gate.

### BITE 4 — Big-bang on a fast-moving main: the program's duration exceeds the rewrite-target's churn rate

`auto.py` alone took **44 commits over 43 days** and is 2,468 LOC; it is still being edited (last
touch 2026-05-28, the day before the EPIC was consolidated). The program's heaviest extraction targets
are exactly the hottest files: `auto.py` (process driver, M3), `chain/__init__.py` 1820 LOC + `bakeoff`
(supervisor, M5/F8), `batch.py` 1529 LOC (execute-DAG, M5/F5), `override.py` 919 LOC (control plane,
M5/F7). A 6-milestone "thorough/high" program is multi-month; over that window main will keep landing
the kind of fixes the MEMORY index documents (shannon staleness, gate tiebreaker downgrade, execute
stall) — many in these exact files. The chain runs each milestone on a worktree off main
(chain.yaml `base_branch: main`, `merge_policy: review`), so every milestone PR rebases onto a moved
target, and the parity gate is honestly labelled as **happy-path control-flow/artifact parity only**
(EPIC §128, M1 W6) — it will NOT catch a behavioral regression that lands on main *during* an
extraction. **Forces:** (a) the program needs a continuously-running parity/characterization oracle on
main, not just per-milestone; (b) the hottest files (auto.py, batch.py, override.py, chain) should be
**feature-frozen on main** for the duration of the milestone that extracts them, or extracted
earliest-possible before more churn accretes; (c) sequence the process-driver extraction (M3) as early
as the dependencies allow precisely because `auto.py` is the fastest-moving target and every extra week
adds commits to re-reconcile.

---

## Single biggest abstraction/complication/simplification through this lens

(See structured fields.)
