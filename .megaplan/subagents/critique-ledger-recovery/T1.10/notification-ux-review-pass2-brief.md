# T1.10 notification/incident UX — independent review pass 2

You are GPT-5.6 Luna at high reasoning. Perform a fresh adversarial review of
exact candidate commit:

`7031b40dcd6ece7a24bbb3fec47fb440dfd57cce`

Worktree:
`/private/tmp/arnold-critique-recovery-notification-ux-20260802`

Do not trust the implementer or passing tests. Do not edit source, amend the
commit, deploy, SSH, contact Discord, or mutate cloud state. You may write only
the result below and disposable test output.

First read the prior FAIL report and explicitly reproduce/refute every finding:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass1-result.md`

That report had 13 blockers: synthetic/shadow authority, caller-selected
parallel custody roots, split diagnostic identity, unfenced provider attempts
and results, pseudo-recipient delivery, forged ack/resolve and state regression,
hard-coded state version, unrebuildable projections, outbox payload/commit
ambiguity, fabricated fallback success, direct Discord/legacy JSONL paths,
malformed input without stable identity/path, and omitted diagnostic wrapper.

Then independently attack the intended invariant:

> Repeated observations are cheap and unlimited; an external effect requires
> one durable, uniquely claimed, authority-bound intent.

Prove or falsify:

1. One canonical root/store is owner-resolved; callers cannot create a parallel
   incident/notification universe.
2. Occurrence, diagnostic attempt, notification intent, outbox row, provider
   attempt, provider result, acknowledgement, resolution, and projection share
   one stable identity/authority lineage.
3. Malformed input and missing resident provenance still create a stable durable
   incident path before failure; they never return blank IDs/paths.
4. Two watchdogs and 200 identical ticks create exactly one occurrence, one
   diagnostic attempt, one notification intent, and at most one provider claim.
5. Provider claim/result state is monotonic; `SUCCEEDED` and `INDETERMINATE` are
   sticky, conflicting replays fail, crash/commit ambiguity never triggers blind
   redispatch, and receipts cannot be fabricated or overwrite success.
6. Discord/provider effects exist only behind the canonical outbox worker. Scan
   all source/materialized wrappers for direct sends, legacy ledgers, fallback
   calls, webhooks, and alternate recipient paths.
7. Missing provenance is non-deliverable; pseudo-recipients cannot reach a real
   provider. Stable nonce/reconciliation rules cover provider uncertainty.
8. Ack/resolve and incident state transitions require real Run Authority and are
   exact-version monotonic; test-only authority cannot enter production paths.
9. Incident cards and projections rebuild solely from authoritative ledger/
   outbox/provider rows after deletion/corruption/restart.
10. ENOSPC before durable intent/attempt prevents provider invocation; ENOSPC or
    response loss after invocation becomes indeterminate and never blind retry.
11. Source, installed wheel, materialized deployment, CLI/wrapper, and help
    surfaces contain the same canonical worker and retired legacy provider path.
12. No secret is logged, included in an incident card, or placed in an idempotency
    key/receipt.

Run the focused/pass-2 tests, broad watchdog/diagnostic regression, concurrency
and crash probes, source scans, installed-wheel/materialization proof, static
checks, and `git diff --check`. Use one test process at a time and controlled
temp roots because local disk headroom is limited.

Write:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass2-result.md`

First line exactly `PASS` or `FAIL`. Include exact files/lines, minimal
reproductions, required corrections, and exact test results. Explicitly state
that this local candidate review does not prove formal T1.10 or authorize cloud
deployment/provider effects.
