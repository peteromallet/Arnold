# Batch 4 NBF06 acceptance checkpoint

## Decision and scope

This receipt records the Batch 4 acceptance of NBF06 only. It does not accept
NBF08 or NBF07, does not authorize a push, merge, deployment, non-live launch,
or mutation of `main`, and does not alter the frozen NBF06 contract. Earlier
NBF01–NBF05 approvals remain preserved.

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4`
- Branch: `reconcile/nbf-attempt4-2297`
- Parent HEAD before this checkpoint commit: `887c25cf8fddcd14fde24fce49697b9c8b3188b0`
- Accepted task: `NBF-06`
- Oracle: Grok 4.6
- Verdict: `FINAL PASS`
- Next eligible batch: Batch 5 / `NBF-08`

The commit SHA for this checkpoint is the authoritative VCS receipt returned
by Git; it is intentionally not copied into this self-referential artifact.

## Implementation evidence

Only implementation evidence is counted below. The planning brief, acceptance
matrix, research, adjudication, literal vectors, packet hashes, and seals are
contract/provenance artifacts and are explicitly excluded from progress math.

| Gate | Command/result |
| --- | --- |
| NBF06 acceptance | `.venv/bin/python -m pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py` — `54 passed` |
| A32 batch | `...::test_a32_batch_no_second_attempt` — `1 passed` |
| A32 fanout | `...::test_a32_fanout_no_second_attempt` — `1 passed` |
| A32 loop | `...::test_a32_loop_execute_no_second_attempt` — `1 passed` |
| A38 | `python scripts/check_nbf06_a38.py --matrix .oracle/research/nbf06-acceptance-test-matrix.md --allowlist .oracle/research/nbf06-acceptance-test-matrix.md --negative-fixtures tests/arnold_pipelines/megaplan/fixtures/nbf06_a38` — `ALLOWLIST PASS; forbidden=0; negative_fixtures=PASS` |
| Production-door/ledger superset | `.venv/bin/python -m pytest -q tests/cloud/test_managed_physical_door.py tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_physical_doors.py tests/workers/test_omp_adapter.py tests/workers/test_omp_physical_door.py tests/arnold_pipelines/megaplan/test_incident_ledger.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py` — `163 passed` |
| Compile | `.venv/bin/python -m py_compile` over all changed NBF06 production modules and checker — passed |
| Whitespace | scoped source/test staged `git diff --check` — passed; full staged diff reports five retained Markdown hard-break findings in the imported frozen planning/adjudication files (bytes unchanged for custody) |

## Accepted implementation surface

The checkpoint covers the shared provider-resilience policy module, incident
schema/ledger integration, shared dispatch and managed/native/OMP doors,
execute/fanout/fallback safety, directly affected tests, and the A38 checker
and negative fixtures. It introduces no second scheduler, admission authority,
terminal writer, provider projection, rotator, journal, or fallback-selection
door.

The status ledger advances to `6/8 = 75%` and `4/6 = 66.7%`. This is a source-
and-test acceptance count; packet vectors, hashes, seals, and planning
documents do not inflate it. `main` remains unmerged.
