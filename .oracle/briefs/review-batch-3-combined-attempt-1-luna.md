# Luna review brief — Batch 3 combined NBF-04/NBF-05 attempt 1

Review `.oracle/rework/batch-3-attempt-1-combined-nbf04-nbf05.md` as a fresh,
read-only integration and authority review on
`reconcile/nbf-attempt4-2297`, based on
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.

Bind the review to the exact 40-path manifest
`.oracle/scripts/nbf-batch3-attempt-1.manifest` (SHA-256
`b28d54edca89ece81ba28d0bab7dae58350adbcbaca568176b66ca80ac12d622`), framed
by `.oracle/scripts/nbf_batch3_diff_v1.py` (SHA-256
`e2ec1d2f153c5990baeca60a9ee862fc8978f84d12fad4d447af1ac75454563a`). Verify
the output SHA-256
`85aa909c52d411a03f660ee301c70079e80ed0c925cf154c8dca3389649c275b`,
aggregate `9cce8961eb5861aba1eb9948e9cb72580bd423de60ba2d9dfd3c7f3a32fec214`,
40 paths, and 663421 raw diff bytes.

Judge the combined NBF-04/NBF-05 candidate only. Trace every real Python and
shell signal/death path through one canonical ledger authority. Verify:

- TERM/KILL confirmations are distinct, consumed, PID/start-bound, and
  record-before-signal; late replay requires exact disposition plus
  `signal_claimed`.
- WBC/native cleanup preserves custody across exceptions, handles crash/replay,
  pre-acceptance holds, natural death, permanent hold, and cross-adapter
  mismatches without unauthorized signal or writes.
- The authority resolver reloads marker, bootstrap manifest, expected runtime
  HEAD, progress digest, boot/container/supervisor identity, and worker receipt
  fields from canonical sources under the ledger lock.
- Real tmux producer bindings use explicit socket/session queries and bind
  server PID/start plus exactly one owned pane PID/start/ID/command and the
  all-pane digest. Replacement, ambiguity, partial metadata, and stale refresh
  must fail closed; non-tmux markers must remain admissible.
- Shell bridges invoke the canonical resolver and preserve no second authority;
  missing identity/ledger/context yields zero signal.

The focused combined test run recorded 174 passes before filesystem exhaustion
caused 9 failures and 187 pytest temporary-directory errors. Treat that run as
environment-contaminated, not acceptance evidence. Use the clean focused
subsets recorded in the packet: authority/liveness/watchdog `51 passed`, the
corrected shell bridge/source-contract pair `2 passed`, real tmux producer /
resolver / replacement pass, inventory `--check` pass, Python compile pass,
all targeted `bash -n` pass, and `git diff --check` pass. Re-run only if the
environment permits; do not reinterpret missing-temp-root errors as semantic
regressions.

Known stale baselines are unrelated runtime-attestation seed absence,
OMP-vs-HERMES fake-output fixture mismatch, and the obsolete provider timeout
124 expectation versus cleanup-hold 75. Return PASS or REWORK with exact
file:line evidence. Do not edit, commit, push, merge, deploy, touch main, or
launch NBF-06/epic work.
