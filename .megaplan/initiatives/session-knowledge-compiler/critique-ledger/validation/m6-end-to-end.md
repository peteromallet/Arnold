# M6-grounded end-to-end validation sequence

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
  finding unless blinded adjudication supplies evidence for a split;
- the unavailable replay corpus remains an explicit accepted limitation and
  reopens only on its recorded conditions;
- failed/dropped/malformed producer cases and `no_additional_findings` are
  represented without fabricating findings or clean custody.

## 1. Offline reconstruction

Run a read-only curator/replayer against the frozen corpus. It must create an
ordered occurrence inventory, cumulative finding set, per-domain projections,
disposition/reopen history, briefing candidates, and a completeness map without
calling models or mutating plan/runtime state. Replay twice from the same bytes;
manifests and projection hashes must match. Independent evidence checks verify
all input hashes and WBC references.

Admission requires zero lost flagged outputs, 100% mapped parseable occurrences,
all unavailable evidence explicit, and the blocked-handoff oracle above. A
semantic disagreement is recorded as uncertain and sent to adjudication; it is
not forced into a deterministic merge.

## 2. Controlled comparison

Evaluate four arms on identical plan snapshots:

1. current-context control;
2. history-preloaded critique;
3. blind discovery followed by history-aware reconciliation;
4. recommended hybrid with optional blind pass, bounded domain briefing,
   reconciliation, and deterministic custody/freshness.

Hold brief, repository/runtime revision, lens assignment, evidence access,
output budget, and all non-context prompt text constant. Run once with the
original mixed profile and once with a fixed homogeneous critic model. Blind
judges classify semantic families, evidence quality, false merges/closures,
novel findings, duplicated actions, and disposition correctness. Results must
remain attributable to exact input/model/prompt versions.

## 3. Report-only shadow

For ordinary new critique runs, create candidate occurrence/ledger/briefing and
comparison reports beside the legacy path. Shadow may not alter critic
selection, prompts, revise input, gate verdict, plan/chain state, or delivery.
WBC receipts and negative mutation probes prove zero authority leakage.

Observe enough rounds to cover every enabled robustness/profile family and at
least the named failure classes: duplicate wording, refinement, regression,
reopen, accepted risk, rejection, deferral, unknown evidence, malformed worker,
stale briefing, overflow/split, rollback, and valid no-additional outcome.

## 4. Gated canary

Enable history-aware briefing/reconciliation only for an explicit allowlist of
new plan IDs. Preserve legacy artifacts and candidate artifacts. Start with
selection/briefing only, then reconciliation, then reviser/gate consumption;
each promotion requires reviewed evidence from the prior boundary. Any automatic
rollback trigger disables candidate consumption and restores the legacy route.

Canary does not authorize broad deployment, old-reader deletion, service
restart, or retroactive migration.

## Acceptance metrics

- zero dropped flagged producer outputs and 100% reconciliation coverage;
- 100% recall of named M6 regression/rediscovery families;
- at least 50% fewer duplicate revision actions than control;
- no more than five percentage points lower independent new-family recall;
- at least 95% evidence support for closure and non-action dispositions;
- zero suppressed significant concerns, false clean custody, stale briefing use,
  or ledger-derived authority mutation;
- correct classification of duplicate/refinement/regression/reopen and the four
  distinct zero/no-new claims;
- bounded context-token/latency overhead within the CL1-approved budget, with no
  silent truncation; and
- mixed-version, replay, disable, and rollback suites fully passing.

## Durable evidence artifacts

- `docs/critique-ledger/evidence/m6-corpus-manifest.json`
- `docs/critique-ledger/evidence/m6-oracle.json`
- `docs/critique-ledger/evidence/offline-replay-report.json`
- `docs/critique-ledger/evidence/controlled-comparison-report.json`
- `docs/critique-ledger/evidence/blind-adjudication-report.json`
- `docs/critique-ledger/evidence/shadow-observation-report.json`
- `docs/critique-ledger/evidence/canary-promotion-receipts.json`
- `docs/critique-ledger/evidence/rollback-rehearsal.json`
- `docs/critique-ledger/evidence/final-conformance-manifest.json`

Each artifact includes schema version, exact source/implementation revision,
input/output hashes, commands, model/profile/prompt vectors where applicable,
WBC receipt references, acceptance verdict, reviewer, unresolved gaps, and the
next authorized gate. Missing or stale evidence stops promotion.
