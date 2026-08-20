# Maintenance runtime consolidation execution plan

- Status: execution-ready for Batch 0; production-code implementation is blocked until source-custody Gate G0 passes
- Integration base: `fce48030a82d4d35d9b4a5184e4c789792b9c172`
- Working branch: `fixer/runtime-convergence-local`
- Target: the editable runtime successor staged for Astrid and Arnold
- Live-chain policy: do not advance, repair, pause, or otherwise mutate either live epic while consolidating code

## Purpose

Selectively port the useful, completed behavior from the `megaplan-maintenance` epic onto the current healthy runtime successor. Preserve the epic's completed work without merging its generated state, failed publication metadata, obsolete identity implementations, or over-broad automation.

This is not a wholesale branch merge. The milestone branches diverged, their final reconcile selected no commits, and later milestones contain generated evidence and older implementations that conflict with the runtime identity work already present at `fce`. The safe unit of integration is a coherent behavior plus its tests, not an entire milestone tip.

## Confidence and remaining uncertainty

Confidence in the selection philosophy and keep/adapt/drop judgments is high (about 90%). The evidence is unusually strong: milestone artifacts, patch topology, current-source comparison, review results, and focused runtime tests all point in the same direction.

The plan is execution-ready in the practical sense: every implementation card has a bounded goal, prerequisites, forbidden behavior, acceptance criteria, focused tests, and a review gate. A Luna implementer can take one card at a time without reconstructing the epic.

The residual uncertainty is concentrated in the tasks marked `[XHARD]`. Those tasks cross authority, compatibility, or crash-recovery boundaries. They are not underspecified; they deliberately require a contract review before code and an adversarial review after code. Gate G0 must also fetch and preserve the cloud-only commits before implementation starts, because those objects are not all present in the local object database.

## Philosophy

**Coherence through minimal, evidence-bound authority, not maximum enforcement.**

- Observe broadly; mutate narrowly.
- A diagnostic fact is not action authority.
- Fail closed only at load-bearing mutation and custody boundaries.
- Keep one enforcement point per invariant.
- Separate evidence, policy, and effects.
- Unknown remains unknown; it does not silently become healthy, failed, or zero.
- Every stricter contract gets an explicit, locked, idempotent migration seam.
- Resume and replay must be safe after any interruption.
- Port behavior and tests, not branch history or generated ledgers.
- Prefer removing redundant gates to adding another source of truth.
- Human and operator authority must be exact, scoped, and auditable.

## Settled Decisions

- **SD-001** — Build on `fce48030a82d4d35d9b4a5184e4c789792b9c172`. _load_bearing: true_
  Rationale: It contains the newest healthy runtime line, the parser repair, and the reconciled runtime identity/manifest behavior.
- **SD-002** — Do not merge a maintenance milestone branch wholesale. _load_bearing: true_
  Rationale: Milestone tips include generated state, failed publication artifacts, config pins, and superseded implementations.
- **SD-003** — The `fce` runtime identity, marker, manifest, parser, and custody contracts win every overlap. _load_bearing: true_
  Rationale: They are newer, tested, and already reconciled with the editable runtime candidates.
- **SD-004** — Preserve every cloud milestone tip under an immutable safety ref before selecting patches. _load_bearing: true_
  Rationale: Exclusion from the runtime does not mean deletion of evidence or history.
- **SD-005** — Liveness and observation surfaces remain diagnostic and cannot independently authorize repair, rebind, delivery, cutover, or escalation. _load_bearing: true_
  Rationale: Activity is not proof of current identity or custody.
- **SD-006** — M5 efficiency behavior is report-only. _load_bearing: true_
  Rationale: No automatic ticket, repair, initiative, schedule, provider, model, or policy mutation is justified by the epic evidence.
- **SD-007** — Test budgets become actual monotonic wall-clock task deadlines, with subprocesses capped by remaining time. _load_bearing: true_
  Rationale: Adding parallel static budget concepts would create contradictory enforcement and misleading guarantees.
- **SD-008** — Implementers run focused tests only; batch validators run integration shards; the broad suite runs once at final convergence. _load_bearing: false_
  Rationale: This localizes failures and avoids paying the full-suite cost for every small card.
- **SD-009** — Consolidation must not mutate the active Astrid or maintenance epic. _load_bearing: true_
  Rationale: Runtime source integration and live-chain recovery are separate operations.
- **SD-010** — Promotion is a pointer/selection change with an already-proven rollback target, never an in-place rewrite of live state. _load_bearing: true_
  Rationale: Rollback must be immediate and must not require data repair.

## Source custody and selection

The source tips to preserve are:

| Milestone | Observed tip | Treatment |
|---|---|---|
| M1 | `67e7b94a4da248b5e92ad56eb4bfa5ba261d9145` | Select liveness/test-budget intent; do not direct-port superseded contracts |
| M2 | `15b881cb47274447b3795c9438fd2de1d9f9d33d` | Port deterministic observation rendering; adapt explicit split-queue migration |
| M3 | `58d4a935539597c2aa3f323e1515054ec1f95fe7` | Already represented by newer `fce` custody behavior; retain as evidence |
| M3b | `7272cdc7f4303219fb399aefd2966f410d79d208` | Select occurrence, delivery, attestation, events, and handoff behaviors |
| M4 | `759e3186f773ae40e58dc9de1e716dfd2ebb8438` | Select pure policy/reporting, claims, receipts, classifier, unblocker, and auditor behavior |
| M5 | `800fa27648245115d5c1412d16ec583d91bdea02` | Select read-only efficiency analysis and fenced report-only projection |

Always exclude:

- generated ledgers, plan bundles, review packets, and auto-publication artifacts;
- `codex.pid`, failed-publish metadata, old chain pins, and milestone-local profile/config changes;
- unresolved M5 policy packets;
- older marker, digest, manifest, runtime identity, or parser implementations superseded by `fce`;
- any automatic ticket creation, reprioritization, initiative activation, repair claim, schedule activation, or provider/model rerouting.

## Difficulty labels

`[XHARD]` means correctness depends on a cross-cutting authority or compatibility invariant that cannot be established by editing one module and running its local tests. It requires:

1. a read-only consumer/transition map;
2. a frozen contract written into the task handoff;
3. one bounded implementation owner;
4. focused failure-injection tests; and
5. an independent adversarial review before dependent work begins.

Large but mechanically bounded tasks are not marked `[XHARD]`.

`[XHARD-REVIEW]` means the review itself requires whole-system synthesis rather than checking one task against local acceptance criteria. It is used for cross-branch selection, architectural coherence, systemic over-enforcement, and final end-state judgment. An ordinary implementation batch can therefore feed an `[XHARD-REVIEW]` gate.

## Execution protocol

- Use one Luna implementer per task card, one independent Luna reviewer per ordinary gate, and the stronger reviewer assignments in the review matrix for load-bearing gates.
- Parallelize only cards with disjoint production files and no unmet dependency.
- No two agents edit the same module concurrently.
- Each implementer returns: commit SHA, files changed, focused commands, results, rejected alternatives, and residual risks.
- Each reviewer reads the diff and production paths, adds a counterexample test when useful, and reports must/should findings with file and function evidence.
- A task with an unresolved must-level authority, identity, migration, or replay finding does not advance.
- Merge cards in the order below. Preserve user changes and never reset the integration worktree.

## Review ownership and timing

`[XHARD]` labels the implementation risk, not the implementer's intelligence or the mere existence of a review. Reviewer ownership is explicit:

| Gate | When | Reviewer | Purpose |
|---|---|---|---|
| G0 `[XHARD-REVIEW]` | Before any production-code card | Luna builds the inventory; Sol adjudicates selection; root decides | Verify custody, exact source hunks, cross-branch contradictions, and keep/adapt/drop completeness |
| G1, G2, G3 | After each ordinary batch | A Luna that implemented none of that batch | Diff review, focused counterexamples, purity/authority/replay checks |
| G3.5 `[XHARD-REVIEW]` | After ordinary foundations, before authority convergence | Fresh Sol architecture reviewer; root decides | Review the branch as a system for duplicate concepts, premature authority, aggression, and missing simplifications |
| G4.1, G4.2, G4.3 | Before and after each T4 `[XHARD]` card | Sol contract/adversarial reviewer; root accepts or rejects | Freeze authority contract before code; attack every production transition afterward |
| G5 | Before and after T5.1 | Sol semantic-compatibility reviewer; root accepts or rejects | Prove schema, prompt, execution, timeout, and resume all mean the same thing |
| G6.1, G6.2 | Before and after each `[XHARD]` card | Sol fence/closure reviewer; root accepts or rejects | Attack concurrency, fence loss, replay, window closure, and hidden authority |
| G6.3 | After the ordinary scheduler handoff | Independent Luna | Prove the handler only consumes T2.1 custody and cannot escalate observations |
| G6.4 `[XHARD-REVIEW]` | After all implementation, before broad validation | Fresh Sol systemic-risk reviewer; root decides | Trace observation-to-effect paths, find over-enforcement and duplicated authority, and demand simplification |
| G7 `[XHARD-REVIEW]` | After all shards, candidate proof, and canary | Fresh Sol final reviewer; root makes promotion recommendation | Assess the final diff and evidence manifest against must-level end-state criteria |

Review mechanics:

- The implementer never reviews its own card.
- The root agent writes/freezes the task handoff, resolves reviewer findings, and decides whether a card may merge.
- For ordinary cards, the reviewer runs only that batch's focused integration shard.
- For `[XHARD]` cards, the pre-code review must approve the contract/consumer map before the Luna implementer starts; the post-code reviewer receives the frozen contract, diff, focused evidence, and failure-injection results.
- A dedicated Luna validation agent runs each final integration shard once. Implementers do not rerun the broad suite.
- Sol reviews are read-only and decision-oriented. Sol does not perform the implementation it later judges.
- No batch advances with an unresolved must-level finding. Should-level findings are recorded with an explicit disposition by the root.

## Batch 0 — Custody and exact patch map

### T0.1 Preserve the milestone objects

Goal: fetch each source tip from the cloud project and create local safety refs such as `refs/heads/safety/maintenance-m1` through `m5`.

Acceptance:

- All six listed tips — M1, M2, M3, M3b, M4, and M5 — resolve locally and the ref-to-SHA manifest is committed as evidence.
- Object reachability is verified after fetch.
- No live branch, chain state, selector, editable install, or remote branch is changed.

Focused checks: `git cat-file -e <sha>^{commit}`, `git show-ref`, and a recorded `git merge-base` against `fce`.

### T0.2 Produce the source selection manifest

Goal: enumerate the exact source commits and file hunks used by every later card, plus the explicit exclusion reason for every patch-unique production commit.

Acceptance:

- Every patch-unique production commit reachable from the milestone tips is classified as keep, adapt, superseded, generated evidence, or unresolved policy.
- The manifest maps selected behavior to a task ID below.
- At minimum it resolves the full source SHAs and hunks behind the known seeds `fa42ff979f69` (T1.1), `3a94a1f54` (T3.1), `9056775d6c` (T4.1), and `62d3cae7fb` (T5.1).
- Every selected card identifies whether it is an exact port, an adaptation, or already present at `fce` before code begins.
- No unclassified production commit remains. Every exclusion names its replacement function/test or is explicitly classified `evidence/config-only` or `unresolved-policy`.

### Gate G0 `[XHARD-REVIEW]` — Custody and selection review

A Luna reviewer checks object reachability and classification completeness. A Sol reviewer then adjudicates the selection across all milestone branches, looking for contradictions, falsely superseded behavior, and unjustified automation. The root records the final keep/adapt/drop disposition. Implementation starts only after G0 passes.

## Batch 1 — Pure observation foundations

These cards may run in parallel after G0.

### T1.1 Deterministic maintenance observation rendering

Goal: port M2's deterministic observation projection without changing the legacy snapshot or adding writes.

Likely files: `arnold_pipelines/megaplan/cloud/status_snapshot.py`, `tests/cloud/test_maintenance_shadow_consumers.py`, adjacent status tests.

Acceptance:

- Identical evidence produces the same `view_hash`; no separate view ID is added unless the source contract proves one is required.
- Missing or contradictory evidence remains typed unknown.
- Legacy snapshot output is unchanged unless a versioned field is explicitly added.
- No writer, dispatcher, scheduler, or repair API is reachable from rendering.

Focused tests: status snapshot projection and maintenance shadow-consumer tests.

### T1.2 Pure operational policy and reporting

Goal: port deterministic M4 policy/report construction as pure functions.

Likely files: new `arnold_pipelines/megaplan/maintenance/operational_policy.py`, `operational_reporting.py`, package exports, focused tests.

Acceptance:

- Cohort identity, suppressors, watermarks, SLO deltas, evidence locators, and content digests are deterministic.
- Missing, late, duplicate, expired, or incoherent evidence cannot produce a stronger result.
- The modules contain no dispatch or control-plane writes and choose no thresholds by inference.

Focused tests: deterministic digest, out-of-order evidence, expired policy, replay round-trip, and mutation-spy tests.

### T1.3 Efficiency read model and inert proposals

Goal: port M5 sources, analysis, baselines, clustering, economics, and routing as immutable read-only models.

Likely files: new `maintenance/efficiency_sources.py`, `efficiency_analysis.py`, `efficiency_baselines.py`, `efficiency_clustering.py`, `efficiency_economics.py`, `efficiency_routing.py`, `efficiency_contracts.py`, and focused tests.

Acceptance:

- Inputs use read-only injected providers.
- Missing cost, quality, model, route, or receipt coordinates stay unknown rather than zero.
- Censored or gapped data cannot support a stronger claim than the evidence.
- Proposals are immutable, evidence-linked, deterministically deduplicated, and structurally `auto_materialization=False`.
- No mutation-capable provider is accepted or called.

Focused tests: malformed/torn reads, censoring, undeclared aliases, cross-environment evidence, stable no-match identity, and mutation spies.

### Gate G1 — Purity and conservative-evidence review

Run the Batch 1 contract/digest shard. The reviewer searches production imports and call graphs for hidden writers, ambient defaults, and any unknown-to-green conversion.

## Batch 2 — Claims, receipts, and repair classification

### T2.1 Scheduler lease and occurrence claims

Goal: introduce one fenced claim point for occurrence-bound maintenance wakeups, with epoch ownership and idempotent terminalization.

Likely files: `resident/schedules.py`, `resident/scheduler.py`, scheduler/lease tests.

Dependencies: T1.2.

Acceptance:

- G0 binds this card to the existing authoritative schedule-store claim function and persisted claim schema; this card extends that seam and cannot introduce a second claim API.
- Exactly one owner can transition an occurrence.
- Stale epochs fail closed and cannot delete or overwrite the current claim.
- TTL reclaim creates a new epoch; terminal writes are idempotent.
- Duplicate wakeups join or no-op.

Focused tests: duplicate claim, stale mutation, TTL reclaim, digest mismatch, and crash before/after claim persistence.

Difficulty note: this is intentionally not `[XHARD]` because `fce` already has the schedule lease/store authority seam. If G0 cannot identify that reusable seam, stop and reclassify the card rather than inventing a second authority system.

### T2.2 Dispatch receipts and reconciliation

Goal: port occurrence/effect-bound receipt initialization and exactly-once reconciliation.

Likely files: `cloud/maintenance_dispatch.py`, `cloud/progress_auditor_controller.py`, focused dispatch tests.

Dependencies: T1.2, T2.1.

Acceptance:

- Report receipts and effect receipts are separate typed schemas. Report-only paths do not require effect coordinates, report receipts cannot satisfy an effect receipt, and cross-kind adoption is rejected.
- Effect-receipt adoption requires exact occurrence, request, effect, and immutable-evidence identity.
- A request file's existence is never treated as completion.
- Reconciliation after a crash is exactly-once and side-effect-free after terminal adoption.
- Allowlisted routing is explicit.

Focused tests: identity mismatch, partial receipt, effect-before-receipt crash, duplicate reconciliation, stale occurrence, unknown receipt state, and report/effect cross-kind rejection.

### T2.3 Evidence-bound repair classification

Goal: admit only the complete deterministic review-quality failure shape into the existing repair contract.

Likely files: `cloud/repair_contract.py`, minimal metadata emission in `handlers/review.py`, classifier tests.

Dependencies: current `fce` target/manifest identity.

Acceptance:

- Generic `quality_gate_blocked`, liveness, quota, open-PR, human-only, and awaiting-human states remain non-dispatchable.
- Only complete, scoped evidence with matching cursor, target, digest, and trusted producer provenance can authorize a repair request.

Focused tests: each rejected class, missing scope, stale target, mismatched cursor/hash, and one valid complete shape.

### Gate G2 — Authority-entry review

Run scheduler/claim, receipt, and repair-contract shards. The reviewer proves there is one claim point, one receipt identity, and no alternate repair-eligibility path.

## Batch 3 — Explicit migration and bounded recovery

### T3.1 Explicit split-queue migration

Goal: adapt M2's stranded repair-request migration into an operator-invoked, locked, bounded, idempotent seam.

Likely files: `cloud/repair_requests.py`, explicit migration CLI/entrypoint if required, migration tests.

Dependencies: T2.3.

Non-goals: automatic migration from observation, status, import, scheduler wakeup, or ordinary queue reads.

API contract to freeze at G0:

- The single production function is `repair_requests.migrate_stranded_requests(request, ...)` (or the exact existing equivalent named by G0); only an explicit operator CLI may call it.
- `MigrationRequest` contains `migration_id`, exact source and target queue roots, source and target identity/digest, `max_requests`, requester identity, and request timestamp.
- `MigrationReceipt` contains the request digest, lock owner/fence epoch, source high-water mark, adopted request IDs/content digests, retained-original proof, terminal state, and receipt digest.
- A durable lock/receipt store is mandatory; `queue_root`, `max_requests`, and `created_at` alone are not a sufficient production API.

Acceptance:

- The explicit operator caller supplies a typed request with exact source/target identity and bounded `max_requests`.
- Originals are retained until verified adoption.
- Concurrent attempts serialize under a lock; exact replay is a no-op.
- Partial interruption resumes without duplication or loss.

Focused tests: concurrent calls, mid-item crash, max bound, mismatched identity, second replay, and observer non-interference.

### T3.2 Maintenance unblocker

Goal: port a bounded unblocker that can produce only a typed occurrence-bound request/checkpoint after two independent observations.

Likely files: new `cloud/maintenance_unblocker.py`, bounded resident handler integration, focused tests.

Dependencies: T1.2, T2.1, T2.2, T2.3.

Acceptance:

- One observation remains unknown.
- Before code, freeze the stable identity subset (occurrence, plan/cursor, runtime manifest, target digest, source cursor) and the explicitly allowed monotonic fields (observation time and permitted counters). The two observations must match the stable subset; all other drift rejects.
- Independence means distinct underlying source cursors/reads, not two timestamps over the same stale projection.
- PID, tmux, heartbeat, path, or lease presence cannot prove authority.
- The unblocker cannot approve or perform its own effect.
- Replay and stale-lease checkpointing are safe.

Focused tests: changed PID, changed lease epoch, changed runtime manifest, duplicate stale projection with different timestamp, missing evidence, producer/verifier separation, replay, stale fence, and no direct mutation.

### T3.3 Read-only six-hour audit enhancements

Goal: port strict window, watermark, cadence, censoring, and deterministic report behavior without control-plane mutation.

Likely files: `cloud/six_hour_auditor.py`, `cloud/progress_auditor_controller.py`, focused auditor tests.

Dependencies: T1.2.

Acceptance:

- Boundary, skew, late, duplicate, out-of-order, censored, and invalid-cadence cases remain deterministic and conservative.
- Missing source evidence produces unknown.
- The auditor is read-only; green never derives from process activity alone.

Focused tests: the focused six-hour auditor/controller shard plus mutation spies.

### Gate G3 — Migration/recovery review

Run repair-request migration, unblocker, and auditor shards. The reviewer injects interruption at persistence boundaries and verifies that observation code cannot invoke migration or recovery effects.

### Gate G3.5 `[XHARD-REVIEW]` — Midpoint coherence and minimalism

A fresh Sol reviewer reads the complete diff from `fce` through G3 rather than reviewing task cards independently.

Acceptance:

- Identity, occurrence, cursor, fence, receipt, evidence, and unknown-state terminology has one meaning across modules.
- No ordinary batch has created a second writer, claim seam, permission gate, migration trigger, or premature action authority.
- The pure observation layers remain useful when mutation evidence is absent.
- Constraints are located at load-bearing boundaries rather than duplicated through callers.
- Redundant checks and adapters are identified for deletion before T4 begins.
- The branch still matches the G0 selection manifest and has not absorbed generated or unresolved policy material.

## Batch 4 — Authority convergence

These tasks are deliberately serial. Each gets its own pre-code contract check and post-code adversarial review.

### T4.1 `[XHARD]` Root liveness/action authority

Goal: make current-target liveness purely diagnostic and route the selected M3b/M4 mutation-capable paths through one evidence-bound permission gate.

Likely files: `cloud/current_target_liveness.py` and every selected repair, rebind, escalation, retrigger, delivery, or cutover consumer found by the T4.1 consumer map.

Dependencies: T2.3, T3.2.

Frozen contract before implementation:

- Liveness may describe activity and contradictions.
- Only exact current target, occurrence/cursor, custody, fence, and required evidence may authorize an effect.
- No consumer may reconstruct authority from a subset of those facts.
- The root seam returns a typed `MutationCapability` bound to action type, occurrence, target, cursor, fence epoch, evidence digest, scope, and expiry. Downstream code may narrow/validate its scope but cannot independently grant authority.

Acceptance:

- The consumer map is complete for every selected M3b/M4 behavior. Every unrelated mutation surface gets an explicit out-of-scope disposition; this task is not a runtime-wide authorization rewrite.
- Every in-scope mutation path calls the same root permission seam.
- Diagnostic callers remain usable when evidence is incomplete.
- Mutation callers fail closed on missing or contradictory identity.
- Old convenience gates are removed rather than layered beside the root gate.
- Valid downstream receipt/cutover/operator evidence without the root capability still rejects.

Focused tests: permission truth table; stale/live PID combinations; marker/manifest contradiction; stale cursor/fence; valid downstream evidence with absent capability; action/scope replay; complete authorized path; static search proving no bypassing in-scope consumer.

### Gate G4.1 — Liveness authority attack

The reviewer traces all production consumers and attempts to produce an effect using PID, heartbeat, path, lease, stale marker, or partial evidence alone.

### T4.2 `[XHARD]` Occurrence adoption, target rebind, and operator pause

Goal: add guarded adoption/rebind/pause seams before cutover, without moving logical resume cursors or inferring authority from operational evidence.

Dependencies: T4.1.

Acceptance:

- Operator intent is bound to one exact action type, occurrence, target identity, root capability, and fence epoch.
- Rebind changes only the explicitly authorized binding under CAS/fence.
- Adoption and pause are idempotent and fail closed on any identity contradiction.
- The logical resume cursor and plan payload remain byte-equivalent. Append-only pause metadata/evidence may change but cannot alter the cursor.
- PID, tmux, repo-path similarity, stopped lease, or stale marker cannot authorize adoption.
- A valid operator token replayed against another occurrence or action rejects.
- Rollback returns to the exact prior binding.

Focused tests: mismatched occurrence/plan/runtime; stale marker with live process; stale epoch; pause/resume race; cursor and plan-payload preservation alongside allowed pause-event append; action/occurrence token replay; duplicate adoption; rebind rollback.

### Gate G4.2 — Operator-authority attack

The reviewer proves operator intent is exact and scoped and that adoption, pause, or rebind cannot smuggle a cursor or runtime identity change.

### T4.3 `[XHARD]` Maintenance delivery and cutover

Goal: integrate delivery/cutover under current `fce` identity using T4.2's explicit pause/rebind primitive, a quiesced-writer proof, one fenced operator, atomic selector/marker transition, content-addressed evidence, and an exact rollback target.

Dependencies: T1.2 through T4.2.

Pre-code binding: G0/T4.2 must name the existing selector, marker, manifest, lease, operator-fence, and rollback receipt paths and their CAS owner. T4.3 may not create an ad hoc second pause, quiescence, rebind, or claim authority.

Acceptance:

- No report directly triggers delivery.
- Cutover requires the typed root capability and T4.2's exact pause/quiescence proof.
- Cutover refuses live writers, stale tokens, manifest/marker mismatch, and incomplete rollback evidence.
- Crash at any publication boundary leaves either the prior target or a resumable, provable transition.
- Duplicate delivery is idempotent.
- Rollback restores the exact prior selection without rewriting plan state.

Focused tests: selector-before-marker/receipt crash, marker/receipt-before-selector crash, every other publication boundary, selector CAS race, absent root capability with otherwise-valid evidence, stale token, live-writer refusal, mismatch, duplicate, and rollback.

### Gate G4.3 — Cutover/custody attack

The reviewer treats every persistence boundary as a crash point and checks that no half-published state can be mistaken for current authority.

## Batch 5 — Real elapsed test deadlines

### T5.1 `[XHARD]` Replace static budget admission with a monotonic task deadline

Goal: enforce the promised task test budget as actual elapsed wall-clock time while preserving retry/resume compatibility.

Likely files: `execute/merge.py`, `orchestration/task_feasibility.py`, `orchestration/validation_jobs.py`, `orchestration/task_splitter.py`, finalize/execution schemas and prompts, and their focused tests.

Contract to freeze before code:

- New plans write `narrow_tests.budget_semantics = "elapsed_wall_clock_v2"`, one positive `test_budget_seconds` task-level duration, and `max_runs`.
- Execution persists `test_budget_state_v2 = {allowed_seconds, consumed_seconds, run_count, active_run, updated_at_utc}`. `active_run` contains the run ID, command digest, UTC start, and remaining budget at launch.
- Within a process, durations use a monotonic clock. A raw monotonic timestamp is never persisted across processes.
- On ordinary completion, add the monotonic run duration to `consumed_seconds`. On resume with an interrupted `active_run`, conservatively charge the non-negative UTC interval capped at the remaining budget; backward/invalid wall-clock movement consumes the recorded remaining budget and fails closed.
- Before each test subprocess, compute remaining task budget.
- The subprocess timeout is `min(command_timeout, remaining_budget)`.
- Admission stops when no positive budget remains, irrespective of the sum of declared command timeouts.
- A task with `max_seconds` and no `budget_semantics` is classified `declared_timeout_sum_v1` and retains its current documented behavior. The loader does not rewrite its artifact. Only newly finalized or explicitly migrated tasks receive v2 fields.
- There is one production enforcement seam; feasibility and prompts describe it rather than independently enforcing competing arithmetic.

Acceptance:

- Sleep/slow-command tests prove actual elapsed enforcement.
- Fast commands with large declared timeouts are not rejected merely because timeout sums exceed the task budget.
- Retry, interruption, and resume cannot reset consumed elapsed time.
- Legacy v1 and new v2 artifacts load deterministically, emit a visible compatibility classification, and never mix state fields.
- `max_runs` and the task deadline are independently enforced at the same root seam.

Focused tests: fast-large-timeout, slow-small-timeout, exhausted-before-launch, interrupted subprocess, resume, clock abstraction, legacy schema, and splitter/feasibility messaging.

### Gate G5 — Deadline semantics review

The reviewer compares the schema, prompt, feasibility display, execution code, and resume artifact to prove they all describe one semantic contract. Run only the deadline/feasibility/splitter/validation shards here.

## Batch 6 — Fenced efficiency observation

### T6.1 `[XHARD]` Append-only fenced efficiency events

Goal: port/adapt M5's existing reporting behavior so reports, clusters, proposals, and corrections persist only as idempotent observation events through one canonical writer.

Likely files: the M5 `maintenance/efficiency_reporting.py`, the existing canonical maintenance event/projection seam, focused emission tests. G0 must name the exact source API and the one canonical event-writer function before implementation; this card replaces/adapts that seam and may not create a second reporter.

Dependencies: T1.3, T2.1.

Acceptance:

- Every append is bound to the current occurrence fence and evidence digest.
- Exact replay returns `already_present`; same occurrence key with a different digest fails closed.
- Fence loss before append writes nothing; projection cannot manufacture a receipt or authority transition.
- Append and projection cursor behavior are deterministic and auditable.
- Ledger/event append is the sole permitted M5 data-product mutation. Schedule claim/terminalization uses the pre-existing T2.1 custody API; neither kind of write can mint closure, dispatch, completion, repair, scheduling-policy, or ticket authority.

Focused tests: duplicate replay, divergent digest, concurrent writers, fence loss at each boundary, append failure, projection failure, dead-letter/retry behavior.

### Gate G6.1 — Persistence/fence attack

The reviewer races writers, steals fences at each boundary, and verifies projections remain observation-only.

### T6.2 `[XHARD]` Closure-proven daily runner

Goal: adapt M5's existing runner to analyze only daily windows proven closed by committed occurrence evidence; catch up and revisit late inputs without inventing cron authority.

Likely files: the M5 `maintenance/efficiency_runner.py`, the existing operational-report closure receipt adapter, focused runner tests. G0 names the exact runner entrypoint and closure-adapter boundary before code.

Dependencies: T6.1 and the committed operational-report chain.

Acceptance:

- Window boundaries come from committed closure evidence, never nominal clock time.
- Unclosed, malformed, torn, or gapped coverage returns a typed non-appending result.
- Production requires a live fence and real prior-key lookup; unsafe optional fallbacks do not exist in production APIs.
- Catch-up and late correction replay are idempotent and preserve prior evidence links.
- No maintenance chain, repair queue, or plan state is modified.

Focused tests: empty/gapped chain, malformed event, stale/reclaimed fence, late correction, nominal-window mismatch, active-chain non-interference, explicit rejection of `fence_check=None`, and rejection of a default/always-`never_seen` prior-key lookup. Add a production call-site audit proving neither unsafe fallback is reachable.

### Gate G6.2 — Window-closure attack

The reviewer attempts to create a daily result from clock boundaries, incomplete windows, duplicate corrections, and stale closure receipts.

### T6.3 Canonical scheduler handoff and negative-authority suite

Goal: run the daily observer from one explicitly owned schedule occurrence and prove observation cannot escalate.

Likely files: `resident/scheduler.py`, `resident/schedules.py`, daily handler tests, new negative-authority tests.

Dependencies: T6.2.

Acceptance:

- This handler is a consumer of T2.1's authoritative claim/lease API. It may not implement claim, replay, terminalization, or stale-lease semantics a second time.
- Foreign schedule IDs, cross-window leases, missing coordinates, and stale claims fail closed.
- Concurrent/replayed wakeups join or no-op; terminal remains terminal.
- Runner failure retains a retryable claim.
- No ticket create/edit/address, repair claim/dispatch, provider/model reroute, schedule-definition change, or unrelated receipt writer is reachable.
- Active Astrid and maintenance chain fixtures remain byte-for-byte unchanged.

Focused tests: schedule ownership, concurrent claim, failure/retry, terminal replay, mutation spies, schedule-store snapshots, active-chain snapshots, and static import/call-graph evidence proving one T2.1 claim function and no ticket, repair-dispatch, schedule-definition, provider/model-routing, or authority-receipt writer is reachable.

### Gate G6.3 — Negative-authority review

The reviewer inspects imports and call sites, not only mocks, and proves all M5 outputs terminate at report-only events.

### Gate G6.4 `[XHARD-REVIEW]` — Systemic aggression and simplification review

A fresh Sol reviewer assesses the entire implemented branch as one operating system, not as a collection of passing cards.

Acceptance:

- Every path from observation to mutation terminates either at a report-only artifact or at the single typed root capability and its explicitly scoped effect.
- Unknown, stale, partial, or contradictory evidence cannot become green or actionable through composition across modules.
- No ticket, repair, scheduling-policy, provider/model, rebind, pause, delivery, or cutover authority appears outside its settled boundary.
- Repeated enforcement, redundant schemas, compatibility layers with no remaining caller, and accidental policy defaults are removed or explicitly justified.
- A valid diagnostic workflow still functions without mutation authority; safety has not become operational paralysis.
- The reviewer proposes deletions and simplifications, not only additional gates.

## Batch 7 — Convergence, runtime validation, and promotion evidence

### T7.1 Completeness and contradiction audit

Goal: compare the final branch against the G0 selection manifest and all milestone tips.

Acceptance:

- Every selected behavior has code and focused tests.
- Every excluded production patch still has a recorded reason.
- No older identity/manifest/parser implementation overwrote `fce`.
- No duplicate enforcement point or contradictory default remains.

### T7.2 Integration test shards

Run each shard once, by a validation agent rather than every implementer:

1. contracts, identities, manifests, markers, digests;
2. repair classification, queue migration, unblocker;
3. scheduler claims, receipts, delivery, pause/rebind/adoption;
4. status projection, operational policy, six-hour auditor;
5. efficiency sources, unknowns, analysis, baselines, clustering, economics;
6. inert routing, fenced reporting, daily runner, negative authority;
7. test-deadline, feasibility, splitter, validation-job semantics;
8. editable-install/runtime conformance, CLI imports, profile resolution;
9. shared-venv manifest, frozen-spec digest, package provenance, and cross-candidate path isolation;
10. one final broad repository suite after all focused shards are green.

Every shard records command, commit, environment identity, result, and artifact digest. State-writing tests use an explicit disposable root.

### T7.3 Candidate runtime installation proof

Goal: build or update both editable candidate installs to the same successor SHA while preserving their separate project state and environment identity.

Targets:

- `/workspace/runtime-candidates/astrid-first`
- `/workspace/runtime-candidates/arnold-4a830c6ac9a0`

Acceptance:

- The allowed mutation targets are exactly the two candidate roots above; live-chain runtime paths are prohibited.
- Both candidates report the approved source commit, package provenance, frozen-spec digest, runtime-manifest digest, shared dependency-venv manifest digest, and CLI behavior.
- Their interpreter and dependency-venv identity are explicit and verified, while their project-state roots remain distinct.
- Neither candidate's `PYTHONPATH` or editable install resolves to the other candidate or to a live source tree.
- Each update writes an install receipt containing candidate path, prior SHA, installed SHA, source/package/spec/manifest/venv digests, command, and timestamp.

### T7.4 `[XHARD]` Disposable canary and rollback proof

Goal: prove read-only plan/CLI behavior, fenced daily observation, and immediate pointer-based rollback without touching live state.

Acceptance:

- The canary uses copied fixtures, a disposable runtime root, frozen spec, and verified venv.
- `config show`, profile resolution, provenance, import, plan read-only paths, event dedupe, and fence outcomes succeed.
- Any live-state write, authority escalation, unexpected model/provider route, or identity divergence stops promotion.
- Rollback selects the prior verified SHA; it does not rewrite data.
- Capture content-addressed before/after snapshots of process identity, runtime selector/marker/manifest, leases, active Astrid plan/chain state, active maintenance plan/chain state, schedule store, and maintenance ledger. Post-canary and post-rollback comparisons must be exact except for explicitly disposable-root artifacts.

### Gate G7 `[XHARD-REVIEW]` — Final promotion review

An independent reviewer receives only the final diff, selection manifest, shard evidence, candidate provenance, canary evidence, and rollback evidence. A machine-readable evidence manifest links every result to its command, source SHA, runtime/spec/venv digests, disposable-root path, and artifact digest; a missing artifact stops the gate. Promotion is allowed only when all must-level criteria pass. Promotion itself remains a separate explicit operation from code consolidation.

## Agent-sized handoff template

Each task dispatched to a Luna agent must contain only:

1. the task card above;
2. the exact source commit/hunks from the G0 manifest;
3. the current base SHA and allowed file set;
4. the dependencies already merged;
5. the focused test commands; and
6. the required return schema;
7. the explicit disposable test root; and
8. a prohibition on writing project or live runtime state from tests.

Do not give an implementer the entire epic history or ask it to run the full suite. If a task grows beyond its allowed file set or discovers a new authority transition, stop that card, record the evidence, and split it rather than improvising a new policy.

## Desired end-state

The end-state is one coherent runtime lineage, not a pile of milestone merges:

- The successor contains `fce` plus every behavior selected by the G0 manifest, with every selected behavior mapped to a task and passing evidence and every excluded production change carrying an explicit reason.
- Runtime identity, marker, manifest, parser, custody, and promotion semantics have one current implementation.
- Liveness is useful for diagnosis but powerless to authorize effects.
- Repair, delivery, adoption, rebind, pause, and cutover use exact occurrence identity, custody, fences, receipts, and idempotent transitions.
- Observation and efficiency systems are deterministic, conservative, append-only, and report-only.
- Unknown evidence stays unknown; economics cannot silently manufacture zeroes or policy.
- Test budgets mean actual elapsed time and survive interruption without reset.
- Legacy state is bridged explicitly; no import/status path performs a surprise migration.
- Both editable runtime candidates are reproducible from the same verified successor SHA while retaining separate project state.
- Active Astrid and maintenance epics are unchanged by consolidation.
- Promotion has a disposable canary, a single final evidence pack, and an immediate pointer-based rollback.

That is materially better and more stable than either source alone: the maintenance epic contributes useful observation, custody, scheduling, repair-quality, and efficiency work, while the successor supplies the newer coherent identity foundation and removes the epic's over-broad or unresolved automation.
