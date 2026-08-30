# W7 Sol pre-freeze audit — two load-bearing corrections

## Verdict

**PASS_FREEZE_AUDIT**

Audited artifact: `/tmp/megado-nbf-sol-plan-v7.md`

Raw SHA-256: `3e76fc3c9eeb8fbd6580d1217db341c1c3e9f16a4be3552eadddbef2ccd9276f`

The artifact was read completely: 3,165 lines, ending `STABILITY: STABLE`.

## 1. Lossless worker-disposition outcome — PASS

- §2.1 explicitly adds `DispatchOutcome.kind=worker_disposition`, requires accepted-launch and canonical disposition context, maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)`, and prohibits coercion or a second disposition append.
- §4.8 requires the terminal writer to validate the previously committed disposition against receipt, fingerprint, phase, spec, worker, and accepted-launch context. Duplicate linkage is idempotent; conflicting linkage or a second terminal kind rejects.
- §4.13 freezes the legal `worker_disposition -> accepted` combination and requires `disposition_id`, worker identity, timing, and common dispatch context. It prohibits provider-exhaustion evidence and ordinary-failure serialization.
- NBF-01 owns the schema, strict round trip, mapping, replay, idempotency, conflict rejection, and exactly-once reservation closure. Its focused tests include `test_worker_disposition.py`, `test_terminal_outcomes.py`, `test_reservation_reconciliation.py`, and ledger transaction/replay suites.
- NBF-02 owns typed intake and terminal-writer integration. Its acceptance requires end-to-end disposition identity preservation, validation of the existing disposition, no duplicate append, and no ordinary-failure/provider-degradation coercion.
- NBF-03 scenario 15 requires the structural trace `accepted launch -> disposition append -> signal -> typed worker_disposition DispatchOutcome -> one terminal append -> reservation closure`, with negative checks for coercion and duplication.
- NBF-04 and NBF-05 own Python and shell producers/recovery respectively, including crash/reconciliation behavior after disposition append or signal and before terminal linkage.
- NBF-06 preserves worker disposition as a typed streak-breaking non-provider outcome. The §10 matrix and §12 completion conditions require binary evidence for record-before-signal, exact linkage, replay/idempotency, and no double append.

This is task- and test-verifiable rather than prose-only.

## 2. Non-circular inventory and exact candidate-SHA binding — PASS

- §2.2 replaces repository revision/self-digest metadata with deterministic `source_inputs_sha256` over normalized sorted signal-bearing paths and contents plus generator/discovery-rule versions, excluding the generated inventory.
- §4.22 specifies the digest inputs and normalization contract; excludes git metadata, the generated artifact, and ordinary validation/evidence files; requires `--check` to recompute the digest and compare the full artifact.
- NBF-05 owns generator implementation and `test_repository_signal_inventory.py`. Acceptance requires deterministic non-circularity, source/version sensitivity, no embedded git revision/self-digest, and proof that committing the generated inventory alone does not stale its source-input identity.
- §4.24 freezes the sequence: finish/regenerate -> commit all candidate content -> prove clean -> record candidate SHA -> validate that SHA -> store evidence outside candidate content -> Luna review -> Sol pre-push acceptance -> push that SHA -> verify remote tip -> final Sol judgment.
- NBF-07 steps 5–15 implement commit-first validation and mandatory restart after any mutation. Steps 16–24 bind independent review, Sol authorization, explicit-SHA push, receipt, and remote verification to the same candidate SHA.
- §11 states that inventory checking, authority checking, shell syntax, the secondary scan, and the authoritative suite run only after all candidate changes are committed and the exact clean SHA is recorded.
- The §10 exact-SHA/non-circularity rows and §12 completion conditions make the sequence and evidence mechanically reviewable.

## 3. Required preservation — PASS

- §§4.16–4.17 and NBF-06 preserve the v6 T8 semantics: only accepted canonical exhausted worker outcomes form the streak; probe/recovery authorization preserves it; the authorized matching child may be observation two; success resets; a different key rekeys at one; ordinary failure or worker disposition breaks consecutiveness; only an authoritative provider-failure-key change otherwise resets/rekeys.
- §4.24, NBF-07 step 25, and §12 preserve candidate-branch-only delivery, guarded `--force-with-lease` after rewritten published history, exact remote-tip verification, and the prohibition on merging `main` without explicit user approval.
- The model policy, custody boundaries, no-box-only-fix rule, and no-new-store/service/scheduler/rotator constraints remain intact.

## Freeze note

No correction is required in the audited v7 plan. The existing `.oracle/tasklist.md` is a pre-v7 derivative and must be synchronized with these contracts before the tasklist itself is frozen.
