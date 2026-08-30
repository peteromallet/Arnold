# NBF-01 Batch 1 rework execution — Luna attempt 1

Date: 2026-08-30
Worktree: /Users/peteromalley/Documents/Arnold-oracle-nbf
Branch: megado-nbf-guard-0826
Base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
Tasklist: .oracle/rework/batch-1-attempt-1.md (sha256 5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c)
Triage receipt: .oracle/receipts/rework-triage-batch-1-attempt-1-grok.md (sha256 7565016b618293fa666f61710f0f95bb8847d6d2336568ff064d8843699efa1e)

## Scope and result

Executed RW-02 -> RW-01 -> RW-03 -> RW-04 -> RW-05 -> RW-06. All were Normal / GPT-5.6 Luna; no [XHARD] item was present. RW-CUSTODY was executed by the separately authorized Luna worker; receipt: .oracle/receipts/rework-nbf01-custody-luna.md (reported digest prefix 48f540c4). I did not edit custody.md, commit, push, rebase, merge, mutate the frozen tasklist/plan, start Batch 2, or touch later-batch launch/admission/T7/T8 owners.

Implemented strict outcome matrix and typed evidence checks; moved NBF read/compare/consume/append decisions for reservation, terminal, child, reconciliation, changed-precondition, probe, and confirmation operations into the existing sequence-sidecar fcntl.flock door; added reservation context binding, keyed provider replay state, reason-gated changed-precondition producers, durable confirmation replacement/expiry/reopen validation, and non-signalling CLI status routing. Added behavioral regressions in the eight named modules, including OS-process contention, torn replay, forged IDs, incompatible payloads, keyed streams, confirmation identity, and fresh-replay receipt identity.

## Immutable command transcripts

Commands ran from the worktree root; output is reproduced verbatim.

    $ pytest -q [exact frozen focused command: the nine named NBF modules]
    ........................................................................ [ 92%]
    ......                                                                   [100%]
    78 passed in 0.65s

    $ pytest -q [exact frozen legacy command: projection, summaries, bridge, phase_result_classify]
    ........................................................................ [ 92%]
    ......                                                                   [100%]
    78 passed in 2.66s

    $ pytest -q test_incident_ledger_transactions.py test_terminal_outcomes.py test_reservation_reconciliation.py
    .........                                                                [100%]
    9 passed in 0.30s

    $ pytest -q test_incident_ledger_transactions.py -k "two_process or torn or crash or contention"
    ...                                                                      [100%]
    3 passed, 2 deselected in 0.16s

    $ pytest -q test_provider_route_projection.py -k "replay or receipt or keyed"
    ...                                                                      [100%]
    3 passed, 1 deselected in 0.12s

    $ pytest -q test_supervision_confirmation.py -k "cli or confirmation or incarnation or reopen"
    ....                                                                     [100%]
    4 passed in 0.13s

    $ python -m py_compile [five exact owned production modules]
    exit 0

    $ git diff --check
    exit 0

CLI subprocess branches:
    status2=2 stdout=0 bytes stderr=disposition schema error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
    status4=4 stdout=0 bytes stderr=invalid ledger location: ledger root must be a directory
    status5=5 stdout=0 bytes stderr=required confirmation missing
    status0=0 stdout={"disposition_id":"d","ledger_event_id":"d","record_id":"d"} stderr=

## Post-rework source identities

Exact production diff command output:
    e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801  -

Owned file git hash-object / SHA-256 pairs:
    arnold_pipelines/megaplan/incident/disposition.py
    git ea1d175d554e2364ca97ae84ff32ee3663b3818e; sha256 04bf85191483258aa8c746fa12c9f5f746becfe288e4eaa0ac69fa2e5491374d
    tests/.../test_changed_precondition_producers.py
    git b6cedc6cb4f7d806e95c41339930a4a9f6803363; sha256 79d59501de3d3f11924b86764f757629de312064d3e06f2f84477a5e19dca547
    tests/.../test_incident_ledger_transactions.py
    git 1fb063bd24496d14e639bb360e1cea4a1d796e4e; sha256 778fa119d6c7b46a9bd70e34d1df30fbb9b1102092383eeb34a304f0abaf3954
    tests/.../test_provider_route_projection.py
    git d39b9b4b1ccb35b6bae567c20c64a2f559d38e8e; sha256 034a83fd510cbb198b807fac6892f23e0ff19cdd029816d8a45fd4747368e63a
    tests/.../test_reservation_reconciliation.py
    git 86d04ecfcefffa77c94261cb10529592725e677c; sha256 eeee8b8970c2e3fcb742015b71085ac1dd6ddbbe246e792e9630b6467d9a18c0
    tests/.../test_scheduling_conditions.py
    git fc54999a025f23d89860facda94b260d1d7e5bb3; sha256 2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb
    tests/.../test_supervision_confirmation.py
    git c002cd92c9ebf0da853f0cdc2e20c7839b642b79; sha256 91328027e373347b71f07c71fd10305199cb18d0397dead8d4f5674d883f4eb0
    tests/.../test_terminal_outcomes.py
    git 4905610fc8e4860a28bc18a24ccbc89b635605b2; sha256 695bc33ad89622ce9fa9227f0a7673cd17f17e7f1f583263e2757be12247195d
    tests/.../test_worker_disposition.py
    git 20699ed29f05e53c3ea034d88d8338b7800029e3; sha256 8484d6d4a85276534743299a72120c6d8dfd0c3cb96a19cea5faececcebaffac

The prior handoff's 52->61 focused-count mutation and unreproducible 4aee815d... production digest remain historical evidence-integrity failures and were not rewritten. The new focused count is an observation, not a target.

