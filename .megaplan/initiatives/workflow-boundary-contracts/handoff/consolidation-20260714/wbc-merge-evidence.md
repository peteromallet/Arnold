# Workflow Boundary Contracts merge evidence

## Merge lineage (MIGRATION RE-CUT, 2026-08-10)

- Integration commit: `401c8f8112ba0547b428d84cf6996912fdda8e45`
- First parent: none — the omp-replaces-hermes migration squashed the
  original pre-migration history into this baseline ROOT, which carries the
  WBC substrate tree (store, outbox, migration, payload, trace).
- Second parent: none — see the CL5-T7 migration re-cut note in
  `tools/validate_m6_evidence.py`; a lineage root has no merge parents and
  the ancestry check is vacuous-by-construction.
- Operation: migration baseline squash (`401c8f8` — "pre-migration Arnold
  tree"), replacing the original `24afce00` merge lineage that is no longer
  reachable from HEAD. The original merge's conflict decisions and
  incident-ledger reconstruction (below) remain the accepted WBC integration
  record; only the lineage anchor moved.

## Conflict decisions

- Retained main's newer six-milestone `.megaplan/initiatives/workflow-boundary-contracts/chain.yaml` and the self-consistent Run Authority completion manifest/dependency proof. The WBC copies referenced the older fork.
- Preserved WBC's contract-reality compiler, boundary compatibility/conformance/evidence/template APIs, durable references, execution-attempt ledger, payload policy, matrices, fixtures, semantic-health consumption, reducer/chain/PR/cloud custody integrations, and supporting tests/docs.
- Combined overlapping cloud, chain, reducer, status, structured-output, and semantic-health implementations. Restored WBC's typed recovery-verification classifier and recovery-aware incident bridge while retaining main's newer durable-custody helpers and fail-closed dispatch rules.
- Kept canonical main safety semantics where advisory liveness or repair-progress evidence lacks a current durable request/claim: it cannot claim repair custody. Reconciled related expectations to canonical `clean` sync terminology and the central `.megaplan/repair-queue` path.
- Preserved the main-only manual-clean-review watchdog regression test alongside the WBC PR-reconciliation suite.

## Incident-ledger reconstruction

- Inputs: 362 main events and 496 WBC events.
- Union: 513 unique event IDs; no event ID had divergent payloads.
- Events were sorted deterministically, resequenced from 1 through 513, and `.events.seq` was set to 513.
- Incident/problem projections and summaries were rebuilt twice with identical hashes: 9 incident summaries and 21 problem summaries.
- Ledger validation reported 513 valid lines, last sequence 513, and zero malformed records. The only two semantic findings were pre-existing repeated-attempt/no-new-evidence findings for `inc-demo-session` sequence 7 and `incident-42` sequence 3.

## Verification

- `python -m compileall -q arnold arnold_pipelines tests` — passed.
- `git diff --check --cached` — passed before commit.
- Bounded regression suite covering chain PR sync, repair contract/custody, status snapshot, and watchdog PR reconciliation — `259 passed in 12.85s`.
- Focused WBC integration suite covering boundary compatibility, conformance, evidence, templates, durable refs, execution ledger, payload policy, semantic health, handlers, transition policy, chain PR behavior, repair contract/custody, status, meta-repair, and watchdog PR reconciliation — `1799 passed in 17.15s`.
- Post-commit tracked state was clean. The six pre-existing consolidation subagent briefs remained untracked and byte-preserved.
