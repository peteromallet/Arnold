# T0.0 RA-CONTAIN final independent review — pass 4

You are a fresh GPT-5.6 Luna independent reviewer. Work read-only in:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Review exact commit `e019cf4519f2e54aea7164390e4e5c11e5ad5517`, which adds the minimal owner-operated RA-CONTAIN journal/API/CLI required by T0.0. Do not edit, commit, push, deploy, or mutate cloud state.

The governing T0.0 requirement is: an exact-tuple Run Authority containment decision must deny all new repair, execute, notify, publish, resume, and deployment effects while preserving only read-only observation; it must be owner-issued, fail closed, independently inspectable, and expose decision ID, exact scope, TTL/termination, CAS/revision, and revoke/audit path. No shell/tmux/marker/queue fallback is acceptable.

Treat this as a release-blocking adversarial review. Inspect the implementation and tests, run your own tests/reproductions, and return a strict `PASS` or `FAIL`. Do not accept merely because existing tests pass.

At minimum prove or falsify:

1. Exact tuple schema/binding and denied-effect set; unknown actions cannot accidentally pass.
2. Current-state authority only: there is no receipt-only, cache-only, marker-only, or other exported/internal helper capable of authorizing after termination, expiry, wrong tuple, journal tampering, or missing journal. Repo-wide search must find zero `verify_containment` references.
3. Owner journal correctness: hash chain, receipt content integrity, known ops/transitions, restart determinism, fail-closed behavior on malformed/torn/unknown records, and explicit audit path.
4. CAS correctness: bool/float/negative cursors rejected; revision is exactly lowercase 64-hex; identical duplicate is idempotent; divergent duplicate and stale concurrent writers fail typed.
5. Concurrency: independent processes racing identical requests converge to one record and identical receipt; divergent racers produce exactly one accepted writer and one typed loser. Repeat enough to expose flakiness.
6. Durability/error semantics: mkdir, lock open/flock/close, journal read/open/write/flush/fsync/close, and parent-directory open/fsync/close failures cannot escape as traceback or untyped success. Pay special attention to failures after bytes may have been appended: ambiguity must refuse rather than claim clean success.
7. TTL: finite positive only; expiry uses authoritative current receipt and refuses closed; malformed expiry data cannot pass.
8. API and real CLI parity: malformed JSON and invalid CAS/filesystem conditions return machine-readable typed refusals without traceback.
9. Package exports and installed-module behavior do not expose a bypass. Inspect both `containment.py` and `run_authority/__init__.py`.
10. Scope discipline: this is a minimal interface only; no hidden cloud mutation, deployment, or legacy authority path was introduced.

Prior independent reviews found and required repair of:

- unchecked revision CAS, omitted deployment denial, unknown journal ops, malformed CLI tracebacks, incomplete tuple/policy contract, unverified receipt integrity;
- escaping storage I/O errors, non-finite TTL, weak process-race coverage;
- unsafe receipt-only `verify_containment`, bool cursor acceptance, swallowed race losers, incomplete filesystem fault coverage.

Confirm every prior finding is truly closed. Include exact commands/results and file:line evidence. If FAIL, give minimal reproducible counterexamples and precise required changes. If PASS, state any residual operational limitation clearly: a local interface implementation is not itself a live cloud containment decision and does not complete T0.0 until installed through accepted Release Authority and used by the owner.

Write the final report to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass4.md`
