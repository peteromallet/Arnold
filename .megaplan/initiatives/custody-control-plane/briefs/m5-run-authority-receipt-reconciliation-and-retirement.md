---
type: brief
slug: m5-run-authority-receipt-reconciliation-and-retirement
title: Run Authority receipt reconciliation and canonical retirement evidence
epic: custody-control-plane
created_at: '2026-07-14T00:00:00+00:00'
---

# M5 — Run Authority receipt reconciliation and retirement

## Outcome

Reconcile the three landed Run Authority milestones against their authoritative
committed ranges and current runtime, replace stale or missing completion
evidence with freshly generated content-addressed evidence, obtain three
`accepted: true` completion receipts, prove a canonical verification result
with zero divergences, and establish durable canonical retirement evidence.
This sprint repairs proof and retirement custody; it does not extend or
reimplement the Run Authority product.

## Known starting evidence

- The exact retirement target is the canonical initiative
  `.megaplan/initiatives/runauthority-epic/`, whose chain identity is
  `runauthority-epic` and whose canonical cloud session is
  `runauthority-epic-cloud`. A similarly named display label or duplicate
  session is not sufficient identity.
- The canonical Run Authority plans are
  `sprint-1-authority-freeze-and-20260710-1935`,
  `sprint-2-dispatch-grants-and-20260710-2200`, and
  `sprint-3-consumer-migration-20260711-0130`.
- All three current `completion_verdict.json` receipts have `accepted: false`.
  M1 and M2 report stale phase/task evidence, landed-diff mismatches, and
  structural collection/import failures. M3 additionally lacks durable output
  for `pytest tests/arnold_pipelines/run_authority/test_reducer.py -v`.
- A fresh local run of that M3 reducer suite currently passes 12/12. This is an
  input fact only until its command, source/runtime revision, raw output,
  timestamp, exit status, and digest are bound into the canonical evidence set.
- `megaplan chain verify` currently returns three rejected milestones and three
  divergences. The existing completion manifest and nominal `done` chain state
  are therefore claims to reconcile, not sufficient admission evidence.
- The redundant `runauthority-epic-all-codex` session has a reported retirement
  record `ret-2e1f0059d83e503a9023` and tombstone SHA-256
  `599e36f5f20e20849294441fd5cae843fc70411f0274512d92250dc2721d187f`.
  M5 must resolve the canonical stored tombstone and independently verify its
  target, hashes, non-actionability, and preservation of canonical assets; the
  prior Discord report is not itself retirement authority. That duplicate-
  session tombstone is supporting evidence only; it cannot retire the canonical
  `runauthority-epic` initiative.

## In scope

- Pin each milestone's actual base/head/merge commits, PR publication evidence,
  claimed files, landed committed range, current content addresses, plan state,
  phase result, finalize snapshot, suite ledger, review, and completion receipt.
- Reconcile stale/missing phase evidence and landed-diff/content-address
  mismatches from source facts. Regenerate evidence through supported Megaplan
  receipt/verification paths; never edit a receipt to force acceptance.
- Resolve every structural collection/import error behind the M1, M2, and M3
  green-suite failures. Baseline or shadow status may not waive collection,
  import, missing-test, or selector failures.
- Rerun and durably bind the M3 reducer suite's 12/12 result to the exact source,
  runtime, command, raw log, exit code, suite ledger entry, phase/task evidence,
  and content digest consumed by M3's completion receipt.
- Generate fresh accepted completion receipts for all three milestones, then
  run the canonical Run Authority chain verification from a clean pinned
  checkout and require `verified_count: 3`, `divergence_count: 0`, and
  `accepted: true` for every milestone.
- Regenerate the Run Authority proof map and completion manifest only through
  supported lifecycle commands after the receipts and zero-divergence check
  pass. Bind chain, North Star, brief, state, publication, proof, receipt, and
  runtime hashes.
- After, and only after, the three receipts are accepted and canonical
  verification reports zero divergences, write the established metadata-only
  retirement marker at
  `.megaplan/initiatives/runauthority-epic/.retired`, with
  `superseded_by: custody-control-plane`, an actual UTC retirement timestamp,
  and `scope: metadata_only`. Do not create or stage this marker earlier.
- Produce a machine-readable retirement attestation under this initiative's
  M5 handoff that binds the exact `runauthority-epic` identity, canonical chain
  state, all three accepted receipt digests, zero-divergence verification
  digest, regenerated proof/manifest digest, and `.retired` marker digest. Bind
  the retired duplicate-session tombstone, fresh absence/non-actionability
  checks, preserved workspace/execution evidence, and zero remaining live
  duplicate Run Authority session/marker as supporting evidence. Retirement
  must not delete canonical source, plans, chain state, proof, or audit evidence.

## Out of scope

New Run Authority semantics, migration/adoption work assigned to M6-M11/M6A, WBC
implementation, hand-authored acceptance receipts or manifests, weakening the
completion contract, deleting canonical evidence, launching another Run
Authority chain, creating the canonical `.retired` marker before all proof gates
pass, or treating a resident status label/Discord message as proof.

## Locked decisions

M5 may begin with rejected Run Authority receipts because producing accepted
receipts is its purpose. Nominal chain completion, merged PRs, a green reducer
subset, or a session tombstone alone cannot satisfy M5. Evidence is accepted
only when it is fresh for the declared committed range and exact current
content. A mismatch remains a blocker; it is never normalized by changing the
expected hash to whatever happens to exist.

The chain runs serially and M6 explicitly depends on M5. The M5 PR must remain
behind manual review/merge. No later sprint may be admitted until the reviewer
checks the three accepted receipts, the zero-divergence canonical verification,
the regenerated content-addressed manifest, the canonical
`runauthority-epic/.retired` marker, and its retirement attestation. Failure or
uncertainty stops the chain.

Before M5 execution, the operator must durably record completion-contract and
full-suite-backstop enforcement for the chain. `off`, `shadow`, or `warn` is not
an admissible execution posture for this proof sprint; a default shadow status
is a preflight blocker, not a waiver.

## Done criteria

- M1, M2, and M3 each have a freshly generated `completion_verdict.json` with
  `accepted: true`; every evidence ref resolves, matches its recorded digest,
  and is current for the authoritative committed range.
- No phase task is stale or missing required output; claimed files match landed
  content; worker activity evidence is readable; structural suites collect and
  import without error; no baseline/shadow waiver masks a structural failure.
- The M3 reducer evidence records 12 passed tests and is durably referenced by
  M3 phase, suite, and completion evidence with exact source/runtime identity.
- Fresh canonical `chain verify` reports all three milestones accepted and
  exactly zero divergences from a clean pinned checkout.
- The lifecycle-generated Run Authority proof map and completion manifest
  validate against the current chain/North Star/briefs, accepted receipts,
  landed publication evidence, and canonical chain state.
- The canonical `.megaplan/initiatives/runauthority-epic/.retired` marker exists
  only after the accepted receipts and zero-divergence verification, names
  `custody-control-plane` as successor, records its actual retirement time in
  UTC, and is content-addressed by the retirement attestation.
- The retirement attestation proves the exact canonical initiative/chain/state
  identity and accepted proof bundle. It also proves the duplicate session's
  exact tombstone, non-actionability, zero live duplicate markers/sessions, and
  preservation of the canonical initiative, workspace, plans, and evidence.
- The M5 handoff contains the commands, exit codes, raw-artifact references,
  hashes, and independent verification needed for manual admission. Any missing,
  stale, rejected, unknown, or divergent item blocks merge and M6.
- Chain runtime evidence records completion-contract and full-suite-backstop
  enforcement before execution; the manual merge gate remains a second,
  independent admission boundary.

## Touchpoints

`.megaplan/initiatives/runauthority-epic/` (including its eventual `.retired`
marker), its three plan directories and canonical chain state,
completion-contract providers/receipt tooling, suite selection and raw
verification logs, Git/PR publication evidence, constrained resident retirement
records, and this initiative's M5 handoff/evidence bundle.

## Anti-scope

Do not relaunch the completed Run Authority epic, rewrite its implementation to
fit stale receipts, copy a passing terminal line into a hand-authored JSON file,
pre-create `.megaplan/initiatives/runauthority-epic/.retired`, delete the retired
session's workspace/evidence, or accept `done`, merged PRs, manifest presence,
or zero live process as a substitute for current proof.

## Handoff and dependencies

Entry dependencies are the landed three-milestone Run Authority source/history,
readable canonical plans/chain state, and access to the constrained retirement
record. Accepted receipts are deliberately not an entry dependency. Handoff to
M6: three accepted content-addressed receipts, zero-divergence verification,
regenerated Run Authority proof/manifest bundle, canonical retirement
marker and attestation, and an empty unresolved-evidence list.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex +prep`. This is evidence
reconstruction across historical commits, plan artifacts, structural suites,
and resident retirement custody. A superficially green but content-mismatched
result would incorrectly authorize every later migration sprint.
