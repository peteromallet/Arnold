# Resident-Managed Agent Artifacts over Discord

**Status:** canonical initiative research; design recommendation, not implementation

**Initiative:** `discord-resident-delegation-delivery-corrective`

**Date:** 2026-07-10

**Scope:** all resident-managed Codex agents and resident profiles, including but not limited to VibeComfy

## Executive recommendation

Add one shared **resident artifact broker** beside the initiative's canonical lifecycle ledger. The broker should ingest inbound Discord attachments into quarantine, validate and scan them, promote accepted bytes into immutable content-addressed storage, and create request-scoped artifact references. It should also accept explicit outbound declarations from any resident-managed agent, capture those files into the same store, apply outbound security policy, and add selected artifact references to the request's terminal-delivery outbox.

Discord remains a transport adapter. Delegated agents never receive expiring Discord CDN URLs and never upload local paths directly. They receive a bounded, read-only projection of authorized artifact references. They return files through a small, launcher-provided declaration command/API, not by relying on prose, final-answer path parsing, or VibeComfy-specific behavior.

The simplest robust architecture is:

```text
Discord message
  -> authorize metadata before download
  -> durable ingest intent + immutable message provenance
  -> quarantine stream (size bound + SHA-256)
  -> MIME/signature validation + malware/policy scan
  -> content-addressed blob store
  -> request-scoped artifact references
  -> read-only run input projection
  -> resident-managed Codex agent
  -> explicit artifact declaration
  -> capture/validate/scan/DLP into the same blob store
  -> deterministic selection and delivery batches
  -> lifecycle outbox
  -> Discord multipart message(s)
```

The lifecycle ledger remains authoritative for custody, state, retries, and delivery. The blob store holds bytes; artifact records hold provenance, policy, names, and authorization; run manifests are compatibility projections. Discord's CDN is never durable storage.

This design deliberately does **not** promise unrestricted safe handling of arbitrary hostile files by the current `danger-full-access` delegated runner. Antivirus, `noexec`, and prompt wording are defense in depth, not a sandbox. Attachment-bearing runs must either use a restricted isolation profile or initially be limited to trusted principals and low-risk file classes.

## Decision summary

1. Build the capability once under the resident runtime/launcher boundary, not separately in VibeComfy or individual profiles.
2. Extend the existing blob-store seam into a general content-addressed artifact store, but do not reuse image-specific metadata as the general artifact model.
3. Give every inbound or outbound file an immutable blob digest and one or more mutable-in-state, immutable-in-provenance artifact references.
4. Require an explicit declaration or a trusted producer contract before a file can be selected for outbound delivery. Filesystem discovery is advisory only.
5. Capture declared files immediately through the broker using an open file descriptor; do not defer reading arbitrary project paths until Discord delivery.
6. Put attachment delivery into the same fenced, retryable outbox as the terminal reply, grouped into deterministic batches.
7. Use standard Discord messages with `multipart/form-data`; do not adopt Components V2 for the first version.
8. Default to conservative transport limits: 10 MiB per outbound file, 25 MiB including multipart request overhead, and at most 10 files per internal batch. Make higher per-file limits capability/config driven, never guessed from Nitro or guild tier.
9. Do not auto-zip, auto-unpack archives, publish raw workspace paths, or use public object URLs. Oversize delivery uses an authenticated, short-lived link only when that serving capability exists and policy permits it.
10. Preserve the initiative's immutable Discord reply provenance, request-id execution uniqueness, leases/fences, and unknown-provider-outcome semantics.

## Goals and non-goals

### Goals

- Make every authorized Discord attachment durably available to the exact resident request and delegated run that accepted it.
- Let an agent attach a newly produced file or an existing file it discovered, with an explicit display name and caption.
- Work with every resident-managed Codex launch by integrating at the common launcher/run envelope rather than at a profile-specific tool layer.
- Keep byte custody, provenance, authorization, selection, validation, delivery, retries, and cleanup explainable from one lifecycle view.
- Preserve useful files across process restarts without retaining them forever.
- Fail visibly and safely when a file cannot be scanned, does not fit Discord, is not authorized, or has an ambiguous send outcome.

### Non-goals

- General public file hosting.
- Automatic execution, compilation, macro expansion, archive extraction, or installation from inbound attachments.
- A guarantee that malware scanning makes a file safe.
- Exactly-once Discord delivery beyond evidence Discord exposes.
- Automatic attachment of every file changed in a worktree.
- Replacing the lifecycle ledger planned by this initiative, the current resident bot loop, or the existing Discord library.
- Deleting legacy voice, image, manifest, or delivery records during initial rollout.

## Current-state findings

The repository already contains useful pieces, but no general end-to-end file contract:

- `resident/discord.py` authorizes before fetching voice content, restricts downloads to Discord CDN hosts, refuses redirects, streams under a byte ceiling, sanitizes audio filenames, and supports voice transcription. Non-audio attachments are not durably ingested or exposed to a request.
- `Message` stores only `has_code_attachment`, `has_image_attachment`, voice metadata, and an optional audio URL. It cannot represent multiple files, immutable hashes, validation state, authorization, or custody.
- `DiscordOutboundSink` sends text chunks and records Discord message IDs. It does not accept files or construct multipart payloads.
- A managed delegated run stores `manifest.json`, `prompt.md`, `run.log`, and `result.md`. Terminal delivery reads only `result.md`; no file declarations are part of `arnold-resident-agent-run-v1`.
- Managed-agent completion retry state currently lives in the run manifest. The corrective initiative already decides that the canonical lifecycle ledger/outbox must become authoritative and manifests become projections.
- The store has a `BlobStore` protocol with local-directory and Supabase implementations, and image ingestion already computes SHA-256. This is a good storage seam, but blob IDs are caller supplied and the surrounding records are image/epic oriented rather than general request artifacts.
- The current managed Codex launcher uses `danger-full-access`. That is a material boundary: a hostile attachment made readable to that process can be copied, executed, or used to attack the workspace and credentials. A read-only file mode alone is not sufficient containment.

The attachment design should therefore be folded into the lifecycle initiative rather than added as a second source of truth. Inbound custody belongs primarily with M1/M2, declaration and agent fencing with M3, multipart delivery with M4, recovery/retention with M5, and adversarial evidence with M6.

## Architecture and ownership

### Components

| Component | Responsibility | Must not do |
|---|---|---|
| Discord ingress adapter | Capture immutable attachment metadata and create ingest intents after authorization | Hand CDN URLs directly to agents; trust remote filename/MIME/size |
| Artifact broker | Quarantine, stream, hash, validate, scan, promote, reference, materialize, capture declarations, and garbage-collect | Decide conversational reply targets; execute file content |
| Content-addressed blob store | Store immutable bytes by digest within a security realm | Store filenames, ACLs, Discord URLs, or delivery state as blob identity |
| Lifecycle ledger | Own request/artifact custody transitions, leases/fences, causal events, and recovery queries | Duplicate blob bytes or treat a run manifest as authority |
| Run input projector | Expose only authorized, accepted artifact references to a run | Mount quarantine or arbitrary host paths |
| Agent declaration adapter | Let any resident-managed agent declare a file with metadata | Parse arbitrary final prose for paths; upload directly to Discord |
| Selection planner | Resolve explicit user/agent intent into an ordered artifact set | Attach undeclared filesystem changes silently |
| Terminal outbox worker | Pack deterministic batches, upload multipart requests, reconcile, retry, and record receipts | Re-read mutable source files at delivery time |
| Preview service | Create optional, sandboxed derivative artifacts | Render active content in the resident process |

### Broker placement

The broker should be resident-neutral and injected into `ResidentRuntime` and the managed launcher through protocols, analogous to `OutboundSink`. Discord-specific metadata lives at the adapter edge; artifact records use neutral fields such as `transport_attachment_id`, `origin`, and `conversation_scope`. AgentBox or Megaplan profiles may add policy, but they should not fork storage or manifest formats.

The deployment root should be outside project worktrees, for example:

```text
<resident-data>/artifacts/
  quarantine/<ingest-id>.part
  blobs/sha256/<first-2>/<next-2>/<64-hex-digest>
  materialized/<run-id>/inputs/<safe-display-name>
```

The exact root is configuration. It must be on the resident's durable volume, mode-restricted, backed up according to the resident data policy, and unavailable through a static web root.

## Artifact discovery and selection

Discovery and selection are different decisions. Discovery finds candidates; selection authorizes a particular immutable capture for a particular delivery.

### Candidate sources, in priority order

1. **Explicit broker declaration.** The agent calls the common declaration adapter with a path, display name, caption, role, and required/optional flag. This is authoritative once the broker captures the bytes.
2. **Trusted producer contract.** A registered resident tool can return artifact IDs in structured output. The tool, not conversational prose, guarantees the artifacts exist and are already in broker custody.
3. **User-named artifact.** If the user explicitly identifies an inbound attachment or a known stored artifact, the request planner can select that existing authorized reference without recapturing it.
4. **Run-output convention.** A launcher may register known outputs such as `result.md`, but they are attachments only when policy says so. `result.md` remains the terminal text source by default.
5. **Bounded filesystem discovery.** At launch and completion, a scanner may compare metadata within configured roots to find new or changed regular files. Ignore `.git`, resident run internals, logs, caches, dependency trees, dotfiles, credential paths, sockets/devices, and files over the discovery ceiling. These are candidates shown to the agent/operator, not auto-selected attachments.
6. **Final-text hints.** A path mentioned in final prose may be shown as an untrusted hint if it resolves inside an allowed root. It must never cause an upload on its own.

### Selection rules

- A delivery artifact must have an accepted explicit declaration, trusted producer output, or exact user selection.
- Explicit `attach=false` or `role=internal` always wins over discovery.
- Sort by declared `order`, then declaration time, then artifact-reference ID for deterministic retries.
- Deduplicate identical blob digests within one delivery unless two different filenames are explicitly required.
- Preserve separate references for identical bytes from different users/messages; physical deduplication never merges provenance or ACLs.
- If a required declaration fails validation, the terminal delivery is an artifact failure and must say so. Optional failures can be omitted with a compact warning.
- If the user asked for a file but no valid declaration exists, send the text result with a visible “no attachable artifact was declared” status. Do not guess.

This policy allows an agent to send a file it **discovered**: it first discovers the path, then explicitly declares it. It avoids the common failure mode where a broad worktree scan leaks `.env`, logs, intermediate build output, or another agent's file.

## Explicit attachment declarations

### Primary interface

Every resident-managed launcher should provide a stable command backed by the broker, conceptually:

```text
resident artifact declare \
  --run "$ARNOLD_RESIDENT_RUN_ID" \
  --path ./reports/analysis.pdf \
  --name analysis.pdf \
  --caption "Architecture analysis and acceptance matrix" \
  --role primary \
  --required
```

The command is a thin authenticated client to the resident broker. It should be placed on the launcher's controlled `PATH`, use the run's unforgeable capability/fence from a sealed environment or inherited file descriptor, and never accept a caller-supplied conversation or Discord target. An agent can declare from any target repo because the run envelope, not the repo, owns the command.

Declaration should **capture immediately**:

1. Resolve the path against configured allowed roots.
2. Open a regular file with no symlink following; reject devices, sockets, FIFOs, directories, hard links to disallowed roots where detectable, and path traversal.
3. Snapshot `fstat`, stream from the open descriptor into broker quarantine while hashing and enforcing limits, then verify the source did not change during capture.
4. Validate, scan, and promote the immutable bytes.
5. Commit the declaration and artifact reference with the current execution fence.
6. Return the artifact-reference ID and accepted/rejected state to the agent.

The agent should retry after closing a file if it receives `source_changed_during_capture`. Delivery never reopens the source path.

### Declaration fields

| Field | Meaning |
|---|---|
| `declaration_id` | Stable idempotency key generated by the client or broker |
| `request_id`, `execution_id`, `run_id`, `fence` | Filled from the authenticated run envelope |
| `source_path` | Restricted internal locator; not shown in Discord or metrics |
| `display_name` | Requested user-facing filename; sanitized separately |
| `caption` | Optional user-facing description, capped before Discord |
| `role` | `primary`, `supporting`, `preview`, or `internal` |
| `order` | Optional deterministic integer ordering |
| `required` | Whether failure must change the terminal outcome |
| `preview_policy` | `auto`, `none`, or `required` |
| `classification` | Agent hint only; policy detection is authoritative |

### Compatibility fallback

Legacy managed agents that cannot invoke the broker may write a versioned declaration sidecar in their run directory. The supervisor validates it only after terminal execution and performs the same capture. This is a migration bridge, not the preferred contract: it has a larger race window and weaker immediate feedback. Arbitrary Markdown links or “Artifacts:” prose are not a declaration format.

## Inbound Discord attachments

### Acceptance sequence

1. The Gateway event supplies attachment metadata. Discord notes that `attachments` is empty without the configured/approved `MESSAGE_CONTENT` intent for relevant guild messages; readiness must test this capability, not merely set the local intent flag.
2. Perform current user/guild/channel authorization **before any attachment network request**, preserving the good property of the voice path.
3. In the same lifecycle transaction that accepts the message, persist immutable Discord provenance plus one `artifact.ingest_requested` record per attachment: attachment snowflake, message snowflake, ordinal, remote filename, declared MIME, declared size, and the signed CDN URL in a restricted short-lived field. Commit replay custody before download.
4. A broker worker claims each ingest intent. It accepts only HTTPS URLs on the exact Discord attachment/media CDN allowlist, follows no redirects, enforces connect/read/total timeouts, and applies declared, `Content-Length`, streamed, per-message, per-user, and global storage quotas.
5. Stream into a randomly named mode-`0600` quarantine file while computing SHA-256. Do not buffer whole generic files in memory.
6. Compare declared size, response length, and actual bytes. Mismatch is evidence and may be retryable once; exceeding a ceiling aborts immediately.
7. Detect MIME from content/signatures and compare it with the declared MIME and extension. The remote values are hints, never authority.
8. Run malware and policy scans. Archives are not unpacked automatically. Encrypted or unscannable active formats remain unavailable unless an explicit policy permits isolated handling.
9. Atomically promote accepted bytes to CAS and commit the artifact reference. Quarantine failures remain isolated and expire quickly.
10. Mark the inbound message ready when every attachment is terminal: accepted, rejected with a user-visible reason, or unavailable. Then construct/coalesce the resident turn. Coalescing retains each message's ordered artifact-reference set; it may not pool files without provenance.

The network fetch cannot be in the database transaction. The crash-safe equivalent is durable intent first, idempotent claim/download second, and no turn dispatch until every attachment reaches a terminal ingest state. If a signed URL expires before recovery, record `source_expired` and ask the user to resend; never silently run the turn as if the file had not existed.

### Agent projection

The run gets a small `attachments.json`/`ATTACHMENTS.md` projection containing artifact IDs, safe names, detected MIME, byte size, source message/request IDs, captions, and materialized relative paths. Bytes are copied or reflinked from CAS into a run-specific input directory and mounted/read-only where isolation supports it. Do **not** hard-link writable files to the CAS inode.

Attachments are labeled as untrusted data in the system prompt. The model must not treat embedded instructions as resident policy. This mitigates document prompt injection but is not a security boundary.

## Content-addressed durable storage

### Identity and layout

Use `sha256:<64 lowercase hex>` as the canonical content digest. Physical keys should be derived only from the digest and a security realm, for example `realm/<realm-id>/sha256/ab/cd/<digest>`. Filename, MIME, origin, owner, request, and retention do not participate in the blob identity.

Realm-scoped deduplication avoids a cross-tenant existence side channel. Even within one realm, access is granted through artifact references, never by presenting a digest. Two references can point to one blob while retaining independent provenance and retention.

### Write protocol

- Quarantine to the same filesystem as local CAS when possible.
- Hash while streaming; `fsync` the file and parent directory as required by the local durability contract.
- Promote with create-if-absent/atomic rename. If the digest already exists, verify size and optionally a read-back digest before discarding the temporary copy.
- Commit the artifact reference and lifecycle event after promotion. A crash can leave an orphan blob, which GC can safely remove after a grace period. It must not leave a reference to missing bytes.
- Object-store implementations use immutable keys, conditional put where supported, server-side encryption, and private buckets. Public `storage_url` values are prohibited.
- Verify digest on retrieval at a configurable sampling rate and always after restore/migration.

The existing `BlobStore` protocol can be evolved or wrapped to implement this, but general artifact identity should not inherit the current epic/image blob-ID convention.

## MIME, size, and file validation

Validation is layered because no single signal is trustworthy. This follows the defense-in-depth guidance in the [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html): authorize uploaders, bound size, sanitize names, compare extension/MIME/signature, store outside a web root, and scan or content-disarm where applicable.

### Required checks

- Unicode-normalize the display filename, take only its basename, remove control/bidi/path characters, reject leading dots and option-like leading hyphens, cap UTF-8 byte length, and create deterministic collision suffixes. The CAS key is always generated and never uses this name.
- Enforce both per-file and aggregate request quotas while streaming. Also enforce per-principal daily quotas, quarantine capacity, and global free-space watermarks.
- Detect MIME using a maintained signature database and, for structured formats, a safe parser. Record declared, detected, and outbound MIME separately.
- Treat extension/MIME/signature disagreement according to risk: normalize benign ambiguity, mark suspicious content, or reject. Never “fix” executable content by renaming it.
- Reject special files, sparse-file abuse, paths outside allowed roots, symlinks, and source files that change during capture.
- Bound dimensions/page count/decompression ratio/parser CPU and memory for images, PDFs, media, and archives.
- Do not expand archives in the initial version. Later archive inspection must use an isolated extractor with member count, nesting, path, expanded-byte, and compression-ratio limits.

### Default limits

Defaults should be configuration, recorded with every validation decision:

- Generic inbound: 10 MiB per file and 25 MiB aggregate per Discord message initially. Preserve the current voice-specific path during migration rather than silently lowering its configured ceiling.
- Generic outbound Discord: 10 MiB per file. A higher verified channel/app capability may raise this, but never infer it from guild metadata alone.
- Multipart request budget: 24 MiB internal packing target under Discord's documented 25 MiB Create Message maximum, leaving room for boundaries and JSON.
- Discovery ceiling: metadata-only for files larger than 50 MiB; no automatic capture.
- Filename: 120 UTF-8 bytes after sanitization.
- Caption/attachment description: 1,024 characters, matching Discord's documented attachment-description ceiling.

Discord states that upload limits apply per attachment and default to 10 MiB, potentially higher for Nitro/boost contexts. It separately documents a 25 MiB maximum Create Message request. The packer must satisfy both; it cannot assume ten 10 MiB files fit one request. See [Discord Uploading Files](https://docs.discord.com/developers/reference#uploading-files) and [Create Message](https://docs.discord.com/developers/resources/message#create-message).

## Malware and security boundaries

### Threats

- Known malware, polyglots, parser exploits, macros, malicious PDFs, decompression bombs, and disguised executables.
- SSRF/redirect abuse through attachment URLs.
- Filesystem traversal, symlink/TOCTOU attacks, devices/FIFOs, and overwriting project files.
- Document prompt injection and data exfiltration through model tools.
- Agents accidentally attaching secrets, credentials, logs, customer data, or another request's artifact.
- Public/signed links escaping the originating conversation.
- Scanner/parser compromise and scan-result staleness.

### Boundaries and policy

1. **Authorization boundary:** reject unauthorized sender/channel metadata before fetching bytes.
2. **Network boundary:** exact Discord CDN hosts, HTTPS, no redirects, bounded streaming. A fresh URL obtained through an authenticated Discord API call is preferable to trusting arbitrary URLs persisted in content.
3. **Quarantine boundary:** random non-executable storage outside repos/web roots; only the broker/scanners can read it.
4. **Scan boundary:** a pluggable malware scanner with engine/signature version and outcome (`clean`, `infected`, `error`, `unsupported`). `clean` means no known finding, not safe. Scanner errors fail closed for agent exposure.
5. **Parser boundary:** preview/extraction in a disposable, unprivileged, resource-limited sandbox with no credentials or network. CDR may produce a separate derivative; never overwrite the original or conceal the transformation.
6. **Agent boundary:** input projection is read-only and contains only accepted references. Attachment-bearing runs should use a restricted sandbox/container with no resident credentials. `noexec` is useful defense in depth but does not stop a privileged process from copying bytes elsewhere.
7. **Outbound boundary:** recapture, malware scan, secret/DLP scan, classification check, and destination authorization before selection. Block private keys, `.env`-like files, credential stores, token patterns, and configured sensitive roots. Overrides require an audited admin confirmation and cannot override known credentials/secrets policy.
8. **Serving boundary:** private storage only. Downloads go through an authorization-checking handler or short-lived scoped signature; never expose local paths or permanent public URLs.

The current `danger-full-access` managed launcher cannot honestly isolate hostile files. The initial production gate should therefore require either a restricted attachment sandbox or a narrow allowlist of trusted principals and low-risk types. This is the most important operational caveat in the design.

## Provenance and custody

Every artifact reference must answer:

- Which immutable bytes are these?
- Who or what introduced them?
- Which Discord message, resident request, turn, execution, and declaration caused custody?
- Which validator/scanner policy accepted or rejected them?
- Who is authorized to read or deliver them, and to which conversation?
- Which derived previews or transformed versions came from them?
- Which outbox batch attempted delivery, with which fence and provider evidence?
- When may the reference and unreferenced bytes be deleted?

Required causal edges are:

```text
Discord attachment -> inbound artifact ref -> resident request/turn -> execution input
agent declaration -> outbound artifact ref -> selection -> delivery group/batch -> Discord attachment receipt
source artifact ref -> preview/CDR derivative ref
```

Artifact references are append-safe in provenance. State can advance monotonically (`requested -> quarantined -> accepted/rejected -> available -> selected -> delivered/expired`), but origin, digest, request, and security-realm fields cannot be rewritten. A correction creates a new event/reference or a superseding relationship.

## Manifest and event schema

### Canonical artifact reference

The following is a logical schema, not a storage prescription:

```json
{
  "schema_version": "arnold-resident-artifact-ref-v1",
  "artifact_ref_id": "arf_...",
  "blob": {
    "digest": "sha256:...",
    "size_bytes": 123456,
    "storage_realm": "resident-default"
  },
  "direction": "outbound",
  "state": "accepted",
  "origin": {
    "kind": "agent_declaration",
    "request_id": "req_...",
    "turn_id": "turn_...",
    "execution_id": "exec_...",
    "run_id": "subagent-...",
    "declaration_id": "decl_...",
    "actor_id": "resident-managed-codex"
  },
  "names": {
    "original": "internal-research-final.pdf",
    "display": "research-report.pdf"
  },
  "media": {
    "declared_mime": "application/pdf",
    "detected_mime": "application/pdf",
    "outbound_mime": "application/pdf"
  },
  "policy": {
    "classification": "conversation_private",
    "validation_profile": "resident-artifact-v1",
    "scan_status": "clean",
    "scanner_engine": "configured-engine",
    "scanner_signature_version": "...",
    "secret_scan_status": "clear"
  },
  "authorization": {
    "principal_id": "discord-user:...",
    "conversation_scope_id": "discord:...",
    "allowed_uses": ["agent_input", "reply_attachment"]
  },
  "presentation": {
    "caption": "Architecture analysis and acceptance matrix",
    "role": "primary",
    "order": 0,
    "required": true
  },
  "retention": {
    "class": "conversation-artifact",
    "expires_at": "2026-08-09T00:00:00Z",
    "legal_hold": false
  },
  "created_at": "2026-07-10T00:00:00Z"
}
```

Restricted source paths, signed CDN URLs, and raw scanner reports belong in access-controlled operational records, not the general manifest projection.

### Inbound Discord origin extension

```json
{
  "kind": "discord_attachment",
  "transport_attachment_id": "123...",
  "transport_message_id": "456...",
  "attachment_ordinal": 0,
  "guild_id": "...",
  "channel_id": "...",
  "thread_id": null,
  "author_id": "...",
  "received_at": "..."
}
```

### Delivery group/outbox item

```json
{
  "schema_version": "arnold-resident-artifact-delivery-v1",
  "delivery_group_id": "adg_...",
  "request_id": "req_...",
  "causal_execution_id": "exec_...",
  "reply_target": {
    "transport": "discord",
    "conversation_key": "discord:...",
    "reply_to_message_id": "456..."
  },
  "terminal_text_digest": "sha256:...",
  "artifact_ref_ids": ["arf_1", "arf_2"],
  "batches": [
    {
      "batch_id": "adb_...:0",
      "index": 0,
      "artifact_ref_ids": ["arf_1", "arf_2"],
      "nonce": "a1b2c3d4e5f6g7h8i9j0-0",
      "status": "pending",
      "record_version": 1,
      "lease_id": null,
      "fence": 0,
      "attempts": []
    }
  ],
  "status": "pending",
  "created_at": "..."
}
```

### Event vocabulary

Use the lifecycle ledger's common envelope (`event_id`, schema version, request/turn/execution IDs, causal event, actor, record version, fence, timestamp) with these artifact kinds:

- `artifact.ingest_requested`
- `artifact.download_claimed`
- `artifact.quarantined`
- `artifact.validation_completed`
- `artifact.rejected`
- `artifact.blob_promoted`
- `artifact.reference_created`
- `artifact.materialized_for_run`
- `artifact.declaration_received`
- `artifact.capture_completed`
- `artifact.selection_planned`
- `artifact.preview_created`
- `artifact.delivery_batched`
- `artifact.upload_attempt_started`
- `artifact.upload_succeeded`
- `artifact.upload_outcome_unknown`
- `artifact.retry_scheduled`
- `artifact.delivery_dead_lettered`
- `artifact.reference_expired`
- `artifact.blob_gc_eligible`
- `artifact.blob_deleted`

Events contain identifiers, outcome categories, sizes, and MIME families, not message contents, filenames in general logs, signed URLs, credentials, or file bytes.

## Discord API constraints and multipart delivery

The design should follow Discord's current documented constraints rather than library folklore:

- Message content is at most 2,000 characters.
- An attachment description is at most 1,024 characters.
- A Create Message request is at most 25 MiB.
- The default upload limit is 10 MiB **per file**, possibly higher depending on context.
- Files require `multipart/form-data`. Non-file fields go in `payload_json`; file parts are uniquely named `files[n]`; each partial attachment uses the matching placeholder ID and may specify filename/description.
- Replies require `READ_MESSAGE_HISTORY`, the referenced message must exist, and it cannot be a system message.
- `nonce` is at most 25 characters. With `enforce_nonce=true`, Discord checks uniqueness only “in the past few minutes”; it is helpful but not a permanent exactly-once key.
- Rate limits must be driven by Discord response headers and `retry_after`, not hard-coded delays.

Sources: [Message Resource / Create Message](https://docs.discord.com/developers/resources/message#create-message), [Uploading Files](https://docs.discord.com/developers/reference#uploading-files), and [Rate Limits](https://docs.discord.com/developers/topics/rate-limits).

### Multipart construction

For each batch, build one standard Create Message request:

- `payload_json.content`: terminal summary on the first batch; compact continuation text on later batches.
- `payload_json.message_reference`: immutable originating Discord message, only on the first batch unless product UX deliberately replies each batch.
- `payload_json.allowed_mentions`: an empty parse list to prevent filenames/captions/result text from causing pings.
- `payload_json.nonce` plus `enforce_nonce=true`: stable per delivery-group/batch.
- `payload_json.attachments[n]`: `id=n`, sanitized unique filename, capped description.
- `files[n]`: exact bytes from the immutable CAS object with detected outbound MIME.

The sender should stream from CAS and know every part size before opening the HTTP request. It must reject a plan that exceeds the request budget instead of waiting for Discord to return 400/413. The current `discord.py` `channel.send` path can be extended if it exposes all required fields and evidence; otherwise a narrow adapter can call the official endpoint while sharing the library's authentication/rate-limit discipline. Do not create a parallel bot loop.

### Multiple files

- Use a conservative internal maximum of 10 files per Discord message even though the current Create Message table does not publish a general attachment-count limit. This is an internal batching policy, not a claim about provider capacity.
- Also pack by estimated encoded request bytes, so the 24 MiB internal request target may split fewer than 10 files.
- Give every batch a stable `batch_id`, artifact list, nonce, and independent outbox state.
- First message: concise outcome plus “Files 1-N of M.” Continuations: “Files X-Y of M for request `<short-id>`.”
- If batch 2 fails after batch 1 succeeds, mark the group `partial`; retry only batch 2. Never resend committed batches.
- A permanent partial failure produces a compact status message/outbox item only if that message itself can be delivered without creating ambiguity.

### Oversize files

Order of preference:

1. Deliver directly if the file and packed request fit the verified Discord capability.
2. If a private artifact-download service exists, send a short-lived, conversation-authorized link with filename, size, digest prefix, and expiry. Suppress unfurls for sensitive artifacts. In a guild channel, a bearer link is visible to everyone who can read the message, so policy may require DM delivery or confirmation.
3. Split or compress only when the user/agent explicitly asks. Never auto-zip: archives hide scan results, worsen UX, and may create decompression risk. A split archive must be scanned before and after construction and clearly labeled.
4. If no secure serving path exists, retain the artifact under normal TTL, send its artifact ID/size and a clear “too large for Discord” failure, and do not expose a local path.

## Filenames, captions, and previews

### Filenames

- Preserve a sanitized form of the declared display name for UX; retain the original only in restricted provenance.
- Normalize Unicode (NFKC), remove control and bidi override characters, collapse whitespace, take the basename, reject `.`/`..`, strip leading dots/hyphens, and cap by UTF-8 bytes.
- Preserve a safe extension only when it agrees with detected type/policy. On suspicious mismatch, reject or use a neutral extension; never disguise content.
- Resolve duplicates deterministically: `report.pdf`, `report-2.pdf`, and so on, based on selection order.
- Prefix `SPOILER_` only when explicitly requested; do not infer sensitivity from content.

### Captions

Use three levels:

1. Terminal summary in message content.
2. Batch label in message content for multi-message delivery.
3. Per-file attachment description, capped at 1,024 characters and redacted like other outbound text.

Captions are never interpreted as Markdown commands or mention permission. The first batch should still stand alone if later batches fail.

### Previews

- Let Discord render supported images naturally. An image may also be referenced as `attachment://filename` in a standard embed, but only for Discord-supported image types.
- For small text/Markdown/JSON/CSV files, include a short escaped snippet in the message only when it materially helps and fits; the attachment remains authoritative.
- PDF first-page images, image thumbnails, and media metadata are optional derivative artifacts produced in a sandbox. Each derivative records its parent digest, renderer/version, scan result, and separate retention.
- Do not auto-preview Office files, HTML, SVG, archives, or executable content in phase one. HTML/SVG can execute active content in viewers; Office/PDF renderers have their own attack surface.
- Preview failure never blocks the original unless `preview_policy=required`.
- Avoid Components V2 initially: Discord documents that setting `IS_COMPONENTS_V2` changes content/attachment presentation rules and is unnecessary for the core file-delivery use case.

## Retention and cleanup

Retention is reference based, not blob based. A blob is deletable only when no live reference, delivery attempt, legal/incident hold, or backup policy requires it.

Recommended configurable defaults:

| Data | Default |
|---|---|
| Unfinished quarantine part | 24 hours |
| Infected/rejected quarantine | 7 days, restricted; immediate purge if policy requires |
| Accepted inbound/outbound conversation artifact reference | 30 days after terminal request |
| Preview derivative | 7 days or parent expiry, whichever is sooner |
| Delivery attempt metadata and provider receipts | 180 days, without file content |
| Dead-letter reference | 30 days after operator resolution |
| Orphan CAS blob grace | 7 days after first observed unreferenced |

These are starting points, not a claim about an existing message-content policy. Production configuration must align with the resident's established Discord content retention, legal hold, and backup deletion behavior.

Cleanup uses mark-and-sweep:

1. Expire references in a ledger transition.
2. Recompute blob reachability across inbound, execution, declaration, preview, outbox, hold, and legacy projections.
3. Mark an unreferenced blob with `gc_eligible_at`.
4. After grace and a second reachability check, delete bytes and record a tombstone.
5. Backups/object versions must age out under a documented schedule; otherwise “deleted” is misleading.

Discord `MESSAGE_DELETE` should create a privacy tombstone and shorten/revoke the inbound reference unless a lawful incident hold exists. It must not silently rewrite history.

## Idempotency, delivery retries, and reconciliation

### Keys

- Inbound artifact identity: transport + conversation scope + message snowflake + attachment snowflake.
- Blob identity: security realm + SHA-256 digest.
- Declaration identity: run/execution + agent-supplied or broker declaration ID.
- Selection identity: request + terminal delivery role + ordered artifact-reference IDs.
- Batch identity: delivery group + deterministic batch index and member digest.
- Provider nonce: stable 25-character encoding of batch identity.

### Send protocol

1. Commit the terminal delivery group and all batches with their exact content/artifact digests.
2. Claim one batch with a lease/fence and persist `sending` plus attempt ID before the network call.
3. Send one multipart request with stable nonce and `enforce_nonce=true`.
4. On a response, verify returned attachment count, filenames, sizes where available, message ID, channel, and nonce; then commit the provider receipt with the current fence.
5. On 429, respect `Retry-After`/`retry_after` and bucket metadata. On retryable 5xx/network failure before a request is known sent, back off with jitter under policy.
6. On timeout/reset after bytes may have reached Discord, record `unknown`, not `retry_pending`.

### Unknown outcomes

Discord nonce enforcement is bounded to the recent past. Reconciliation should consume the resident's Gateway `MESSAGE_CREATE` events and, if necessary and authorized, inspect a bounded recent channel history for a bot-authored message with the stable nonce. A match commits success and attachment receipts. No match while still inside the nonce window permits a same-nonce retry. Once the window is no longer safely known, unresolved delivery becomes operator-visible `unknown/dead_letter`; do not risk a duplicate while claiming exactly-once behavior.

Editing an existing message to add missing files is not the default recovery mechanism. Discord API v10 requires the edit request's `attachments` array to include every retained attachment, which complicates custody and can accidentally remove files. Independent immutable batches are simpler.

## Authorization and privacy

- Preserve current inbound allowlists. Attachment metadata does not authorize downloading; authorize the subject and destination first.
- Bind every artifact reference to a principal and immutable conversation/request scope. The agent gets only refs selected into its run.
- A declaration cannot choose or alter the Discord destination. Delivery inherits the originating request's immutable reply target.
- Re-check the bot's send/attach/read-history permissions at delivery, but never retarget to a mutable “current” channel when permission fails.
- Conversation history should contain artifact IDs and safe summaries, not signed URLs or raw bytes. Do not automatically inject extracted full text into future turns.
- Hashes, filenames, MIME details, user/channel IDs, and scanner findings can be sensitive. Keep filenames out of metric labels; show full hashes only in restricted diagnostics; use digest prefixes in user UX.
- Do not submit private files to public malware-scanning services. Scanner providers must meet the same data residency/privacy policy as storage.
- Signed oversize links must be short-lived, scoped to one artifact and authorization context, revocable, and audited. A stable public URL is forbidden.
- DLP and redaction run on terminal text, captions, filenames, text-like files, and extractable metadata. Binary formats that cannot be inspected under policy fail closed or require explicit approved handling.

## Failure states and user-visible behavior

| Failure | Durable state | Default user behavior |
|---|---|---|
| Unauthorized sender/channel | denied; no download intent | No file fetch; existing denial behavior/audit |
| Missing attachment metadata due intent/readiness | ingress capability failure | State that attachments were unavailable; do not run as attachment-free |
| CDN URL expired/unavailable | `source_expired`/`download_failed` | Ask user to resend; retain metadata only |
| Declared/actual size exceeds policy | `rejected_size` | Name safe file and configured limit |
| MIME/signature/extension suspicious | `rejected_type` | Explain unsupported or mismatched type without exposing scanner internals |
| Malware found | `rejected_malware` | Say file was blocked; no agent exposure |
| Scanner unavailable/error | `scan_blocked` | Retry boundedly, then visible fail-closed status |
| Archive/encrypted active content unsupported | `rejected_unsupported` | Request a safe extracted format |
| Materialization fails/missing blob | `custody_error` | Do not launch; reconcile or dead-letter |
| Agent declares outside root/symlink/device | `declaration_rejected_path` | Return structured error to agent; audit |
| Source changes during capture | `source_changed` | Ask agent to close/stabilize and redeclare |
| Outbound malware/secret finding | `delivery_blocked_policy` | Omit optional file or fail required file; never print the secret |
| No explicit declaration | no selection | Send text with “no attachable artifact declared” when a file was expected |
| File too large for Discord, no link service | `oversize_retained` | Report artifact ID, size, and retention; no local path |
| Discord 403/404 or deleted reply target | permanent delivery failure/dead letter | No silent channel fallback; operator-visible exact reason |
| Discord 429/5xx | retry scheduled | Usually no extra user message until terminal/dead-letter |
| Timeout after possible acceptance | `unknown` | Reconcile by nonce/Gateway/history; never immediate blind retry |
| Later batch fails after earlier success | `partial` | Preserve delivered receipts; retry only missing batch; report partial terminally if permanent |
| Retention expires before delivery | invariant violation/dead letter | Alert; never claim delivery |

Deleting or losing the original Discord message makes an exact reply impossible. The default must be no silent fallback. A separately authorized operator transition may permit an unthreaded message in the same immutable conversation, clearly labeled as a fallback, but that is a new effect with its own outbox key.

## Observability and operations

### Structured logs/traces

Include request, turn, execution, artifact-reference, declaration, delivery-group, batch, attempt, lease, fence, and provider-message IDs as applicable. Include outcome category, MIME family, byte count, duration, and policy/scanner version. Exclude message/file contents, signed URLs, tokens, full local paths, and generally filenames.

Useful spans:

- `artifact.ingest`
- `artifact.download`
- `artifact.validate`
- `artifact.scan`
- `artifact.promote`
- `artifact.materialize`
- `artifact.capture_declaration`
- `artifact.plan_delivery`
- `artifact.discord_upload`
- `artifact.reconcile_unknown`
- `artifact.gc`

### Metrics

- `resident_artifact_ingest_total{outcome,source,mime_family}`
- `resident_artifact_bytes{direction,mime_family}` histogram
- `resident_artifact_validation_total{outcome,rule}`
- `resident_artifact_scan_total{outcome,engine}`
- `resident_artifact_quarantine_age_seconds` oldest gauge
- `resident_artifact_declaration_total{outcome,role}`
- `resident_artifact_delivery_total{outcome,batch_count}`
- `resident_artifact_delivery_attempts` histogram
- `resident_artifact_delivery_oldest_pending_seconds`
- `resident_artifact_unknown_outcome_total`
- `resident_artifact_partial_delivery_total`
- `resident_artifact_dead_letter_total{reason}`
- `resident_artifact_cas_bytes` and `resident_artifact_unreferenced_bytes`
- `resident_artifact_gc_total{outcome}`

Never label metrics with request/user/channel/artifact IDs, filename, digest, or MIME subtype where cardinality/privacy is uncontrolled.

### Alerts and operator view

Alert on quarantine/pending age, scan-service outage, storage low-water mark, repeated validation invariant failures, unknown Discord sends, dead letters, missing blobs, partial delivery age, unauthorized access attempts, migration divergence, and GC failures.

One status command/view should show the lifecycle by request: inbound attachments, scan decisions, run projections, declarations, selected refs, batch states, provider receipts, expiry, and safe operator actions. Recovery actions are constrained ledger transitions (`retry`, `reconcile`, `approve fallback`, `extend retention`, `purge`), not arbitrary shell edits.

## UX contract

### Inbound

- React/acknowledge only after durable message and ingest intent custody, not after successful parsing.
- If scanning takes noticeable time, say “Received 2 files; validating them before the agent starts.”
- Show safe filenames and counts, not hashes or internal paths.
- For mixed accepted/rejected inputs, launch only if request policy permits and clearly list omissions. A required rejected file blocks the run.
- An attachment-only Discord message is a valid request only if the resident has an instruction/context for what to do; otherwise the normal agent can ask for intent after safe ingest.

### Outbound

- The first delivery message stands alone: outcome, verification, caveat, and “Attached: N files.”
- Each file has a meaningful sanitized name and short caption.
- Multi-batch messages show a stable short request ID and progress (`Files 1-6 of 12`).
- Optional omitted files are summarized once, not with noisy per-retry messages.
- Oversize UX gives size, reason, secure-link expiry if present, and artifact retention deadline.
- A user can reply “send only the PDF” because artifact IDs/names remain associated with the originating request and authorization scope.

## Alternatives evaluated

| Alternative | Advantages | Problems | Decision |
|---|---|---|---|
| Parse file paths from final agent prose | Very little code | Ambiguous, spoofable, leaks paths, races mutable files, model-specific | Reject |
| Attach every new/changed worktree file | Appears automatic | High secret/intermediate leakage risk; noisy; branch/worktree ambiguity | Reject |
| Convention-only `outputs/` directory | Simple and cross-agent | Still permits stale/unintended files; lacks immediate validation and provenance | Keep only as discovery input |
| Sidecar JSON written at run end | Cross-agent, easy migration | Malformed/racy; no immediate broker feedback; files can disappear/change | Compatibility fallback |
| Agent uploads directly to Discord | Fast path | Gives transport credentials/authority to agent; bypasses outbox, policy, provenance, retries | Reject |
| Store only Discord CDN URLs | No local bytes | Signed URLs expire; Discord deletion loses custody; no safe scan/materialization | Reject |
| Store bytes in lifecycle database | Transactionally convenient | Poor large-object behavior, backup bloat, DB coupling | Reject for bytes; keep metadata in ledger/store |
| Separate VibeComfy attachment service | Local optimization | Duplicates policy/state; excludes other resident agents; lifecycle split brain | Reject |
| General broker + CAS + ledger/outbox | Clear custody, cross-agent, durable, testable | More schema and operational components | Recommend |
| Object store first | Strong multi-host durability/scaling | Credentials, service dependency, signed-link/privacy complexity | Backend option after local durable CAS contract |
| Local durable CAS first | Reuses current seams/volume; simplest deployment | Requires backup and shared-volume discipline | Recommend first backend |

## Incremental implementation plan

This is a proposed work breakdown for the existing corrective initiative, not a new initiative.

### Phase 0 — Contract and characterization

- Add versioned artifact/reference/declaration/delivery schemas and transition table to the M1 lifecycle contract.
- Inventory current voice attachment, image blob, message flags, managed manifest, completion sweep, and Discord fake behavior.
- Define policy configuration, security realms, limits, retention, and feature flags.
- Extend Discord fakes to preserve attachment metadata, multipart parts, nonce, and provider outcomes.

**Gate:** schema rejects mutable provenance, missing request/reply scope, stale fences, missing blob references, and illegal terminal regression.

### Phase 1 — General artifact broker and CAS

- Wrap/evolve `BlobStore` with digest-derived immutable keys, quarantine, atomic promotion, stat/verify, and reference-aware GC.
- Implement filename, MIME/signature, size, malware, secret-scan, and policy result interfaces with fake deterministic scanners.
- Add artifact ledger/store APIs and a read-only operator status projection.

**Gate:** crash tests at every write boundary never yield a live ref to missing bytes; orphan bytes are safely collectable.

### Phase 2 — Inbound Discord custody and agent projection

- Persist attachment metadata/intents transactionally with message provenance in M2.
- Replace the audio-only downloader shape with broker streaming while keeping transcription behavior compatible.
- Gate turn readiness on terminal attachment ingest states.
- Materialize accepted refs into restricted run inputs and include a bounded manifest in agent context.

**Gate:** unauthorized traffic causes zero network fetches; restart/replay preserves every accepted attachment or a visible terminal failure.

### Phase 3 — Cross-agent declarations and selection

- Add the authenticated common declaration adapter to the resident-managed launcher in M3.
- Capture from open descriptors with root/path/type/TOCTOU checks and execution fences.
- Add the legacy sidecar importer and bounded advisory discovery.
- Update the common completion-delivery prompt to explain declaration, required/optional behavior, and safe names/captions.

**Gate:** all resident-managed Codex profiles use the same declaration path; a stale/superseded worker cannot declare or select a file.

### Phase 4 — Artifact-aware terminal outbox and Discord multipart

- Extend `OutboundMessage`/outbox projections with immutable artifact refs and delivery groups/batches in M4.
- Implement deterministic packing, multipart streaming, replies, empty allowed mentions, captions, receipt verification, rate-limit handling, nonce reconciliation, partial status, and dead letters.
- Keep text-only behavior byte-for-byte compatible when no artifacts are selected.

**Gate:** process death before/during/after multipart send converges without resending committed batches; unknown outcomes remain explicit.

### Phase 5 — Recovery, retention, previews, and oversize links

- Add M5 startup/continuous reconciliation for ingest claims, missing projections, sending leases, unknown outcomes, expired refs, and orphan blobs.
- Add mark-and-sweep GC, backup deletion documentation, and Discord deletion privacy events.
- Add only low-risk preview derivatives first.
- Add authenticated oversize serving after its authorization model is reviewed; until then fail visibly without local paths.

**Gate:** seeded partial-state matrix converges under repeated concurrent sweeps; no retained outbox item loses its blob.

### Phase 6 — Adversarial rollout

- Run the M6 fault/security suite and map results to every North Star invariant.
- Flags: `metadata_only` -> `quarantine_shadow` -> trusted-principal inbound -> declaration shadow -> trusted-principal multipart canary -> broader rollout.
- Require scanner health, restricted attachment runner or documented trusted-type gate, storage headroom, dashboards, runbook, rollback, and retention jobs before canary.
- Rollback disables new ingest/delivery while retaining ledger/CAS data and text-only serving authority; it does not delete artifacts.

**Gate:** canary has no provenance violations, secret/malware escapes, duplicate visible batches, unresolved old unknowns, or cleanup backlog beyond thresholds.

## Acceptance test matrix

### Contract and storage

- Same bytes from two messages yield one physical realm blob and two provenance/ACL refs.
- Same digest in different security realms does not grant or reveal cross-realm access.
- Declared, detected, and outbound MIME are persisted separately.
- Crash before promotion leaves only expiring quarantine; crash after promotion/before ref leaves a GC-safe orphan; ref commit cannot precede durable bytes.
- Corrupt/missing CAS bytes fail retrieval, alert, and never deliver.
- GC retains a blob referenced by inbound, run, preview, outbox, dead letter, legal hold, or legacy projection; it deletes only after two reachability checks and grace.

### Inbound security and custody

- Unauthorized user, guild, or channel results in no CDN request.
- HTTP, lookalike host, user-info host trick, DNS/redirect, and non-Discord URLs are rejected.
- Declared-size, `Content-Length`, and streamed-size lies hit the correct ceiling without excess memory/disk use.
- Filename traversal, Unicode controls, double extensions, null/control bytes, and collisions produce safe deterministic names.
- MIME spoof/polyglot fixture is rejected or quarantined according to policy.
- Known malware test fixture is blocked; scanner timeout/error fails closed; scan engine/version is recorded.
- Archive bomb, excessive image dimensions, huge PDF page count, and encrypted active document are bounded.
- Kill/restart at intent, download claim, partial stream, quarantine fsync, scan, promotion, ref commit, and materialization yields exactly one terminal artifact outcome.
- Expired Discord URL is visible and prevents silent attachment-free dispatch.
- Two messages coalesced in either schedule retain ordered per-message artifact refs and exact reply provenance.
- Attachment-only and mixed accepted/rejected messages follow required/optional policy.
- Run projection cannot mutate CAS bytes and cannot access another request's refs.

### Declarations and discovery

- A valid produced file is captured immediately and survives source deletion before delivery.
- A discovered existing file can be explicitly declared and retains declaration/run provenance.
- Relative traversal, absolute disallowed root, symlink, hard-link edge case, directory, FIFO, device, socket, and missing file are rejected.
- A file changed/truncated/appended during capture returns `source_changed` and creates no accepted ref.
- Duplicate declaration ID is idempotent; conflicting reuse is rejected.
- Concurrent declarations preserve deterministic order and filename collision resolution.
- A stale execution fence cannot declare, replace, or select artifacts.
- Advisory filesystem discovery never auto-attaches `.env`, keys, logs, caches, run internals, or any undeclared candidate.
- Legacy sidecar imports valid records once and rejects malformed/path-unsafe records visibly.
- VibeComfy, Megaplan, and AgentBox resident profiles exercise the same launcher/broker contract.

### Outbound policy and Discord API

- Private key/token fixture in a required file blocks delivery without logging the secret; optional file omission is reported.
- Malware finding on an outbound file blocks it even if the agent created it.
- Multipart parts use unique `files[n]`, matching attachment IDs, safe filenames, detected MIME, capped descriptions, immutable bytes, empty allowed mentions, correct reply reference, and stable nonce.
- Text-only requests preserve current chunk/reply behavior.
- One file, multiple files, duplicate digest/different name, filename collisions, empty file, and binary file deliver correctly.
- Packing splits on both internal file-count and 24 MiB request budgets; no request exceeds 25 MiB.
- A file over the verified per-file limit chooses secure link or `oversize_retained`, never a local path or blind upload.
- A 400 validation failure and 401/403/404 are permanent/dead-lettered appropriately; a deleted reply target does not silently retarget.
- A 429 uses provider `retry_after`; route/global buckets are respected; retry storms do not trip invalid-request limits.
- 5xx and pre-send network errors back off under fake time.
- Timeout after possible provider acceptance becomes `unknown`; a Gateway/history nonce match reconciles to the returned message/attachments.
- Same-nonce retry inside the safe window creates one visible message; unresolved outcome beyond the window dead-letters rather than claiming exactly once.
- Kill after Discord accepts but before receipt commit reconciles after restart.
- Three batches with batch two failure retain batches one/three evidence and retry only the missing batch according to ordering policy; permanent result is `partial`.
- Returned attachment receipt mismatch is an invariant violation, not success.

### Privacy, retention, and operations

- Artifact access in a different user/conversation scope is denied even when the digest is known.
- Metrics/logs contain no content, signed URL, token, full path, filename label, or full digest.
- Signed oversize link expires, is revocable/audited, and enforces the intended scope.
- Discord message deletion creates a tombstone and expiry transition without rewriting provenance.
- Retention fake-clock tests cover quarantine, accepted refs, previews, dead letters, holds, orphan grace, and backup-age reporting.
- Startup recovery completes before ingress readiness or reports bounded degraded readiness visibly.
- Operator `retry`, `reconcile`, fallback, retention extension, and purge actions require authorization and create ledger events.
- Feature-flag tests cover legacy text/audio only, shadow ingest, dual projections, new authority, rollback, and split-brain detection.

## Rollout caveats and recommended destination

This report is stored at the correct canonical destination: the `research/` directory of the existing `discord-resident-delegation-delivery-corrective` initiative. No new initiative is warranted.

The design is ready to inform brief revisions, but implementation should not begin by merely adding `files=` to `DiscordOutboundSink`. The first dependency is the initiative's unified lifecycle ledger/outbox and immutable request provenance. The security rollout must also resolve the current full-permission agent boundary for attachment-bearing runs; without that, the honest initial scope is trusted users and tightly controlled file classes, not arbitrary Discord uploads.
