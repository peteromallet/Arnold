# RA-CONTAIN repair pass 8 (after adversarial review pass 7)

Use GPT-5.6 Luna high reasoning. Work only in:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Start from exact clean commit `25dc026546b9586db63ec0a39e5987321bf4bd0f`. Do not touch
the dirty main checkout, cloud, external services, or other worktrees. Do not push/deploy.
Read the complete FAIL report:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass7-result.md`

Repair all five findings without weakening existing coverage.

1. Make reconciliation's *own* pending/final CAS crash family recursively recoverable.
   If the reconcile journal row is durable and the final anchor CAS commits or is
   ambiguous, later exact replay/fresh signed reconciliation must recognize authenticated
   reconcile transition metadata and converge to one committed head. Never overwrite the
   reconcile candidate with stale metadata from the original incident transition. Verify
   head operation/request digest/record hash/receipt digest plus `status()` and all seven
   effect checks after recovery.
2. Revalidate the signed envelope after acquiring the cross-process journal lock and
   immediately before nonce/idempotency reservation/effect transition. A request that
   expires while blocked must reject with zero journal/anchor/identity mutation. Use one
   explicit acceptance clock source; no caller clock bypass.
3. Make one-time provisioning/genesis resumable and ambiguity-safe. A genesis anchor that
   committed before response loss must permit exact signed receipt replay to create/adopt
   the exact canonical journal metadata. Divergent genesis/replay must conflict. Cover
   failures before/after nonce reserve, anchor commit, journal creation, and metadata commit;
   no valid external genesis may be permanently stranded.
4. Require terminate's signed target to equal the active receipt exact tuple and bind the
   tuple in the terminate record/replay validator. Wrong-target same decision ID fails typed
   before any mutation.
5. Enforce state-specific exact head schemas and semantic relations: sequence-zero
   `previous_revision == GENESIS_REVISION`; `occurrence` only on indeterminate; pending may
   not carry indeterminate-only fields; committed/pending/indeterminate required/forbidden
   fields and predecessor/candidate relationships are exact.

Add direct regressions for every pass-7 reproduction, including reconciliation-final-CAS
response loss followed by exact and fresh recovery, lock-wait expiry with unchanged stores,
genesis response loss/restart/exact adoption/divergent rejection, terminate wrong tuple, and
mutated head schemas. Preserve all prior replay/concurrency/CLI/TTL/rollback tests.

Run the complete RA focused suite, reducer/dependency closure, static/build/installed-wheel
checks, `uv lock --check`, and `git diff --check`. Inspect your own diff adversarially.
Commit only a clean repair. Final response must state commit, exact commands/counts, and the
formal external GEN-DEPLOY/cloud decision blocker; do not claim T0.0 complete.
