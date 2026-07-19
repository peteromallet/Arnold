# CL5 — Coordinated cutover, verification, and legacy retirement

## Outcome

Complete one all-at-once migration of the Megaplan critique loop to the accepted
critique-ledger architecture. Verify custody and semantic-loop integrity at the
cutover boundary, retire the replaced path, and leave one supported system with
a content-addressed backup and one bounded whole-cutover recovery procedure.

## In scope

- Revalidate every CL1–CL4 handoff, the exact implementation/source revision,
  WBC contract and receipts, the frozen M6 oracle, and the target environment.
- Produce a content-addressed pre-cutover backup of legacy critique artifacts,
  new ledger inputs/events, payload references, receipts, and restore metadata.
- Quiesce new critique-loop admission, complete or explicitly mark in-flight
  attempts, run the one-time import, and verify occurrence/disposition coverage.
- Switch critic briefings, reconciliation, reviser, gate, and lifecycle-facing
  projections together to the accepted ledger revision; do not stage boundaries.
- Run the minimum fixed-corpus and new-run smoke checks, resume admission only
  after fail-closed custody checks pass, then remove/disable replaced writers,
  readers, flags, and fallback routing while retaining immutable evidence.
- Write the final cutover receipt and retirement proof.

## Cutover checklist

1. Pin source, target, schema, WBC, corpus, and operator-approval revisions.
2. Stop new admissions; drain or mark every in-flight attempt indeterminate.
3. Hash and verify the backup; prove one restore in an isolated fixture.
4. Import retained history once; require complete occurrence accounting and
   explicit `legacy_unknown` for semantics that cannot be reconstructed.
5. Re-run the M6 oracle, replay/projection hashes, WBC receipt checks, and
   negative-authority tests against the exact cutover build.
6. Switch the whole critique loop once; run a bounded healthy and failure smoke
   case; keep admission closed on any missing, stale, or corrupt custody.
7. Retire the replaced path and record the sole supported architecture.

## Bounded recovery procedure

Recovery is allowed only during the cutover window and operates on the complete
cutover, never on individual consumption boundaries. On any failed integrity or
smoke check: stop admission; preserve the failed append-only evidence; restore
the verified pre-cutover bundle and the single prior runtime/config revision;
rebuild projections; verify hashes and WBC receipts; and record the failed
cutover. Do not resume on a partially mixed state or declare convergence. A
second cutover requires a new reviewed receipt against a corrected revision.

## Out of scope

Canaries, cohort allowlists, prolonged shadow/report-only operation, dual-write
windows, broad mixed-version support, per-component rollback, dashboard/SLO
programs, historical semantic invention, generalized knowledge storage, or
authority transfer. This brief does not itself authorize push, deployment,
restart, or destructive cleanup outside the eventual reviewed chain execution.

## Locked decisions

- WBC owns durable attempt/effect evidence, payload references, receipts,
  persistence, and compatibility boundaries.
- The critique ledger owns immutable critic occurrences, semantic finding
  identities, disposition/reopen events, bounded history briefings, and derived
  rebuildable projections.
- Existing Megaplan components retain critic selection, revision, gate, and
  lifecycle authority.
- Missing occurrence coverage, stale briefing inputs, invalid schemas, broken
  payload references, unsupported closure, or receipt/replay mismatch fail
  closed before admission resumes.
- The replaced path is retired after successful cutover verification; retained
  legacy bytes are recovery evidence, not a supported live compatibility mode.

## Open questions

- What exact maintenance boundary and operator own the final cutover command?
- Which in-flight attempt states can drain and which must become indeterminate?
- What retention/access class applies to the pre-cutover recovery bundle?

## Constraints

Consume only accepted CL1–CL4 handoffs and the exact revisions they bind. Stop
on drift, incomplete backup, failed restore proof, custody gaps, or unresolved
authority. The cutover and recovery procedure must remain short enough to review
as one atomic operational change and must not create a standing legacy route.

## Done criteria

- M6 reconstructs the five-occurrence semantic finding and retained replay
  limitation; replay/projection hashes are deterministic on the cutover build.
- Every accepted critic attempt/occurrence has WBC evidence or an explicit
  indeterminate/unavailable result; false clean completion is impossible.
- One cutover receipt binds source/target/schema/corpus hashes, backup identity,
  import counts, smoke results, WBC receipts, operator/reviewer, and timestamp.
- Replaced writers/readers/flags/fallbacks are absent or hard-disabled, and one
  target architecture serves all new critique loops.
- The isolated restore proof succeeds; no production mixed state, canary,
  shadow authority, or prolonged compatibility path remains.

## Touchpoints

Critique/evaluator/reconciler/reviser/gate adapters; WBC persistence, payload,
receipt, and compatibility boundaries; import/backup/restore tooling; exact
cutover configuration; focused corpus, replay, fault, and authority tests.

## Written completion handoff

Write and review `docs/critique-ledger/handoffs/cl5-cutover-completion.json` with
all milestone/handoff/source hashes, M6 and semantic-loop results, backup and
isolated-restore proof, WBC receipts, import/coverage counts, cutover and smoke
receipts, retired-path inventory, unresolved operational facts, and an explicit
`single_target_architecture_active: true`. This is the epic completion evidence.
