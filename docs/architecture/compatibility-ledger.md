# Compatibility Ledger

Every legacy alias, compatibility shim, or retained duplicate path that remains
after the `messaging-boundary-cleanup-v2` epic is recorded here.  Each entry has
an owner, evidence of current callers, fixture/test coverage, and a deletion
trigger.

## Legend

- **Owner**: module/team responsible for the compatibility path.
- **Caller evidence**: how we know it is still used.
- **Fixture coverage**: tests that would fail if the path were removed or
  changed.
- **Deletion trigger**: the condition under which the path may be removed.

## Backend compatibility paths

### `build_legacy_agent_edit_v1`

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Adds v1 field aliases (`apply_allowed`, `candidate_graph`,
  `graph_unchanged`, etc.) to canonical agent-edit responses.
- **Caller evidence**: Called by `FailureEnvelope.to_dict`,
  `ensure_agent_edit_response_contract`, and legacy consumer code paths.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py`,
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: All external consumers (panel, CLI, persisted session
  readers) have migrated to canonical field names and the frontend no longer
  reads v1 aliases.

### `apply_allowed` / `canvas_apply_allowed` / `queue_allowed` v1 booleans

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Backward-compatible boolean flags produced by
  `build_legacy_agent_edit_v1`.
- **Caller evidence**: Frontend panel and some existing tests still read these
  fields.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py`,
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: Frontend reads eligibility from the canonical
  `eligibility` object only.

### `FieldChange` frozen dataclass (unchanged)

- **Owner**: `vibecomfy/porting/edit/types.py`
- **Purpose**: Canonical 4-field representation of a field change.
- **Caller evidence**: Used across `contracts.py`, `edit.py`, porting, and
  executor modules.
- **Fixture coverage**: Extensive; `tests/test_comfy_nodes_agent_*` and
  porting tests.
- **Deletion trigger**: N/A — this is the canonical shape, not a compatibility
  path.

### `DiagnosticRecord` optional `path` / `mtime` fields

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Carry local filesystem metadata for CLI debug consumers.
- **Caller evidence**: Used by `tests/test_comfy_nodes_agent_contracts.py`
  round-trip test and may be used by future CLI record consumers.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py`.
- **Deletion trigger**: When all consumers read turn paths from the canonical
  `(session_id, turn_id)` tuple instead of the local `path` field.

### Raw session/chat readers (`read_session_chat`, `read_session_json`)

- **Owner**: `vibecomfy/comfy_nodes/agent/session.py` / `edit.py`
- **Purpose**: Persisted session artifacts retain raw execution internals for
  debug, audit, and issue-bundle surfaces.
- **Caller evidence**: `read_session_bundle` and debug/CLI flows need the raw
  data; HTTP routes project before serialization.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_edit.py`
  (`test_session_bundle_route_retains_raw_sentinels`).
- **Deletion trigger**: When the storage format itself is migrated and all
  debug/audit consumers read through projected accessors.

## Frontend compatibility paths

### `vibecomfy_roundtrip.js` retained orchestration glue

- **Owner**: frontend panel (`vibecomfy/comfy_nodes/web/`)
- **Purpose**: Event wiring, lifecycle coordination, and dependency assembly
  after renderers/pollers were extracted.
- **Caller evidence**: It is the top-level panel entry point and is loaded by
  ComfyUI.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_status_poller.test.mjs`.
- **Deletion trigger**: Only when the panel entry point is replaced by a
  smaller orchestrator and all event wiring has been moved to dedicated
  modules.

### Legacy import wrappers in `vibecomfy_roundtrip.js`

- **Owner**: frontend panel
- **Purpose**: Re-export or adapt older module shapes so existing call sites
  keep working.
- **Caller evidence**: Some internal panel modules still import through these
  wrappers.
- **Fixture coverage**: Browser smoke tests.
- **Deletion trigger**: When all internal callers import directly from the
  canonical owner module.

### `vibecomfy_roundtrip.js` duplicate status polling

- **Owner**: `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- **Purpose**: Legacy status-fetch and retry path retained while the extracted
  `agent_status_poller.js` becomes the single owner.
- **Caller evidence**: Roundtrip orchestration still calls `refreshAgentStatus`
  from the legacy path during panel open/settings changes.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_status_poller.test.mjs`.
- **Deletion trigger**: All status polling, route-select population, and
  choose-engine gating is routed through `agent_status_poller.js` and the
  duplicate helpers are removed from `vibecomfy_roundtrip.js`.

### `chatMessages` / `transcriptMessages` dual-array mirror

- **Owner**: `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- **Purpose**: `chatMessages` is the historical source array;
  `transcriptMessages` is the new canonical source.  The lifecycle reducer
  keeps both in sync so older render paths and tests that still read
  `chatMessages` continue to work.
- **Caller evidence**: Several existing renderers/tests still reference
  `panel.state.chatMessages`.
- **Fixture coverage**: `tests/browser/agent_edit_lifecycle.test.mjs`,
  `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: When all consumers read from `transcriptMessages` and
  `chatMessages` is removed from panel state.

### Legacy `canonical_activity` pending-progress fallback

- **Owner**: `vibecomfy/comfy_nodes/web/panel_thread.js`
- **Purpose**: WebSocket progress events may carry a legacy `canonical_activity`
  snapshot.  `populateAgentBubbleDetail` renders its safe details when the
  normalized response detail has no equivalent statement-level progress.
- **Caller evidence**: Active-row rendering tests exercise pending bubbles
  built from websocket progress payloads.
- **Fixture coverage**: `tests/browser/active_row_rendering.test.mjs`.
- **Deletion trigger**: When websocket progress is emitted as normalized
  `responseDetails` and `canonical_activity` is no longer produced.

### Panel-level `lastAppliedChanges` fallback

- **Owner**: `vibecomfy/comfy_nodes/web/panel_thread.js`
- **Purpose**: After rehydrate, a turn's own snapshot may not carry applied
  feedback, so the bubble detail falls back to `panel.state.lastAppliedChanges`.
- **Caller evidence**: Roundtrip smoke tests assert applied feedback survives
  apply and rehydrate.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: When rehydrate payloads include per-turn applied
  feedback in the normalized `responseDetails` compartment.

### `queueAllowed` retained in detail snapshots

- **Owner**: `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- **Purpose**: `rememberTurnDetailSnapshot` carries the legacy `queueAllowed`
  boolean so that expanded bubble details can render queue state for turns that
  predate the normalized `queueDisplay` compartment.
- **Caller evidence**: Roundtrip smoke tests assert queue state in expanded
  bubbles.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: When all turn snapshots are produced with the canonical
  `queueDisplay` object and the legacy boolean is no longer read.

### Response-detail merge across chat rehydrate

- **Owner**: `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- **Purpose**: `_handleChatRehydrateSuccess` merges incoming per-turn
  `responseDetails` with locally-built compartments instead of replacing them
  wholesale, preserving live `queueDisplay`, `candidate`, and `eligibility`
  state.
- **Caller evidence**: Roundtrip smoke tests assert queue/candidate details
  survive rehydrate.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: When backend rehydrate projection always includes the
  full normalized detail compartment and frontend no longer needs to merge.

### Graph-scan queue-blocker fallback

- **Owner**: `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`
- **Purpose**: `safeQueueDisplay` falls back to scanning the live graph for
  unlowered `vibecomfy.code/exec/loop` intent nodes when the report-level queue
  blocker is absent.
- **Caller evidence**: Roundtrip smoke tests for lowered/unlowered intent
  nodes.
- **Fixture coverage**: `tests/browser/roundtrip_smoke.test.mjs`.
- **Deletion trigger**: When the executor always emits an authoritative queue
  display and the frontend no longer needs graph introspection for queue
  safety.

### Legacy alias fixtures in browser tests

- **Owner**: `tests/browser/projection_boundary_helpers.mjs`,
  `tests/test_agent_edit_compatibility_ledger.py`
- **Purpose**: Enumerate and explicitly allowlist legacy agent-edit aliases
  (`executor_pending`, `apply_allowed`, `canvas_apply_allowed`, `field_changes`)
  so tests can prove they do not leak into normal renderer state/DOM.
- **Caller evidence**: The compatibility ledger test scans the listed roots and
  the boundary-helper tests assert forbidden aliases are rejected.
- **Fixture coverage**: `tests/test_agent_edit_compatibility_ledger.py`,
  `tests/browser/projection_boundary_helpers.test.mjs`.
- **Deletion trigger**: When the aliases are no longer present anywhere in the
  codebase and the allowlists can be removed.

### `panel_overlay.js` alias-blocking regex

- **Owner**: `vibecomfy/comfy_nodes/web/panel_overlay.js`
- **Purpose**: Preview overlay text is scrubbed by a regex that matches legacy
  apply/queue alias strings so they cannot appear in normal UI surfaces.
- **Caller evidence**: Overlay rendering code and compatibility ledger scan.
- **Fixture coverage**: `tests/test_agent_edit_compatibility_ledger.py`.
- **Deletion trigger**: When the aliases no longer exist and the regex can be
  removed.

## Removed in this epic

- Ad-hoc raw-field leakage through chat/session rehydrate HTTP responses;
  replaced by allowlist-based public projection in `contracts.py`.
- Direct use of raw execution fields in normal browser render paths; replaced
  by `transcriptMessage` / `responseDetail` selectors and explicit
  diagnostic/audit affordances.
- Unconditional frontend ingestion of raw backend payloads; replaced by
  `agent_edit_response_contract.js` projection and `splitRehydrateProjectionInput`.
