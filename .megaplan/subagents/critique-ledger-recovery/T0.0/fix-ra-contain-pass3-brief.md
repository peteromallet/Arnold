# GPT-5.6 Luna repair pass 3 — remove alternate authority and close proof gaps

Work in `/private/tmp/arnold-critique-recovery-ra-contain-20260802` on exact
HEAD `eaeca1e7d97deb93ecbdd0f68930001f9f810d84`.

Read the pass-3 independent FAIL review in the shared T0.0 subagent directory.
Fix every blocker and prove it directly:

1. Delete the receipt-only `verify_containment` API and remove it from every
   export/import/test/caller. Do not keep a compatibility alias. The only policy
   answer must be `ContainmentStore.check`, which replays the authoritative
   journal. Search the whole repo to prove no caller remains.
2. Reject booleans for `expected_cursor` in issue and terminate, and reject any
   non-integer/negative cursor. Validate expected revision as an exact 64-char
   lowercase hex digest, not merely a string. Add API and CLI tests.
3. Wrap `Path.exists()`/status read and every expected filesystem operation in
   typed storage failures. Add deterministic fault-injection unit tests for
   mkdir, lock open/acquire/close, journal exists/read/open/write/flush/fsync/
   close, directory open/fsync/close. For each ambiguous post-write failure,
   the issuing call must return typed indeterminate/storage refusal and never a
   success receipt. Add real CLI subprocess tests for all filesystem failure
   classes reproducible without unsafe permissions (parent-is-file, journal-is-
   directory, unreadable/invalid journal), asserting JSON/nonzero/no traceback.
4. Replace the race test's swallowed exceptions with a multiprocessing queue or
   result files that capture `accepted`, `idempotent`, or the exact typed loser
   code. Run identical and divergent issuer races repeatedly. Assert identical
   racers converge to one record and the same receipt; divergent racers yield
   exactly one accepted and one typed stale/conflict loser, with one record.
   Add concurrent terminate behavior if needed to prove no duplicate terminal
   record.
5. Preserve append/restart/digest and prior failure coverage. Keep all test
   artifacts inside pytest temp paths and avoid destructive cleanup commands.

Run focused tests repeatedly (at least five race iterations), the complete Run
Authority/relevant CLI/cloud containment suites, `git diff --check`, and an
`rg` proof that the unsafe helper has zero remaining references. Commit a new
follow-up commit; do not amend/push/deploy. Update the external handoff with
the exact commit and test evidence.
