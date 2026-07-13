# Add Resident Completion Attachments v1 Sprint

Amend the existing `discord-resident-delegation-delivery-corrective` initiative and executable chain so that **Resident Completion Attachments v1** is a new final sprint/milestone after every existing lifecycle-correctness milestone. Do not launch, resume, approve, or otherwise operate the paused chain.

Required scope:

- Structured, machine-readable attachment declarations taught in the resident-managed agent system prompt and represented in the result protocol; do not infer attachment paths from final prose.
- Durable capture of declared files before Discord delivery, with retries reading immutable captured copies rather than mutable source paths.
- Opt-in and disabled by default.
- Basic validation only: files must be regular files inside the delegated task's project directory; reject traversal, symlinks, directories, devices, sockets, and changing/unreadable files.
- Limits: 10 MiB per file; 24 MiB per Discord message batch; at most 10 files per batch; at most 3 batches per completion (roughly 72 MiB total). Oversize outputs must be split or archived into compliant parts.
- No malware, secret, or DLP scanning in v1. Explicitly document that a full-access agent can copy sensitive material into an allowed project file and exfiltrate it; project containment is not a security boundary.
- Preserve text delivery if an attachment fails and report attachment-level or batch-level partial failures clearly.
- Durable retry/idempotency and delivery evidence covering captured hashes/metadata, deterministic batches, provider receipts/message IDs, and partial/unknown outcomes. Avoid blind retries when provider outcome is ambiguous.
- Preserve compatibility for text-only completions and non-Discord transports.
- Add objective acceptance criteria and focused tests for prompt/protocol declaration, capture validation, limits, batching, retries, partial failure, compatibility, and disabled-by-default configuration.

Editorial requirements:

- Use only the canonical `megaplan-initiatives-v1` initiative tree.
- Add/update the final milestone brief under `briefs/`, update `chain.yaml`, and update README/NORTHSTAR/notes or decisions only as needed for a coherent executable epic.
- Preserve all existing unrelated work and the current paused Sprint 2 state; this task is editorial only.
- Inspect current numbering and choose the next final sprint number without renumbering existing milestones.
- Validate YAML/schema/dependency order and relevant initiative-layout/editorial tests.
- Return a concise summary of exact milestone added, changed planning artifacts, validation results, and any unresolved blocker.
