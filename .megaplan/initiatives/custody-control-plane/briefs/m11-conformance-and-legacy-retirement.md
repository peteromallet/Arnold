---
type: brief
slug: m11-conformance-and-legacy-retirement
title: Cross-contract acceptance/conformance suite and legacy bypass retirement
epic: custody-control-plane
created_at: '2026-07-13T00:00:00+00:00'
---

# M11 — Cross-contract acceptance suite and legacy retirement

## Outcome

Deliver one comprehensive cross-contract acceptance/conformance suite for Run
Authority, WBC, Custody, lifecycle mutation, and projections across every
supported pipeline surface. Exercise rollback, cross-host custody, persistence,
restart, mixed-version, replay, and reconciliation behavior; retire only legacy
bypasses whose parity and zero-reader/writer gates pass; and generate content-
addressed completion evidence. Completion also requires installed-runtime
canary/live proof and one genuine eligible blocked-run recovery; local tests and
nominal manifests cannot substitute. Scope is no more than two weeks.

M11 closes C01–C20 from
`decisions/m10-m11-structural-conformance-closure-20260723.md`. It consumes the
exact accepted M10 launch/effect/replay handoff and revalidates it byte-for-byte
before initialization, canary, or retirement eligibility.

## Binding 2026-07-27 production-recovery amendment

This amendment is required acceptance scope, not a follow-up ticket. It records
failures observed while recovering M10 on the installed Hetzner worker and
supersedes older topology language in this brief where the two conflict.

- The supported production recovery topology is one durable failure occurrence,
  one non-agent event trigger, one singleton `simple_fixer` operator, at most one
  canonical target runner, and a three-hour missed-event reconciliation
  backstop. Do not re-enable watchdog, L1/L2/L3 investigator, repair-loop,
  meta-repair, periodic audit-agent, or managed-child fanout to satisfy older
  wording. The immediate trigger and three-hour timer must invoke the same
  implementation and share the same singleton/occurrence claim.
- Preserve the existing p95 under-five-minute eligible-blocker-to-accepted-
  repair-or-typed-escalation requirement with the event trigger. The three-hour
  timer is only the independently scheduled missed-event backstop; polling every
  three hours alone does not satisfy the SLO. All older references in this brief
  to hourly watchdog or six-hour recovery topology are replaced by this
  immediate-trigger plus three-hour-backstop design.
- Bind acceptance to the installed path actually used in production:
  `megaplan-progress-audit.service`,
  `/usr/local/bin/arnold-progress-auditor`, its exact systemd environment and
  wrapper hashes, the pinned `MEGAPLAN_SIMPLE_FIXER_SOURCE_ROOT`, the loaded
  `simple_fixer.py` hash/commit, the target marker, and the target runtime
  provenance receipt. A source-only test, editable checkout, prompt snapshot,
  or nominal service status cannot satisfy this canary.
- At M11 initialization, import, hash, and join the three production recovery
  cycles `20260727T183804.052936Z`, `20260727T194726.076432Z`, and
  `20260727T200106.626010Z` from `/workspace/audit-reports/`, including their
  prompts, operator results, transcripts, reports, before/after fingerprints,
  target-runtime cutover/provenance receipts, focused-test evidence, and later
  target events. Preserve the tested target-runtime commit
  `e25f236d16b420881f4aafe87897e119b8d0dd8a`; fail closed if any cited artifact
  is missing, mutable, unredacted, or cannot be bound to the exact occurrence.
- Keep the fixer simple: the model prompt may investigate unknown causes, but a
  small deterministic envelope must enforce the singleton lock, exact durable
  occurrence identity, maximum two unchanged-fingerprint mutation attempts,
  current Run Authority/Custody/WBC action gates before every mutation, one
  canonical target runner, a hard no-child/no-subagent fence, redacted durable
  transcript/result, and typed escalation. Prompt text alone is not proof of
  the no-child fence.
- The repair actor cannot verify itself. A separate verifier must later read the
  exact occurrence, runtime/process identity, target state and receipts at 5m,
  1h, and the next three-hour reconciliation. `state_cursor_advanced` alone is
  insufficient: repeated identical divergence events, phase churn, status-only
  rewrites, a fresh PID, or process presence without accepted work are negative
  controls, not progress. Accepted progress requires a durable task/phase
  acceptance or a fresh run-bound model/tool heartbeat followed by authoritative
  forward movement; terminal repair also requires projection agreement.
- Add the exact divergent-duplicate regression that failed in production.
  Inject a divergent duplicate while transaction cleanup observes an already
  ended transaction or commit failure. `DivergentDuplicateError` must remain the
  primary typed outcome; quarantine must be durable or the result must remain
  typed `INDETERMINATE`; no second terminal row/effect may exist. Restart/replay
  of the same fixture must converge to the same typed result without blind
  retry. A cleanup `OperationalError` may never mask the primary typed failure.
- Add a cross-field phase-result invariant: `blocked_by_prereq` requires at
  least one typed `blocked_tasks` entry after filtering stale projections
  against durably completed task IDs. The producer must reject an empty
  prerequisite block, and the reducer must emit `invalid_phase_result` /
  `classification_incompatible` bound to the exact receipt hash. It must never
  reinterpret the contradiction as a generic quality block or silently retry.
- Add execution-ownership/scope regressions. Every execute batch must carry
  complete batch-scope ownership evidence; unrelated operator/probe files must
  be preserved outside claimed execution ownership. Exact replay must have no
  added/missing files or unclaimed LOC. Repeated
  `authority_divergence: batch_scope_missing_batch_scope` followed by phase
  restart is a failed canary even if a cursor, state hash, or artifact changes.
- Add installed-runtime symbol and review-routing regressions. Every helper
  referenced by the execute/review recovery path, including
  `_attach_next_step_runtime`, must exist in and be exercised from the exact
  loaded runtime; source-only import success is insufficient. Every review
  rework item must bind to one concrete known finalize task ID. A generic or
  unknown ID such as `REVIEW` must become a typed invalid-review/classification
  result and one actionable escalation; it may not be fed back into execute,
  consume rerun attempts, or create an execute/review loop.
- Add cross-surface agreement tests that reject `is_blocked=true` or an
  attention/repairable-failure card after the authoritative occurrence is
  cleared and the plan is validly `executed`, `reviewed`, or finalized without
  a current failure. Conversely, projections may not hide a current durable
  failure merely because a runner exists.

## In scope

- Revalidate the exact M10 source/seed/runtime/process launch manifest,
  materialized M10 snapshot, accepted transaction, and handoff before creating
  M11. Any changed, missing, ambiguous, or unpublished identity is a stop.
- Execute every C01–C20 negative control, including missing/ambiguous chain
  binding, mixed loaded modules, executable/unowned `.pth`, stale selector-bound
  process, wrapper/supervisor drift, fabricated schema fields, request marker
  without decision, syntactic authority, lease/cache/history corruption,
  activity-only recurrence, failed guard output, unregistered repair outcome,
  stale status/review/watchdog evidence, and source-shadowed installed tests.
- Enforce version-gated WBC store/outbox expand/contract, contiguous migration
  checksums, explicit legacy/unknown semantics, and zero old-writer authority.
- Close every residual migration-matrix row with exact prerequisite and M6-M10
  proof, machine-verifiable owner contract, source/runtime/contract hashes, rollback result, and
  retirement evidence.
- Close every generated WBC boundary-inventory row with the named producer and
  consumer owner, implementation commit, start/phase/terminal writers,
  data-policy/migration disposition, static call-site case, captured runtime
  trace, positive test, negative bypass test, and fault/replay evidence.
- Run old-reader/new-writer, new-reader/old-run, cross-version, replay/restart,
  cross-environment, projection delete/rebuild, false-liveness, duplicate/
  partial-persistence, recovery/effect, and static/runtime no-bypass suites.
- Package the matrix as a named, repeatable top-level acceptance suite with
  machine-readable case IDs, owner contract, input version vector, expected
  decision, evidence refs, and raw result digest. Reuse WBC's conformance runner
  where it owns boundary behavior and add custody/Run Authority integration
  cases without copying WBC's owned suite.
- Regenerate the semantic call-site inventory and runtime-trace coverage from
  the exact pinned source/install/runtime revision and require exact set
  equality. Fail on an unexplained call site, an untraced declared contract, or
  a trace with no registered exact-version contract row.
- Exercise the conjunctive action gate for dispatch, repair, completion,
  cancellation, publication, and delivery. Each action passes only with a
  current scoped Run Authority grant/coordinator fence and a current exact-
  occurrence Custody lease/custody epoch; required WBC evidence is then checked
  as boundary completion evidence.
- Prove WBC contracts, ledger events, receipts, findings, payload references,
  RunAuthorityView, CanonicalRunState, custody/status projections, process/tmux
  facts, and terminal artifacts alone cannot authorize any action.
- Exercise stale run revisions, coordinator fences, custody epochs, expired or
  transferred leases, cross-host handoff/reclaim, PID reuse, wrong occurrence,
  T7/T12 and same-basename cross-binding, torn cursor vectors, and orphan custody.
- Exercise duplicate/late/lost/out-of-order triggers and retries, crash between
  every persistence/effect boundary, restart/replay, projection delete/rebuild,
  immediate event triggering, three-hour missed-event reconciliation, and
  delayed independent verification.
- Verify installed/editable/cloud/runtime revision equality and support-manifest
  coverage; test shadow, canary, promotion, kill switch, and forced rollback.
- Run storage migration/backfill and mixed-version acceptance across each
  supported schema, interrupted upgrade/resume, legacy explicit-unknown reads,
  retention/legal hold/tombstone, cross-tenant access, encryption-required and
  missing-key cases.
- Exercise the staged rollout record in isolated/non-production scope in order:
  shadow evidence/telemetry;
  deterministic Transaction Spine and Strategy Roadmap replay; idle projection
  canary; planner/executor canary; repair/worker canary; exact installed-runtime
  reconciliation; then one genuine supported blocked-run recovery. Produce
  deployment/deletion eligibility evidence without performing unauthorized
  production deployment, promotion, or destructive removal.
- Include the captured M5 quality-block chain-of-custody as a named regression:
  structured `failed: <detail>` evidence, canonical classification, eligible
  trigger, single-fixer and canonical-runner provenance, dispatch/launch
  failure, bounded repair, three-hour missed-event reconciliation, and final
  independent outcome must all remain joinable under one exact occurrence.
- For the genuine block, prove durable eligible blocker event, exact signature,
  current Run Authority fence, current Custody lease/epoch, one singleton fixer
  occurrence claim, accepted repair or typed escalation within
  the p95 SLO, authoritative resumed progress, independent 5m/1h/3h checks,
  projection agreement, and no duplicate/replayed effect.
- Prove both outcomes for that regression: a repairable deterministic block
  reaches one accepted repair, while an unapproved or genuinely incoherent case
  reaches one typed human gate. Neither may stall as unknown due to prefix
  parsing, disappear because the immediate trigger was lost, or count as recovered
  without authoritative progress and independent verification.
- Mark raw-state/status/process/marker/sidecar/wrapper/compatibility authority
  bypasses eligible for removal only after their gates pass; preserve required
  read-only historical adapters with explicit expiry. Actual destructive removal
  remains a separately authorized operational effect.
- Create a deliberate proof map and generate the initiative completion manifest
  through the chain lifecycle.

## Out of scope

Rewriting historical events, changing Run Authority or WBC ownership/contracts,
unrelated cleanup, force-proceed, unapproved production deployment/promotion,
or deleting a path because grep or status prose merely suggests it is unused.

## Locked decisions

Retirement requires current Run Authority/WBC manifests, exact-version parity,
zero authority readers/writers, adversarial and projection-rebuild proof,
mixed-version/replay compatibility, canary and forced rollback evidence, and a
machine-generated deletion-eligibility list. Completion is the generated content-addressed
manifest, not a status label, green subset, or hand-authored JSON.

The user phrase "port excipation suit" is interpreted as this comprehensive
acceptance/conformance suite. Repository evidence contains established
acceptance-suite and conformance-suite terminology but no separate
"excipation" or "port exception" contract to preserve.

## Open questions

- Are there any supported-surface exceptions? The target is zero; each proposed
  exception requires an explicit machine-verifiable owner, reason, expiry, and
  proven non-authoritative behavior, otherwise retirement/conformance fails.
- Which historical adapters remain necessary and how is their zero-authority
  property continuously tested until expiry?
- Which production promotion/deployment/deletion actions require operational
  approval after the code/evidence milestone completes?
- Do installed, editable, cloud, and resident runtime revisions and contract
  hashes match the proved source at the promotion gate?

## Constraints

Run only from a clean pinned checkout with current prerequisite manifests.
Deletion and rollout are separate authorized effects; milestone planning or
test completion alone does not authorize production deployment, restart,
promotion, or destructive removal. Rollback must preserve authoritative history
and may not restore legacy write authority.

## Done criteria

- One integrated launch/cutover test joins source and seed binding, target
  checkout/HEAD, runtime vector, marker CAS, supervisor receipt, resident and
  single-fixer process identity, worker preflight, fresh gate, A→B, and independently
  verified B→A. Component-only helper tests cannot satisfy this case.
- One canonical acceptance adapter and target-bound chain loader drive status,
  fixer, advancement, successor admission, resident, and Discord; all C16
  contradictions remain visible and cannot render `done` or accepted progress.
- Static call-site equality and runtime traces prove every provider/effect path
  uses C13's WBC protocol; all C20 retirement predicates pass per path before a
  generated deletion disposition exists.
- Every residual matrix row is canonical or retired with proof; zero unowned,
  unexplained, warn-only, or authority-increasing compatibility exemption remains.
- Every WBC row is `conformant` or a validated read-only `retired` adapter with
  expiry. Schema existence, generated support declarations, unit/fixture-only
  emitters, manual assertions, and best-effort receipts are explicitly
  insufficient; the suite fails if any required implementation/static/runtime/
  negative/fault/migration evidence field is absent.
- Integrated adversarial suites prove exact-version enforcement, controlled
  writers, WBC/runtime adoption, deterministic projection rebuild, pure
  observers, safe retry/recovery/effects, and cross-system agreement.
- The action matrix proves all six action classes reject every single-factor
  case (Run Authority only, Custody only, WBC only, projection only) and accept
  only the correctly scoped current Run Authority plus Custody pair with any
  required WBC boundary evidence.
- Stale fence/epoch and cross-host races accept exactly one owner/action;
  previous owners cannot renew, repair, complete, cancel, publish, or deliver.
- Retry/reconciliation cases are idempotent, repair occurrence identity is
  exact, and persistence/restart/rebuild cases produce no duplicate effect,
  false closure, lost attempt, open terminal custody, or projection authority.
- Static/runtime scans and negative tests prove removed bypasses cannot dispatch,
  advance, repair, retry, publish, deliver, or claim completion.
- Negative scans reject direct legacy writers, missing pre-dispatch starts,
  missing/multiple/post-terminal events, swallowed append/query failures,
  `|| true` wrapper bypasses, raw-state/token/prose authority consumers, and
  implicit-latest contract or migration reads.
- Canary and forced rollback preserve authority/evidence and do not restore dual
  authority; installed/editable/cloud/resident source identity is verified.
- Captured-plan replay covers every F01-F17 traceability row, the idle and
  worker/repair canaries are content-addressed, and installed-runtime
  reconciliation proves exact source/package/wrapper/config/contract provenance.
- One genuine blocked-run acceptance—not a fixture, mocked status, nominal
  manifest, fresh PID, or local repair commit—meets recovery, custody, resumed-
  progress, delayed-verification, and projection-agreement gates.
- Named installed-runtime cases prove: divergent duplicate rollback never masks
  its typed outcome; restart/replay is deterministic; empty
  `blocked_by_prereq` is rejected by producer and reducer; stale blocked
  projections cannot override durable completion; execution ownership/batch
  scope is complete; repeated authority divergence cannot count as progress;
  execute/review recovery has no missing loaded-runtime symbol; review rework
  IDs bind to concrete finalize tasks; and status/attention projections agree
  with the authoritative current occurrence.
- One production-path canary proves durable occurrence → immediate trigger →
  one singleton fixer claim → current action gates → at most one canonical
  runner → accepted progress or one typed escalation → separate delayed
  verification. A second canary drops the immediate trigger and proves the
  three-hour reconciliation catches the same occurrence without duplication.
- The installed canary proves the exact systemd unit, wrapper, pinned fixer
  source, prompt/input digest, target runtime and marker identities; zero new
  managed-agent or legacy-repair manifests/processes; deterministic child-launch
  denial; and the unchanged-fingerprint circuit breaker.
- Productive-versus-replayed ledger coverage exposes unknowns and preserves
  legitimate workload; exact projection-I/O and compaction measurements are
  recorded or remain explicitly unknown rather than inferred as zero.
- A deliberate proof map covers each milestone, matrix row, adversarial case,
  rollback, zero-bypass scan, publication evidence, and prerequisite manifest;
  the chain-generated completion manifest validates against all inputs.

## Touchpoints

All migration-matrix surfaces, compatibility/export/shim/wrapper paths,
packaging/install/runtime identity, tests/CI/docs/runbooks, canary/rollback
controls, prerequisite proof, chain state/publication evidence, proof map, and
completion manifest generation.

## Anti-scope

Do not weaken a gate to make the matrix green, accept nominal completion,
hand-author a manifest, delete WBC/Run Authority-owned surfaces, normalize old
runs by writing them, or perform deployment/restart/promotion without separate
authority. Do not restore a legacy bypass as rollback.

## Stop and rollback conditions

Stop rollout and deletion on any provenance mismatch, replay divergence, false
canary signal, genuine-block failure, legacy authority caller, compatibility
gap, or missing content hash. Forced rollback must disable promotion/effects and
retain the new authority/evidence path; if rollback needs a legacy writer, the
epic is not conformant and cannot complete. Deleted paths remain deleted unless
their separately approved restoration proof preserves single authority.

## Handoff and dependencies

Dependencies: M10 evidence bundle, unchanged M5-M11 plus M6A chain/briefs/North Star,
current Run Authority evidence, the exact audited WBC merge commit and matching
ancestry/support/runtime evidence, machine-generated deletion/promotion eligibility record,
and clean pinned runtime identity. Handoff: chain-generated completion
manifest and proof map, final support/ownership matrix, compatibility expiry
register, canary/runtime-reconciliation/genuine-block receipts, conformance and
rollback reports, legacy deletion/retirement eligibility receipts, and operational runbook.
Any hashed input change invalidates this handoff.

## F01–F17 amendment contract

This milestone is the final acceptance and retirement owner for every F01–F17
row and R1–R3, with specific primary acceptance for F05, F10, and F17. It must
verify predecessor evidence; it may not re-implement or silently waive a row.

- **Prerequisite:** complete M10 evidence bundle, unchanged protected M5/M5A/M6
  definitions, exact M6A–M10 handoffs, and one clean source/install/wrapper/
  config/contract/process vector.
- **Structural amendment:** the complete C01–C20 decision and exact M10 launch
  manifest are predecessor contracts, not optional evidence attachments.
- **First safe action:** from the clean pin, revalidate every manifest,
  recommendation allocation, inventory row, artifact digest, dependency, and
  compatibility expiry before running a canary or marking deletion eligible.
- **Deliverables:** `evidence/f01-f17-completion-index.json`, named top-level
  acceptance suite, exact-runtime trace inventory, captured replay/canary/
  rollback reports, genuine-block receipt, zero-bypass scan, proof map,
  compatibility register, and chain-generated completion manifest.
- **Acceptance evidence:** every F row has scope owner, predecessor receipts,
  positive/negative/fault/migration/replay proof, exact runtime trace, rollback,
  and retirement disposition; R1–R3 measures pass together; no component-only
  or unknown field is coerced to acceptance.
- **Component-versus-wiring safeguard:** schemas, manifests, commits, focused
  tests, fixtures, PIDs, and status labels remain insufficient unless the exact
  supported runtime call site is traced and accepted by its named owner.
- **Version/custody safeguard:** any hash/vector mismatch invalidates the suite.
  Deletion, deployment, restart, promotion, or live-chain mutation remain
  separately authorized operations; this milestone may only produce their
  machine-verifiable eligibility evidence.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. This milestone certifies
global parity and may remove compatibility paths; a locally green but globally
wrong plan could make recovery impossible or permanently violate authority
invariants across the pipeline.
