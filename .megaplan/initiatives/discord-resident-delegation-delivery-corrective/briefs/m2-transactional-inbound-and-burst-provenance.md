# M2 — Transactional Inbound Custody, Artifact Broker, and Provenance-Safe Bursts

## Outcome

Route every Discord ingress path through immutable message envelopes and crash-safe turn custody, and add the resident-neutral artifact broker that converts authorized attachment metadata into quarantined, validated/scanned, content-addressed request artifacts before a turn can launch. Every accepted message and attachment is replayable, and every grouped request retains its exact origin, reply target, ordered artifact set, and visible terminal ingest outcome.

## Scope

Incident addition: persist deterministically explicit execution/delegation intent during accepted-message custody, before general resident model reasoning. The initial router receives a bounded purpose-specific envelope; large cloud snapshots, initiative inventories, and unrelated history are loaded on demand after custody. Ambiguous execution requests create durable clarification intent rather than existing only in transient prompt text.

In scope: atomically persist acceptance, message provenance, turn membership, replay/checkpoint state, and one durable ingest intent per Discord attachment; add additive artifact/blob/reference/validation state and events against the completed M1 ledger without reopening M1; implement bounded quarantine streaming, SHA-256 realm-scoped CAS promotion, create-if-absent verification, reference creation after durable bytes, filename/MIME/signature/size validation, malware/secret/policy scanner interfaces with deterministic fakes, quotas and storage watermarks; authorize before any fetch; enforce exact Discord CDN HTTPS allowlists, no redirects, timeouts, declared/header/streamed-size checks, and source-expiry handling; make turn readiness wait for every attachment to reach accepted/rejected/unavailable; preserve ordered per-message artifact references through deterministic burst coalescing; materialize only accepted request-scoped refs into bounded read-only `attachments.json`/`ATTACHMENTS.md` run projections; lease/claim and replay incomplete inbound work after interruption.

Cover every resident ingress and dispatch path that can accept or reconstruct Discord work: normal messages, attachment-only messages, mixed accepted/rejected inputs, voice/transcription and existing image/blob behavior, escalations, burst timers, restart replay, scheduler/recovery re-entry, VP todo/sweep or repair-created turns, and legacy message compatibility readers. Keep the sprint within roughly two human-weeks by leaving agent declarations and outbound upload to M3/M4.

Out of scope: agent-produced artifact declaration, multipart Discord delivery, general archive extraction/previewing, authenticated oversize serving, destructive legacy migration, or production-wide rollout.

## Locked decisions

- M1 ledger and transition APIs remain authoritative and completed; M2 adds a versioned artifact lifecycle extension rather than rewriting M1 history.
- Authorization and durable `artifact.ingest_requested` custody precede network download. Network fetch is an idempotent worker step, never part of the acceptance transaction.
- Accepted explicit execution/delegation intent is durable before general model reasoning. Model/tool invocation is a worker effect, not the first record that the user asked for execution.
- Discord CDN URLs and remote names/MIME/sizes are restricted transient hints, never durable byte identity or agent inputs.
- Quarantine is outside repos/web roots, mode-restricted, non-executable, capacity-bounded, and scanner-only. Scanner error/unsupported active content fails closed for agent exposure.
- CAS identity is `security realm + sha256 digest`; a live artifact reference cannot commit before durable bytes. Deduplication never merges provenance, authorization, retention, or conversation scope.
- Coalescing cannot pool or mutate attachment provenance. Every member keeps its ordered refs and the deterministic primary/request envelope.
- Run projections expose only accepted refs for the exact request and cannot hard-link writable bytes to CAS. Attachment-bearing execution is gated until M3 enforces the restricted launcher boundary.
- Preserve current voice-specific configured limits during migration. Generic defaults follow the canonical design: 10 MiB per inbound file and 25 MiB aggregate per message, configurable and recorded with the decision.

## Open questions for the plan

- Which existing `BlobStore` seam should be wrapped/evolved for digest-derived immutable keys, atomic promotion, stat/verify, and backend-neutral reference-aware GC without inheriting image-specific metadata?
- What deterministic primary attribution rule best preserves current burst UX while keeping each message and attachment independently addressable?
- Which maintained signature detector and pluggable local/private scanner interfaces fit the deployment without submitting private bytes to public services?
- Where should acknowledgement intent be created so durable custody is causal while M4 remains the only sender?

## Constraints

Preserve current authorization, content retention, secrets, service availability, and unrelated dirty work/active chains. Do not persist credentials, public blob URLs, full local paths, or signed CDN URLs in general projections/logs. Stream generic files rather than buffering them. Reject path/control/bidi abuse, special files, unsafe type mismatches, oversized/decompression-risk content, and storage low-watermark violations deterministically. Do not claim scanning makes hostile content safe. Recovery uses ledger leases/fences and constrained resident mechanisms, not PID guesses or arbitrary shell.

## Done criteria and acceptance evidence

- Schema/transition tests prove immutable origin/digest/request/realm fields, separate declared/detected/outbound MIME, realm-scoped physical deduplication with separate ACL/provenance refs, terminal monotonicity, and rejection of a reference to missing/non-durable bytes.
- Crash tests at intent, claim, partial stream, quarantine fsync, validation/scan, CAS promotion, ref commit, readiness, burst membership, materialization, and checkpoint boundaries converge to one visible terminal outcome; orphan bytes are collectable and no accepted turn silently loses an attachment.
- Unauthorized user/guild/channel causes zero fetches. HTTP/lookalike/user-info/redirect/non-Discord URLs, size lies, traversal/Unicode names, MIME spoof/polyglot, malware fixture, scanner timeout/error, encrypted/active unsupported content, archive bombs, huge dimensions/pages, quota/disk pressure, and expired URLs hit explicit states and safe user behavior.
- Duplicate/reordered transport delivery and multi-message bursts preserve ordered per-message refs and immutable exact reply provenance across DM/thread/channel, later arrivals, interleaved acknowledgements, fake time, restart, scheduler/repair/todo replay, and compatibility reads.
- Timeout/crash tests before resident reasoning, during routing, and before the first tool call prove that an accepted explicit execution request retains durable requested custody or a durable clarification outcome.
- Accepted projections are bounded, read-only, request-scoped, digest-verified as configured, labeled untrusted, and cannot access another request/realm or mutate CAS. Required rejected/missing artifacts block dispatch; permitted optional omissions are visible.
- Existing focused runtime, Discord, voice/transcription, image/blob, escalation, scheduler/todo, and compatibility suites remain green with explicit projection updates.

## Touchpoints

Expected areas: `resident/runtime.py`, coalescing/inbound models and stores, `resident/discord.py`, blob/artifact broker and policy modules, run projection/launcher envelope, scheduler/todo/repair entry points, service readiness/configuration, resident fakes, and `tests/resident/`.

## Anti-scope

Do not reopen or edit M1 assets, send files to Discord, expose quarantine/CAS directly to an unrestricted agent, auto-unpack archives, add public object URLs, replace the Discord bot loop/library, or rewrite unrelated cloud supervision.
