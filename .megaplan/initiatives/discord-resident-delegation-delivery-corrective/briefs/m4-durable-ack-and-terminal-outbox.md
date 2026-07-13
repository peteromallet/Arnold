# M4 — Artifact-Aware Fenced Acknowledgement and Terminal Outbox

## Outcome

Deliver acknowledgements, terminal text, and explicitly selected artifacts through one durable, retryable, fenced outbox tied to immutable request provenance. Deterministic multipart batches preserve immutable bytes and provider evidence across retries/restarts, represent partial and unknown outcomes honestly, and keep text-only behavior compatible when no artifact is selected.

## Scope

Incident addition: resident routing/model timeouts, usage-limit failures, process failures, malformed responses, and crashes must atomically record both the turn transition and an idempotent terminal failure outbox intent before the exception is propagated or logged.

In scope: acknowledgement and terminal delivery-group intent committed with causal state; exact terminal text digest and ordered artifact-ref selection; deterministic batch IDs/member digests, packing by configurable verified per-file capability, conservative 10-file internal ceiling, and 24 MiB internal multipart target below Discord's 25 MiB request ceiling; outbox claim/lease/fence, attempt/receipt, retry/backoff/dead-letter state; standard Discord `multipart/form-data` with `payload_json`, unique `files[n]`, matching partial attachment IDs, sanitized deterministic filenames, capped descriptions/captions, detected outbound MIME, empty allowed mentions, immutable reply reference, stable <=25-character nonce, and `enforce_nonce=true`; CAS streaming with known sizes; receipt validation for message/channel/nonce/attachment count/names/sizes; provider rate-limit headers and `retry_after`; permanent vs pre-send retryable vs post-send-possible unknown classification; Gateway/bounded-history nonce reconciliation; independently committed multi-batch/partial delivery and retry-only-missing behavior; oversize retained failure or reviewed private scoped link when that capability exists; compatibility projections to legacy delivery fields/manifests/status.

Route all acknowledgement/terminal sends—including normal completion, synchronous profile replies, managed-agent completion/reaper, repair/recovery, scheduler, VP todo/sweep, legacy manifest sweep, and compatibility resend paths—through the same artifact-aware outbox authority. Eliminate direct-send bypasses or reduce them to explicit compatibility adapters that create canonical intent before effects.

Out of scope: automatic zip/split, public object URLs, Components V2, arbitrary transport abstraction, generalized object serving, or production cutover of all legacy data.

## Locked decisions

- Intent, terminal text digest, exact ordered artifact refs, deterministic batches, and reply target commit before any network call. Delivery rereads immutable CAS bytes, never mutable source paths.
- A send occurs only from a claimed item/batch with the current fence and stable identity. Committed batches are never resent when another batch fails.
- Unknown provider outcomes remain `unknown/reconcile`; nonce uniqueness is only a bounded reconciliation aid, never a permanent exactly-once guarantee or reason for blind retry.
- Reply target and destination authorization come only from immutable originating provenance. Permission loss/deleted target cannot silently retarget to a current channel.
- Default outbound per-file ceiling is 10 MiB unless a verified configured capability raises it. Packing obeys both per-file and total encoded request budgets.
- Explicit declarations/trusted producer refs/exact user selection are the only artifact sources. Required selection failure changes terminal outcome; optional omission is reported once.
- Standard messages/multipart are the first-version transport. Text-only requests preserve existing chunk/reply semantics byte-for-byte where practical.
- No auto-zip, auto-split, raw local path, or permanent/public URL. Secure oversize links require separately reviewed authorization; otherwise retain under TTL and fail visibly with artifact ID/size.

## Open questions for the plan

- Does the current Discord library expose multipart placeholders, nonce enforcement, reply metadata, rate-limit evidence, and attachment receipts sufficiently, or is a narrow official-endpoint adapter required while retaining the same bot/rate-limit discipline?
- What bounded Gateway/recent-history evidence is available for reconciliation, and when does the safe same-nonce retry window end?
- What retry/dead-letter budgets fit existing operations for acknowledgement, text-only terminal, and independently failing artifact batches?
- How should acknowledgement and terminal groups interact when execution completes before acknowledgement delivery without allowing terminal reordering or duplicate status noise?

## Constraints

Do not log contents, signed URLs, secrets, full paths, filenames as metric labels, or full digests. Use fake clock/provider tests. Validate all sizes before opening the HTTP request. Respect route/global rate-limit headers, avoid invalid-request storms, and never hold DB transactions across network I/O. Keep the first batch self-contained and user-readable if later batches fail.

## Done criteria and acceptance evidence

- Provider/fault matrix covers one/many/duplicate-digest files, safe-name collisions, empty/binary files, text-only, success, 400, 401/403/404, 429, 5xx, pre-send failure, timeout after possible acceptance, duplicate callbacks, process death before/during/after upload, lease expiry, and stale completion.
- Multipart assertions prove matching `files[n]`/attachment IDs, immutable bytes, safe names, correct MIME/captions, empty mentions, exact reply target, stable nonce, and no request beyond file/request budgets. Packing splits deterministically by count and encoded size.
- Gateway/history nonce match reconciles unknown success and exact attachment receipts. Safe-window same-nonce retry yields one visible message; unresolved old unknowns become operator-visible dead letters rather than claimed exactly-once success.
- Multi-batch tests preserve delivered receipts, retry only missing batches, and expose permanent `partial`; a returned attachment mismatch is an invariant violation, never success.
- Required blocked/oversize/no-declaration cases change terminal status without exposing secrets/paths; optional omissions are visible once; secure-link behavior is absent or fully authorization/expiry tested.
- Burst/interleaving and normal/repair/scheduler/todo/reaper/legacy compatibility E2E tests prove all sends use immutable provenance and the canonical outbox, with no mutable-cursor or direct-upload bypass.
- Timeout-before-first-tool-call and every resident failure class each produce one idempotent user-visible terminal outcome; `failed && message_sent=false` without outbox custody is an invariant violation.
- Status exposes group/batch/attempt/fence, next retry, exact safe provider evidence, unknown/partial/dead-letter reason, and causal request/execution/artifact refs.

## Touchpoints

Expected areas: lifecycle outbox/store/worker, Discord outbound adapter/fakes, `OutboundMessage` and terminal renderer, artifact selection/packer/CAS reader, Gateway reconciliation, managed completion and scheduler/todo/repair senders, legacy delivery projections, and outbound integration tests.

## Anti-scope

Do not let agents upload directly, reopen mutable project paths at send time, silently omit required artifacts, blindly retry unknown outcomes, retarget deleted replies, auto-package files, add public hosting, or create a parallel Discord bot loop.
