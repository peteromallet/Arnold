# Agent Panel Architecture

This document records the canonical data model and module owners for the
VibeComfy agent-edit panel after the `messaging-boundary-cleanup-v2` epic.
It is the source of truth for which module owns which responsibility and for
the allowed data flow between panel subsystems.

## Canonical model

The panel consumes a small, stable set of backend contracts:

| Concept | Canonical type / function | Owner |
|---|---|---|
| Turn identity | `TurnIdentity` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Apply eligibility | `ApplyEligibility` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Public outcome | `public_outcome_from_turn_outcome` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Response envelope | `turn_envelope`, `success_envelope`, `failure_envelope` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Failure classification | `classify_failure`, `FailureKind` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Diagnostics record | `DiagnosticRecord` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Session read | `iter_turn_records`, `read_state` | `vibecomfy/comfy_nodes/agent/session.py` |
| Session mutate | `accept_turn`, `reject_turn`, `allocate_turn` | `vibecomfy/comfy_nodes/agent/session.py` |
| Audit write | `write_audit` | `vibecomfy/comfy_nodes/agent/audit.py` |
| Field-change repair | `repair_field_changes` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Public transcript message | `public_transcript_message` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Public response detail | `public_response_detail` | `vibecomfy/comfy_nodes/agent/contracts.py` |
| Public session JSON | `public_session_json_payload` | `vibecomfy/comfy_nodes/agent/contracts.py` |

No other module may define competing shapes for these concepts.

## Module owners

### Backend

- `contracts.py` owns the durable data shapes and pure adapters, including all
  public-projection helpers.
- `session.py` owns durable session state, locking, idempotency, and disk
  iteration.
- `audit.py` owns redaction-aware diagnostic persistence.
- `edit.py` orchestrates agent-edit logic but does not own the canonical
  shapes or state mutation.
- `routes.py` is a thin HTTP boundary; it applies public projection before
  serialization and delegates to `edit.py` and `session.py` for data.

### Frontend

- `vibecomfy_roundtrip.js` is an orchestration shell.  It owns event wiring,
  lifecycle coordination, and dependency assembly.  It no longer implements
  status polling, settings rendering, candidate eligibility, diagnostics
  reporting, or response-shape normalization locally.
- `agent_status_poller.js` owns status polling and route/provider readiness.
- `panel_composer.js` owns settings and developer renderer bodies.
- `panel_thread.js` owns thread rendering and expanded bubble details.
- `agent_candidate_actions.js` owns candidate apply/reject eligibility
  selectors and candidate bubble action state.  `vibecomfy_roundtrip.js`
  imports this module for current-candidate controls instead of reimplementing
  eligibility locally.
- `agent_edit_lifecycle.js` owns durable session/turn lifecycle state and
  chat-rehydrate ingestion.
- `agent_edit_response_contract.js` owns frontend projection of backend
  response payloads into normalized transcript/detail/diagnostic buckets.  Lifecycle,
  thread, and roundtrip code consume its normalized readers instead of reaching
  into raw backend payload variants directly.
- `panel_overlay.js` owns preview-overlay rendering and alias blocking.
- `diagnostics_reporting.js` owns browser diagnostics capture, issue report
  assembly, audit export/download, issue ZIP bundling, rating submission, and
  the Having issues modal.  `vibecomfy_roundtrip.js` configures its injected
  browser dependencies and re-exports the public diagnostics helpers.

## Allowed data flow

```
HTTP (routes.py)
  -> edit.py orchestration
    -> session.py state read / mutate
    -> audit.py diagnostic write
    -> contracts.py envelope builders / public projection
  -> frontend facade
    -> response adapter (agent_edit_response_contract.js)
      -> selector modules (lifecycle, status poller, candidate actions)
        -> renderer modules (composer, thread, overlay)
          -> vibecomfy_roundtrip.js orchestration / event wiring
    -> diagnostics/export boundary (diagnostics_reporting.js)
```

Normal UI render paths must consume data through selectors.  Raw session
files, audit internals, and execution-stage details are only reachable
through explicit debug/export surfaces (`_agent_edit_debug.py`, issue bundle
flow, audit downloads, and the developer-expanded sections of bubble details).

Backend routes that serve normal UI payloads (`/agent-edit/chat`,
`/agent-edit/session-json`) apply allowlist-based public projection in
`contracts.py` before JSON serialization.  The frontend's
`agent_edit_response_contract.js` is a second line of defense, not the
primary safety boundary.

The diagnostics/export boundary is an adaptor surface only.  Its ownership of
diagnostics capture, issue bundles, audit downloads, ratings, and the Having
issues modal does not change normal UI transcript, detail, or event render
semantics; those paths still flow through the response adapter, selector
modules, and renderer modules above.

## Boundaries enforced by tests

- `test_pristine_architecture_guardrails.py` proves internal outcome kinds
  never leak into public outcomes.
- `test_pristine_architecture_guardrails.py` proves response envelopes are
  JSON-safe and contain no internal sentinel objects.
- `test_pristine_architecture_guardrails.py` proves apply eligibility stays
  consistent with gate state.
- `test_pristine_architecture_guardrails.py` proves session rehydrate
  normalizes baseline state safely.
- `test_pristine_architecture_guardrails.py` proves audit and CLI debug
  evidence paths produce readable artifacts.
- `test_agent_edit_compatibility_ledger.py` proves legacy aliases stay inside
  explicit allowlists.
- `tests/browser/projection_boundary_helpers.mjs` proves normal transcript,
  response-detail, and DOM payloads cannot carry forbidden raw execution,
  audit, provider, or filesystem-path fields.
- `tests/browser/*.mjs` prove collapsed chat, expanded details, history
  rehydrate, and explicit audit/debug separation work end-to-end.

## What changed in this epic

- Backend rehydrate/session payloads are projected through safe
  `public_*` contracts before reaching the browser.
- `read_session_chat` and `read_session_json` remain raw for internal/debug
  consumers; route boundaries apply public projection.
- `agent_edit_response_contract.js` splits raw rehydrate input from normal
  renderer state and routes diagnostics/audit artifacts into explicit
  affordances.
- `panel_thread.js` renders expanded bubble details from normalized
  `responseDetails` compartments, with narrow fallbacks for legacy pending
  progress and applied-feedback shapes (recorded in the Compatibility Ledger).
- Status polling ownership was extracted to `agent_status_poller.js`; the
  legacy duplicate in `vibecomfy_roundtrip.js` is retained as a compatibility
  mirror until removal criteria are met.
