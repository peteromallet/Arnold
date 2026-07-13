# M7 — Resident Completion Attachments v1

## Outcome

Add an opt-in resident completion capability that lets a resident-managed delegated agent declare project files through a structured result contract, captures accepted bytes into durable immutable custody, and delivers deterministic attachment batches with the completion's Discord reply. Text completion remains independently deliverable, while every rejected file, failed batch, ambiguous provider outcome, and retry is represented honestly and durably.

This is the final additive milestone. It follows M1–M6 and does not reopen, renumber, or weaken their lifecycle-correctness contracts.

## Scope

In scope: the resident-managed agent system prompt; the versioned machine-readable completion/result protocol; opt-in configuration and transport capability gating; declaration parsing; project-root-confined file validation; stable capture into resident-owned durable storage; captured SHA-256 and metadata evidence; deterministic Discord batching; durable outbox attempts, provider receipts/message IDs, retry/reconciliation state, and attachment- or batch-level partial/unknown reporting; text-only and non-Discord compatibility; focused unit, fault, restart, and adapter tests; operator-facing configuration and security documentation.

Out of scope: inferring attachment paths from final prose, scanning the project tree, inbound Discord attachments, malware scanning, secret scanning, DLP, content classification, archive inspection, sandboxing a full-access agent, public file hosting, automatic splitting or archiving, and operating or changing the state of the paused chain.

## Locked product and protocol decisions

- The resident-managed agent system prompt teaches a versioned, machine-readable attachment declaration. The result protocol carries an ordered attachment collection separate from final prose. No path in prose, Markdown links, terminal output, manifest discovery, or worktree diff authorizes an upload.
- Each declaration identifies a project-relative source path and the minimal presentation metadata needed by delivery. Protocol validation produces explicit per-declaration accepted or rejected state; malformed declarations never silently become text-derived paths.
- Completion attachments are opt-in and disabled by default. Enabling them requires explicit resident configuration and a Discord transport capability; absent, false, invalid, or unsupported configuration preserves the existing text-only path.
- The capture boundary is the delegated task's project directory. A declared source must be a readable regular file within that directory. Reject absolute/traversal escapes, symlinks (including symlinked path components), directories, devices, FIFOs, sockets, and files that are unreadable or change while being captured.
- Validate and hash while copying to resident-owned durable storage, compare stable pre/post open-file metadata, and publish capture evidence only after the immutable copy is complete and durably committed. Delivery and every retry read the captured copy by its durable identity, never the mutable source path.
- A file may contain at most 10 MiB (10,485,760 bytes). A Discord batch may contain at most 24 MiB (25,165,824 bytes) and 10 files. A completion may contain at most three batches, so its attachment payload is bounded to roughly 72 MiB and 30 files. Packing is deterministic from the accepted declaration order and captured sizes. A source that cannot fit these limits is rejected with guidance that the producing agent must split or archive it into compliant declared parts; v1 does not transform it automatically.
- Text delivery is independently durable and is attempted even if declaration, capture, batching, or attachment delivery fails. User-visible completion status identifies each rejected/failed attachment or batch without claiming that the text failed, and does not expose sensitive absolute paths.
- Each logical batch has a stable idempotency identity and immutable ordered capture membership. Durable evidence includes capture identity, SHA-256, byte count and safe metadata; batch identity/order; attempt state; provider receipt and message ID when known; and explicit sent, retryable, permanent-failure, partial, or unknown outcomes.
- Retry only failures known to be pre-send or provider-rejected. When provider acceptance is ambiguous, reconcile using supported provider receipt/message evidence and keep the batch `unknown` or require an explicit operator decision; never blindly resend it. A successful batch is never rebuilt from source paths or resent because a sibling batch failed.
- Text-only completions retain their existing protocol and delivery behavior. Non-Discord transports ignore or report the unsupported attachment capability according to their existing result contract while still delivering text; this milestone does not force Discord limits or APIs into transport-neutral code.

## Security boundary and explicit v1 limitation

V1 performs basic filesystem validation only. It does not perform malware, secret, or DLP scanning. This limitation applies to the M7 completion-output feature and does not remove separate inbound-artifact scanning contracts from earlier milestones. Project-directory containment is only an eligibility rule: project containment is not a security boundary. A full-access delegated agent can copy credentials, tokens, private source, or other sensitive material into an allowed regular project file and declare it for Discord delivery. The feature must be documented and configured as an exfiltration-capable trust decision; path containment, hashing, and immutable capture do not make file contents safe.

## Open questions for the plan

- Which existing resident result-envelope version should gain the attachment collection, and what compatibility projection is required for older result readers?
- Which resident-owned storage primitive from M1–M6 should hold captures and retention references without introducing a second delivery authority?
- What Discord API evidence can deterministically reconcile an accepted-but-unacknowledged multipart send, and which cases must remain operator-visible `unknown`?
- How should safe display names and duplicate declared paths be normalized without changing declaration order or leaking source layout?

## Constraints

Preserve all unrelated dirty work, completed lifecycle contracts, the current paused Sprint 2 state, existing text delivery, and non-Discord transports. Do not launch, resume, approve, retry, reconcile, or otherwise operate the chain. Do not claim malware/secret safety, treat project containment as isolation, parse final prose for files, re-read mutable source files on retry, exceed any count/byte/batch limit, or convert ambiguous provider outcomes into assumed success or automatic resend.

## Done criteria and objective acceptance evidence

- Prompt/protocol tests assert the resident-managed system prompt documents the structured declaration syntax, the versioned result schema accepts ordered valid declarations and rejects malformed ones, final prose alone yields zero attachments, and legacy text-only results still parse unchanged.
- Configuration tests prove the feature is disabled for absent/default/false configuration, enables only through the explicit opt-in plus Discord capability, and leaves non-Discord text delivery compatible.
- Capture tests cover a readable in-root regular file plus absolute paths, `..` traversal, lexical and resolved escapes, symlink leaf/components, directories, devices, FIFOs, sockets, unreadable files, replacement/truncation/mutation during capture, and source deletion/change after capture. Successful evidence matches the captured bytes' SHA-256 and size, and retries succeed from the immutable copy without opening the source.
- Limit tests use exact byte boundaries at 10 MiB per file and 24 MiB per batch, 10 files per batch, and three batches per completion; one-byte/count overages are rejected. Oversize results receive split/archive guidance and are never silently truncated, transformed, or sent.
- Deterministic batching tests prove identical ordered declarations and captured metadata produce identical batch identities/membership across restart, while byte/count constraints and the three-batch ceiling always hold.
- Delivery fault tests cover text success with declaration/capture failure, mixed attachment acceptance, a failed middle batch with successful siblings, retryable pre-send/provider rejection, permanent rejection, process death before and after provider acceptance, persisted receipts/message IDs, partial outcomes, and unresolved ambiguity with no blind resend.
- Idempotency tests prove duplicate completion processing converges on one capture per declaration identity and one logical send per batch; committed batches are not resent and failed siblings do not mutate successful batch membership.
- Compatibility tests prove unchanged text-only Discord completions and all existing non-Discord completion transports continue to deliver text when the attachment feature is disabled, unsupported, empty, partially failed, or fully failed.
- Documentation states every limit, opt-in/default behavior, split/archive responsibility, retention/retry evidence, partial/unknown semantics, absence of malware/secret/DLP scanning, and the full-access-agent exfiltration risk.
- Focused suites and proportional resident/Discord result-delivery regressions pass, and a final traceability table maps each criterion above to executable tests and persisted evidence fields.

## Touchpoints

Expected areas: resident-managed agent prompt construction; delegated result protocol/parser; resident configuration; project-root-safe capture and durable storage; completion/outbox records; Discord multipart adapter and reconciliation; transport capability handling; resident/Discord tests; operator/security documentation.

## Anti-scope

Do not infer paths from prose, broaden v1 into content scanning or sandboxing, treat containment as confidentiality, auto-package oversize files, sacrifice text delivery for attachment atomicity, retry from project paths, blindly resend unknown provider outcomes, alter non-Discord semantics, or touch paused-chain runtime state.
