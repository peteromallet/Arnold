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

## In scope

- Close every residual migration-matrix row with exact prerequisite and M6-M10
  proof, owner sign-off, source/runtime/contract hashes, rollback result, and
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
  missed-event reconciliation, six-hour backstop, and independent verification.
- Verify installed/editable/cloud/runtime revision equality and support-manifest
  coverage; test shadow, canary, promotion, kill switch, and forced rollback.
- Run storage migration/backfill and mixed-version acceptance across each
  supported schema, interrupted upgrade/resume, legacy explicit-unknown reads,
  retention/legal hold/tombstone, cross-tenant access, encryption-required and
  missing-key cases.
- Execute the staged rollout record in order: shadow evidence/telemetry;
  deterministic Transaction Spine and Strategy Roadmap replay; idle projection
  canary; planner/executor canary; repair/worker canary; controlled installed-
  runtime deployment; then one genuine supported blocked-run recovery.
- Include the captured M5 quality-block chain-of-custody as a named regression:
  structured `failed: <detail>` evidence, canonical classification, eligible
  trigger, managed-worker provenance, dispatch/launch failure, bounded
  meta-repair, six-hour reconciliation, and final independent outcome must all
  remain joinable under one exact occurrence.
- For the genuine block, prove durable eligible blocker event, exact signature,
  current Run Authority fence, current Custody lease/epoch, one managed repair,
  accepted repair or typed escalation within
  the p95 SLO, authoritative resumed progress, independent 5m/1h/6h checks,
  projection agreement, and no duplicate/replayed effect.
- Prove both outcomes for that regression: a repairable deterministic block
  reaches one accepted repair, while an unapproved or genuinely incoherent case
  reaches one typed human gate. Neither may stall as unknown due to prefix
  parsing, disappear because L1 was never launched, or count as recovered
  without authoritative progress and independent verification.
- Remove approved raw-state/status/process/marker/sidecar/wrapper/compatibility
  authority bypasses only after their gates pass; preserve required read-only
  historical adapters with explicit expiry.
- Create a deliberate proof map and generate the initiative completion manifest
  through the chain lifecycle.

## Out of scope

Rewriting historical events, changing Run Authority or WBC ownership/contracts,
unrelated cleanup, force-proceed, unapproved production deployment/promotion,
or deleting a path because grep or status prose merely suggests it is unused.

## Locked decisions

Retirement requires current Run Authority/WBC manifests, exact-version parity,
zero authority readers/writers, adversarial and projection-rebuild proof,
mixed-version/replay compatibility, canary and forced rollback evidence, and an
explicit approved deletion list. Completion is the generated content-addressed
manifest, not a status label, green subset, or hand-authored JSON.

The user phrase "port excipation suit" is interpreted as this comprehensive
acceptance/conformance suite. Repository evidence contains established
acceptance-suite and conformance-suite terminology but no separate
"excipation" or "port exception" contract to preserve.

## Open questions

- Are there any supported-surface exceptions? The target is zero; each proposed
  exception requires explicit owner, reason, expiry, non-authoritative behavior,
  and separate approval, otherwise retirement/conformance fails.
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

- Every residual matrix row is canonical or retired with proof; zero unowned,
  unexplained, warn-only, or authority-increasing compatibility exemption remains.
- Every WBC row is `conformant` or an approved read-only `retired` adapter with
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
  worker/repair canaries are content-addressed, and controlled deployment proves
  exact source/package/wrapper/config/contract/running-process provenance.
- One genuine blocked-run acceptance—not a fixture, mocked status, nominal
  manifest, fresh PID, or local repair commit—meets recovery, custody, resumed-
  progress, delayed-verification, and projection-agreement gates.
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
ancestry/support/runtime evidence, approved deletion/promotion record,
and clean pinned runtime identity. Handoff: chain-generated completion
manifest and proof map, final support/ownership matrix, compatibility expiry
register, canary/controlled-deployment/genuine-block receipts, conformance and
rollback reports, legacy deletion/retirement receipts, and operational runbook.
Any hashed input change invalidates this handoff.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. This milestone certifies
global parity and may remove compatibility paths; a locally green but globally
wrong plan could make recovery impossible or permanently violate authority
invariants across the pipeline.
