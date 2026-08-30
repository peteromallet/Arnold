# NBF-01 Rework 2 — Luna executor evidence

> **Executor evidence, not oracle review.** This records implementation and validation by the Normal/Luna executor. It does not issue PASS_BATCH_1 or ACCEPTED_ISSUES.

Date: 2026-08-30 (Europe/Berlin)
Repository: /Users/peteromalley/Documents/Arnold-oracle-nbf
Executor: GPT-5.6 Luna / Normal executor
Rework: NBF-01, Batch 1, rework attempt 2

## Provenance and freeze

- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- origin/main resolved to that exact commit; it is an ancestor of the candidate HEAD.
- Frozen tasklist SHA-256: 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
- North Star SHA-256: d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
- Rework instructions SHA-256: 6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721
- Prior Grok check-in SHA-256: 2d82e2d09e1ff7e49ac895878a5cbabc19e19dda4d109bd528da54c83e6b79a8

The frozen tasklist was not edited. No commit, push, rebase, reset, staging, Batch 2 start, or historical-artifact rewrite was performed.

## RW2 implementation result

RW2-01 through RW2-04 were implemented in the existing NBF seams:

- one locked journal compare/read/append/replay path with fail-closed strict schema validation, reservation and terminal context binding, atomic idempotent terminal linkage, positive reconciliation evidence, and single-use changed-precondition authorization;
- complete dispatch-outcome incompatibility checks and strict producer, authoritative-snapshot, evidence-digest, OOM, unknown-death, and identity validation;
- provider replay keyed by phase/route/fallback configuration/provider key, with applicable-key reset, rekey, streak break, probe/recovery linkage, and one composite child reservation with deterministic post-commit receipt;
- durable two-scan confirmation identity, replacement, expiry, reopen/replay, locked single consumption, and non-signalling CLI status routing;
- removal of the listed unofficial ledger/schema/constructor aliases and the unconstrained reason-specific producer **kwargs surfaces;
- named behavioral tests for every previously marked NBF hole, including a real child-process crash after locked read and before append, a torn composite record, two-process terminal/confirmation races, keyed replay, CLI statuses 0/2/3/4/5, and legacy regression coverage.

Previously accepted MET behavior was preserved, including one event journal, one sequence-sidecar flock, strict no-launch/worker disposition separation, lossless phase-result mapping, no coercion, fingerprint/key volatile-field exclusions, composite reservation shape, no provider mutation for scheduling or no-launch, and no second store.

## Exact validation transcripts

Working directory for every command below:
 /Users/peteromalley/Documents/Arnold-oracle-nbf

All commands exited 0. stderr was empty for each command. The listed stdout SHA-256 values were captured from a fresh rerun of the exact command with stdout piped to shasum -a 256; the displayed output is the unpiped fresh run immediately preceding that capture.

### Focused NBF + unchanged legacy ledger module

    pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_incident_ledger.py

    ........................................................................ [ 71%]
    .............................                                            [100%]
    101 passed in 15.84s

Exit: 0 | stdout SHA-256: b65c234b540a8ba455d4d8aedd6643801fe1f216e44f1206b4511bb7589eae0a | stderr: empty

### Adversarial transaction/crash/lock subprocesses

    pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py -k "two_process or torn or crash or contention"

    .....                                                                    [100%]
    5 passed, 8 deselected in 2.20s

Exit: 0 | stdout SHA-256: 142ef7303768015839a001696a5be491b5038a99745f38f3c82e2924547d1a50 | stderr: empty

### Keyed provider replay and receipt adversaries

    pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py -k "replay or receipt or keyed"

    ....                                                                     [100%]
    4 passed, 6 deselected in 0.33s

Exit: 0 | stdout SHA-256: 382a52f030b0e847fff2af67160f51aa026553bf424e2b1f27fdb89b432aa4c3 | stderr: empty

### Confirmation/reopen/CLI-adjacent adversaries

    pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py -k "cli or confirmation or incarnation or reopen"

    ......                                                                   [100%]
    6 passed in 0.37s

Exit: 0 | stdout SHA-256: e3184752be711e1a9894f4e87ac586c9888a5cebd407de809432fd27354b8bcc | stderr: empty

### Required legacy incident/phase regressions

    pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py

    ........................................................................ [ 92%]
    ......                                                                   [100%]
    78 passed in 1.86s

Exit: 0 | stdout SHA-256: 7a485e5ac5b4bcfcc4d2e9634304d027e360eab8fd581f38f5612b029598fe32 | stderr: empty

### Compile gate

    python -m py_compile arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/disposition.py

Result: no output. Exit: 0 | stdout SHA-256: e3b0c44298fc1c1499baf4c8996fb92427ae41e4649b934ca495991b7852b855 | stderr: empty

### Diff whitespace gate

    git diff --check

Result: no output. Exit: 0 | stdout SHA-256: e3b0c44298fc1c1499b934ca495991b7852b855 | stderr: empty

### Explicit CLI subprocess coverage

The focused run collected and passed these subprocess tests. Each invokes this exact argv from the repository cwd, with a pytest-created temporary ledger root and JSON on stdin:

    python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <pytest-temporary-ledger-root> --json-stdin

Cases and observed statuses:

- test_cli_status_0_one_json_ack_no_signal: status 0, one JSON ack, consumed matching worker confirmation, no signal;
- test_cli_status_2_malformed_or_schema: status 2 for malformed JSON and schema-invalid JSON even when confirmation is absent;
- test_cli_status_3_append_or_lock_failure: status 3 for valid payload at a valid ledger location whose append path is an unusable directory;
- test_cli_status_4_invalid_ledger_location: status 4 for a file supplied as the ledger location;
- test_cli_status_5_missing_and_already_consumed_confirmation: status 5 for missing and already/differently-consumed confirmation.

## Owned production diff digest

Exact frozen tracked-production digest command:

    git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256

Observed digest: 16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d

New untracked owned production file:

- arnold_pipelines/megaplan/incident/disposition.py
  - git hash-object: 5fb675a96d0ce096af881a3feadcdc8b31c8cc65
  - shasum -a 256: 8212c519d1afcaba5f4fa9aa3be7a23d753ec2ad5ed9662572c79b457af0b38a

Production source SHA-256 manifest:

    8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923  arnold_pipelines/megaplan/incident/__init__.py
    34a5231bd1b9bf00f591e73019e8e5f82ac8d520c03ede3e1974380cdd643fcc  arnold_pipelines/megaplan/incident/ledger.py
    87ddcd85df7309def841ef39f315f9427863a1445e5369d33af75e72d1466276  arnold_pipelines/megaplan/incident/schema.py
    8212c519d1afcaba5f4fa9aa3be7a23d753ec2ad5ed9662572c79b457af0b38a  arnold_pipelines/megaplan/incident/disposition.py
    18f500c8ed2870a22bcdc5a64ec8ec6af8ca5bd099f2e00d5a11722563bad259  arnold_pipelines/megaplan/orchestration/phase_result.py
    a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641  arnold_pipelines/megaplan/orchestration/phase_result_classify.py

## Evidence-integrity notes

- Historical 52-vs-61 count discrepancy and unreproducible 4aee815d... digest remain historical evidence-integrity failures of the original handoff; they were not rewritten.
- Attempt-1 78/78 and e060f650... remain historical observations, not targets or newly claimed evidence.
- This is executor evidence only. A separate oracle review is still required for any Batch 1 acceptance decision.

