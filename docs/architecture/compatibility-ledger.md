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

### `AgentError`

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py`
- **Purpose**: Python import compatibility alias for `FailureEnvelope`.
- **Caller evidence**: `routes.py` and `edit.py` still import `AgentError` for
  failure response helper signatures; `contracts.py` exports
  `AgentError = FailureEnvelope`.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_contracts.py` asserts the
  alias identity, with failure envelope behavior covered by
  `tests/test_pristine_architecture_guardrails.py` and
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: Remove only when active imports use `FailureEnvelope`
  directly and downstream code no longer relies on the exported name.

### Failure hint camelCase inputs

- **Owner**: `vibecomfy/comfy_nodes/agent/contracts.py` and
  `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`.
- **Purpose**: Normalize historical or frontend-shaped public error inputs such
  as `failureKind` and `nextAction` to canonical snake_case public outcomes.
- **Caller evidence**: `FAILURE_HINT_KEYS` includes both snake_case and
  camelCase forms, and the browser normalizer mirrors those accepted inputs.
- **Fixture coverage**:
  `tests/test_comfy_nodes_agent_contracts.py::test_ensure_agent_edit_response_contract_maps_all_failure_hint_keys_to_error`,
  browser response-contract tests, and persisted error stamping tests in
  `tests/test_comfy_nodes_agent_edit.py`.
- **Deletion trigger**: Drop camelCase inputs after historical persisted error
  outcomes using `failureKind`/`nextAction` are outside the supported rehydrate
  window and snake_case-only fixtures cover the same failures.

### `apply_eligible`

- **Owner**: agent-edit backend contract and frontend response normalizer.
- **Purpose**: Canonical executor/apply authorization bit, with compatibility
  fallback only where old payloads are normalized into eligibility state.
- **Caller evidence**: Backend edit/routes code stamps it on relevant
  responses; the browser normalizer and lifecycle code gate Apply behavior from
  it when canonical candidate data is present.
- **Fixture coverage**: `tests/test_pristine_architecture_guardrails.py`,
  `tests/test_comfy_nodes_agent_edit.py`,
  `tests/browser/agent_edit_response_contract.test.mjs`,
  `tests/browser/roundtrip_smoke.test.mjs`, and
  `tests/browser/payload_contracts.test.mjs`.
- **Deletion trigger**: N/A for the canonical authorization field. Remove only
  compatibility inference from historical raw payloads after
  `eligibility.applyable` and `ApplyCandidate` state are the only frontend
  apply contract.

### Clarify/noop forbidden-key guards

- **Owner**: `vibecomfy/comfy_nodes/agent/routes.py`.
- **Purpose**: `_CLARIFY_FORBIDDEN_KEYS` and the shared non-applyable forbidden
  key set prevent candidate/apply fields from leaking into clarify/noop
  responses.
- **Caller evidence**: Route stamping uses the guard before returning
  non-applyable response shapes.
- **Fixture coverage**: Clarify/noop response tests in
  `tests/test_comfy_nodes_agent_edit.py` and forbidden-field assertions in
  `tests/browser/payload_contracts.test.mjs`.
- **Deletion trigger**: N/A — this is a route contract guard, not a compatibility
  shim.

### Graph hash fields

- **Owner**: agent-edit backend session/edit contract and frontend lifecycle.
- **Purpose**: `client_graph_hash` identifies the client/request graph snapshot;
  `candidate_graph_hash` identifies candidate artifacts. These are canonical
  active/session/diagnostic fields, not removable legacy aliases.
- **Caller evidence**: `session.py` records and validates the hashes;
  `edit.py` stamps candidate and failure responses; `vibecomfy_roundtrip.js`
  sends request/action hashes and displays candidate hash diagnostics;
  `agent_edit_lifecycle.js` preserves recovery hashes.
- **Fixture coverage**: `tests/test_comfy_nodes_agent_edit.py`,
  backend-spine graph-hash tests, `tests/browser/roundtrip_smoke.test.mjs`,
  `tests/browser/agent_edit_lifecycle.test.mjs`, and payload-contract fixtures.
- **Deletion trigger**: N/A for `client_graph_hash` and `candidate_graph_hash`.
  They may move behind named projections for UI display, but the backend/session
  identity fields remain canonical.

### `submitted_client_graph_hash` / `action_client_graph_hash`

- **Owner**: `vibecomfy/comfy_nodes/agent/session.py`.
- **Purpose**: Session migration/action-validation fields that preserve
  submit-time and action-time client hashes for stale-state checks.
- **Caller evidence**: Session allocation stores `submitted_client_graph_hash`;
  accept/reject validation reads it and records `action_client_graph_hash`;
  `edit.py` rehydrates submit hash from turn records.
- **Fixture coverage**:
  `tests/test_comfy_nodes_agent_edit.py::test_agent_edit_accept_matches_browser_client_graph_hash`,
  backend-spine stale-state/hash tests, and persisted session fixtures under
  `tests/fixtures/e2e_sessions/`.
- **Deletion trigger**: Remove only after persisted sessions are migrated and
  accept/reject tests prove canonical `submit_graph_hash` plus turn identity
  cover the same stale-state behavior.

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
