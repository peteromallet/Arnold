# Executor Durability And Chat Flow Repair Plan

Date: 2026-06-22

Megaplan execution brief: `.megaplan/briefs/executor-durability-chat-flow.md`

## Goal

Make the VibeComfy agent panel behave like one durable conversation and edit workflow:

- Sent messages persist.
- Assistant responses persist.
- Message order remains stable across a second submit.
- The model receives the right recent conversation context.
- Applyable graph candidates can be accepted without special cases.
- False `Canvas changed` / `Rebaseline & retry` does not appear for unchanged graphs.

The repair is not one UI tweak. It is a contract repair across frontend state, backend routes, executor result serialization, session artifacts, model context construction, and apply/rebaseline checks.

## Current Failure Model

The strongest ground-truth diagnosis is:

1. The frontend submit path appends optimistic user and pending assistant messages to `panel.state.chatMessages`, then posts to the executor-backed route.
2. Current `/vibecomfy/agent-edit` and `/vibecomfy/agent-executor` both route through `_handle_agent_executor_submit`.
3. The executor can call the legacy durable edit implementation for revise/adapt work.
4. That legacy path can allocate a session turn and produce rich metadata.
5. The executor adapter then collapses the rich response into an `ImplementationResult` / `ExecutorResult` shape that mostly preserves `graph` and `message`.
6. The serialized executor response can look valid to the frontend while missing load-bearing durability fields such as `session_id`, `turn_id`, candidate hashes, baseline metadata, artifacts, and chat records.
7. Terminal no-session replies can fall back to `panel.state.message`, which is single-valued and rendered synthetically after `chatMessages`.
8. On the next submit, the frontend can render `user1 -> user2 -> pending2 -> assistant1` because the old assistant response was not a real transcript entry.
9. Apply/rebaseline has a separate false-stale path: frontend apply treats ComfyUI live graph revision token drift as a hard stale signal even when the structural graph hash is unchanged.

This means there are two primary repair tracks:

- **Durability and transcript repair:** every visible agent response must become a durable turn or a deliberate stable local transcript entry.
- **Semantic stale detection repair:** `Canvas changed` must mean actual graph/baseline drift, not missing metadata or live revision churn.

## Design Rules

These are the soft rules that should guide implementation and code review. They are not separate features; they are how the hard invariants stay true as the code changes.

- Backend durable session state is the source of truth for the UI-facing agent panel.
- Frontend `chatMessages` may be optimistic while a submit is in flight, but completed assistant replies must reconcile to durable backend turns or explicit stable local messages.
- `panel.state.message` is status/detail state, not transcript storage.
- The model's conversation context should be built from durable backend chat history, not from whatever the frontend happened to render.
- The default prompt memory policy is the last five relevant durable messages plus the current user message, subject only to explicit route/model budget constraints.
- The classifier model is the semantic routing authority. Pre-classifier Python code may build context and enforce mechanical request validity, but it must not decide whether a user intent is too ambiguous, unsafe, impossible, or clarification-worthy.
- Missing models, unknown node packs, and unrelated pre-existing graph/runtime problems are classifier context and post-edit validation evidence, not reasons to bypass the classifier.
- Applyable means durable. If a candidate cannot be accepted/rejected/rebaselined by `session_id` and `turn_id`, the UI should not present it as applyable.
- Missing metadata is a contract failure or malformed response, not canvas drift.
- `Canvas changed` is reserved for semantic graph/baseline drift that rebaseline can actually repair.
- ComfyUI live revision tokens are diagnostics; structural hashes and backend CAS are authority.
- Rehydrate should replace optimistic local messages by stable identity, not append duplicates.
- Idempotency should replay the same durable turn response, not create a second turn or return a partial response.
- Stateless executor behavior, if kept, must be visibly non-applyable and must not masquerade as the durable agent-edit workflow.

## Non-Goals (Explicit Out-Of-Scope)

These are capabilities this repair explicitly does **not** add. They are called out so future readers know these were considered and deferred, not overlooked.

### Cross-Session Memory / Search

- The repair does **not** introduce memory or search across different sessions or different user conversations.
- Each session remains a self-contained durable conversation thread. The model's context window for a given session includes only durable messages from that same session.
- Cross-session retrieval, semantic search over past sessions, or "remember what user said yesterday across sessions" are **out of scope** for this repair. These would require a separate memory/search subsystem (e.g., vector embeddings, session indexing) that is not part of the current durable-conversation contract.

### Broad Historical Migrations

- The repair does **not** attempt to silently migrate, backfill, or repair old broken sessions that lack durable turn artifacts.
- Sessions created during the broken period may be missing `session_id`, `turn_id`, chat artifacts, or baseline metadata. New code must handle these defensively (no crashes on rehydrate, no misleading apply UI), but it must **not** attempt a broad data migration to bring them up to the new contract.
- A targeted migration would only be considered if a failing test proves it is strictly required for the UI-facing agent panel to function. Even then, the migration would be scoped to the minimum necessary records, not a broad historical sweep.

### Frontend-Only Transcript Authority

- The repair intentionally does **not** make frontend `recent_messages` or `panel.state.chatMessages` the authoritative source of conversation history for model context.
- Backend durable session state remains the canonical source of truth. Frontend state is optimistic while a submit is in flight and is reconciled against durable backend turns when the response arrives.

### Model Provider Changes

- The repair does **not** change model providers or profile selection.
- The `PROMPT_MEMORY_MESSAGES = 5` policy is preserved and aligned across executor and legacy edit paths.
- Classifier prompt changes are in scope where they replace removed deterministic pre-classifier blockers. The point is not to change providers or add a second policy layer; it is to make the one classifier own semantic routing.

### Unrelated ComfyUI Paths

- The repair does **not** refactor ComfyUI graph projection, native authoring, porting, template compilation, or custom-node packaging paths.
- Changes are scoped exclusively to agent executor/edit/session/frontend lifecycle surfaces.

## Non-Negotiable Invariants

### Durable Conversation Invariants

- Every user-visible submit has a stable `session_id`.
- Every visible user/assistant exchange has a stable `turn_id`.
- Each turn writes request, response, and chat artifacts.
- Chat rehydrate can reconstruct the transcript without relying on frontend-only `panel.state.message`.
- Optimistic frontend messages are temporary and reconcile against durable backend messages.
- A no-session response must either be explicitly non-durable and materialized into local `chatMessages`, or the route must create a durable session before returning it. It must not live only in a single global `message` slot.

### Candidate And Apply Invariants

- An applyable candidate must include `session_id`, `turn_id`, submit hash, candidate hash, baseline metadata, and artifact/audit references.
- `/agent-edit/accept`, `/reject`, `/rebaseline`, and `/chat` must be able to operate against executor-created turns without special cases.
- Missing candidate metadata is a malformed/non-applyable response, not a stale canvas.
- A successful model answer that fails durability writes must not be returned as applyable.

### Stale/Rebaseline Invariants

- `Canvas changed` means structural graph state or scoped touched-region state changed.
- Backend CAS mismatch remains a true stale condition.
- Structural hash drift remains a true stale condition.
- Scoped touched-region verification failure remains a true stale condition.
- `liveCanvasToken` / ComfyUI graph revision drift is diagnostic only unless structural graph state also changed.

### Model Context Invariants

- The model should receive recent conversation context from durable session turns, not from fragile frontend display state.
- The frontend should send current prompt, session identity, idempotency key, and graph/baseline payloads.
- Backend prompt/context construction should choose the recent message window.
- Policy: include the last five relevant durable chat messages, plus the current user message, unless a route-specific prompt builder has a stricter budget.
- If previous messages are missing because earlier turns were non-durable, that should be visible as a contract/debug gap rather than silently pretending context exists.

### Classifier Ownership Invariants

- Every normal user turn reaches the LLM classifier.
- The executor must not synthesize a `clarify` route before classification for semantic reasons such as nonexistent node references, ambiguous pronouns, missing attachments, conflicting constraints, huge video requests, or architecture-mixing concerns.
- Those cases belong in the classifier prompt/context so the model can decide whether to clarify, inspect, revise, or adapt.
- The exception is delegated clarification continuation: if a prior clarify turn exists and the user says "pick some please", "you figure it out", or equivalent, the executor may deterministically restore the previously blocked edit route to avoid a clarification loop.
- Validation stays after classification/implementation. It may reject malformed candidates or newly introduced graph damage, but it should not prevent intent classification.

## Implementation Plan

### 0. Remove Semantic Pre-Classifier Blockers

Remove deterministic semantic blockers from the runtime path.

Former blocker categories become classifier-owned instructions/context:

- no graph available for an edit
- referenced node cannot be resolved from the node map or conversation
- ambiguous references such as "it" / "that node"
- missing required attachments
- conflicting constraints
- unrealistic resolution/frame requests
- architecture splice requests that need a bridge/adapter decision

Implementation direction:

- Delete the pre-classifier blocker helper and call site.
- Update the classifier prompt to say the model is the semantic routing authority.
- Keep graph summary, node reference map, prior clarification, recent messages, latest candidate, and blocked route/task in the classifier prompt.
- Bias concrete localized changes toward `revise`, especially code-node/PIL/frame-processing edits, even when the surrounding workflow has unrelated missing models or unknown custom nodes.
- Preserve the delegated-clarification shortcut only as an anti-loop mechanism.
- Add tests proving formerly blocked inputs call the classifier and that the prompt contains the former blocker categories.

### 1. Preserve Rich Executor Metadata

Fix the executor adapter boundary first.

For revise/adapt candidates, where executor implementation delegates to `handle_agent_edit`, preserve the rich durable edit response instead of collapsing it to only `graph` and `message`.

Required result fields:

- `session_id`
- `turn_id`
- `submit_graph_hash`
- `candidate_graph_hash`
- baseline graph/hash metadata
- `audit_ref`
- `delta_ops` / change details where available
- apply eligibility
- candidate graph
- user-visible assistant message
- artifact references needed by rehydrate/apply/reject/rebaseline

Implementation direction:

- Extend `ImplementationResult` / `ExecutorResult` to carry durable edit metadata, or embed the durable edit response as a first-class payload.
- Make `_serialize_executor_result` merge that metadata into the public response envelope.
- Add contract tests that fail if route compatibility fields are present but durability fields are missing.

Avoid allocating duplicate turns if `handle_agent_edit` already allocated one. Preserve first; allocate only for executor response kinds that do not go through the durable path.

### 2. Make Noop/Clarify/Inspect Durable Or Explicitly Local

If a response appears in the chat, the transcript must have a source of truth.

Preferred design:

- Noop, clarify, inspect, and candidate responses all allocate/write durable turns.
- Each writes `request.json`, `response.json`, and `chat.json`.
- `read_session_chat` can return all visible messages in order.

Acceptable fallback for truly stateless executor use:

- Mark the response explicitly non-durable.
- Materialize the assistant reply into `panel.state.chatMessages` with a stable local ID.
- Never rely on `panel.state.message` as transcript storage.
- Disable apply/rating/session-only actions for non-durable responses.

The UI-facing agent panel should use the preferred durable design.

### 3. Repair Frontend Transcript Lifecycle

Make `chatMessages` the canonical visible transcript.

Required behavior:

```text
submit 1: user1 -> pending1
response 1: user1 -> assistant1
submit 2: user1 -> assistant1 -> user2 -> pending2
response 2: user1 -> assistant1 -> user2 -> assistant2
```

Implementation direction:

- Clear stale `panel.state.message` on submit start.
- Suppress synthetic terminal rendering during active submit.
- When a terminal response has no `sessionId`, push a real assistant message into `chatMessages` before clearing pending.
- When a terminal response has `sessionId`, rehydrate and replace optimistic entries using stable keys.
- Keep an epoch/sequence guard so stale rehydrate responses cannot overwrite newer local transcript state.

### 4. Add Backend-Owned Conversation Context

Do not make model context depend on frontend rendering state.

Confirmed current behavior:

- `buildSubmitBody()` sends current graph, task, route, model, `session_id`, client hashes/tokens, and idempotency key.
- It does not send `chatMessages`, prior turns, or any transcript payload.
- The executor backend can load recent history from disk only when `request.session_id` is present.
- `_build_session_context()` reads recent session chat and currently loads a small recent window.
- `PROMPT_MEMORY_MESSAGES = 5` already exists in the legacy edit path.
- On first submit, or after `session_id` is stripped/lost, the model receives no prior conversation context beyond the current request and graph context.

Implementation direction:

- On submit, frontend sends current prompt plus `session_id` when available.
- Backend loads durable session chat for that session.
- Prompt/context builder selects the last five relevant messages before the current user message.
- Include both user and assistant messages, preserving order.
- Exclude pending/synthetic/local-only frontend messages unless they have been committed into durable session state.
- Include enough turn metadata for trace/debug, but keep model-facing content concise.
- As a resilience fallback, consider a `recent_messages` request field populated from frontend `chatMessages`, but do not make it authoritative for the UI agent panel. Durable backend turns should remain the source of truth.

Repair target:

- Preserve `session_id` / `turn_id` in the executor response so subsequent submits can keep using backend-loaded prompt memory.
- Make noop/clarify/inspect durable too, otherwise those conversational turns cannot participate in the next model prompt.
- Align executor and legacy edit prompt memory around one named policy, preferably `PROMPT_MEMORY_MESSAGES = 5`, with route-specific truncation only for budget pressure.

### 5. Separate Malformed From Stale

Before apply, validate candidate contract separately from canvas freshness.

Malformed/non-applyable:

- missing `session_id`
- missing `turn_id`
- missing candidate graph
- missing candidate hash
- malformed graph JSON
- missing baseline metadata needed by backend accept

Stale/rebaseline:

- backend `STALE_STATE_MISMATCH`
- structural graph hash changed
- scoped touched-region verification failed
- semantic baseline changed since submit

The user should not see `Rebaseline & retry` for malformed candidate metadata. That should show a contract/debug failure and, if possible, a normal retry/resubmit path.

### 6. Fix False Rebaseline

Keep the existing true stale protections, but stop treating live revision churn as authority.

Implementation direction:

- In apply-time freshness checks, if `liveCanvasToken` differs but structural graph hash is unchanged, do not dispatch `STALE_CANVAS_APPLY`.
- Keep the token in debug telemetry.
- Only block apply when structural hash or scoped semantic checks indicate real graph drift, or when backend CAS rejects the accept.

Test this explicitly by simulating ComfyUI graph revision increment with unchanged structural graph hash.

### 7. Prove The Whole Flow

Add tests around invariants, not just response shape.

Backend tests:

- `/vibecomfy/agent-executor` revise/adapt candidate returns `session_id`, `turn_id`, hashes, audit metadata, and creates turn artifacts.
- Clarify/noop/inspect responses are durable chat turns or explicitly marked non-durable and non-applyable.
- Second executor turn appends a new turn without overwriting turn one.
- Chat rehydrate returns `user1 -> assistant1 -> user2 -> assistant2`.
- Backend model context builder includes last five relevant durable messages in order.
- First submit without a session has no prior context, then response creates a session; second submit with that session includes prior user/assistant messages.
- Idempotency replay returns the same durable turn response and does not create duplicate turns.

Frontend tests:

- Second submit order remains `user1 -> assistant1 -> user2 -> pending2`.
- Rehydrate replaces optimistic entries rather than duplicating them.
- Terminal no-session fallback, if still supported, preserves two responses in order.
- Applyable missing `sessionId` / `turnId` is malformed/non-applyable, not stale.
- Normal unchanged structural graph with changed `liveCanvasToken` does not show `Canvas changed`.

End-to-end browser smoke:

- Send first message, receive durable assistant response.
- Send second message, verify first assistant response remains above second user message.
- Ask for an edit, receive candidate with turn metadata.
- Apply candidate successfully.
- Verify no false `Rebaseline & retry` when structural graph is unchanged.
- Refresh/reopen panel and verify transcript rehydrates in the same order.

## Confidence Assessment

This plan should solve the cluster if implemented as a contract repair, not as isolated patches.

High confidence:

- Preserving rich executor metadata fixes the apply/session continuity break for candidate edits.
- Materializing terminal responses into durable chat turns fixes the "only latest response" and second-message ordering bugs.
- Demoting `liveCanvasToken` drift when structural hash is unchanged fixes the normal false-rebaseline path.

Medium confidence:

- Some executor response kinds may need explicit durability adapters if they do not naturally flow through `handle_agent_edit`.
- A frontend `recent_messages` fallback may be useful for resilience, but should not substitute for durable backend prompt memory in the primary UI path.

Main integration risks:

- Idempotency could replay stale or partial responses if response records are not keyed to durable turns.
- Optimistic frontend messages could duplicate durable rehydrate messages without stable reconciliation keys.
- Old broken sessions may contain missing artifacts and should be handled defensively.

## Suggested Implementation Order

1. Add failing tests for executor durability, transcript ordering, model context history, and false rebaseline.
2. Preserve rich durable metadata through executor implementation and serialization.
3. Make noop/clarify/inspect responses durable, or explicitly local and non-applyable.
4. Repair frontend transcript lifecycle around `chatMessages`, synthetic fallback, and rehydrate reconciliation.
5. Implement backend-owned last-five conversation context from durable session turns.
6. Separate malformed candidate handling from stale/rebaseline UI.
7. Fix apply-time stale detection so live token drift alone cannot hard-block.
8. Run backend tests, browser tests, and a live two-message-plus-apply smoke.

## Rollback Strategy

If preserving durability through executor is too risky in one step:

- Restore `/vibecomfy/agent-edit` to the legacy session-aware route path for UI submits.
- Keep `/vibecomfy/agent-executor` as an additive experimental/stateless route.
- Mark executor-only candidates non-applyable until they produce durable turns.

This rollback is worse architecturally, but it restores the user-facing invariant: the ComfyUI agent panel should only show applyable candidates that are backed by durable session turns.
