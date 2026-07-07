# Agent UI Lifecycle Parity Plan

## Problem

The agent UI has multiple places acting as lifecycle state owners:

- Production submit/rehydrate/apply code in `vibecomfy_roundtrip.js`.
- Demo preview stage projection in `preview_picker.js`.
- Agentic test replay stage projection in `agentic_replay.js`.

Only one of those should own lifecycle state. `agent_edit_lifecycle.js` already states the intended contract: lifecycle fields such as `phase`, `candidateGraph`, `applyEligibility`, `responseDetails`, `transcriptMessages`, and review/apply state are store-owned and should not be ad hoc assigned outside lifecycle transitions.

Today, preview and replay simulate production agent states by directly mutating `panel.state`.

That has already caused preview-only drift:

- Preview-stage response details auto-opened because `preview_picker.js` wrote `expandedBubbleTurnKeys` directly.
- Preview overlay failures were harder to reason about because demo/replay code bypassed normal projection and lifecycle boundaries.
- `agentic_replay.js` references `RENDER_SECTIONS.CANDIDATE`, but `RENDER_SECTIONS` does not define `CANDIDATE`, so tests can accidentally pass an undefined render section.
- Preview/replay fixtures can bypass `projectTranscriptMessage`, `projectResponseDetail`, strict canonical selectors, candidate invalidation, render obligations, and safe projection boundaries.

The root problem is not one bad assignment. The root problem is duplicated lifecycle implementation.

## Goal

Make agent UI lifecycle state have exactly one owner, then make preview and replay feed that owner instead of pretending to be it.

Preview and replay should be production replays, not parallel lifecycle implementations.

The desired boundary is:

```text
source input -> canonical event/response payload -> lifecycle/projection commit API -> render
```

Production, preview, and replay should differ only in payload source:

- Production source: backend routes, websocket events, chat rehydrate, accept/reject.
- Preview source: canned scenario JSON from `/vibecomfy/demo/scenario`.
- Agentic replay source: stored run/test replay JSON from `/vibecomfy/agentic-replay/...`.

They should share the same lifecycle mutations, response projections, render obligations, and detail expansion semantics.

## Non-Goals

- Do not route preview through real production network submit routes.
- Do not make demo/replay POST to production accept/reject endpoints.
- Do not remove stage navigation or visual graph replay behavior.
- Do not collapse demo/replay-only toolbar metadata into lifecycle state.

## Important Constraint

Do not route preview through the full live network submit function.

Production has at least two relevant phases:

1. Optimistic submit state: user message, pending agent response, submit metadata.
2. Canonical response or rehydrate commit: candidate/no-op/clarify/error projection, transcript, response details, eligibility, review state.

Preview/replay should reuse those commit boundaries, not the transport or live fetch path.

## Proposed Shared Commit API

Introduce a small source-agnostic frontend commit layer. It can start in `vibecomfy_roundtrip.js` while behavior is being extracted, but the target should be a focused module such as:

```text
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js
```

This module should be the public frontend API for applying agent lifecycle inputs to panel state.

The commit layer should not branch on source names such as production, demo, or replay. Differences belong in upstream adapters that normalize production responses, demo scenarios, and replay fixtures into canonical envelopes.

Start with the smallest stable surface:

```js
commitOptimisticSubmit(panel, normalizedSubmit)

commitTerminalAgentEnvelope(panel, normalizedEnvelope)
```

Once candidate-response parity is proven, split out additional named helpers only where the seams are stable:

```js
commitRehydrateTranscript(panel, normalizedTranscript)

commitCandidateRestore(panel, normalizedCandidate)

commitApplyResolved(panel, normalizedApplyResult)
```

`commitTerminalAgentEnvelope(...)` can dispatch internally by canonical outcome kind:

```text
candidate_review | clarify | noop | error
```

These helpers should own:

- Calls to `transition(...)`.
- Calls to `projectTranscriptMessage`, `projectResponseDetail`, and strict canonical selectors.
- Pending response promotion/cleanup.
- Candidate invalidation and preview diff cache invalidation.
- Render obligation fulfillment and dirty section normalization.
- Normalization of render dirty sections.
- Guarding lifecycle field writes behind `transition(...)`.

They may return obligations or normalized side-effect intents for the caller to fulfill. They should not become broad orchestration functions.

They should not own:

- Fetching from production or demo endpoints.
- Applying or mutating canvas graph snapshots.
- Resolving the active canvas scope.
- Installing overlays, repainting the graph, or activating layout preview.
- `pushHistory(...)`, `pushTurnStatus(...)`, or other UI recording side effects.
- `reconcileResponseBatchTurns(...)`.
- Scroll state such as `ensureThreadRenderState(...).forceScrollOnNextRender`.
- Session storage or persistence.
- Demo/replay-only UI metadata such as `__demoStage`, `_replay`, toolbar state, or selected scenario IDs.

`commitApplyResolved(...)` should mean "reflect an apply result that already happened." It should receive an already-accepted apply result and already-computed canvas/apply metadata. It must not own accept/reject POSTs, CAS decisions, stale-state decisions, or raw canvas mutation.

## Ownership Rules

### Lifecycle-Owned Fields

Fields listed in `LIFECYCLE_STATE_FIELDS` in `agent_edit_lifecycle.js` may only be changed by:

- `transition(...)`
- helpers in the shared commit layer
- tightly scoped production-only glue that the shared commit layer has not yet absorbed

Preview/replay modules must not directly assign them.

### UI/Tooling-Owned Fields

Preview/replay modules may own local UI metadata:

- selected run/scenario IDs
- toolbar loading/error text
- `__demoStage`
- `__demoStageIndex`
- `_replay`

These fields must not become inputs to production lifecycle decisions.

`chatMessages` is not listed in `LIFECYCLE_STATE_FIELDS`, but it is close enough to lifecycle state to require the same discipline in preview/replay. Preview and replay should update transcript-visible messages through canonical commit/projection paths, not by hand-building parallel chat state.

### Graph Visualization Side Effects

Preview/replay may still apply original/candidate graphs to the canvas for stage navigation. That is visualization, not lifecycle authority.

The lifecycle source of truth must remain the commit API.

## Migration Plan

### 1. Establish Guardrails First

Add tests before the larger migration:

- `preview_picker.js` and `agentic_replay.js` must not write lifecycle-owned fields directly.
- Render requests must not contain undefined dirty sections.
- Preview/replay must never auto-populate `expandedBubbleTurnKeys`.

Use `LIFECYCLE_STATE_FIELDS` from `agent_edit_lifecycle.js` as the source of truth for ownership.

Also fix the known render-section drift immediately:

- remove `RENDER_SECTIONS.CANDIDATE` from `agentic_replay.js`
- add a test that fails on any undefined dirty section

### 2. Extract Production Candidate Commit Without Behavior Change

Extract the production candidate terminal response logic from `vibecomfy_roundtrip.js` into a callable helper without changing behavior.

Start narrowly with the candidate response path, because that is where preview/replay drift is most visible:

- Candidate graph and report.
- Apply eligibility.
- Transcript messages.
- Response details.
- `AWAITING_REVIEW` phase.
- Preview overlay enablement and layout preview activation.

Good first extraction targets:

- pending response promotion and cleanup
- candidate-arrival response handling in `vibecomfy_roundtrip.js`
- `_writeLatestCandidateTransition(...)` and `_handleCandidateResponse(...)` in `agent_edit_lifecycle.js`

Only after that is stable, cover clarify/no-op/error if preview/replay fixtures need them.

Implementation notes:

- Keep existing production tests green after each extraction.
- Do not move fetch logic into the commit module.
- Do not move raw canvas mutation into the commit module.
- Preserve current backend CAS authority for Apply.
- Do not extract rehydrate or apply in the first slice.

### 3. Convert Demo Preview Picker

Update `preview_picker.js` stage handling:

- `before_send`: apply original graph for visualization and clear via lifecycle/reset helper.
- `sent_loading`: call `commitOptimisticSubmit(...)`.
- `ready_to_apply`: convert scenario data to a canonical candidate envelope and call `commitTerminalAgentEnvelope(...)`.
- `applied`: use `commitApplyResolved(...)` with an already-computed demo apply result and no production POST.

Allowed direct state writes after migration:

- `__demoMode`
- `__demoStage`
- `__demoStageIndex`
- toolbar/loading/selection state outside `panel.state`

Disallowed direct state writes:

- lifecycle fields listed in `LIFECYCLE_STATE_FIELDS`
- `expandedBubbleTurnKeys` except preserving existing user-controlled state
- raw `responseDetails` from fixtures without projection

The preview picker should become:

```text
scenario selector + fixture adapter + stage controls + graph visualization
```

It should no longer be a lifecycle reducer.

### 4. Convert Agentic Replay

Update `agentic_replay.js` to stop snapshotting state with:

```js
Object.assign(panel.state, createAgentEditState(), ...)
```

Replay stage handling should reuse the same commit helpers:

- `sent`: user-message commit.
- `thinking`: optimistic submit plus pending response state.
- `ready_to_apply`: canonical candidate response commit.
- `applied`: visualization-only apply replay, or `commitApplyResolved(...)` only if the fixture has an already-resolved apply result that matches production semantics.

Replay may still apply original/candidate graphs to the canvas for visual navigation, but that should be treated as a visualization side effect, not lifecycle state authority.

Also remove `RENDER_SECTIONS.CANDIDATE`; use defined render sections or lifecycle-returned obligations.

Replay has one extra requirement that production does not: reverse navigation. Do not solve reverse navigation by restoring arbitrary handcrafted lifecycle snapshots.

Use this strategy instead:

1. Save the pre-replay lifecycle baseline before replay starts.
2. To move backward or jump to an earlier stage, restore that baseline.
3. Replay canonical commits forward until the target stage.
4. Apply graph visualization for the target stage after lifecycle commits.
5. On clear/exit, restore the pre-replay lifecycle baseline exactly.

The baseline restore must use a precise allowlist. A full `panel.state` restore risks clobbering UI state; a lifecycle-only restore risks leaving chat thread state, expansion state, queue guard state, preview diff caches, or runtime side effects behind. Define and test the restore set before converting reverse navigation.

This also avoids session and turn identity collisions. Replay must not permanently overwrite the user's active `sessionId` or `turnId`; those values should be restored when replay exits.

The replay viewer should become:

```text
run/test selector + replay fixture adapter + stage controls + graph visualization
```

It should no longer be a lifecycle reducer.

### 5. Normalize Demo/Replay Fixture Shape

Keep existing endpoint compatibility during migration. Do not make fixture-schema churn a prerequisite for the first candidate-parity slice.

First write small adapters that produce the transition payload shape needed for candidate commits. Once behavior is proven, introduce a canonical internal fixture shape:

```json
{
  "session_id": "...",
  "turn_id": "...",
  "query": "...",
  "response": {
    "ok": true,
    "outcome": { "kind": "edit", "summary": "..." },
    "candidate": {
      "state": "candidate",
      "graph": {},
      "graph_hash": "..."
    },
    "eligibility": {
      "applyable": true,
      "reason": "applyable"
    },
    "report": {},
    "change_details": {}
  }
}
```

The adapter from old demo/replay fixture JSON to this canonical shape should be small and tested.

### 6. Retire Old Direct-State Paths

Once preview and replay use the commit API:

- delete obsolete helper code that hand-builds lifecycle snapshots
- remove tests that assert handcrafted state rather than production-equivalent state
- keep tests for toolbar behavior and visual stage navigation
- document the allowed demo/replay metadata fields near the guardrail test

## Required Tests

Suggested new test files:

- `lifecycle_ownership_scan.test.mjs`
- `render_section_safety.test.mjs`
- `preview_replay_parity.test.mjs`
- `preview_replay_projection_leak.test.mjs`

### Commit Helper Tests

Exercise the shared commit layer directly:

- optimistic submit creates the agreed canonical subset of production pending transcript state
- canonical candidate response enters review with safe projected details
- canonical no-op/clarify/error responses do not create candidate controls
- apply success clears candidate state consistently

Production optimistic submit includes user and pending agent bubbles, executor progress, submit epoch/local IDs, `lastSubmit`, abort state, history/status side effects, and scroll behavior. Preview/replay do not necessarily need every one of those. The first tests must explicitly define which subset is lifecycle-canonical and which effects remain caller-owned.

### Parity Tests

Feed the same canonical candidate fixture through:

1. Production commit helper.
2. Preview/demo commit path.
3. Agentic replay commit path.

Compare lifecycle state excluding allowed metadata:

- `phase`
- `sessionId`
- `turnId`
- `candidateGraph`
- `candidateGraphHash`
- `candidateReport`
- `applyEligibility`
- `applyAllowed`
- `canvasApplyAllowed`
- `queueAllowed`
- `transcriptMessages`
- `responseDetails`
- `changeDetails`

Exclude scope IDs, baseline authority, audit/debug fields, in-flight submit metadata, demo/replay metadata, history/undo state, and user-controlled expansion state.

### Projection Boundary Tests

Assert replayed preview details are produced through `projectResponseDetail` and do not leak:

- raw graph payloads
- provider diagnostics
- model/system prompts
- audit paths
- debug payloads
- live LiteGraph objects

### Detail Expansion Tests

Assert preview and replay:

- leave details collapsed when reaching review stage
- preserve user-expanded details across re-render/rehydrate where production does
- never auto-write `expandedBubbleTurnKeys` for candidate arrival

### Render Obligation Tests

Assert all dirty sections passed to `scheduleRenderAgentPanel` are members of `RENDER_SECTIONS`.

This catches drift like `RENDER_SECTIONS.CANDIDATE`.

### Static Ownership Tests

Add a regression that scans `preview_picker.js` and `agentic_replay.js` for direct assignments to `LIFECYCLE_STATE_FIELDS`.

This should be conservative, comment-aware, and allow explicitly listed demo/replay metadata fields only. It should also flag direct preview/replay writes to transcript/chat/detail fields that would bypass projection, even when those fields are not part of `LIFECYCLE_STATE_FIELDS`.

### Replay Navigation Tests

Assert replay-specific behavior:

- reverse navigation clears candidate state by restoring baseline and replaying forward
- clear/exit restores pre-replay lifecycle state exactly
- active `sessionId` and `turnId` are restored after replay exits
- pruned stage lists still navigate correctly
- runs without `original_graph` still clear correctly
- replay is blocked or safely exits while a production submit/apply is in flight
- scope switching during replay/demo stage navigation does not leak candidate state across workflows

### Fixture Adapter Tests

Assert old demo/replay endpoint payloads adapt into canonical internal payloads without leaking raw debug fields into normal UI state.

## Manual Verification Matrix

Before merging the migration, exercise:

- production submit -> candidate -> overlay -> apply -> reject
- production rehydrate with an open candidate
- preview picker through all stages in normal and layout-preview scenarios
- agentic replay through all stages, including backward keyboard navigation
- workflow tab switching with different chat scopes
- enter and exit preview/replay while a production candidate is already active
- preview apply/reject without production accept/reject POSTs
- overlay diff rendering in both production and preview

## Risks

- `vibecomfy_roundtrip.js` currently interleaves lifecycle transitions, fetch transport, graph side effects, history rows, pending response management, and rendering. Extract the commit API in small slices.
- Demo apply currently has a local no-backend branch. Preserve the no-POST behavior while still using lifecycle transitions for state changes.
- Layout preview scenarios may intentionally apply candidate graph visually during review. Keep that as a graph visualization side effect, but do not let it define lifecycle state.
- Existing tests assert hand-built preview/replay state. They should be rewritten to assert parity with production-derived state instead.
- A too-broad rewrite could destabilize production submit/apply. Start with candidate response commit extraction and guardrails.
- A too-narrow fix would leave agentic replay as a second lifecycle implementation and allow the same class of bug to recur there.
- Leaving both the old direct-write paths and the new commit API active for the same behavior would create two writers. Delete or disable old preview/replay lifecycle writes as each commit path lands.
- Commit helpers must never initialize, reset, or auto-populate `expandedBubbleTurnKeys`.
- A replay "applied" stage is not necessarily the same thing as a production apply success. Treat it as visualization unless the fixture carries an already-resolved apply result.
- Static ownership tests catch obvious direct writes, but not every alias, helper call, spread, or indirect mutation. Treat them as guardrails, not proof.

## Stop/Go Criteria

Stop and fix before merging if:

- any production lifecycle test fails
- static ownership tests find direct preview/replay lifecycle writes
- any render request contains an undefined section
- parity tests show lifecycle drift between production, preview, and replay
- any commit helper writes `expandedBubbleTurnKeys`
- preview/replay apply performs production accept/reject POSTs

Proceed only when the automated guardrails and manual verification matrix pass.

## First Implementation Slice

The first slice should be deliberately small:

1. Add render-section safety tests and remove `RENDER_SECTIONS.CANDIDATE`.
2. Add ownership tests for preview/replay direct lifecycle writes, including `Object.assign`.
3. Extract only the production candidate terminal commit, preserving behavior.
4. Convert preview `ready_to_apply` to that candidate commit, with graph visualization kept outside.
5. Convert replay forward navigation through `ready_to_apply` to baseline plus replayed commits.
6. Add reverse navigation and exit-restore tests.

Do not move rehydrate, apply, clarify/no-op/error, or fixture schema cleanup into this first slice unless the candidate extraction forces a small supporting change.

## Completion Criteria

This work is done when:

- there is a shared frontend commit API for optimistic submit, canonical response/rehydrate, and apply success
- `preview_picker.js` no longer directly writes lifecycle-owned state.
- `agentic_replay.js` no longer directly writes lifecycle-owned state.
- Preview/replay candidate arrival uses the same projection and lifecycle commit behavior as production candidate arrival.
- Demo/replay apply uses lifecycle transitions and still avoids production accept/reject POSTs.
- Undefined render sections fail tests.
- Detail expansion behavior is identical between production, preview, and replay.
