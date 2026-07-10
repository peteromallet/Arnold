# M1: State Compartments And Selectors

## Outcome

Define and implement explicit frontend state compartments for user-facing
transcript messages, safe response details, internal execution events, durable
status, and audit references. Normal consumers should have named selectors or
projection helpers instead of reading raw panel state.

## Scope

In:

- Inventory every normal-path write to chat/detail/progress state from submit,
  websocket events, `batch_turns`, rehydrate, session state, and audit/debug
  callbacks.
- Define the canonical frontend compartments:
  - `TranscriptMessage`
  - `ResponseDetail`
  - `ExecutionEvent`
  - `AuditArtifact`
  - status/stage snapshots where needed
- Add or extend selector/projection APIs that return only safe transcript/detail
  data to normal renderers.
- Keep raw execution/audit fields available for explicit debug and audit
  surfaces.
- Add focused tests for compartment transitions and selector output.

Out:

- Broad frontend module decomposition.
- Cosmetic rendering changes.
- Backend response schema changes except fixture updates needed to test frontend
  projections.

## Locked Decisions

- `agent_edit_lifecycle.js` owns durable transcript lifecycle state.
- `agent_turn_feed.js` owns execution/activity event normalization.
- `agent_edit_response_contract.js` owns response contract readers and safe
  selectors unless prep proves a new `agent_message_boundary.js` would reduce
  coupling.
- `panel.state.turns` may remain only as a compatibility mirror with caller
  evidence and ledger entry.

## Done Criteria

- Normal render-facing selector output contains no raw `batch_turns`, debug,
  audit, provider payloads, budgets, exit modes, raw paths, model prompts, or
  raw diagnostic strings.
- Existing transcript ordering and rehydrate lifecycle tests still pass.
- Any compatibility mirror has owner, test coverage, and deletion trigger.

## Touchpoints

- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `vibecomfy/comfy_nodes/web/agent_turn_feed.js`
- `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `tests/browser/payload_contracts.test.mjs`
- `tests/browser/agent_edit_lifecycle_transcript.test.mjs`

## Validation

```bash
node --test tests/browser/payload_contracts.test.mjs
node --test tests/browser/agent_edit_lifecycle_transcript.test.mjs
node --test tests/browser/roundtrip_smoke.test.mjs
```
