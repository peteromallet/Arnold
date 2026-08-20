# GPT-5.6 Luna repair pass 2 — close remaining RA-CONTAIN failures

Work in `/private/tmp/arnold-critique-recovery-ra-contain-20260802` on exact
current HEAD `0b757880ea25ff75afc2a701c920c38f18385568`.

Read the second independent FAIL review:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-independent-review-pass2.md`

Fix every remaining blocker and coverage gap, preserving the owner contract
already corrected:

1. Wrap all expected owner-local filesystem errors from directory/lock open,
   journal read/open/append/fsync/close and directory fsync as typed
   `ContainmentError` subclasses. Direct API callers receive typed errors. CLI
   emits stable JSON/nonzero with no traceback for each path. Do not silently
   continue, repair, truncate, or claim an append after uncertain durability.
2. Validate TTL before hashing: real finite numeric, strictly positive, and not
   bool. Reject `nan`, `inf`, `-inf`, zero, negative, strings, and booleans as a
   typed contract refusal at API and CLI boundaries.
3. Add actual separate-OS-process tests for identical and divergent issue races
   using the same expected `(cursor, revision)`. Assert exactly one durable
   issue record and no divergent accepted decision; document/verify the precise
   idempotent loser behavior.
4. Add restart/process tests proving issue + terminate retains both immutable
   records and deterministic state/digest.
5. Add explicit CLI JSON/nonzero/no-traceback tests for storage I/O, malformed
   JSON, invalid subcommand/cursor/TTL, unknown action, wrong tuple, expired or
   terminated receipt, wrong revision, corrupt/torn journal, and tampered
   receipt. Exercise the real subprocess entrypoint.
6. Ensure test helper cleanup is safe and confined to pytest temp directories.

Run the focused tests repeatedly enough to expose race flakiness, then the full
Run Authority and relevant CLI/cloud containment suites, plus `git diff --check`.
Commit a new follow-up commit without amending prior history. Do not push/deploy.
Update the external implementation handoff with this new commit and exact test
commands/results. Return concise evidence.
