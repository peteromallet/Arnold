# Backend Module Ownership Map

This document records the canonical owner for each backend boundary touched by
agent-edit turns.  It is the source of truth for where a responsibility lives,
which module is allowed to import it, and which modules are consumers only.

## 1. Boundaries

| Boundary | Canonical owner | What it owns | Consumers (read-only) |
|---|---|---|---|
| Response envelope | `contracts.py` | `turn_envelope`, `success_envelope`, `failure_envelope`, `build_legacy_agent_edit_v1`, `ensure_agent_edit_response_contract` | `edit.py`, `routes.py` |
| Chat artifacts | `edit.py` | `_write_turn_chat_artifact` (line ~1466) | `routes.py` reads via `read_session_chat` |
| Session artifact iteration | `session.py` | `iter_turn_records` | `edit.py:read_session_chat`, CLI `_agent_edit_debug.py` |
| Accept / reject / idempotency | `session.py` | `accept_turn`, `reject_turn`, `_mutate_turn_state` | `routes.py` thin wrappers |
| Field-change type | `porting/edit/types.py` | `FieldChange` frozen dataclass | `contracts.py`, `edit.py` |
| Field-change repair | `contracts.py` | `repair_field_changes` | `edit.py` |
| Diagnostics contract | `contracts.py` | `DiagnosticRecord` | `audit.py` (writer), CLI `_agent_edit_debug.py` (reader) |
| Diagnostics persistence | `audit.py` | `write_audit` | `edit.py`, `routes.py` |

## 2. Principles

1. **Canonical types live in `contracts.py` or `porting/edit/types.py`.**
   No other module may define a competing `FieldChange`, `FailureEnvelope`,
   `TurnOutcome`, or `DiagnosticRecord`.

2. **Server-side state mutation is owned by `session.py`.**
   `edit.py` orchestrates logic; `routes.py` only dispatches HTTP requests.
   Both delegate accept/reject/idempotency to `session.py`.

3. **Disk iteration is owned by `session.py`.**
   `iter_turn_records` is the only canonical reader that walks turn
   directories and joins `response.json` with `session_state.json` lifecycle
   data.  `edit.py:read_session_chat` may keep its own chat-specific display
   logic but should reuse `iter_turn_records` for the raw walk when practical.

4. **CLI debug is a consumer, not an owner.**
   `_agent_edit_debug.py` imports `iter_turn_records` from `session.py` and
   `DiagnosticRecord` from `contracts.py`, then applies its own text formatting.
   It must not re-implement the turn walk.

## 3. Exceptions / compatibility notes

- `edit.py:read_session_chat` retains chat-specific fallback logic (reading
  `chat.json`, building display messages, bounding message count).  The
  underlying turn iteration is delegated to `session.py:iter_turn_records`.
- `audit.py:normalize_agent_edit_v2_metadata` stays in `audit.py` because it
  normalizes audit-specific metadata shapes and is not duplicated elsewhere.
- `_agent_edit_debug.py` continues to format output columns, colors, and
  summary widths locally.  That formatting is a presentation-layer concern, not
  a backend boundary.
