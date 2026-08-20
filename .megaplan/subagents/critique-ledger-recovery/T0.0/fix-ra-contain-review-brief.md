# GPT-5.6 Luna repair — T0.0 RA-CONTAIN review failures

Work in `/private/tmp/arnold-critique-recovery-ra-contain-20260802` on current
HEAD `6a4be1aa2b6e31587802402c1602f18430840478`.

Read and fix every blocking finding in the independent review:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-independent-review.md`

Do not merely add assertions around the old behavior. Make the owner contract
coherent:

- CAS is `(cursor, owner_revision)`, where owner revision is the current
  authoritative journal digest. Genesis has cursor 0 and the declared genesis
  digest. `status` exposes both; `issue`/`terminate` compare both before append.
  Do not copy an unchecked expected revision into a receipt.
- The exact incident tuple has precisely these required non-empty scalar string
  fields and no extras/nested values: `selection_session`, `spec`, `workspace`,
  `plan`, `branch`, `profile`, `runtime`.
- Denied effects include `resume`, `repair`, `execute`, `publish`, `notify`, and
  `deployment`. Preserved read action is exactly `observe`.
- Add a typed policy result/API and CLI `check` operation that reads/replays the
  authoritative journal, binds the exact tuple, and returns `DENIED` for the
  six effects, `ALLOWED` for `observe`, and a typed refusal/nonzero exit for
  unknown action, missing/inactive/expired receipt, wrong tuple, corrupt state,
  or integrity failure. A fabricated receipt must never be the authority.
- Strict replay rejects unknown operations, invalid transition ordering,
  divergent duplicate identity, wrong receipt hash, and malformed/truncated
  records. Replay must verify receipt content hashes and the record hash chain.
- CLI invalid JSON and all expected user/storage contract failures return stable
  JSON and documented nonzero codes without tracebacks.
- Keep owner-local append/fsync and process locking. Do not claim repair of a
  torn journal; fail closed and make the audit result explicit.

Add comprehensive tests for every minimum case in the original implementation
brief and every review reproducer, including separate-process concurrent issue,
issue+terminate record retention/restart, deterministic replay digest, wrong
revision, missing journal check, unknown op/action, malformed JSON, receipt
tampering, exact tuple rejection, expiry, deployment denial, observe allowance,
and CLI exit/JSON behavior. The tests must assert behavior, not only line count.

Run focused tests and the full Run Authority + relevant CLI regression suites,
then `git diff --check`. Commit a new follow-up commit (do not amend history).
Do not push or deploy.

Update the implementation handoff at
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-implementation-result.md`
with the new commit, actual test commands/counts, and no stale success claims.
Return the commit and concise evidence.
