# Pre-launch verification — CROSS-BRIEF SEAM CONSISTENCY

**Vantage:** the 14 briefs (m0,m1,m2,m2.5,m3,m4,m5a,m5b,m5-eval,m5-cal,m5c,m5d,m6,m7) were
written in parallel. This audit checks whether their HANDOFF CONTRACTS actually align: do the
shapes one milestone *produces* match what its consumer *consumes*, and does the depends_on graph
encoded in prose have a real producer for every "depends on Mx's Y".

Grounded against `main` 2026-05-29. Builds on the already-confirmed class ("the plan assumes
harness/megaplan features that don't exist"): the autonomy ladder in chain.yaml is silently
dropped by `chain/__init__.py` (only `abort:` is read; `retry:`/`escalate:` ladder keys and
`bump_profile`/`bump_robustness`/`require_clean_base` are unimplemented). The findings below are
the *seam* analogue of that class.

---

## THE STRUCTURAL FINDING (gates the autonomy story for the whole epic)

### S1 — The depends_on graph is PROSE ONLY; chain.yaml + the harness encode pure LINEAR order, no edges, no parallelism. [blocks-launch-as-described]

Every brief carries a `Depends_on:` line and PROGRAM.md draws a DAG with explicit parallel tracks
(`M5a ∥ M5b ∥ M5-eval`, `M6 ∥ M5d`, `M2 ∥ M2.5`, the three M7 sinks ∥). The acceptance gates lean
on these edges being *enforced* — e.g. "M5-cal start is machine-gated on M5-eval's CI being green"
(m5-cal Constraints; m5-eval Done #7: "a CI assertion proves no calibration code references the
Ledger before this milestone's gates pass").

**Evidence:**
- `.megaplan/briefs/epic-pipeline-unification/chain.yaml` has **NO `depends_on` key** (grep: zero hits).
- `megaplan/chain/__init__.py:171` `MilestoneSpec` fields are
  `{label, idea, branch, profile, robustness, vendor, depth, critic, deepseek_provider, with_prep,
  with_feedback, prep_clarify, prep_direction, phase_model, bakeoff, notes}` — **no `depends_on`,
  no `parallel`, no `gate_on`**. `grep depends_on|parallel megaplan/chain/__init__.py` → zero.
- The chain runs milestones strictly in list order, one at a time. There is no machinery to
  express "M5-eval gates M5-cal" beyond *putting m5-eval before m5-cal in the list* (which the
  YAML does at lines 66/72 — correct), and there is no machinery to express the ∥ fan-outs at all.

**Why it matters at the seam level:** the program's most order-sensitive edge —
M5-eval → M5-cal (PROGRAM risk #3, "non-negotiable, treated as non-negotiable by all three
lenses") — is enforced ONLY by list adjacency, not by a green-gate. If m5-eval merges red-but-not-
halted (and the autonomy ladder that would halt it is itself dropped — the confirmed class), m5-cal
starts anyway and Goodharts on a bare float exactly as the brief warns. The "CI assertion proves no
calibration code references the Ledger before the gate passes" (m5-eval Done #7) is a *test the
milestone must build*, not a chain-level gate — it cannot exist until m5-eval runs, so it cannot
gate m5-cal's *start*.

**Fix:** Either (a) state explicitly in the EPIC + each brief that depends_on is enforced SOLELY by
linear chain order + the per-milestone strangler gate (and drop all ∥ language from the runnable
artifact, since the harness serializes everything anyway — the parallelism is a human-planning
fiction the chain cannot honor), or (b) add a real `depends_on`/gate field to `MilestoneSpec` +
the chain driver as an M1/W8 deliverable (it is not currently in M1 scope — M1/W8 only lints the
chain↔EPIC↔briefs *triple* for 1:1 label/path mapping, NOT a dependency DAG). Until one of these
lands, every "gated on Mx green" claim across m5-cal, m5-eval, m6, m5d is aspirational.

---

## CONTRACT-SHAPE SEAMS (writer-flagged + newly found)

### S2 — M4 Evaluand scaffold record shape vs M5-eval consumption: ALIGNED, with one field-name drift. [minor]

Writer-flagged seam (M5-eval ↔ M4 Evaluand record shape). Verdict: substantively consistent.
- M4 ships `{judge-version, rubric-version, input-set-hash, score, recorded_at}` (m4 Outcome #7,
  Done #10).
- M5-eval extends to `{piece-version, judge-version, rubric-version, input-set-hash, score,
  provenance, taint, recorded_at}` (m5-eval Scope #2) — a pure superset (adds `piece-version`,
  `provenance`, `taint`). Additive, frozen-types-compatible. Good.

**Drift:** M4 Done #10 calls it `{judge-version, rubric-version, input-set-hash, score}`; m5-cal
Scope #1 cites "the M5-eval / m4 `:30` record shape `{judge-version, rubric-version, input-set-hash,
score}`" — i.e. m5-cal consumes the M4 shape, NOT the M5-eval superset, even though m5-cal runs
AFTER m5-eval and m5-eval is its hard prerequisite. m5-cal's `CapabilityClaim.outcome:EvaluandRef`
should reference the *attributable* M5-eval record (with provenance/taint, which m5-cal's
taint-aware aggregation in Scope #6 actually NEEDS — it reads `taint_class` to decide shared-vs-
tenant-local). m5-cal cites the pre-attribution M4 shape as its outcome source. Reconcile: m5-cal's
EvaluandRef must point at the M5-eval attribution tuple (which carries the taint m5-cal's Scope #6
reads), not the M4 scaffold tuple.

**Fix:** In m5-cal Scope #1, change the EvaluandRef target from "m4 `:30` record shape" to the
M5-eval attributable Evaluand `{piece-version, judge-version, rubric-version, input-set-hash, score,
provenance, taint, recorded_at}`, and note that the `taint_class` of Scope #6 derives from that
record's `taint` field (so there is one taint source, not two).

### S3 — M2.5 ↔ M3 `_pipeline_paused_stage`: M2.5 looks for it in the WRONG module. [must-fix-in-M0/M1]

Writer-flagged seam. M2.5 Scope #4 says: "`_pipeline_paused_stage` does NOT appear in `auto.py`
today — locate its real home (`_core/workflow.py` / state-machine) and reconcile it in the
[resume-model] decision."

**Evidence (actual home):**
- `megaplan/_pipeline/run_cli.py:267` — `paused_stage = existing_state.get("_pipeline_paused_stage")`
- `megaplan/_pipeline/steps/human_gate.py:94` — writes `"_pipeline_paused_stage": self.name`
- `megaplan/cli/__init__.py:951` — `state.pop("_pipeline_paused_stage", None)`

It lives in the **`_pipeline` in-process runner + the human_gate step + the CLI**, NOT in
`_core/workflow.py`. M2.5's guess sends the resume-model decision author to the wrong file; the
encoding is owned by the in-process pipeline path (which M3's in-process driver / M5c's F6
clarify-node both touch). This matters because the resume-model decision (M2.5 deliverable) is the
SINGLE input M3's resume policy and M5a's Manifest-keyed resume both build on (PROGRAM
M2.5→M3→M5a). A decision written against the wrong home will mis-specify which writer M3 must
reconcile. Note also: M5c F6 cites the *same* resume cursor via `awaiting_user.json` /
`_pipeline/resume.py:104` / `_pipeline/run_cli.py:271` — so the real reconciliation is three-way
(`_pipeline_paused_stage` + `resume_cursor`/`current_state` + `awaiting_user.json`), and M2.5's
"three encodings" list (`_pipeline_paused_stage` vs `current_state`/`next_step`/`resume_cursor` vs
`STATE_AWAITING_HUMAN`) does not name the `awaiting_user.json` cursor that M5c F6 depends on.

**Fix:** Correct M2.5 Scope #4 + Locked-decisions to cite the real home
(`_pipeline/run_cli.py:267`, `steps/human_gate.py:94`, `cli/__init__.py:951`), and add the
`awaiting_user.json` cursor (`_pipeline/executor.py:264,376` → `resume.py:104` → `run_cli.py:271`)
as a fourth encoding to reconcile, since M5c F6's pause/resume hook consumes it.

### S4 — M5-cal ↔ M5-eval: the gate edge is stated both directions but the harness can't enforce "start gated on green". [fix-before-its-milestone]

Writer-flagged seam. The vocabulary is consistent (m5-cal reads EvaluandRefs; m5-eval forbids bare
floats via the same grep-gate pattern). The *enforcement* is the problem, and it is the S1 problem
in concrete form:
- m5-eval Done #7: "M5-cal's start is machine-gated on #2 (grep) + #6 (oracle) green; a CI
  assertion proves no calibration/routing-query code references the Ledger before this milestone's
  gates pass."
- m5-cal Constraints: "Gate the start on M5-eval's CI being green (REGISTER X3: dependency
  readiness = test result, no human scheduler)."

But there is no chain-level "start gated on prior milestone's CI" mechanism (S1). The CI assertion
m5-eval ships can forbid m5-cal *code* from referencing the Ledger early (a grep over the m5-cal
module) — but that only fires once m5-cal is being built, and nothing stops the chain from
*starting* m5-cal if m5-eval's gate went red without halting (the dropped ladder). So the
"non-negotiable edge" is enforced by (a) list order and (b) a grep that lives inside the very
milestone it is supposed to gate.

**Fix:** Make the guard a STANDING CI test that lands in m5-eval and runs on every PR thereafter
(not a one-shot at m5-cal start): "if `megaplan/calibration/` exists AND m5-eval's oracle marker is
not green, fail CI." Tie it to the M0 strangler-gate verdict (W6) so a red m5-eval oracle blocks
the m5-cal milestone's *merge*, the one seam the harness can actually enforce. State that the
chain's linear order is the *start* gate and the standing CI test is the *merge* gate.

### S5 — M2 Port shape vs M3 Conveyance/Activation: ALIGNED (taint reuse is explicit). [no-issue / confirms intent]

M3 Scope explicitly reuses M2's taint lattice ("reuses the M2 taint lattice (do NOT invent taint
twice)", Locked decisions; PROGRAM Conveyance fold-in "reusing M2's taint lattice, never inventing
it twice"). M2 ships taint-in-the-content-hash (R3, spatial); M3 ships the RunEnvelope taint
joined-at-merge (temporal). Activation identity = `hash(node + input-Ports + profile)` consumes M2
Ports. M2 anti-scope explicitly defers Conveyance/Work-Envelope to M3. The producer/consumer shapes
match; this seam is clean. (Watch item, not a finding: M2 ships taint as a "no-op-propagating
field" seed; M3 makes propagation real — confirm M3's join is additive over M2's seeded field, not
a re-typing, to keep frozen-types discipline. Both briefs say additive.)

### S6 — M4 RecoveryPolicy target-vocabulary vs M5b/M5c/M5d run-outcome vocabulary: ALIGNED by design (target-agnostic), but the M5b→M5c handoff TYPE is under-specified. [fix-before-its-milestone]

The intended chain: M4 `classify(error) -> {retry_fresh|retry_transient|escalate|halt(kind)}` with
`halt(kind)`/`escalate` **target-agnostic, no `STATE_*`** (M4 Locked; "M5c owns the control
vocabulary"). M5b's F5 reducer returns a typed `Reduce[T]`, planning binding maps to `phase_outcome`
∈ `{success, blocked_by_quality, blocked_by_prereq, timeout}`. M5c defines the run-outcome enum
`{succeeded, failed, escalated, blocked, awaiting_human}` and "maps execute outcomes into" it
(PROGRAM M5c depends_on M5b). M5d branches on the M5c `blocked` run-OUTCOME.

The seam works conceptually — each layer stays in its own vocabulary and the next maps it. BUT the
*type* M5b hands M5c is specified only as "a typed `Reduce[T]`" (m5b Open-Q#2: "M5b defines the
reducer's return TYPE so M5c can consume it without F5 re-importing `STATE_BLOCKED`"). m5b does NOT
name that type, and m5c does NOT cite consuming an M5b type — m5c maps from planning's `STATE_*`
literals directly (m5c F7 binding). So the declared handoff ("M5b defines the type M5c consumes")
has no concrete contract in either brief: m5b says "I define a type for M5c," m5c says "I map from
planning STATE_*." The two phase-outcome → run-outcome mappings
(`{success,blocked_by_quality,blocked_by_prereq,timeout}` → `{succeeded,failed,escalated,blocked,
awaiting_human}`) are never written down in either brief.

**Fix:** Name the M5b reducer return type concretely in m5b (e.g. `BatchOutcome[T]` / the frozen
`Reduce[T]` instance) and have m5c cite it as the input its planning binding maps to the run-outcome
enum. Write the `phase_outcome → run_outcome` mapping table in m5c (it is 4→5 and not obviously
total — e.g. where does `timeout` go: `failed` or `escalated`? where does `blocked_by_prereq` go vs
`blocked_by_quality`?). This is exactly the silent-downgrade class MEMORY flags
(`gate_tiebreaker_downgrade`).

### S7 — M5c control trio name drift: `read_valid_targets` (interface) vs `valid_targets` (projection) used interchangeably by M5d. [minor]

M5c defines TWO things with near-identical names:
- the projection functions `valid_targets(state)` / `recover_targets(state)` (m5c Outcome #2), and
- the control-interface trio `(read_valid_targets, apply_transition, synthesize_artifacts)`
  (m5c Outcome #3).

M5d invokes both names as if they were one: "resolved through `read_valid_targets(run_state)` →
`apply_transition(target)`" (m5d Scope B) AND "the chain reads `valid_targets(run_state)` and calls
`apply_transition(target)`" (m5d Scope C). PROGRAM.md repeats both (`valid_targets(state)` at :256,
`read_valid_targets` at :257). A consumer (M5d) cannot bind against an interface whose forward-read
method has two names. Trivial to fix but it is a real contract ambiguity at the M5c→M5d seam — M5d
is the *only external consumer* of the M5c interface, so the one place the name must be exact is the
one place it drifts.

**Fix:** Pick one name in m5c (recommend `read_valid_targets` as the interface method, with
`valid_targets(state)` being its planning-binding implementation) and make m5d + PROGRAM cite that
single name.

### S8 — M5d depends on M5c's `awaiting_human` for PR-merge, but M5c F6 ships `awaiting_human` as halt-and-wait while M5d needs auto-merge-on-green: the AUTO-RESOLVE actor is unowned. [fix-before-its-milestone]

M5d Open-Q#3 RESOLVED: "the PR-merge wait binds onto M5c's `awaiting_human` outcome + F6 auto-merge
— green CI+gates → supervisor auto-merges (`gh`); red → auto-escalate." But M5c F6 is explicitly
"**halt-and-wait**" (m5c F6: "F6 is halt-and-wait; F7 is the operator action that mutates and
un-halts"). M5c ships `awaiting_human` as a *pausable terminal* + a resume cursor; it does NOT ship
an auto-merger. m5c F6's auto-resolution story (REGISTER row "STATE_AWAITING_PR_MERGE → auto-merge
via gh") is in the REGISTER but neither m5c nor m5d *owns building* the `gh` auto-merge actor: m5c
says "F6 halts and persists a cursor," m5d says "binds onto F6 auto-merge" — but "F6 auto-merge"
is not an m5c deliverable (m5c F6 Done criteria are clarify-node + pause/resume cursor round-trip,
no merger). The auto-merge-on-green actor that turns `awaiting_human` from a park into an autonomous
proceed is in nobody's Scope. This is a human-blocker leak: without that actor, PR-merge `awaiting_
human` is a real human park (the exact thing REGISTER row 73 says is converted).

**Fix:** Assign the `gh` auto-merge-on-green actor to a concrete milestone. It belongs in M5d
(supervisor tier — it is run-granularity orchestration over the PR-merge choreography
`chain/__init__.py:1318-1514`), but m5d must STATE it builds the auto-merger, not "binds onto F6
auto-merge" (which doesn't exist in m5c). Update m5c F6 to clarify it ships only the
halt+cursor+resume primitive, and the auto-resolve actor (brief/prep-research → stronger model →
auto-merge) is M5d's binding.

### S9 — M5a `PromoteFn → "the M2 routing-key type"` but M2 never defines a "routing-key type" by that name. [must-fix-in-M0/M1 (M2 scope)]

M5a Open-Q#2 (Locked): "`PromoteFn` → returns the **M2 routing-key type** (re-type against the real
M2 surface name, not a placeholder)." M5a Scope: "Re-type `PromoteFn` to return the M2 **routing-key**
type." But **M2's brief never defines a type called "routing-key"**. M2 ships `ReduceResult`/
`Aggregate[T]`, `SelectionResult`, `StateDelta`, `Port`, and moves the 4-verdict mapping to a
planning binding `planning_reduce(aggregate) -> GateRecommendation`. There is no `RoutingKey` type
in M2's Scope/Locked/Touchpoints. M5a is depending on an M2 producer ("the M2 routing-key type")
that M2 does not emit under that name. M5-eval inherits the ambiguity (it reuses M5a's vocabulary).
This is the seam analogue of the confirmed harness-feature-that-doesn't-exist class: a downstream
brief names an upstream artifact that the upstream brief does not actually define.

**Fix:** Either (a) add an explicit `RoutingKey` (or rename — m5c F7 talks about "routing key" too,
m5a F3 "promote the result back to a routing key") type to M2's Scope/Locked/Touchpoints so the
producer exists, or (b) have M5a/M5c/M5-eval cite the concrete M2 type that plays this role (likely
`SelectionResult.winner` or a label off `ReduceResult`). As written, M5a's done-criterion "PromoteFn
returns structured M2 types (routing key / Reduce[T])" cannot be satisfied because one of the two
named types does not exist upstream.

### S10 — Three "kill the read-time substring vendor classification" owners (M4, M5-eval, M5-cal) — overlapping claims on `cost.py:370`/`cost.py:23` with no clean baton. [minor]

`observability/cost.py`'s substring vendor classifier (`_classify_vendor` cost.py:23, the read-time
classify at cost.py:370) is claimed as "kill it" by THREE briefs:
- M4 Scope #7: "Kill the read-time substring vendor classification (`cost.py` classifies vendor by
  substring — UU#14)."
- M5-eval Touchpoints anti-pattern: "`observability/cost.py:370` (read-time vendor-substring
  classification — the comparison must be a join, never a heuristic re-derivation)."
- M5-cal Touchpoints: "`cost.py:23,71-118` ... kill the read-time substring `_classify_vendor`
  reliance once the Ledger is the source (report-only here, retired with R5 at M6 per m4 §7)."

M6 Scope #5 (R7 load-bearing) is where it actually retires. The drift: M4 says "kill," m5-eval says
"must be a join, never substring," m5-cal says "report-only here, retired at M6," M6 says "R7 made
load-bearing." Whether `_classify_vendor` is *removed* at M4 or only *shadowed and removed at M6* is
stated inconsistently (M4 "kill" vs m5-cal "report-only here, retired at M6"). Per strangler
discipline the M6 reading is correct (no deletion before the dual-run oracle), so M4's "kill" is the
overstatement.

**Fix:** Align the verbs: M4 *stops READING from* the substring classifier on the new path (the
one-Ledger emits lineage), but the old classifier stays live until M6 retires it (strangler). Change
M4 Scope #7 "Kill" → "stop the new path reading the substring classifier; the old read stays live,
retired at M6." This is consistent with every brief's own strangler section; only the verb drifts.

---

## SEAMS CHECKED AND FOUND CONSISTENT (no action)

- **M1 grep-gate scaffold → M2/M5a/M5b/M5-eval/M5c grep gates**: M1 ships the
  ZERO-`GateRecommendation` ratcheting scaffold (count-and-forbid-growth); M2 drives it to zero in
  6 named SDK modules; M5a adds `pattern_joins.py`+`pattern_types.py` to scope; M5b adds
  `_PHASE_OUTCOMES`/`STATE_BLOCKED`; M5-eval adds bare-float; M5c adds `STATE_*`. Each is an
  additive mirror of the same pattern. Consistent escalation, no contradiction.
- **M3 realized-graph `predecessors()` → M5c `recover_targets` → M6 next-step collapse**: M3 builds
  `build_topology`/`predecessors()`; M5c consumes it for `recover_targets` (no 4th persisted copy);
  M6 collapses all three next-step encodings onto it. The producer (M3) and both consumers (M5c,
  M6) cite the same single source. Clean.
- **M5a Behavioral Identity Manifest → M3 resume keys on it → M6 discovery identity → M7-capsule
  Definition / M7-warrant rationale anchor**: the Manifest hash is produced once (M5a R6) and every
  downstream consumer (M3 resume, M6 discovery, M7 capsule/warrant) references the same hash, with
  M7 explicitly "no fourth identity string." Clean. (Note the back-edge: M5a depends on M3 for the
  realized graph it hashes, AND M3 resume depends on M5a's Manifest — handled by M5a landing the
  Manifest behind M3's existing default-OFF flag, m5a Open-Q#4. The circular dep is real but the
  briefs resolve it by ordering M5a after M3 and gating behind M3's flag.)
- **M4 one-Ledger `EventSink.emit` join-key → M5-eval / M5-cal / M6 journal unification**: M4 lands
  the shared schema + join key (report-only); M5-eval/M5-cal ride it (no new journal); M6 flips it
  load-bearing. Each downstream brief explicitly says "no new journal, rides M4's R5." Clean.
- **Robustness/profile vocabulary**: chain.yaml uses `thorough`/`extreme` (valid —
  `ROBUSTNESS_LEVELS = ('bare','light','full','thorough','extreme')`) and profiles `apex`/`premium`
  (both present in `megaplan/profiles`). The chain.yaml parses; not a false seam.

---

## Bootstrapping-circularity note (reinforces the confirmed class)

The depends_on graph (S1) compounds the confirmed autonomy-ladder gap: the chain needs the very
machinery the milestones build. M5c builds the run-outcome vocabulary + control interface that the
*autonomy ladder* (retry/escalate/halt) is supposed to drive — but the chain runs on the FROZEN M0
engine (m0/m3 "epic runs the toggle OFF on the pinned engine"), so the chain driving the build uses
the OLD `auto.py`/`chain` autonomy, which (confirmed) ignores the ladder keys. So even after M5c/M4
build a real `classify→{retry,escalate,halt}` spine, the epic that is DRIVING the build never uses
it — it is the pinned old engine whose `on_failure` reads only `abort:`. The autonomy guarantees the
briefs lean on are built by the epic but cannot govern the epic. This is correct-by-strangler-design
(don't self-host the half-built engine) but it means the "zero human blockers" guarantee for the
BUILD rests entirely on the OLD engine's behavior, which is the one the confirmed finding shows drops
the ladder to `stop_chain`. Net: at every red gate the build halts on a human (stop_chain), exactly
as the confirmed finding states — and none of the 14 milestones can fix that for the build itself,
because they run inside it on the frozen engine, not as it.
