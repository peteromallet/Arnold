# T1.10 notification UX repair pass 2

Use GPT-5.6 Luna high reasoning. Work only in:

`/private/tmp/arnold-critique-recovery-notification-ux-20260802`

Start from exact commit `d060d7ce1b2ac09f36f828c2136dc2e5dacbad62`. Do not touch
the dirty main checkout, cloud, providers, or external services. Do not push/deploy. Read
the full FAIL report and repair every finding at root without weakening tests:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass1-result.md`

## Binding repair requirements

1. Remove every synthetic/shadow grant. Admission, diagnostic terminalization,
   acknowledgement/resolution, provider claim, and delivery eligibility must consume and
   validate real current Run Authority + Custody + WBC evidence through the canonical
   action gate. If those owner adapters are unavailable in this branch, production paths
   must fail typed/closed; provide explicit test-only fixtures that cannot be mistaken for
   authority.
2. Resolve the authoritative store through a pinned owner store identity/current runtime
   authority. Caller-selected roots must not create parallel production custody islands.
   Bind store ID, target/occurrence tuple, epoch/fence and runtime generation.
3. One incident has exactly one canonical notification intent/GLEK. Diagnostic resident
   completion must claim/terminalize that intent or be strictly non-delivery. Remove the
   second resident completion delivery identity.
4. Make provider attempt/outcome state fenced and monotonic across all attempts:
   - unknown intents reject;
   - `(intent, attempt, request_digest)` exact replay only; divergence conflicts;
   - receipt schema/provider evidence and message IDs/counts are validated and bound;
   - terminal outcomes cannot regress/overwrite;
   - `INDETERMINATE` is intent-level sticky and no later claim/attempt/FAILED row can make
     redispatch eligible without a real signed reconciliation transition;
   - process races have one winner.
5. Pre-provenance identity is non-dispatchable custody, never a Discord destination or
   pseudo-recipient. On provenance failure persist one terminal/tombstoned intent that no
   worker can deliver. A delivery worker must enforce this before provider calls.
6. Authenticate acknowledge/resolve actors and action-specific authority; use immutable
   request digest and legal monotonic state transition (`resolved` never regresses).
   Same-action divergence gets a typed conflict, not raw SQLite error.
7. Replace fixed version 1 with a canonical monotonic incident state machine. Identical
   observation dedupes; one meaningful accepted state transition creates exactly one new
   state version/intent; illegal regressions/divergence reject.
8. Add deterministic reducers/rebuild for launch state and incident card from canonical
   ledger/outbox/provider/authority state. Deleted/corrupt projections cannot suppress
   retry/reconcile or become authority. Do not accept arbitrary caller card JSON.
9. Fix `SqliteLedgerOutbox.append_event_with_outbox`: bind canonical outbox
   ID/destination/payload to duplicate identity and reject divergence. Add commit ambiguity
   reconciliation—no blind retry or false failure/success after uncertain COMMIT.
10. Retire or make canonical `record_fallback_delivery`; arbitrary result JSON can never
    fabricate delivered state and persistence errors may not be swallowed.
11. Remove/disable every executable sibling direct Discord/webhook/provider path and legacy
    notification JSONL authority, especially `arnold-repair-loop.send_discord_escalation`
    and unlocked whole-file sequence writers. Evidence-only JSONL must be explicitly
    non-authoritative and incapable of dispatch.
12. Create stable bounded incident/attempt identity and state path before *all* payload/
    state/gate/provenance validation failures on API and CLI; no blank/exception-only path.
13. Ship the diagnostic wrapper/module in clean materialized deployments and test installed
    runtime/import/help behavior. Add/define the canonical delivery worker surface; if the
    real production worker is not yet available, fail closed and state that T1.10 remains
    integration-blocked.

## Required proof

Keep the existing 397-test surface. Add direct regression probes for every reproduction in
the report, including two canonical-store roots, forged authority, divergent provider
digest, fabricated receipt, terminal overwrite, post-ambiguity attempts, meaningful state
versions, projection deletion/corruption, divergent outbox payload, SQLite commit ambiguity,
all direct-send source scans, malformed pre-identity input, and clean materialization.
Include separate-process races and ENOSPC before effect. Prove zero provider calls whenever
authority/custody/persistence/provenance is missing or ambiguous.

Run targeted/broader tests, shell syntax, static checks, installed-wheel/materialization
tests, and `git diff --check`. Inspect your own diff adversarially. Commit only when clean.
Final report must include commit, exact commands/counts, what production integration remains,
and must not claim formal completion if real owner adapters/delivery worker are unavailable.
