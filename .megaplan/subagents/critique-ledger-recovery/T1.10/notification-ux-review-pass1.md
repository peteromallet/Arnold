# T1.10 notification UX adversarial review pass 1

Use GPT-5.6 Luna high reasoning. Perform a fresh READ-ONLY review of exact commit:

`d060d7ce1b2ac09f36f828c2136dc2e5dacbad62`

in:

`/private/tmp/arnold-critique-recovery-notification-ux-20260802`

Do not edit, commit, push, deploy, contact providers, or mutate cloud/external state.
You may run local tests and ephemeral fault/concurrency probes. Do not trust the
implementation's tests or its comments.

## Intended contract

Repeated observation of one incident is unlimited and cheap. One external notification
requires a uniquely claimed durable intent admitted through real current Run Authority,
Custody, and WBC; observation and diagnostic launch must create stable identity before
provenance validation; missing provenance becomes one terminal diagnostic result; the
watchdog never calls a provider; provider ambiguity is sticky `INDETERMINATE` and forbids
blind redispatch; acknowledgement/resolution are real authority transitions; the incident
card is a rebuildable projection, never authority. Two processes and 200 identical scans
must produce at most one accepted notification outcome.

## Main-agent concerns to investigate, not assume

1. `incident_notification.py` appears to manufacture
   `GrantRef("run-authority:incident-notification-admission")` rather than validate a real
   current Run Authority decision/fence/capability. Prove whether this is synthetic/shadow
   authority and whether any effect can be enqueued without accepted authority/custody.
2. `authority_transition()` appears to accept arbitrary nonempty `authority_id` and
   `actor_id` strings. Prove whether a UI caller can acknowledge/resolve without owner
   validation, and whether same-action divergent requests are conflict-fenced.
3. The module creates `.incident-notifications.sqlite3` under a caller-selected root and
   labels it canonical WBC/ledger custody. Determine whether it actually joins the accepted
   owner WBC store/Run Authority/Custody or creates a parallel authority island.
4. Admission appends ledger+outbox, then separately inserts `incident_occurrences`.
   Determine the exact crash semantics before/between/after these transactions and whether
   replay can always rebuild a complete occurrence/card without duplicate/dangling intents.
5. Validate that the outbox append itself rejects same idempotency identity with divergent
   payload, works across separate processes, persists before any provider call, and handles
   ENOSPC/fsync/SQLite ambiguity fail-closed.
6. `state_version` appears hard-coded to 1. Determine whether meaningful transitions can
   enqueue exactly one new notification and repeated observations merely update a card,
   without losing the current state machine.
7. Provider attempt/result tables may permit same attempt/different request digests,
   SUCCEEDED→FAILED overwrite, fabricated receipts, or retry after ambiguous/successful
   application. Test monotonic terminal outcomes and process races.
8. The recipient fallback `discord:provenance-pending:<digest>` must never become a real
   provider route. Prove the worker refuses it and no synthetic provider identity escapes.
9. Search all watchdog/diagnostic paths for Discord/webhook/curl/provider calls or fallback
   sends—not only the changed function. Prove observers can only enqueue.
10. Verify diagnostic identity/state truly precedes every provenance validation and all
    failures return nonblank stable IDs/paths.
11. Verify the incident card includes all required fields and can actually be rebuilt from
    authority data after deletion/corruption; comments are not a rebuild implementation.
12. Check unsafe JSONL whole-file authority paths and concurrent sequence assignment were
    retired from the production path rather than left active alongside the new store.
13. Verify installed/shipped runtime surfaces use this code and no stale wrapper bypasses
    it. Include shell syntax and relevant watchdog integration tests.

Run targeted tests plus new local reproductions. Inspect exact diff and surrounding code.
Write the review to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass1-result.md`

Start with exactly `PASS` or `FAIL`. For each defect include severity, exact file/function/
line, reproduction/reasoning, and minimum root fix. A PASS requires the full local contract,
not merely “no direct Discord call.” State separately what remains blocked on integration,
deployment, or a production delivery worker. Include exact commands/test counts.
