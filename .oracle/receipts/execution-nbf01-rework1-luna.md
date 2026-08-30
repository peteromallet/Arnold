# Receipt — NBF-01 Batch 1 rework execution, Luna attempt 1

Date: 2026-08-30
Executor: GPT-5.6 Luna
Implementation: RW-02, RW-01, RW-03, RW-04, RW-05, RW-06
Classification: all Normal; no [XHARD]
Base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
Rework tasklist sha256: 5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c
Grok triage receipt sha256: 7565016b618293fa666f61710f0f95bb8847d6d2336568ff064d8843699efa1e
Custody worker receipt: .oracle/receipts/rework-nbf01-custody-luna.md (reported sha256 prefix 48f540c4)

## Decision and boundaries

The six Normal rework tasks were implemented and verified in the existing
candidate tree. RW-CUSTODY was handled by its separately authorized worker; I
did not edit custody.md. No commit, push, merge, rebase, reset, clean, plan or
frozen-tasklist mutation, Batch 2 dispatch, or later-batch source change was
performed.

Focused NBF suite: 78 passed (observed count).
Legacy regression suite: 78 passed.
Adversarial ledger, keyed replay, and confirmation subsets: 3/3, 3/3, and 4/4
passed respectively.
py_compile: exit 0.
git diff --check: exit 0.
CLI subprocess statuses: 0, 2, 4, and 5 all reproduced; status 0 emitted one
JSON acknowledgement and did not signal.

The prior executor receipt's 52-to-61 test-count mutation and unreproducible
4aee815d... owned production digest remain historical evidence-integrity
failures. This receipt records fresh observed results only and does not rewrite
the prior receipt.

## Fresh candidate digest

Production diff command:
git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py
arnold_pipelines/megaplan/incident/ledger.py
arnold_pipelines/megaplan/incident/schema.py
arnold_pipelines/megaplan/orchestration/phase_result.py
arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256
Output: e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801

Owned files and git hash-object / SHA-256 are recorded in the companion
finding .oracle/findings/execution-nbf01-rework1-luna.md.

## Evidence

Full command transcript, exact focused/legacy commands, adversarial commands,
compile/whitespace checks, CLI branch outputs, and all owned-file identities:
.oracle/findings/execution-nbf01-rework1-luna.md

This receipt is immutable after publication.

