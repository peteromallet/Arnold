# M4: Suspension-Aware Composition

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Make the `status = suspended` discriminant (already frozen into the type in m0a) actually behave when results compose. The edge hunt falsified the "human-seam and composition fall out free" claim: today `SubloopStep` (`_pipeline/subloop.py:23-30, 83-105`) promotes ONLY a `GateRecommendation`, the child result never composes up, and it NEVER checks `halt_reason`, so a suspended child is silently treated as completed. There is no compose/reduce for `ContractResult` at all (joins reduce recommendations only, `pattern_joins.py:17-86`).

This milestone makes composition suspension-aware: subloop and fan-out check `halt_reason` and propagate a suspended child UP rather than auto-completing it, and the contract DEFINES how `ContractResult`s compose/reduce across fan-out and subloop. This is the foundation HOOK that `human_review` and resume later plug into — the proof the primitive generalizes.

`Suspension` is now the typed INTERACTION ENVELOPE defined in m0a (`kind`/`awaitable`, `prompt`, `display_refs[]`, `resume_input_schema`, `resume_cursor`, `thread_ref`, `actor`, `deadline`/`on_timeout`/`default_action`); m4 CONSUMES it and does NOT redefine it.

## Scope

IN:

- Make `SubloopStep` (`_pipeline/subloop.py:23-30, 83-105`) check the child `ContractResult.status` / `halt_reason` and propagate `status = suspended` UP instead of silently completing the parent.
- Make fan-out / join composition (`pattern_joins.py:17-86`, which today reduces recommendations only) compose child `ContractResult`s, propagating a suspended child to the parent result.
- DEFINE the canonical compose/reduce semantics for `ContractResult` across fan-out and subloop as a status lattice `completed < suspended < failed` with MAX-WINS reduction. Critically, a `failed` parent STILL carries `pending_suspensions` — a suspended child's cursor is NEVER dropped just because a sibling failed.
- Carry the `Suspension` interaction envelope (the typed shape from m0a — `kind`/`awaitable`, `prompt`, `display_refs[]`, `resume_input_schema`, `resume_cursor`, `thread_ref`, `actor`, `deadline`/`on_timeout`/`default_action`) up through composition; m4 consumes it, does not redefine it. Multiple suspended children form a COMPOSITE suspension group: the v1 barrier blocks on ALL children; resume supports both targeted (one child) and batch (all) answers; the composite cursor is the source of truth and survives process exit.
- Keep the v1 status lattice (`completed < suspended < failed`, max-wins) + the barrier as the BUILT DEFAULT.
- DESIGN (do NOT build) two DEFERRED EXTENSION POINTS — design the seam so they slot in later without a contract migration; the v1 default ships:
  - (i) SCOPED suspension propagation: a child incident/branch flow that suspends must NOT auto-lift the whole (streaming) parent to suspended. The v1 barrier/max-wins lattice is the DEFAULT; scoping is the EXTENSION (a real bug to avoid for a streaming supervisor with a suspending child branch). Leave the seam where a scope boundary could intercept propagation; do not implement scoping.
  - (ii) Policy-driven result-reduce `{quorum | best-effort | budget | saturation}` as a PLUGGABLE policy OVER the default lattice reduce. Make the reduce a policy slot; ship only the v1 max-wins/barrier default behind it; do not build the alternate policies.
- `SubloopStep` maps a child `suspended` / `awaiting_user` → parent `suspended` BEFORE the legacy `GateRecommendation` promote, so a suspended child is never lost to the existing promote path.
- Tests: a suspended child in a subloop suspends the parent (no longer auto-completes); a fan-out with one suspended branch yields a suspended parent; an all-completed fan-out reduces to completed; a failed child reduces per the lattice; a MIXED failed+suspended fan-out yields a failed parent that STILL carries the suspended child's `pending_suspensions` (cursor not dropped); targeted and batch resume both work; the composite cursor persists across a process restart.

OUT:

- The `human_review` verb itself, resume UX/CLI, and who-answers routing — these are FEATURES that plug into this suspension primitive, not foundation; m4 provides the hook, not the human verb.
- Producing suspended results from workers (m3 emits `status`; m4 is about PROPAGATION through composition).
- Migration of any IO site (m5/m6).
- Authoring-API enforcement (m7).
- Changes to the m0a type (the `status` enum and `Suspension` interaction-envelope shape are already frozen there; m4 consumes, does not redefine).
- BUILDING the two deferred extension points: SCOPED suspension propagation and the alternate result-reduce policies `{quorum|best-effort|budget|saturation}`. m4 designs the seam (a scope-boundary interception point; a pluggable reduce-policy slot) and ships ONLY the v1 lattice + barrier default; the extensions are NOT built.

## Locked Decisions

- The `status` discriminant `{completed | suspended | failed}` and the `Suspension` interaction-envelope shape already live in m0a; m4 makes composition AWARE of them and CONSUMES the envelope, it does not redefine them.
- The v1 status lattice (`completed < suspended < failed`, max-wins) + barrier is the BUILT DEFAULT. Two extension points are DESIGNED but NOT built: (i) SCOPED suspension propagation — a suspending child incident/branch must NOT auto-lift a streaming parent to suspended; the barrier/max-wins lattice is the default, scoping is the extension; (ii) policy-driven result-reduce `{quorum|best-effort|budget|saturation}` as a pluggable policy OVER the default. Design the seam; ship only the default.
- Composition is suspension-aware: a parent propagates a suspended child UP and NEVER auto-completes it (the corrected non-free seam).
- The contract DEFINES how `ContractResult`s compose/reduce across fan-out and subloop — this is part of the foundation, not left implicit. The reduce is a status lattice `completed < suspended < failed` with MAX-WINS.
- A `failed` parent STILL carries `pending_suspensions` — a suspended child's cursor is NEVER dropped because a sibling failed (the load-bearing invariant: always preserve a suspended cursor in a mixed failed+suspended reduce).
- Multiple suspended children form a COMPOSITE suspension group; the v1 barrier blocks on ALL children; resume supports targeted + batch; the composite cursor is the source of truth and survives process exit.
- `SubloopStep` maps a child `suspended` / `awaiting_user` → parent `suspended` BEFORE the legacy `GateRecommendation` promote.
- `human_review`, resume UX, and routing are features that plug INTO this primitive; the foundation provides the hook, it does not assume the human seam is free.

## Open Questions

- Whether subloop and fan-out share one compose/reduce implementation or need distinct reducers behind the same defined semantics.
- How a propagated suspension interacts with the existing `next="halt"` + `state_patch={"_pipeline_paused": True}` side-channel (`_pipeline/executor.py:262`) and `awaiting_user.json` during the transition — bridge or replace.
- Where the parent's formed `Suspension` is persisted so resume (a later feature) can pick it up.

## Constraints

- A suspended child must NEVER be observable as completed at the parent — the silent-completion bug is the regression target.
- The compose/reduce semantics must be deterministic and total over all status combinations.
- Existing non-suspending subloop/fan-out behavior (all-completed reductions, recommendation joins) must be preserved.
- Must not modify the m0a type.
- Bases on m0a (status/Suspension) and m2 (typed `StepResult` payload); m3's worker-emitted status is the producer side this consumes.

## Done Criteria

1. `SubloopStep` checks the child `status`/`halt_reason` and propagates `status = suspended` up; the silently-completed-suspended-child bug is reproduced and no longer occurs (regression test).
2. Fan-out/join composition composes child `ContractResult`s; a fan-out with one suspended branch yields a suspended parent (test).
3. Canonical compose/reduce semantics for `ContractResult` are defined and documented, total over `completed`/`suspended`/`failed` combinations, and covered by tests.
4. A suspended subtree surfaces a single resumable `Suspension` at the parent (the m0a interaction envelope — carrying at least `kind`/`awaitable`, `prompt`, `display_refs[]`, `resume_input_schema`, `resume_cursor`, `thread_ref`, `actor`); a test inspects the propagated envelope; m4 consumes the m0a shape without redefining it.
5. An all-completed fan-out still reduces to completed and existing recommendation joins still work (no regression).
6. The reduce is the lattice `completed < suspended < failed` (max-wins) and a `failed` parent STILL carries the suspended child's `pending_suspensions`: in a mixed failed+suspended reduce NO suspended child cursor is ever lost; a regression test proves the cursor survives the failed sibling.
7. Resume works for both targeted (one child) and batch (all) answers against a composite suspension group; tests prove each by feeding a PROGRAMMATIC/SIMULATED resume answer (a fixture matching `resume_input_schema`) — the suspend→resume cycle is driven entirely by test fixtures and NEVER waits on a real human, so the path runs autonomously to completion.
8. The composite cursor is the source of truth and persists across a process restart; a test kills/reloads the process and resumes from the persisted composite cursor.
9. `SubloopStep` maps child `suspended`/`awaiting_user` → parent `suspended` BEFORE the legacy `GateRecommendation` promote; a test proves the mapping precedes the promote so no suspended child is lost to it.
10. No human verb, resume CLI, or routing is added; m4 delivers only the composition hook.
11. The v1 lattice + barrier ships as the built DEFAULT, and the two deferred extension points are DESIGNED but NOT built: the reduce is a pluggable policy SLOT with only the v1 max-wins/barrier policy implemented (alternate `{quorum|best-effort|budget|saturation}` policies are not built), and a scope-boundary interception point exists for SCOPED suspension propagation without scoping being implemented (a streaming parent with a suspending child branch still uses the v1 default lift); a test asserts the default behavior and that the seams are present-but-unbuilt.

## Touchpoints

- `megaplan/_pipeline/subloop.py:23-30`, `:83-105` (`SubloopStep` — map child `suspended`/`awaiting_user`→parent `suspended` BEFORE the legacy promote)
- `megaplan/_pipeline/pattern_joins.py:17-86` (fan-out/join reduce — lattice `completed<suspended<failed` max-wins over `ContractResult`s as the BUILT DEFAULT behind a pluggable reduce-policy SLOT; composite suspension group; failed parent retains `pending_suspensions`)
- a scope-boundary interception point for the DEFERRED scoped-suspension-propagation extension (designed, not built — streaming parent with a suspending child branch keeps the v1 default lift)
- the composite-cursor store (source of truth, persisted to survive process exit; targeted + batch resume)
- `megaplan/_pipeline/executor.py:262` (`next="halt"` + `_pipeline_paused` side-channel being superseded/bridged)
- m0a `status` enum + `Suspension` shape (consumed)
- composition tests (suspended-child-suspends-parent, fan-out-one-suspended, mixed-status reduce, failed-parent-retains-pending_suspensions, targeted+batch-resume, composite-cursor-survives-restart, all-completed no-regression)

## Rubric

- Profile: `partnered`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the corrected non-free seam — the edge hunt proved composition silently completes suspended children, which is a correctness hole the foundation must close to claim generality. Defining total compose/reduce semantics is subtle and the regression is real, so it earns thorough/high; it sits at partnered because the `status`/`Suspension` abstraction was already settled in m0a and this is bounded propagation work over it rather than new vocabulary.
