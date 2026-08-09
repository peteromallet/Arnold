# M6-grounded semantic-loop migration gates

## Frozen corpus

CL1 content-addresses the preserved plan
`m6-exact-contract-and-20260716-1303` at repository revision
`ea2be1fe36c42c4f19afedd2c096b5dcec7c56df`. The proof map includes all five
plan/critique/evaluator/gate rounds; producer/raw artifacts; five critique
custody and step receipts; revision metadata; gate signals/carry; state/events;
faults; and exact model/profile/prompt vectors.

Required oracle facts:

- round 4 finding `CF-CD1C58FBC288E3BBA77C` identifies the blocked-prerequisite
  versus missing-artifact drift-checker conflict;
- round 5 contains four semantically equivalent occurrences from correctness,
  verification, criteria quality, and prerequisite ordering;
- `gate_signals_v5.json` reports `recurring_critiques: []` because current code
  compares adjacent normalized concern text;
- all five occurrences remain distinct evidence but reconcile to one semantic
  finding unless adjudicated evidence supports a split;
- the unavailable replay corpus remains an explicit accepted limitation and
  reopens only on its recorded conditions; and
- failed/dropped/malformed producer cases and `no_additional_findings` are
  represented without fabricated findings or clean custody.

## Gate 1 — early reconstruction and thin semantic loop

Before durable migration work, run the CL1 record contract through the frozen
M6 fixture: immutable occurrences → semantic finding identity → disposition and
reopen events → bounded domain briefing → reviser/gate projection. Replay twice
from the same retained bytes. Ordered manifests and projection hashes must match,
with no model call, runtime mutation, or lifecycle write.

Admission to CL2 requires zero lost flagged outputs, 100% mapped parseable
occurrences, explicit unavailable evidence, the five-occurrence/one-finding
oracle, the accepted replay limitation, and fail-closed behavior for missing or
stale custody. This is an implementation gate inside the migration, not a
report-only production phase.

## Gate 2 — integrated semantic loop

CL4 reruns the same oracle through the WBC-backed persistence, evaluator routing,
bounded briefings, reconciliation, reviser, and gate adapters. It also exercises
healthy, duplicate, refinement, regression, reopen, accepted-risk, rejection,
deferral, unknown-evidence, malformed-worker, overflow/split, and valid
no-additional cases.

The integrated gate requires:

- zero dropped flagged producer outputs and 100% reconciliation coverage;
- correct classification of duplicate/refinement/regression/reopen and the four
  distinct zero/no-new claims;
- one structured action/non-action per requested finding;
- no unsupported closure, stale briefing use, silent truncation, false clean
  custody, or ledger-derived lifecycle/gate authority; and
- byte-equivalent projection rebuild from WBC-backed retained inputs.

## Gate 3 — exact-build pre-cutover revalidation

CL5 reruns Gates 1 and 2 against the exact cutover source, schema, WBC, corpus,
model/profile, and configuration revisions after the backup and isolated restore
proof exist. It adds only a bounded healthy new-run smoke case and a deliberate
custody-failure case. Failure keeps admission closed; it never falls through to
a mixed or partially migrated path.

## Durable evidence artifacts

- `docs/critique-ledger/evidence/m6-corpus-manifest.json`
- `docs/critique-ledger/evidence/m6-oracle.json`
- `docs/critique-ledger/evidence/cl1-semantic-loop-gate.json`
- `docs/critique-ledger/evidence/cl4-integrated-loop-gate.json`
- `docs/critique-ledger/evidence/pre-cutover-revalidation.json`
- `docs/critique-ledger/evidence/cutover-backup-restore-proof.json`
- `docs/critique-ledger/evidence/cutover-completion-receipt.json`

Each artifact includes schema version, exact source/implementation revision,
input/output hashes, commands, model/profile/prompt vectors where applicable,
WBC receipt references, acceptance verdict, reviewer, unresolved gaps, and the
next authorized gate. Missing, stale, or mismatched evidence stops the chain.
