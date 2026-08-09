# M3 — Idempotent Delegation, Restricted Artifact Runs, and Fenced Declarations

## Outcome

Make delegated execution unique by resident request id and give every resident-managed Codex launch the same restricted attachment-bearing run envelope, read-only authorized input projection, and authenticated explicit outbound artifact declaration contract. Duplicate/stale workers cannot execute or declare/select artifacts, and declared bytes survive source mutation or deletion because the broker captures them immediately.

## Scope

Incident addition: consume the durable requested-execution custody created during inbound acceptance; reaching the launcher tool is not the first durable evidence that execution was requested.

In scope: ledger-backed launch intent/execution identity, atomic get-or-create/claim, durable launch receipts, lease renewal/reclaim, ambiguous launch recovery, and result/side-effect fences; a common launcher-provided `resident artifact declare` command/API bound to unforgeable run/execution/request identity and current fence; immediate no-symlink open/fstat/stream/recheck capture through the M2 broker with allowed-root, regular-file, special-file, hard-link/path traversal, source-change, size, malware, secret/DLP, classification, and destination-scope policy; explicit display name/caption/role/order/required/preview metadata; idempotent declaration IDs and deterministic selection/deduplication/collision rules; trusted producer artifact IDs; exact authorized user selection; bounded advisory filesystem discovery that never auto-selects; versioned legacy sidecar import as the only compatibility fallback; bounded `attachments.json`/`ATTACHMENTS.md` plus materialized relative inputs; run-manifest/result/status projections from the canonical ledger.

Apply the common contract across every resident-managed Codex caller and profile, including normal conversational delegation, VibeComfy, Megaplan/AgentBox resident profiles, repair/supervisor launches, scheduler jobs, VP todo/sweep handlers, reapers/recovery relaunches, and legacy/current manifest compatibility paths. Attachment-bearing runs must use a restricted sandbox/container with no resident credentials/network as policy requires and read-only request inputs, or be gated by an explicit trusted-principal + low-risk-type feature policy until that boundary is available.

Out of scope: Discord multipart upload, general Arnold workflow fencing, arbitrary archive extraction/preview, granting transport credentials to agents, or parsing paths from final prose.

## Locked decisions

- `request_id` is the logical execution uniqueness scope; attempts may vary without authorizing a second logical execution.
- Every committing worker presents the current lease/fence/version. Superseded workers cannot publish results, declarations, selections, or terminal intents.
- The authenticated run envelope supplies request/execution/run/fence and conversation scope; the agent cannot choose or alter a Discord target.
- Declaration captures from an already-open regular-file descriptor into broker custody immediately, verifies the source did not change, and returns a structured accepted/rejected artifact ref. Delivery never reopens the source path.
- Explicit declaration, trusted structured producer output, or exact authorized user selection is required. Discovery and final-text paths are hints only; `role=internal`/`attach=false` always wins.
- Selection order is declared order, declaration time, then artifact-ref ID. Same-digest refs retain independent provenance; physical/delivery dedupe never grants access.
- Manifests, sidecars, `result.md`, and filesystem scans are projections/bridges, never authority. Arbitrary Markdown links or “Artifacts:” prose are not declarations.
- Malware scanning, read-only modes, `noexec`, and prompt warnings are defense in depth, not substitutes for the restricted attachment execution boundary.

## Open questions for the plan

- Which available runner/container controls provide the smallest enforceable attachment profile while preserving required Codex repo operations and preventing access to resident credentials or other request artifacts?
- Which exact process-creation/receipt point counts as committed external launch when persistence is interrupted, and how is an orphan live process reconciled without PID-only trust?
- What launcher capability transport (sealed environment, inherited descriptor, or local authenticated endpoint) best prevents declaration forgery and cross-run use?
- Which existing producer/profile outputs warrant registered structured contracts, and which must use the common declaration command?

## Constraints

Preserve sealed stdin, explicit model/reasoning, target workspace, current secret handling, resident-vs-workflow distinction, and text-only behavior. Do not make CAS writable or hard-linked into a run, reveal internal paths, send bytes to public scanning services, or allow declaration outside configured roots. Concurrent duplicates must converge without busy loops. Required artifact failures must affect the terminal result; optional omissions must be compact and visible.

## Done criteria and acceptance evidence

- Concurrent launch callers for one request produce one logical execution and at most one authorized agent run; crash tests cover intent-before-spawn, spawn-before-receipt, receipt-before-projection, lease expiry/reclaim, result commit, declaration capture, and terminal intent.
- Timeout/crash before `launch_subagent` or any equivalent launcher call leaves the accepted requested-execution record claimable and cannot be mistaken for “nothing requested”; replay reaches one launch, one clarification, or one terminal failure.
- A stale fence cannot publish a result, declare/replace/select an artifact, import a sidecar, or create delivery intent. Duplicate declaration ID is idempotent; conflicting reuse is rejected.
- Valid produced/discovered files are explicitly declared, captured immutably, and remain deliverable after source deletion. Traversal, absolute disallowed roots, symlink, directory, FIFO, device, socket, missing file, unsafe hard-link edge, and mutate/truncate/append-during-capture cases create no accepted ref.
- Malware/secret/private-key/token fixtures block without logging content. Concurrent declarations preserve deterministic order, captions, required/optional semantics, safe filename collisions, and destination authorization.
- Advisory discovery excludes `.git`, run internals, dotfiles, credentials, logs, caches, dependencies, sockets/devices, sensitive roots, and over-ceiling files and never auto-attaches any candidate. Final prose cannot trigger capture.
- Normal, VibeComfy, Megaplan, AgentBox, repair, scheduler, VP todo/sweep, restart/reaper, and legacy sidecar/manifest tests prove they traverse the same launcher/broker contract and cannot access another request's refs.
- Restricted-run tests prove accepted request inputs are read-only and bounded and resident credentials/other request artifacts are absent. If full isolation is not available, readiness/canary tests fail closed outside the documented trusted-principal/type gate.

## Touchpoints

Expected areas: `resident/subagent.py`, common runner/worker envelope, resident tool/profile launch handling, artifact declaration client/broker/selection policy, run manifest/status projections, scheduler/todo/repair callers, service configuration/isolation, and `tests/resident/` launcher/profile suites.

## Anti-scope

Do not broaden resident permissions, hand Discord credentials/targets to an agent, infer selection from filesystem changes or prose, treat scanning as containment, add arbitrary remote shell execution, or refactor all Arnold process supervision.
