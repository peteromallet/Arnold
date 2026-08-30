# Receipt: NBF-01 rework 2 Luna executor

Classification: executor evidence, not oracle review

Date: 2026-08-30 (Europe/Berlin)
Repository: /Users/peteromalley/Documents/Arnold-oracle-nbf
Executor: GPT-5.6 Luna / Normal executor

## Candidate binding

- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Frozen tasklist digest: 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
- North Star digest: d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
- Rework attempt-2 digest: 6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721
- Prior Grok check-in digest: 2d82e2d09e1ff7e49ac895878a5cbabc19e19dda4d109bd528da54c83e6b79a8

The frozen tasklist was not mutated. No commit, push, Batch 2 launch, or historical evidence rewrite occurred.

## Fresh results

All commands ran from /Users/peteromalley/Documents/Arnold-oracle-nbf, exited 0, and had empty stderr.

| exact command family | result | stdout SHA-256 |
| --- | --- | --- |
| focused NBF + test_incident_ledger.py | 101 passed | b65c234b540a8ba455d4d8aedd6643801fe1f216e44f1206b4511bb7589eae0a |
| transaction -k "two_process or torn or crash or contention" | 5 passed, 8 deselected | 142ef7303768015839a001696a5be491b5038a99745f38f3c82e2924547d1a50 |
| provider -k "replay or receipt or keyed" | 4 passed, 6 deselected | 382a52f030b0e847fff2af67160f51aa026553bf424e2b1f27fdb89b432aa4c3 |
| confirmation -k "cli or confirmation or incarnation or reopen" | 6 passed | e3184752be711e1a9894f4e87ac586c9888a5cebd407de809432fd27354b8bcc |
| required legacy incident/phase set | 78 passed | 7a485e5ac5b4bcfcc4d2e9634304d027e360eab8fd581f38f5612b029598fe32 |
| required python -m py_compile ... | exit 0, no output | e3b0c44298fc1c1499baf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| git diff --check | exit 0, no output | e3b0c44298fc1c1499b934ca495991b7852b855 |

The full exact argv and displayed outputs are in the companion executor finding.

Explicit CLI subprocess cases passed for statuses 0, 2, 3, 4, and 5. The status-0 case required a consumed, identity-matching worker confirmation and emitted one JSON acknowledgement without signalling. Status 2 was exercised for malformed and schema-invalid input; status 3 for valid-location append failure; status 4 for invalid location; and status 5 for missing and already/differently-consumed confirmation.

## Production digest

Exact tracked-production diff command:

    git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256

Tracked-production diff digest: 16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d

Untracked owned production file:

    arnold_pipelines/megaplan/incident/disposition.py
    git hash-object: 5fb675a96d0ce096af881a3feadcdc8b31c8cc65
    shasum -a 256: 8212c519d1afcaba5f4fa9aa3be7a23d753ec2ad5ed9662572c79b457af0b38a

## Owned-file manifest

The following are the git hash-object / shasum -a 256 pairs from the fresh receipt capture. The five modified production files are represented in the tracked diff digest above; the new production and eight new test modules are listed explicitly here.

    arnold_pipelines/megaplan/incident/disposition.py
    5fb675a96d0ce096af881a3feadcdc8b31c8cc65
    8212c519d1afcaba5f4fa9aa3be7a23d753ec2ad5ed9662572c79b457af0b38a

    tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
    b6cedc6cb4f7d806e95c41339930a4a9f6803363
    79d59501de3d3f11924b86764f757629de312064d3e06f2f84477a5e19dca547

    tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
    d45fb936d69f90954f09e267662e50503e6b62f0
    522903756431534096d2d0d1205834b878b0cbfa33a166229ff4fcd0ac65f5a4

    tests/arnold_pipelines/megaplan/test_provider_route_projection.py
    e3fe6f278345eadae1a2335d912ee97ac78d790b
    c644f550273afde279d5adff4527c5821a8850c24a3b46019832ec956b39fa0c

    tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
    be6bee9ff18e6ae9343e843095ddd7f67429af72
    a013b4d2de9e43857cc5cdc12bd9a304177bee0f536d1d3eac6817f0047a48eb

    tests/arnold_pipelines/megaplan/test_scheduling_conditions.py
    fc54999a025f23d89860facda94b260d1d7e5bb3
    2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb

    tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
    1bf257c63450a6fe7214625dffbbeff44b6ee46b
    7b2e40eafde4e3fca4cbf6831337455d7e138bf8cf4155c5544c0d0ff0978759

    tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
    0fd46e4d02c1aa89be265291e256d6fca705472a
    7fd0fedcb70251c62a04abdc2456365172c8fc3a72b3af909973ba19d0cb8497

    tests/arnold_pipelines/megaplan/test_worker_disposition.py
    ed2f3281e72c624fed7ea1eaf0cb4fc317119b4f
    a75ec92d7426b794c24567ce00cbb09040edc2cbc289e77a3ff528ec81b38991

## Executor boundary

The implementation is complete and fresh executor validation is green. This receipt intentionally stops at executor evidence. It does not self-issue an oracle verdict, commit, push, or start Batch 2.

