# T0.0 RA-CONTAIN independent release review — pass 5

You are a fresh GPT-5.6 Luna independent, read-only authority reviewer. Work in:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Review exact commit `a0334cfbc9e3bfde6aa3310c45975d539153b1f5`. Do not edit, commit, deploy, push, provision real secrets, or mutate cloud.

Read the pass-4 FAIL report and the pass-4 repair handoff in:

- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass4.md`
- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-pass4-repair-result.md`

Return strict `PASS` or `FAIL` for local release candidacy. Run independent counterexamples; do not accept on the repository's tests alone.

Prove every original T0.0 requirement and every prior finding, with special adversarial focus on the new design:

1. The owner head really prevents valid-prefix rollback. Test journal-only rollback, head-only rollback, and rollback of both journal and head to a previously valid authenticated pair. Decide whether the documented production trust boundary makes the latter impossible; inspect defaults and real CLI wiring, not just constructor options. A head adjacent to the journal on the same rollback/failure domain must not be described as external rollback protection.
2. Missing/corrupt/stale/ahead/mismatched/pending head always refuses `status`, `check`, retry, issue, and terminate. Recovery must adopt or abort only the exact pending candidate/base and append an auditable reconcile transition.
3. Crash at every persistence operation, including pending-head mkdir/open/write/flush/fsync/close, atomic temp write/replace/parent fsync/close, journal operations, lock operations, and failures during reconcile itself. Check fresh-process behavior and whether a crash while writing pending intent can destroy the last committed anchor irrecoverably or accidentally authorize.
4. Post-append ambiguity can never become ordinary idempotent success. Genuine identical duplicates are idempotent only while current/active; all divergent same-ID fields and post-termination reissue are typed.
5. Full stored schema validation, including exact field sets/types/relationships, finite TTL/timestamps, fixed effects/read class/termination policy, revision/content/record hashes, audit path, terminate and reconcile records. Rehash malformed states and exercise the real CLI; no traceback.
6. Owner authentication is an enforceable production boundary rather than a caller-declared string. Inspect secret lifecycle and every leak surface: command-line arguments/process listing, environment, repr, JSON output, dataclass equality, `token()` or similar extraction, tests/logs, file permissions, and provisioning. A CLI `--owner-secret` or public method that returns raw secret should be treated as a release blocker unless the contract explicitly and safely contains it.
7. The real CLI must support a distinct owner-controlled anchor/trust domain if that is required by the design. Confirm it cannot silently default the journal and head into the same incident-volume rollback domain in production.
8. Provisioning must be one authorized one-time operation, cannot overwrite/adopt preexisting journal/head state, and cannot let an arbitrary caller create a new canonical authority store at the canonical path.
9. Current-state check reads the authenticated current owner head each time; there is no receipt/cache/marker/process bypass and zero `verify_containment` references.
10. Run repeated independent process races, broader Run Authority tests, diff hygiene, exports, and scope audit. No cloud/legacy mutation path may have been introduced.

If FAIL, include minimal reproductions and exact required fixes. If PASS, explicitly state the residual operational requirements: accepted Release Authority deployment, off-volume owner anchor/capability provisioning, exact runtime tuple, and real owner-issued cloud receipt still remain and T0.0 is not yet complete.

Write the report to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass5.md`
