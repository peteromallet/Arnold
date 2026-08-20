# T0.0 RA-CONTAIN repair pass 4 — anchored current authority

You are the GPT-5.6 Luna mutation-authorized implementer for non-VERY-HARD task T0.0. Work only in the isolated worktree:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Start from exact commit `e019cf4519f2e54aea7164390e4e5c11e5ad5517`. Do not amend or rewrite earlier commits. Do not push, deploy, SSH-mutate, touch the dirty main checkout, or change cloud state. Implement, test, and commit one follow-up repair.

Read the complete independent FAIL report first:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass4.md`

This is an authority interface. Fix the root contract, not only the listed examples. A self-consistent hash-chained file is not sufficient current authority because a valid-prefix rollback can resurrect a terminated decision.

Required outcomes:

1. **Authoritative current-head binding.** Bind journal replay/check/status to a durable owner head/anchor so a missing tail, valid-prefix rollback, mismatched head, missing/corrupt head, or journal-ahead/head-ahead state refuses typed and cannot authorize. Inspect and reuse the repository's canonical Run Authority/owner-store primitives if they exist. Do not invent a marker, cache, tmux, queue, or projection as authority. If a standalone local adapter remains for tests, make the production contract require an authenticated/owner-controlled anchor and name its trust boundary explicitly. A second unauthenticated file that can be silently rolled back with the journal is not a complete solution.
2. **Crash/ambiguity protocol.** Define and implement the write ordering and recovery semantics for journal append, journal fsync, anchor/head commit, atomic replace/CAS, directory fsync, and close. Any failure after bytes may have been written must leave current-state checks/status in a typed indeterminate/refused state; retry may not turn that uncertainty into clean idempotent success. Provide an explicit, owner-authorized reconcile/recover operation if necessary; it must validate the exact fully written record and current anchor and produce an auditable transition, never silently adopt.
3. **Strict schema everywhere.** Use one canonical validator for issue receipts, terminate/reconcile records, and the current receipt during replay/check. Enforce exact field sets; scalar/non-empty decision ID, issuer, reason; exact tuple; fixed denied effects/read class; finite positive-or-null TTL; parseable finite timestamps; allowed termination policy values; exact lowercase 64-hex revisions/content hashes; cursor/revision relationships; audit path; state; and per-operation fields. Rehashed malformed data must fail closed.
4. **True idempotency.** A duplicate is idempotent only when the complete normalized request identity matches the persisted receipt and the persisted decision is still active/current. Different issuer, reason, TTL, termination policy, tuple, or decision identity is `DuplicateConflict`; stale/divergent CAS is typed. Reissue after termination must never return success or a terminated receipt.
5. **Owner issuance boundary.** Enforce—not merely record—the trusted owner identity/capability used for issue, terminate, and any reconcile. Reuse an existing repository owner/capability contract where possible. The CLI/API must not let an arbitrary caller self-declare `issuer=attacker` and mint authority. Document the production trust boundary and make tests prove unauthorized calls fail. Do not hard-code a real secret or expose credentials in output.
6. **CLI/API typed parity.** All malformed stored/input forms (including missing decision ID, invalid created_at types, NaN persisted TTL, bad anchor/head, wrong owner capability) must emit machine-readable typed refusal with no traceback. Do not catch broad exceptions as a substitute for validating state.
7. **Exports and bypass audit.** Keep `verify_containment` absent repo-wide. Export the intentional public error/contract types consistently from the package; no receipt-only/current-state bypass. `check()` must read current anchored state on every call.
8. **Regression and fault suite.** Add exact tests for every pass-4 reproducer plus:
   - valid-prefix rollback after termination;
   - journal/head rollback or mismatch according to the documented trust model;
   - crash at every persistence boundary, then restart, status, check, retry, and explicit recovery;
   - divergent same-ID fields and post-termination reissue;
   - strict mutated/rehashed receipt/record matrix;
   - unauthorized owner identities/capabilities;
   - real CLI malformed-state and auth failures;
   - 20 repeated separate-process identical/divergent races with explicit outcomes;
   - restart determinism and no extra records on genuine idempotent retry.

Acceptance before commit:

- focused containment tests pass;
- broader `tests/arnold_pipelines/run_authority` and relevant `tests/run_authority`/cloud containment tests pass;
- the new rollback/crash/race tests are repeated and non-flaky;
- `git diff --check` clean;
- repo-wide zero `verify_containment` references;
- an adversarial self-reproduction cannot recreate any pass-4 blocker.

Commit the repair as a new commit. Then write a concise handoff with exact commit, changed contract, commands/results, trust-boundary explanation, and residual limitations to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-pass4-repair-result.md`

Do not claim T0.0 complete: even a locally accepted interface still requires an accepted Release Authority deployment and an actual owner-issued cloud containment receipt.
