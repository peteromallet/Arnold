# T1.10 notification/incident UX — Luna repair pass 2

You are the GPT-5.6 Luna mutation-authorized implementer for the notification
authority/UX lane. Work only in:

`/private/tmp/arnold-critique-recovery-notification-ux-20260802`

The exact current candidate is commit
`7031b40dcd6ece7a24bbb3fec47fb440dfd57cce`. Read the complete independent
FAIL report before editing:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass2-result.md`

Repair the invariant at root: observations may repeat indefinitely, but an
external notification effect requires exactly one durable, owner-authorized,
uniquely claimed intent and independently verifiable provider outcome.

Close every remaining blocker and turn the review probes into regressions:

1. Remove caller-mintable/test authority from every production path. Resolve a
   sealed owner-installed authority and one canonical WBC/Custody store root;
   test helpers must be structurally incapable of entering production APIs.
2. Preserve one stable occurrence/diagnostic/run/authority lineage from
   admission through terminalization. Authority rotation/fence rereads must not
   rewrite replay identity or create divergent event payloads.
3. Permit only one active provider claim, exact CAS-fenced by intent, attempt,
   request digest, stable nonce/GLEK, and authority fence. A later attempt may
   start only after the prior one is durably terminal.
4. Require typed provider-verifiable success evidence. Empty/arbitrary injected
   mappings must not become success. Unknown post-send outcomes remain
   indeterminate until a real signed/durable owner reconciliation transition.
5. Reject pseudo/derived/caller-supplied recipients unless they resolve through
   validated resident provenance and an owner-installed provider route.
6. Preserve acknowledged/resolved state under all replay/upsert paths; make
   transitions monotonic and require the exact expected state version.
7. Implement a deterministic reducer that reconstructs occurrence, intent,
   authority state, and card projections from authoritative ledger/outbox/
   provider history after canonical-row deletion or corruption.
8. Retire or quarantine every alternate incident lifecycle writer, including
   the progress-auditor JSONL path and watchdog webhook ambiguity. Add a real
   canonical outbox worker wrapper/adapter that fails closed without installed
   owner/provider configuration.
9. Create stable durable identity/state before every validation boundary,
   including malformed gate tokens and malformed escalation IDs.
10. Persist allowlisted/redacted payload and provider receipt fields only.
    Never persist secrets or secret-derived idempotency material.
11. Preserve the pass-2 fixes: direct Discord retired, missing provenance
    custody-only and tombstoned, deterministic outbox commit reconciliation,
    packaged diagnostic wrapper, same-slot race fencing, immutable terminal
    receipts, and card rebuild.

Run focused tests plus the reviewer's exact adversarial probes, two-process/200
tick races, provider crash/response-loss/ENOSPC tests, shell/static checks, and
installed-wheel/materialization parity. Use one large test process at a time and
controlled scratch because local disk headroom is limited. Delete only exact
task-created scratch after use.

When the implementation is reviewable, create one new commit and leave the
worktree clean. Write a concise result to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-repair-pass2-result.md`

Include exact commit, tests, probes, remaining external integration limits, and
why no cloud/provider effect was performed. Do not deploy, contact Discord,
edit the master checklist, or claim formal T1.10 completion. This produces only
a candidate for a fresh independent Luna review.
