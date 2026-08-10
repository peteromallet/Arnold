# Discord Resident Correlation and Reply-Delivery Architecture

Date: 2026-07-10

## Decision

Adopt a ledger-first correlation model. Generate an opaque, server-side
`correlation_tag` for every logical delegation, but make it a diagnostic and
recovery alias only. The normal completion path must follow stored relations:

`delegation -> resident turn/request -> primary ingress envelope -> terminal outbox intent`

The reply target is copied from the immutable ingress envelope into the outbox
intent when the result commits. Completion must never parse routing data from the
agent's FINAL text, search mutable conversation cursors, choose the newest
manifest, or trust a tag supplied by a user/model.

This is a refinement of the active corrective initiative, not a competing
architecture. Its North Star and M1 ledger direction are correct. The immediate
managed-Codex manifest/sweep work in `/workspace/arnold` is useful as a
compatibility bridge, but is not a sufficient authority boundary.

## Current-state findings

1. In the working tree, inbound Discord messages are persisted with a stable
   `discord_message_id`, but conversation `last_*` and `delivery_cursor` fields
   are mutable pointers (`resident/runtime.py:183-219`). A burst creates one turn
   over multiple message IDs (`runtime.py:221-249`).
2. Both the resident turn reply and delegated launch provenance currently select
   `items[-1]` (`runtime.py:262-272`, `runtime.py:297-307`). A later/reordered
   burst member can therefore become the reply source even though every member
   has its own stored Discord ID.
3. `LaunchSubagentInput.request_id` is optional and exposed to the model
   (`resident/profile.py:415-423`). The runtime injects `launch_origin`, but does
   not inject a canonical request, turn, or tool-call slot identity.
4. Every managed-Codex call creates a new UUID-bearing run directory and spawns a
   process before any transactional uniqueness claim (`resident/subagent.py:270-370`).
   `request_id` is copied into the manifest but does not prevent duplicate
   execution.
5. Completion state, origin, retries, and provider receipts live in each
   manifest. Duplicate delivery is suppressed by choosing the newest sibling
   manifest for the same optional request tuple (`subagent.py:556-612`), which
   conflates accidental duplicate launches with intentional multiple
   delegations from one message.
6. The delivery sweep has useful stopgap properties: a file lock, persisted
   pre-send state, a stable Discord nonce, redaction, retry evidence, and exact
   reply references (`subagent.py:614-949`; `discord.py:246-281`). Its remaining
   gaps are material:
   - the manifest is still the authority and a missing manifest makes the run
     undiscoverable;
   - all send exceptions become retryable, including 401/403/404 and deleted
     sources;
   - timeouts are retried rather than held as provider-unknown;
   - multi-chunk receipts are recorded only after every chunk succeeds;
   - a local file lock is not a cross-host/database claim;
   - Discord nonce uniqueness is only checked for the past few minutes, so it
     cannot prove indefinite exactly-once delivery;
   - `unknown` is skipped by the claim code and has no reconciliation worker.
7. Normal resident replies remain direct sends rather than outbox sends. A crash
   between provider acceptance and turn completion can still produce ambiguous
   or duplicate output.
8. The active initiative's M1 branch completed a clean, shadow-only lifecycle
   ledger implementation at `bdd2e67e8`; its focused lifecycle tests pass. M1's
   authority inventory, however, was built from a baseline where `subagent.py`
   was still the old synchronous Hermes launcher. It does not inventory the
   large managed-Codex manifest/delivery patch currently present in
   `/workspace/arnold`.
9. M1 also needs one identity clarification before cutover. The contract says
   the `resident_request_id` belongs to the deterministic primary envelope, but
   the shadow runtime creates a lifecycle request for every ingress envelope
   before coalescing, then associates all burst-member rows with the primary
   request while leaving non-primary request states at `member_registered`
   (active branch `resident/runtime.py:340-497`). Do not carry that ambiguity
   into delegation or recovery queries.

## Canonical identifiers and mappings

| Identifier | Cardinality and authority | Required rule |
| --- | --- | --- |
| `resident_instance_id` | One per bot installation/tenant | Scopes every external identifier and prevents cross-installation lookup. |
| `transport_message_key` | One per accepted Discord message | Unique tuple `(resident_instance_id, transport, channel_id, discord_message_id)`. Keep guild/thread/DM fields for validation. Discord snowflakes are not accepted without their stored scope. |
| `ingress_envelope_id` | One-to-one with transport message | Immutable internal ID created transactionally at acceptance. Contains routing IDs, author/authorization subject, received/accepted time, and legacy `Message.id`, but no message body beyond existing message retention. |
| `source_request_id` | One per accepted ingress envelope | Stable pre-coalescing correlation/custody ID. Duplicate gateway delivery converges here. |
| `resident_turn_id` | One per single message or closed burst | Owns ordered source membership and exactly one immutable `primary_source_request_id`. Primary rule: earliest accepted envelope, envelope ID as tie-breaker. Non-primary source requests record `coalesced_into_turn_id`; they are not orphan execution candidates. |
| `delegation_id` | One per intentional logical subagent run | Primary logical execution identity. A turn may have zero, one, or many delegations. A delegation may cite one or many source requests through an ordered `delegation_sources` join, with exactly one primary source. |
| `delegation_slot_id` | One per launch tool-call slot | Stable replay key created by the runtime, not the model: `(resident_turn_id, canonical_tool_call_ordinal)`. Replaying the same slot converges; a second intentional run uses a different slot. |
| `correlation_tag` | One opaque alias per delegation | At least 128 random bits (or a tenant-keyed HMAC encoding), unique under `resident_instance_id`, unguessable, never supplied by user/model, never parsed from FINAL text. |
| `run_attempt_id` | Many per delegation | Identifies wrapper/spawn attempts. Only the current monotonically fenced attempt may invoke the agent or publish a result. |
| `result_id` | At most one committed result version per delegation | Stores result artifact locator, digest, classification, and committing fence. The agent text contains no routing contract. |
| `outbox_intent_id` | One per logical visible effect | Terminal key is `(delegation_id, "terminal_reply", render_version)`; acknowledgement keys are turn/request scoped. The intent snapshots the immutable conversation target and reply message ID. |
| `outbox_chunk_id` | One per rendered Discord chunk | `(outbox_intent_id, chunk_index, content_digest)`. Each chunk has its own stable provider nonce and receipt so partial sends can resume safely. |
| `delivery_attempt_id` | Many per chunk | Records fence, attempt number, start/end time, provider outcome, message ID, HTTP/Discord category, and retry/reconcile time. |

Do not overload `request_id` with message, turn, delegation, and run-attempt
meaning. M1 should preserve its per-ingress request identity and add an explicit
turn/group identity plus delegation identity. The managed manifest should
project all three.

## Immutable launch provenance

Before process creation, atomically get-or-create the delegation and first run
attempt with:

- resident instance/tenant ID;
- `resident_turn_id`, ordered source request/envelope IDs, and primary source;
- exact Discord guild/channel/thread-or-DM IDs and primary source message/reply
  target copied from the ingress envelope;
- author and authorization-subject IDs needed for audit, subject to retention;
- canonical tool-call slot and causal turn/tool-call IDs;
- task digest, implementation/backend/model/config digests, target workspace
  identity, and code/version identity;
- delegation ID, correlation tag, run-attempt ID, lease holder, fence generation,
  and timestamps;
- intended completion effect/render version.

The public `launch_subagent` schema should not accept `request_id` or a
correlation tag. The resident runtime injects a trusted context containing the
turn, source set, primary source, and tool slot after authorization. A manifest
is written only as a projection/evidence artifact after the ledger intent exists.

To close the spawn-before-receipt crash window, a spawned wrapper must atomically
activate its attempt/fence before invoking Codex. Competing wrappers exit before
agent invocation. Because the delegated agent can mutate files, attempts should
run in attempt-isolated worktrees and only the current fence may promote the
resulting diff. If shared-worktree execution is retained, recovery must prove and
stop the old process before relaunch; ledger fencing alone cannot undo stale
filesystem writes.

## Lookup position

Tag lookup is recovery-only.

Primary completion uses the worker's stored `delegation_id` and current fence to
commit a result. That transaction creates the terminal outbox intent from the
delegation's stored primary ingress relation. The dispatcher loads the outbox by
its primary key. There is no tag search in the happy path.

Recovery may resolve `(resident_instance_id, correlation_tag)` to exactly one
delegation. Zero matches becomes `unresolved`; more than one match is an
integrity incident and both records are quarantined. Never use "newest match",
substring search, tag text copied from Discord/FINAL, or a cross-tenant lookup.

## Idempotent completion delivery

1. The current execution fence commits `result_id` and a terminal outbox intent
   in one transaction. Repeating the commit with the same result/effect digest
   returns the existing records; a different digest is a conflict.
2. An outbox worker claims a chunk with compare-and-set lease/fence semantics,
   persists `sending` plus the stable nonce before I/O, and sends an exact reply
   using the snapshotted target.
3. Provider success stores the Discord message ID and advances that chunk to
   `sent`. The intent becomes `sent` only when every required chunk is sent.
4. Duplicate callbacks/worker completions are idempotent by effect key and
   provider message ID. Stale fences cannot write receipts or advance state.
5. Retryable failures use bounded exponential backoff with jitter and Discord's
   `Retry-After`. Permanent failures dead-letter immediately. Attempt and age
   budgets dead-letter exhausted retryable work.

Discord supports `enforce_nonce`, but its uniqueness check covers only messages
created by the same author in the past few minutes. A stable nonce is therefore
a short-window dedupe mechanism, not a permanent exactly-once guarantee. The
provider adapter should reconcile an ambiguous attempt using the send response,
gateway receipt, and a bounded channel-history search for the bot author plus
nonce before retrying. Within the provider nonce window it may retry the same
nonce. After that window, an unresolved attempt remains `unknown` and requires
operator reconciliation; it must not be blindly resent. See the official
[Discord Create Message documentation](https://docs.discord.com/developers/resources/message#create-message).

## State and retry policy

Keep execution and delivery state separate.

- Execution: `intent_recorded -> claimed -> activating -> running ->
  result_ready -> succeeded|failed`; recovery states are `launch_unknown`,
  `abandoned`, and `dead_lettered`.
- Outbox/chunk: `intent_recorded -> claimed -> sending -> sent`; alternate states
  are `retryable_failure`, `unknown_reconcile`, `permanent_failure`, and
  `dead_lettered`.

Classify outcomes as follows:

| Condition | Required disposition |
| --- | --- |
| 429, transient network failure known to occur before acceptance, Discord 5xx | Retry with persisted backoff/`Retry-After`. |
| Timeout/connection loss after bytes may have reached Discord | `unknown_reconcile`; do not report sent and do not immediately create a new effect. |
| 400 invalid payload, 401, 403 | Permanent failure/dead letter after storing redacted category evidence. |
| 404 source/channel missing or Discord reply says referenced message does not exist | `source_unavailable` permanent failure. Never retarget to a newer message or silently post a non-reply. Discord requires a reply source to exist, and message references default to failing if it does not. |
| Missing result artifact after successful execution state | Invariant violation/unknown result; no fabricated success. |
| Missing or corrupt manifest with intact ledger/result | Rebuild projection and continue from ledger. |
| Manifest exists but ledger identity is absent | Legacy importer creates a quarantined migration record or `unknown`; the manifest does not become authority. |

Official Discord documentation confirms that replies require the referenced
message to exist and that a deleted reference is represented as null; see
[Message Resource / Message Reference](https://docs.discord.com/developers/resources/message#message-reference-structure).

## Required behavior for difficult cardinalities and failures

- **Multiple Discord messages -> one run:** retain ordered many-to-one
  `delegation_sources`; freeze one primary source by the turn's earliest-accepted
  rule; reply only to that source. Later cursors/messages cannot alter it.
- **One Discord message -> several runs:** create several delegation slots and
  IDs, each with its own result/outbox effect. Each final reply may target the
  same source without being treated as a duplicate.
- **Duplicate launch:** the same turn/tool slot returns the existing delegation
  and launch receipt. It never creates another authorized agent invocation.
- **Restarted resident:** startup reconciliation runs before ingress readiness,
  then a bounded continuous worker reclaims expired claims, activates pending
  attempts, reconciles unknown sends, and advances outbox items.
- **Copied/colliding tags:** user/model text is ignored. A database uniqueness
  violation blocks launch; an ambiguous legacy collision is quarantined and
  alerted, never resolved by timestamp.
- **Deleted source message:** preserve the target, record permanent
  `source_unavailable`, and dead-letter. Do not fall back to the conversation's
  current cursor or latest message.
- **Missing manifests:** use ledger/result records; regenerate the manifest
  projection. If neither ledger nor a safely importable legacy record exists,
  report `unknown` rather than guessing.

## Privacy and security

- Treat Discord user, guild, channel, thread, DM, and message IDs as personal or
  tenant data even though they are not credentials.
- Store routing IDs only in the access-controlled lifecycle store/outbox. Do not
  use them as metric labels or expose them in model hot context unless a tool
  action strictly needs them.
- Make correlation tags opaque and unguessable. Tenant-scope every lookup and
  authorize the caller before returning status, preventing tag-based IDOR.
- Provenance records contain no prompt/result/message content. Existing message
  retention remains separate. Store result locators and digests; redact final
  text before rendering and never persist Discord response bodies or auth
  headers.
- Encrypt durable stores/backups under existing infrastructure policy, restrict
  manifest permissions, and define retention/tombstone behavior. Deleting
  content need not delete the minimal audit identity required to prevent replay.
- Revalidate the stored resident instance and transport scope at send time; no
  runtime caller may substitute a channel/reply target.

## Migration and backfill

1. Reconcile the current working-tree managed-Codex patch into the initiative's
   authority inventory before M2/M3. Do not let the active M1 branch overwrite or
   ignore it.
2. Add schema/version fields for `resident_instance_id`, `resident_turn_id`,
   delegation/source joins, delegation slot/tag, run attempts, and chunk-level
   outbox attempts. Resolve the M1 per-envelope versus primary-request ambiguity.
3. Shadow-write ledger identities while legacy `Message`, `BotTurn`,
   `ResidentConversation`, manifest, and `completion_delivery` fields remain
   readable projections. Compare the two views and alert on divergence.
4. Backfill deterministically:
   - message + conversation records -> ingress/source request;
   - bot turn `triggered_by_message_ids` -> turn/membership/primary;
   - managed manifest with valid origin/request -> delegation/run attempt;
   - result and delivery fields -> result/outbox attempts.
5. If a legacy record has one provable source, import it. If origins disagree,
   tags collide, multiple manifests claim one slot, or only mutable cursors are
   available, import as `unknown/quarantined`; never choose newest.
6. Cut authority per migrated request, not globally: old-only -> shadow ->
   ledger-authoritative canary -> wider cutover. In ledger-authoritative mode,
   legacy fields are projections only. Rollback changes serving authority but
   retains all new records and fences to avoid split-brain replay.
7. Do not destructively delete legacy manifests/records in this initiative.

## Observability and hot context

Operator/status views should expose bounded, non-secret fields:

- `correlation_tag`, `delegation_id`, `resident_turn_id`, and primary
  `source_request_id`;
- source count and origin kind (`dm`, `guild_channel`, `thread`), but not raw
  user/channel IDs in metric labels;
- execution state, state age, attempt count, current fence generation, lease
  expiry/heartbeat age, backend/model, result presence/digest prefix;
- terminal outbox state, chunks sent/total, delivery attempt count, last outcome
  category/HTTP or Discord code, next retry, unknown age, dead-letter reason;
- duplicate launch/send prevented counts, recovery action/reason, provenance
  completeness, manifest projection status, schema/migration mode, and ledger
  projection divergence.

Alert on oldest pending/unknown age, lease/recovery lag, retry exhaustion,
dead-letter count, tag/identity collision, stale-fence commit rejection, missing
provenance, manifest/ledger divergence, and startup reconciliation failure.

The resident model's hot context should receive only correlation tag, high-level
state, age, result/delivery status, and safe error category. Full route IDs,
author IDs, provider response text, prompts, and result contents stay behind
authorized tools.

## Exact acceptance tests

Use fake clocks, transactional barriers, deterministic fault injection, and a
Discord adapter fake that records nonce/reference/provider acceptance. Do not
prove correctness with sleeps or PID-only assertions.

1. Two concurrent deliveries of one gateway event create exactly one envelope,
   source request, legacy inbound projection, and acceptance event.
2. The same message ID under a different resident instance or mismatched channel
   cannot alias the original; a stored-scope mismatch is rejected and audited.
3. For A then B in one burst, including reversed callback scheduling, membership
   is ordered by accepted sequence, A is primary, and later C/cursor updates do
   not change A's target.
4. A two-message turn launching one delegation stores both sources, one primary,
   and delivers exactly one terminal effect replying to the primary.
5. One source launching slots 0 and 1 creates two delegations and two distinct
   terminal effects to the same source; replay of either slot creates none.
6. N concurrent calls for one `(turn, slot)` return one delegation and authorize
   at most one wrapper to invoke Codex.
7. Kill/restart at intent-before-spawn, spawn-before-activation, activation-before-
   manifest, worker-start-before-heartbeat, result-before-outbox, and
   outbox-before-sweep; each converges without a second authorized invocation.
8. A superseded fence cannot invoke/publish a result, create an outbox intent,
   commit an attempt receipt, or promote attempt-worktree changes.
9. Missing, corrupt, and duplicate manifests with a complete ledger are rebuilt
   as projections and neither duplicate execution nor delivery.
10. A copied user/model tag is ignored. A forced unique-index collision blocks
    launch. A seeded ambiguous legacy collision quarantines both records and
    sends nothing.
11. Successful one-chunk delivery records the reply reference, stable nonce,
    provider message ID, receipt, and terminal state; replay sends nothing.
12. A three-chunk delivery failing after chunk 1 persists chunk 1's receipt and
    resumes at chunk 2 without resending chunk 1.
13. 429 honors `Retry-After`; 5xx and known-preaccept network errors back off with
    a bounded attempt/age budget.
14. Timeout after provider acceptance enters `unknown_reconcile`; a gateway or
    history nonce match advances it to sent without another visible message.
15. An unknown retried with the same nonce inside Discord's uniqueness window
    returns the existing message and records it once.
16. An unresolved unknown after the nonce window dead-letters/awaits operator
    action and is not automatically resent.
17. 400/401/403 become permanent failures with redacted evidence and no retry.
18. Deleted source, missing channel, and lost reply permission never retarget to
    the newest message; they become explicit permanent/dead-letter states.
19. Crash after Discord acceptance but before receipt persistence reconciles to
    the provider message; crash before I/O safely retries.
20. Duplicate provider callback and stale sender completion are idempotent and
    cannot regress `sent`.
21. Resident restart performs reconciliation before accepting a new inbound
    event; concurrent startup/continuous sweepers converge under CAS/fences.
22. Legacy fixtures cover current managed manifests, prior manifest schema,
    request-only provenance, origin-only provenance, delivered/retry/unknown
    fields, no manifest with ledger, and irreducibly ambiguous cursor-only state.
23. Old-only, shadow, ledger-authoritative canary, and rollback modes preserve
    read compatibility and reject split-brain writes.
24. Metrics/log/hot-context snapshots contain no message text, result text,
    credentials, provider body, or raw high-cardinality user/channel identifiers.
25. End-to-end test: Discord A+B -> accepted envelopes -> turn -> one delegation
    -> restart during execution -> result commit -> restart during send -> one
    visible reply to A, with monotone ledger history and complete receipts.

## Incremental implementation plan

1. **Reconciliation gate:** land or explicitly supersede the current
   managed-Codex manifest/sweep patch in the corrective worktree; update M1's
   inventory. Reconcile the active plan/chain cursor before starting M2.
2. **Identity correction:** amend the additive M1 schema/contract with tenant,
   turn/group, delegation-source, delegation-slot/tag, run-attempt, result, and
   chunk records. Resolve non-primary source lifecycle disposition. Keep shadow
   mode.
3. **Transactional ingress (M2):** atomically persist accepted envelope/source
   request and replay checkpoint; close turns with ordered membership and frozen
   primary; recover before ingress readiness.
4. **Fenced delegation (M3):** remove model-supplied request IDs, inject trusted
   runtime context, transactional get-or-create per slot, wrapper activation
   handshake, leases/fences, isolated attempt worktrees, and manifest projection.
5. **Durable outbox (M4):** commit result and terminal intent together; add
   chunk-level claims, stable nonces, receipts, failure classification,
   unknown-reconcile, dead letters, and exact immutable replies. Route ordinary
   resident replies/acks through the same outbox.
6. **Recovery/migration (M5):** bounded startup/continuous reconciliation,
   deterministic import/quarantine, dual-read projection comparison, canary
   authority flag, rollback, and constrained operator actions.
7. **Adversarial rollout (M6):** run the 25-test matrix, expose the listed
   observability fields, canary until pending/unknown/recovery/divergence gates
   remain healthy, then widen. Preserve the explicit caveat that Discord cannot
   guarantee indefinite exactly-once creation after an unresolved timeout.

## Verification performed

- Read the current resident ingress, storage, tool context, managed-Codex
  launcher/worker, manifest discovery, completion sweep, Discord adapter,
  scheduler, hot-context projection, and focused tests in `/workspace/arnold`.
- Read the corrective initiative North Star, locked decisions, six milestone
  briefs, active M1 lifecycle contract/inventory/schema/store/runtime work, plan
  state, chain state, and completion evidence.
- `pytest -q tests/resident/test_launch_subagent.py tests/resident/test_discord_adapter.py tests/resident/test_discord_outbound.py`
  -> **35 passed** in `/workspace/arnold`.
- `pytest -q tests/resident/test_lifecycle_contract.py tests/resident/test_lifecycle_store.py tests/resident/test_runtime_lifecycle_shadow.py tests/store/test_file_lifecycle.py tests/store/test_multi_lifecycle.py`
  -> **18 passed** on the active M1 branch.
- `megaplan introspect --plan m1-lifecycle-contract-and-20260710-2126` -> plan
  state `done`, clean branch `bdd2e67e8`, no outstanding plan flags. The chain
  cursor remained stale at milestone 0 / `execute`, so operational advancement
  was not independently confirmed.
- Direct cloud status could not authenticate from this environment; inspection
  used the configured mounted cloud workspace and its durable state/events.

