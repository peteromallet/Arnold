# Maintenance runtime consolidation execution plan

- Status: execution-ready for Batch 0; production-code implementation is blocked until source-custody Gate G0 passes
- Integration base: `fce48030a82d4d35d9b4a5184e4c789792b9c172`
- Remote integration target: `origin/fixer/runtime-convergence-r`; the executor creates a fresh local task/integration branch and always pushes explicitly to `fixer/runtime-convergence-r`
- Target: the editable runtime successor staged for Astrid and Arnold
- Live-chain policy: do not advance, repair, pause, or otherwise mutate either live epic while consolidating code

## Purpose

Selectively port the useful, completed behavior from the `megaplan-maintenance` epic onto the current healthy runtime successor. Preserve the epic's completed work without merging its generated state, failed publication metadata, obsolete identity implementations, or over-broad automation.

This is not a wholesale branch merge. The milestone branches diverged, their final reconcile selected no commits, and later milestones contain generated evidence and older implementations that conflict with the runtime identity work already present at `fce`. The safe unit of integration is a coherent behavior plus its tests, not an entire milestone tip.

## Confidence and remaining uncertainty

Confidence in the selection philosophy and keep/adapt/drop judgments is high (about 90%). The evidence is unusually strong: milestone artifacts, patch topology, current-source comparison, review results, and focused runtime tests all point in the same direction.

The plan is execution-ready in the practical sense: every implementation card has a bounded goal, prerequisites, forbidden behavior, acceptance criteria, focused tests, and a review gate. A correctly routed implementer can take one card at a time without reconstructing the epic.

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

## Incident class 2026-08-20 mapping (astrid-first)

| Failure | Plan home | Not |
|---|---|---|
| Unguarded stdout tee `BrokenPipeError` | T7.1 already-present helper (P9) | T4.*, identity |
| Babysitter goal/sandbox vs bwrap | T2.4 (P1), P6 | T3.3 product read-only |
| Receipt failed + rc 0 | T2.2 (P2) + T2.4 | T2.1 second claim |
| Phantom PID owner | T2.4 + G3.5/G6.4 (P8) | T4.1 PID-as-authority (already forbidden) |
| Ambient vs seed `megaplan_engine_root()` | T4.1 import_root binding (P3) | SHA pin / `advance_generation` |
| Operator recover-blocked + rebind + start | T3.2 sequence + T4.2 label guard (P4) | Unblocker self-effect |
| Two-commit/two-rebind tax | Protocol note + T4.3 deletion (P5) | Recovery design |
| Phase-contract 3/3 fence | T2.3 keep (P7) | Mechanical replay |

SD-009 still forbids mutating the live Astrid/maintenance epics as consolidation. This table is a successor contract, not a live-box repair instruction.

## Post-G0 amendment constraints and residual risks

The operator-directed post-G0 source additions are `7fe994abf` (babysitter sandbox plus false-success return-code fix), bound to T2.4, and `0425372ec` (stdout-tee `BrokenPipeError` helper), bound to T2.4/T7.1 as applicable. Both are on the epic branch for candidate `astrid-first` (`/workspace/arnold-ref/.git/worktrees/astrid-first`) and were not in the G0 M1–M5 selection. They must not be treated as covered by the existing G0 manifest: T0.2 requires a follow-on additive selection-manifest update card before the affected implementation cards are fully source-bound. This amendment does not rewrite or regenerate the G0 manifest.

Rejected and forbidden alternatives:

- no T4.4-shaped atomic identity vector, seed/preflight-SHA/epoch pin, or state-schema launch pin;
- no second occurrence owner, claim API, cutover writer, rebind writer, or authority seam;
- no restoration of the babysitter manifest→marker→chain→seed ceremony;
- no automatic `recover-blocked`, automatic rebind, or watchdog replay from T3.2;
- no `advance_generation` as recovery;
- no receipt↔rc coupling duplicated in T2.2 rather than enforced once in T2.4;
- the fixer sequence is not a normal operator runbook; it is a fixer-executable last-rung contract;
- no `--sandbox read-only` on this host when bwrap user-namespace creation fails;
- product read-only is a production-API write prohibition, not a process-sandbox assumption;
- a dead PID is not an active owner, and a live PID is not authority;
- the 3/3 deterministic phase-contract fence is not weakened;
- the stdout helper is not moved to T5.1 or dropped because G0 omitted its hunk;
- the G0 manifest is not rewritten in this amendment;
- no production code, tests, validators, evidence-manifest changes, or live-epic mutation are authorized by this card.

Residual risks:

1. The two source commits remain unbound in the existing selection manifest until the follow-on additive T0.2 card; implementation must not pretend the current G0 manifest covers them.
2. The pre-T4.3 expected-head/content-digest tax remains operationally noisy until the gates are deleted and must not become successor authority.
3. Cloud bwrap namespace failure is infrastructure; later shards must prove product non-mutation with spies/fingerprints and classify namespace failure separately.
4. This explicit operator amendment changes plan authority after J1; the single amendment commit and changed-file list are the audit boundary.
5. The goal-document line is intentionally minimal; this plan remains complete task-order authority.
6. This card produces no implementation or test evidence; later T2.4/T7.1 implementation and independent reviews must prove these contracts.

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

`[HARD]` / `[HARD-REVIEW]` are bounded Luna implementation/review work with a frozen contract and exact file allowance. Review repairs become separate `[HARD-REVISION]` (Luna) or `[XHARD-REVISION]` (Grok 4.6) cards. A revision is XHARD whenever it affects authority, custody, identity, migration, concurrency/replay, compatibility/public schema, live-runtime behavior, task scope, acceptance semantics, or policy; ambiguity is itself routed to a fresh Grok judgment.

## Execution protocol

- Route every `[XHARD]`, `[XHARD-REVIEW]`, `[XHARD-REVISION]`, and material judgment to Grok 4.6 through `subagent-launcher`. Route every ordinary/unlabelled implementation as `[HARD]`, every ordinary review as `[HARD-REVIEW]`, and every bounded `[HARD-REVISION]` to GPT-5.6 Luna through the same launcher.
- All research, brief preparation, file mapping, implementation, test execution, review, revision, integration/push, candidate work, canary operation, evidence validation, judgment, and final report assembly is performed by routed subagents. The orchestrator only dispatches, watches receipts, advances deterministic state, and relays the reviewed result.
- Parallelize only cards whose complete allowed production-and-test file sets are disjoint and whose dependencies are already merged. Any shared export, fixture, helper, or test file forces serialization.
- No two agents edit the same file or worktree concurrently.
- Each implementer returns: commit SHA, files changed, focused commands, results, rejected alternatives, and residual risks.
- Each reviewer reads the diff and production paths, specifies a concrete counterexample test when useful, and reports must/should findings with file and function evidence. A fresh routed `[HARD-REVISION]` or `[XHARD-REVISION]` subagent adds any required test/fix; read-only reviewers do not edit.
- A task with an unresolved must-level authority, identity, migration, or replay finding does not advance.
- Merge cards in the order below. Preserve user changes and never reset the integration worktree.
- Every operator mutation against a live epic — `recover-blocked`, `runtime-rebind`, `chain start`, and engine-runtime admission — runs under the seed/import environment: `PYTHONPATH=<import_root>`, `ARNOLD_RUNTIME_MANIFEST=...`, and the generation interpreter. Ambient-shell engine-root resolution is forbidden.
- **Pre-deletion operator tax (evidence/compatibility, not authority):** until the seed-store, `dispatch-current.json`, `MEGAPLAN_RUNTIME_LAUNCH_SEED`, same-root receipt-byte-equality, and `runtime_vector_sha256` gates are deleted, each engine commit still pays the known tax: update manifest `expected_head` telemetry without `advance_generation`, then perform content-digest rebind if that binding still exists. This must not be ported as a successor gate or recovery design; after T4.3 gate deletion, same `import_root` is a non-event.

## Review ownership and timing

`[XHARD]` labels the implementation risk, not the implementer's intelligence or the mere existence of a review. Reviewer ownership is explicit:

| Gate | When | Reviewer | Purpose |
|---|---|---|---|
| G0 `[XHARD-REVIEW]` | Before any production-code card | Luna inventory/validator; Grok 4.6 adjudicates selection; Luna records the judgment receipt | Verify custody, exact source hunks, cross-branch contradictions, and keep/adapt/drop completeness |
| G1, G2, G3 `[HARD-REVIEW]` | After each ordinary batch | A Luna that implemented none of that batch | Diff review, focused counterexamples, purity/authority/replay checks |
| G3.5 `[XHARD-REVIEW]` | After ordinary foundations, before authority convergence | Fresh Grok 4.6 architecture reviewer/judge | Review the branch as a system for duplicate concepts, premature authority, aggression, and missing simplifications |
| G4.1, G4.2, G4.3 `[XHARD-REVIEW]` | Before and after each T4 `[XHARD]` card | Grok 4.6 contract/adversarial reviewer/judge | Freeze authority contract before code; attack every production transition afterward |
| G5 `[XHARD-REVIEW]` | Before and after T5.1 | Grok 4.6 semantic-compatibility reviewer/judge | Prove schema, prompt, execution, timeout, and resume all mean the same thing |
| G6.1, G6.2 `[XHARD-REVIEW]` | Before and after each `[XHARD]` card | Grok 4.6 fence/closure reviewer/judge | Attack concurrency, fence loss, replay, window closure, and hidden authority |
| G6.3 `[HARD-REVIEW]` | After the ordinary scheduler handoff | Independent Luna | Prove the handler only consumes T2.1 custody and cannot escalate observations |
| G6.4 `[XHARD-REVIEW]` | After all implementation, before broad validation | Fresh Grok 4.6 systemic-risk reviewer/judge | Trace observation-to-effect paths, find over-enforcement and duplicated authority, and demand simplification |
| G7.4-pre / G7.4-post `[XHARD-REVIEW]` | Immediately before and after T7.4 | Two fresh Grok 4.6 reviewers, distinct from the T7.4 implementer | Freeze canary mutation boundaries first, then attack canary/rollback evidence before the broad suite |
| G7 `[XHARD-REVIEW]` | After T7.5 closes and validates the evidence manifest | Fresh Grok 4.6 final reviewer/judge produces promotion recommendation | Assess the final diff and evidence manifest against must-level end-state criteria |

Review mechanics:

- The implementer never reviews its own card.
- A Luna brief-preparation subagent writes the task handoff from the frozen card. Reviewer findings become evidence-linked revision cards; material dispositions go to fresh Grok judgment subagents. A fresh Luna integration subagent merges/pushes only after the required passing review/judgment receipts exist.
- For ordinary cards, the reviewer runs only that batch's focused integration shard.
- For `[XHARD]` cards, a Grok 4.6 pre-code review must approve the contract/consumer map before a separate Grok 4.6 implementer starts; a fresh Grok 4.6 post-code reviewer receives the frozen contract, diff, focused evidence, and failure-injection results.
- A dedicated Luna validation agent runs each final integration shard once. Implementers do not rerun the broad suite.
- Grok reviews are read-only and decision-oriented. No Grok instance reviews an implementation produced by that same instance.
- Every launcher call records a globally unique wrapper-generated `invocation_id`, launcher/child PID identity, resolved model, start/end time, exit status, exact command digest, brief digest, and result digest. The evidence validator rejects any reused invocation ID and rejects a review whose invocation or process identity equals any implementation it judges.
- No batch advances with an unresolved must-level finding. Should-level acceptance/risk dispositions are material judgments and require a Grok receipt; mechanical should fixes may route as `[HARD-REVISION]` only after their acceptance semantics are already frozen.

## Batch 0 — Custody and exact patch map

### T0.0 Capture the immutable live-state baseline

Goal: before any fetch-side operation, test, process intervention, or candidate write, capture a read-only content-addressed baseline for proving non-interference.

Capture: process identities, runtime selectors/markers/manifests, leases/fences, active Astrid plan/chain state, active maintenance plan/chain state including the final reconcile, schedule store, maintenance ledger, both candidate roots and their provenance, and the integration source/remote refs.

Acceptance: the baseline records paths, timestamps, source cursors, artifact digests, and any unknown/unreadable dimension without mutating or terminalizing any process, plan, chain, selector, candidate, or ledger. All later stateful cards cite this baseline and T7.4 compares against it.

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
- Operator-directed post-G0 additions do not rewrite this committed G0 manifest. T0.2 must carry a follow-on additive selection-manifest update that binds `7fe994abf` to T2.4 and `0425372ec` to T2.4/T7.1 before those cards are treated as fully source-bound.

### T0.3 Scaffold the machine-readable evidence contract

Goal: create the evidence manifest schema and deterministic validator before production implementation starts.

Files: `docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json`, a versioned JSON schema beside it, `scripts/validate_maintenance_runtime_consolidation_evidence.py`, `scripts/run_maintenance_consolidation_agent.py`, and focused validator/launcher-receipt tests.

The schema requires:

- integration base/current SHA and G0 selection-manifest path/digest;
- one record per task with label, selected source hunks, input/output SHA, commit, complete file allowance, implementer model/invocation identity, and focused-test receipts;
- an ordered `review_invocations` collection for every `[XHARD]` task, separately recording pre-review, implementation, and post-review identities/dispositions; ordinary gates use their own independent review record;
- one record per reviewer finding with finding ID, must/should severity, proposed and adjudicated revision class, `[HARD-REVISION]` or `[XHARD-REVISION]` invocation/commit, counterexample evidence, re-review invocation/verdict, and superseded artifact digests;
- one record per material judgment with Grok invocation identity, exact question, evidence inputs, decisive recommendation, rejected alternatives, affected contracts/tasks, and downstream route;
- one atomic file-allowance registry record per task covering production files, tests, fixtures, exports, helpers, generated surfaces, lifecycle state, and allowance digest;
- one record per shard with canonical command, SHA, interpreter, runtime/spec/venv digests, disposable root, status, artifact path, and digest;
- candidate install receipts, before/after live-state snapshot digests, canary/rollback receipts, and the broad-suite singleton receipt; and
- uniqueness/referential-integrity rules proving every selected behavior maps to a task, every task maps to a gate, every gate reviewer is independent, every hard task has the ordered pre-review → implementation → post-review lifecycle, no active allowance overlaps another, and every required artifact exists and matches its digest.

`scripts/run_maintenance_consolidation_agent.py` is the only allowed launcher after its bootstrap. It generates the invocation ID internally, atomically writes a start receipt, invokes the repository `subagent-launcher`, captures child PID/process identity and resolved model from launcher output, hashes the exact command/brief/result, and closes the receipt with exit status and timestamps. The caller cannot supply or attest its own invocation ID. It rejects a dispatch whose complete file allowance overlaps any active task. Its routing table enforces Grok 4.6 for `[XHARD]`, `[XHARD-REVIEW]`, `[XHARD-REVISION]`, and `judgment`; Luna for `[HARD]`, `[HARD-REVIEW]`, `[HARD-REVISION]`, brief/workspace/integration/validation/report roles; and rejects unclassified revision work.

Canonical validation command:

```bash
python scripts/validate_maintenance_runtime_consolidation_evidence.py \
  docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json
```

Acceptance: an empty scaffold reports the exact missing required records; complete synthetic evidence passes; duplicate task/gate/shard/finding/judgment IDs, any globally reused `invocation_id`, wrong task/review/revision/judgment model routing, unclassified review repairs, incomplete finding→revision→re-review chains, missing Grok receipts for material judgments, missing/overlapping allowances, wrong hard-review ordering, implementer/reviewer process identity equality, missing files, digest mismatch, unmapped selected behavior, and a second broad-suite authoritative invocation all fail deterministically. T0.3's own Luna bootstrap launch is the only direct-launch exception and its direct command/output digest is recorded before the wrapper becomes mandatory.

### Gate G0 `[XHARD-REVIEW]` — Custody and selection review

A Luna inventory/validation agent checks object reachability and classification completeness without adjudicating the selection. A Grok 4.6 reviewer/judge then adjudicates the selection across all milestone branches, looking for contradictions, falsely superseded behavior, and unjustified automation. A Luna evidence agent records the Grok keep/adapt/drop judgment receipt without changing it. Implementation starts only after G0 passes.

## Batch 1 — Pure observation foundations

These cards may run in parallel after G0 only after their complete production-and-test file allowances are frozen and proven disjoint. A shared package export, fixture, helper, or test file serializes the affected cards.

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

### Gate G1 `[HARD-REVIEW]` — Purity and conservative-evidence review

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
- Watchdog re-arm of the same occurrence requires a failed session receipt, not a completed receipt whose payload was later rewritten.

- Focused tests: identity mismatch, partial receipt, effect-before-receipt crash, duplicate reconciliation, stale occurrence, unknown receipt state, report/effect cross-kind rejection, no re-arm after rc 0, and re-arm after an honesty-failed session with nonzero rc.

### T2.4 `[XHARD]` Fixer transport honesty

Goal: make the babysitter/watchdog loop honest about session outcome, sandbox capability, and owner liveness. This is one receipt/transport enforcement point, not a second claim or cutover writer. Live Tree Authority is unchanged, and the J2-deleted babysitter manifest→marker→chain→seed ceremony remains deleted.

Likely files: `cloud/babysitter/launch.py`, `cloud/babysitter/render_babysitter_goal.py`, the watchdog owner-liveness reader, `resident/subagent.py`, and focused babysitter/managed-provider tests.

Dependencies: T2.2.

Sandbox contract:

- Probe bwrap capability with `bwrap --ro-bind / / -- true`.
- When the probe fails on this host, use `--sandbox danger-full-access` plus an explicit no-mutation contract and pre/post product-tree fingerprints. Goal text and exec argv must agree. Never emit `--sandbox read-only` on this host.

Receipt/return-code contract:

- Receipt `status` and process return code are one fact at this enforcement point.
- An honesty downgrade, including a still-blocked or failed target, writes `status=failed` and returns nonzero. A downgraded receipt with rc 0 is a contract failure. The watchdog must not re-arm the same occurrence from rc 0.

Owner-liveness contract:

- Use `kill(pid, 0)` or an equivalent liveness check against recorded `babysitter_pid` and `supervisor_pid` where applicable.
- A `launched`/`running` receipt whose recorded PID is dead is `failed`, not an active owner; a later incarnation may start. A live PID still stands down. A recorded PID is not authority.

Focused acceptance:

- A failing bwrap probe produces `danger-full-access` in both goal text and argv.
- A false-success downgrade returns nonzero; a dead-PID receipt is reclaimable/classified failed; a live-PID receipt stands down; a fingerprint mismatch fails the session rather than claiming success; and a still-blocked target cannot close as success.
- The receipt, return-code, and owner-liveness fixtures cover the transport contract without adding authority.

Operator-directed post-G0 source additions: `7fe994abf` (babysitter sandbox plus false-success return-code fix) and `0425372ec` (stdout-tee `BrokenPipeError` helper) are on the epic branch for candidate `astrid-first` (`/workspace/arnold-ref/.git/worktrees/astrid-first`) and were not in the G0 M1–M5 selection. Bind `7fe994abf` to T2.4 and `0425372ec` to T2.4/T7.1 as applicable; do not rewrite the G0 manifest here. T0.2 requires a follow-on additive selection-manifest update card to bind these commits before the affected implementation cards are treated as fully source-bound.

Forbidden within T2.4: no new claim API, rebind writer, seed ceremony, SHA pin, occurrence owner, or live-chain recovery.

Focused tests: bwrap-fail→danger-full-access, false-success rc nonzero, phantom-PID reclaim, live-PID stand-down, fingerprint mismatch, and still-blocked-target closure refusal.

### T2.3 Evidence-bound repair classification

Goal: admit only the complete deterministic review-quality failure shape into the existing repair contract.

Likely files: `cloud/repair_contract.py`, minimal metadata emission in `handlers/review.py`, classifier tests.

Dependencies: current `fce` target/manifest identity.

Acceptance:

- Generic `quality_gate_blocked`, liveness, quota, open-PR, human-only, and awaiting-human states remain non-dispatchable.
- Only complete, scoped evidence with matching cursor, target, digest, and trusted producer provenance can authorize a repair request.
- The phase-contract fence stays: identical `deterministic_phase_failure` fingerprints cannot be mechanically retried without an explicit `repair-commit` bound to `engine_runtime`. Observation, liveness, and babysitter completion cannot waive it.

Focused tests: each rejected class, missing scope, stale target, mismatched cursor/hash, and one valid complete shape.

### Gate G2 `[HARD-REVIEW]` — Authority-entry review

Run scheduler/claim, receipt, repair-contract, and fixer-transport shards, using the P6 verification transport where applicable. The reviewer proves there is one claim point, one receipt identity, and no alternate repair-eligibility path; babysitter session rc, receipt status, and owner-PID liveness cannot disagree, and a still-blocked target cannot close as success. T2.4 is included in this review scope with its focused transport tests.

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

Non-goals:

- automatic `recover-blocked`;
- automatic `runtime-rebind`;
- watchdog replay of a deterministic phase failure without a new repair commit.

Acceptance:

- One observation remains unknown.
- Before code, freeze the stable identity subset (occurrence, plan/cursor, runtime manifest, target digest, source cursor) and the explicitly allowed monotonic fields (observation time and permitted counters). The two observations must match the stable subset; all other drift rejects.
- Independence means distinct underlying source cursors/reads, not two timestamps over the same stale projection.
- PID, tmux, heartbeat, path, or lease presence cannot prove authority.
- The unblocker cannot approve or perform its own effect.
- Replay and stale-lease checkpointing are safe.

Supported fixer-executable recovery contract for `deterministic_phase_failure` with `retry_strategy=repair_phase_contract` (explicit, documented, tested, and not automatic):

1. Land the engine patch on the live `import_root` tree.
2. Until T4.3 deletes the seed gates, update manifest `expected_head` as telemetry only; do not call `advance_generation`.
3. Until those gates are deleted, perform `runtime-rebind` for any remaining content-digest binding using the milestone identity **label** `m7`, never the sequence index `6`.
4. Run `override recover-blocked` with `--repair-commit <sha> --failure-fingerprint <exact> --repair-scope engine_runtime --user-approved`.
5. Run `chain start --one`.

All applicable commands run under the T4.1 seed/import environment. The milestone-label guard accepts `m7` and rejects numeric index `6` with an error identifying `_identity_labels`. The recover receipt authority is `explicit_repair_commit_bound_to_engine_runtime`. After seed-gate deletion, same-import-root is a non-event. The operator may execute this only as the last rung of babysitting 1.3; this sequence primarily specifies fixer verbs, not a standing human runbook. T3.2 remains observation-only and may emit only the typed request/checkpoint naming this sequence; it cannot perform recover-blocked, rebind, or chain start.

The phase-contract fence remains in force: identical `deterministic_phase_failure` fingerprints cannot be mechanically retried without a new repair commit bound to `engine_runtime`.

Focused tests: label `m7` accepted; numeric index `6` rejected with an error naming `_identity_labels`; ambient-root recovery rejected; seed/import-root recovery admitted with the explicit receipt authority; same-import-root post-gate deletion is a non-event; and replay without a new repair commit remains fenced.

Focused tests: changed PID, changed lease epoch, changed runtime manifest, duplicate stale projection with different timestamp, missing evidence, producer/verifier separation, replay, stale fence, no direct mutation, and observation-only fixer-sequence emission.

### T3.3 Read-only six-hour audit enhancements

Goal: port strict window, watermark, cadence, censoring, and deterministic report behavior without control-plane mutation.

Likely files: `cloud/six_hour_auditor.py`, `cloud/progress_auditor_controller.py`, focused auditor tests.

Dependencies: T1.2.

Acceptance:

- Boundary, skew, late, duplicate, out-of-order, censored, and invalid-cadence cases remain deterministic and conservative.
- Missing source evidence produces unknown.
- The auditor is read-only; green never derives from process activity alone.
- Cloud-box verification follows the isolation transport in P6: a test requiring a working bwrap user namespace is invalid infrastructure for this host. When the probe fails, use `--sandbox danger-full-access` with explicit no-mutation and pre/post product-tree fingerprints. Product read-only remains a production-API write prohibition proven by mutation spies and fingerprints.

Focused tests: the focused six-hour auditor/controller shard plus mutation spies.

### Gate G3 `[HARD-REVIEW]` — Migration/recovery review

Run repair-request migration, unblocker, and auditor shards. The reviewer injects interruption at persistence boundaries and verifies that observation code cannot invoke migration or recovery effects.

### Gate G3.5 `[XHARD-REVIEW]` — Midpoint coherence and minimalism

A fresh Grok 4.6 reviewer reads the complete diff from `fce` through G3 rather than reviewing task cards independently.

Acceptance:

- Identity, occurrence, cursor, fence, receipt, evidence, and unknown-state terminology has one meaning across modules.
- No ordinary batch has created a second writer, claim seam, permission gate, migration trigger, or premature action authority.
- The pure observation layers remain useful when mutation evidence is absent.
- Constraints are located at load-bearing boundaries rather than duplicated through callers.
- Redundant checks and adapters are identified for deletion before T4 begins.
- The branch still matches the G0 selection manifest and has not absorbed generated or unresolved policy material.
- Owner-liveness classification for babysitter/watchdog uses a live PID check; a recorded PID is neither authority (SD-005) nor proof of a live owner. Dead-PID-as-live-owner is over-enforcement, phantom-PID stand-down is operational paralysis, and live-PID-as-authority is under-enforcement already forbidden by the settled decisions. T2.4 owns this transport contract; T2.1 remains the sole claim seam.

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
- For `engine_runtime` / `recover-blocked`, `MutationCapability` binds the live tree at `epic.runtime_root` (`import_root`) plus the generation interpreter. Ambient `megaplan_engine_root()` resolved from the container `PYTHONPATH` is not an authority input; on the incident host it resolves to a read-only `-live` tree and causes `phase_repair_commit_mismatch`. The SHA of the import-root tree is telemetry only, never the CAS authority or a new pin.

Acceptance:

- The consumer map is complete for every selected M3b/M4 behavior. Every unrelated mutation surface gets an explicit out-of-scope disposition; this task is not a runtime-wide authorization rewrite.
- Every in-scope mutation path calls the same root permission seam.
- Diagnostic callers remain usable when evidence is incomplete.
- Mutation callers fail closed on missing or contradictory identity.
- Old convenience gates are removed rather than layered beside the root gate.
- Valid downstream receipt/cutover/operator evidence without the root capability still rejects.

- An ambient-vs-seed fixture where ambient `megaplan_engine_root()` is a foreign/read-only tree and seed `PYTHONPATH=<import_root>` is the live tree proves `engine_runtime` admission and `MutationCapability` minting bind the live `epic.runtime_root` (`import_root`) plus the generation interpreter; ambient mismatch is a typed error rather than silent alternate-root selection. Operator recovery commands that admit `engine_runtime` refuse unless process `import_root` equals the manifest tree selector.
Focused tests: permission truth table; stale/live PID combinations; marker/manifest contradiction; stale cursor/fence; valid downstream evidence with absent capability; action/scope replay; complete authorized path; ambient-vs-seed import-root mismatch; static search proving no bypassing in-scope consumer.

### Gate G4.1 `[XHARD-REVIEW]` — Liveness authority attack

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
- The `runtime-rebind` guard accepts milestone identity label `m7` and rejects sequence index `6` with an error identifying `_identity_labels`; rebind cannot be authorized by a numeric sequence index.

Focused tests: permission truth table; stale/live PID combinations; marker/manifest contradiction; stale cursor/fence; valid downstream evidence with absent capability; action/scope replay; complete authorized path; ambient-vs-seed import-root mismatch; runtime-rebind label/index guard; static search proving no bypassing in-scope consumer.

### Gate G4.2 `[XHARD-REVIEW]` — Operator-authority attack

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
- After cutover, an engine commit on the same `import_root` requires no rebind and no generation bump. A test that still requires the two-commit/two-rebind dance after gate deletion is a must-fail.

Focused tests: selector-before-marker/receipt crash, marker/receipt-before-selector crash, every other publication boundary, selector CAS race, absent root capability with otherwise-valid evidence, stale token, live-writer refusal, mismatch, duplicate, and rollback.

### Gate G4.3 `[XHARD-REVIEW]` — Cutover/custody attack

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

### Gate G5 `[XHARD-REVIEW]` — Deadline semantics review

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

### Gate G6.1 `[XHARD-REVIEW]` — Persistence/fence attack

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

### Gate G6.2 `[XHARD-REVIEW]` — Window-closure attack

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

### Gate G6.3 `[HARD-REVIEW]` — Negative-authority review

The reviewer inspects imports and call sites, not only mocks, and proves all M5 outputs terminate at report-only events.

### Gate G6.4 `[XHARD-REVIEW]` — Systemic aggression and simplification review

A fresh Grok 4.6 reviewer assesses the entire implemented branch as one operating system, not as a collection of passing cards.

Acceptance:

- Every path from observation to mutation terminates either at a report-only artifact or at the single typed root capability and its explicitly scoped effect.
- Unknown, stale, partial, or contradictory evidence cannot become green or actionable through composition across modules.
- No ticket, repair, scheduling-policy, provider/model, rebind, pause, delivery, or cutover authority appears outside its settled boundary.
- Repeated enforcement, redundant schemas, compatibility layers with no remaining caller, and accidental policy defaults are removed or explicitly justified.
- A valid diagnostic workflow still functions without mutation authority; safety has not become operational paralysis.
- The reviewer proposes deletions and simplifications, not only additional gates.

- A fixer or diagnostic loop that exits 0, stands down, or reports completed while the target occurrence is still blocked is a must finding, even if a receipt field was later rewritten to failed.
- The reviewer must demand simplification rather than a second occurrence owner or cutover writer. T2.1 remains the sole claim seam; T4.4 remains absent.

## Batch 7 — Convergence, runtime validation, and promotion evidence

### T7.1 Completeness and contradiction audit

Goal: compare the final branch against the G0 selection manifest and all milestone tips.

Dependencies: G6.4 passes.

Acceptance:

- Every selected behavior has code and focused tests.
- Every excluded production patch still has a recorded reason.
- No older identity/manifest/parser implementation overwrote `fce`.
- No duplicate enforcement point or contradictory default remains.
- The successor contains the best-effort stdout writer for managed-provider tees from the epic `resident/subagent.py` helper in `0425372ec`, swallowing both `BrokenPipeError` and `OSError` on begin, chunk, recovery, and end writes. Absence is a must finding even though G0 did not select the hunk: it is a live execute-batch blocker, not an identity concern. This source addition is also a T0.2 follow-on additive selection-manifest obligation; do not edit the G0 manifest here.
- Freeze `docs/arnold/maintenance-runtime-consolidation-evidence/test-shards.json` with exactly nine ordered shard IDs, each shard's full `python -m pytest -q <selectors...>` command, command digest, complete selector/test-file set, changed behavior/task coverage, approved interpreter digest, and disposable-root policy.
- The evidence validator proves every selected behavior and every changed/new test file is covered by at least one intended shard, no test selector/file is assigned to multiple shards, all commands resolve at the current SHA, and shard IDs/order match T7.2.

### T7.2 Integration test shards

Dependencies: T7.1 passes.

Run each of these nine frozen canonical commands once and in order, by a Luna validation agent rather than every implementer. The semantic names below are identifiers; the authoritative exact selectors and command digests come from T7.1's validated `test-shards.json`:

1. contracts, identities, manifests, markers, digests;
2. repair classification, queue migration, unblocker;
3. scheduler claims, receipts, fixer transport honesty (T2.4), delivery, pause/rebind/adoption;
4. status projection, operational policy, six-hour auditor;
5. efficiency sources, unknowns, analysis, baselines, clustering, economics;
6. inert routing, fenced reporting, daily runner, negative authority;
7. test-deadline, feasibility, splitter, validation-job semantics;
8. editable-install/runtime conformance, CLI imports, profile resolution;
9. shared-venv manifest, frozen-spec digest, package provenance, and cross-candidate path isolation.

Every shard records command, commit, environment identity, result, and artifact digest. State-writing tests use an explicit disposable root.

Shard runners on the cloud box follow the P6 transport: probe `bwrap --ro-bind / / -- true`; when namespace creation fails, use `--sandbox danger-full-access` with explicit no-mutation and pre/post product-tree fingerprints. A shard failure caused by bwrap namespace creation is infrastructure, not a product failure. Product read-only remains proven by mutation spies and fingerprints.

### T7.3 Candidate runtime installation proof

Goal: build or update both editable candidate installs to the same successor SHA while preserving their separate project state and environment identity.

Owner: GPT-5.6 Luna through `subagent-launcher`.

Dependencies: T7.2 shards 1–9 all pass and their receipts validate.

Targets:

- `/workspace/runtime-candidates/astrid-first`
- `/workspace/runtime-candidates/arnold-4a830c6ac9a0`

Acceptance:

- The allowed mutation targets are exactly the two candidate roots above; live-chain runtime paths are prohibited.
- Both candidates report the approved source commit, package provenance, frozen-spec digest, runtime-manifest digest, shared dependency-venv manifest digest, and CLI behavior.
- Their interpreter and dependency-venv identity are explicit and verified, while their project-state roots remain distinct.
- Neither candidate's `PYTHONPATH` or editable install resolves to the other candidate or to a live source tree.
- Each update writes an install receipt containing candidate path, prior SHA, installed SHA, source/package/spec/manifest/venv digests, command, and timestamp.

### Gate G7.4-pre `[XHARD-REVIEW]` — Canary contract review

A fresh Grok 4.6 reviewer approves the exact disposable root, allowed candidate operations, prohibited live paths, pre-existing T0.0 baseline, before/after snapshot set, stop conditions, and pointer-only rollback contract. T7.4 cannot start until this review passes.

### T7.4 `[XHARD]` Disposable canary and rollback proof

Goal: prove read-only plan/CLI behavior, fenced daily observation, and immediate pointer-based rollback without touching live state.

Dependencies: T7.3 passes, both candidate install receipts validate, and G7.4-pre passes.

Acceptance:

- The canary uses copied fixtures, a disposable runtime root, frozen spec, and verified venv.
- `config show`, profile resolution, provenance, import, plan read-only paths, event dedupe, and fence outcomes succeed.
- Any live-state write, authority escalation, unexpected model/provider route, or identity divergence stops promotion.
- Rollback selects the prior verified SHA; it does not rewrite data.
- Refresh the same dimensions captured by T0.0 immediately before T7.4 without replacing the immutable T0.0 baseline, then capture post-canary and post-rollback snapshots. Comparisons against both T0.0 and the immediate pre-canary snapshot must be exact except for explicitly disposable-root artifacts and separately approved candidate-install receipts.

### Gate G7.4-post `[XHARD-REVIEW]` — Canary and rollback attack

A different fresh Grok 4.6 reviewer receives the frozen pre-review contract, T7.4 implementation invocation, candidate receipts, command/output evidence, and T0.0-versus-post-run comparisons. It must reject any live-state delta, scope escape, provenance mismatch, non-pointer rollback, missing crash boundary, or narrative-only claim. T7.5 remains blocked until this post-review passes.

### T7.5 Final broad suite and evidence closure

Owner: one dedicated GPT-5.6 Luna validator through `subagent-launcher`.

Dependencies: T7.4 and G7.4-post pass with validated canary and rollback receipts.

Goal: run the broad repository suite exactly once as the final test invocation, then close the machine-readable evidence manifest.

Canonical command, using the approved integration interpreter from the manifest:

```bash
python -m pytest -q
```

Before launch, atomically create the evidence key/lock `broad_suite_once_v1` bound to the current integration SHA, interpreter digest, command digest, Luna invocation ID, and output path. An existing key refuses another launch. The one authoritative invocation writes start/end time, exit status, output artifact/digest, and resource summary. An infrastructure failure blocks G7 and requires an explicit fresh Grok adjudication receipt; it may not be silently rerun or replaced by a second authoritative receipt.

After the suite passes, run the canonical T0.3 evidence validator. T7.5 passes only when the suite receipt and the complete manifest validate with no missing or dangling record.

### Gate G7 `[XHARD-REVIEW]` — Final promotion review

Dependencies: T7.5 passes and the canonical evidence validator exits zero.

An independent reviewer receives only the final diff, selection manifest, shard evidence, candidate provenance, canary evidence, and rollback evidence. A machine-readable evidence manifest links every result to its command, source SHA, runtime/spec/venv digests, disposable-root path, and artifact digest; a missing artifact stops the gate. Promotion is allowed only when all must-level criteria pass. Promotion itself remains a separate explicit operation from code consolidation.

## Agent-sized handoff template

Each task dispatched to its routed Grok 4.6 or Luna agent must contain only:

1. the task card above;
2. the exact source commit/hunks from the G0 manifest when the task ports milestone behavior;
3. the current base SHA and allowed file set;
4. the dependencies already merged;
5. the focused test commands; and
6. the required return schema;
7. the explicit disposable test root; and
8. a prohibition on writing project or live runtime state from tests;
9. verification isolation: if `bwrap --ro-bind / / -- true` fails, investigators and validators run with `--sandbox danger-full-access` under an explicit no-mutation contract and pre/post product-tree fingerprints. Do not use `--sandbox read-only` as the isolation mechanism on this host. Product read-only remains a write-prohibition on production APIs, proven by mutation spies and fingerprints, not by bwrap.

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
