# Agent Panel Architecture

This document records the canonical data model and module owners for the
VibeComfy agent-edit panel after the `pristine-agent-architecture` cleanup.
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

No other module may define competing shapes for these concepts.

## Module owners

### Backend

- `contracts.py` owns the durable data shapes and pure adapters.
- `session.py` owns durable session state, locking, idempotency, and disk
  iteration.
- `audit.py` owns redaction-aware diagnostic persistence.
- `edit.py` orchestrates agent-edit logic but does not own the canonical
  shapes or state mutation.
- `routes.py` is a thin HTTP boundary; it delegates to `edit.py` and
  `session.py`.

### Frontend

- `vibecomfy_roundtrip.js` is an orchestration shell.  It owns event wiring,
  lifecycle coordination, and dependency assembly.  It no longer implements
  status polling, settings rendering, or candidate eligibility logic locally.
- `agent_status_poller.js` owns status polling and route/provider readiness.
- `panel_composer.js` owns settings and developer renderer bodies.
- `panel_thread.js` owns thread rendering.
- `agent_candidate_actions.js` (created in M5) owns candidate apply/reject
  eligibility selectors.
- `agent_edit_lifecycle.js` owns durable session/turn lifecycle state.

## Allowed data flow

```
HTTP (routes.py)
  -> edit.py orchestration
    -> session.py state read / mutate
    -> audit.py diagnostic write
    -> contracts.py envelope builders
  -> frontend facade
    -> selector modules (lifecycle, status poller, candidate actions)
      -> renderer modules (composer, thread)
        -> vibecomfy_roundtrip.js orchestration / event wiring
```

Normal UI render paths must consume data through selectors.  Raw session
files, audit internals, and execution-stage details are only reachable
through explicit debug/export surfaces (`_agent_edit_debug.py`, issue bundle
flow, audit downloads).

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

## What was removed

- Duplicate frontend status/settings renderers from
  `vibecomfy_roundtrip.js` (M5).
- Ad-hoc CLI turn walk in `_agent_edit_debug.py`; it now imports
  `iter_turn_records` from `session.py` (M6).
- Field-change repair helpers from `edit.py`; canonical implementation lives
  in `contracts.py` (M6).
