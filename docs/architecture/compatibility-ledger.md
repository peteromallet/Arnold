# Compatibility Ledger

Every legacy alias, compatibility shim, or retained duplicate path that remains
after the `pristine-agent-architecture` epic is recorded here.  Each entry has
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

## Frontend compatibility paths

### `vibecomfy_roundtrip.js` retained orchestration glue

- **Owner**: frontend panel (`vibecomfy/comfy_nodes/web/`)
- **Purpose**: Event wiring, lifecycle coordination, and dependency assembly
  after renderers/pollers were extracted in M5.
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

## Removed in this epic

- Duplicate status/settings renderers in `vibecomfy_roundtrip.js` (M5).
- Monolith-local status polling and choose-engine gating in
  `vibecomfy_roundtrip.js` (M5).
- Ad-hoc turn walk in `_agent_edit_debug.py`; replaced by
  `session.py:iter_turn_records` (M6).
- Field-change repair helpers in `edit.py`; canonical implementation moved to
  `contracts.py:repair_field_changes` (M6).
- Stale root scratch files (`comfyui_arnold_debug*.png`, `chain_run.pid`,
  `temp/counter.txt`) (M7).
