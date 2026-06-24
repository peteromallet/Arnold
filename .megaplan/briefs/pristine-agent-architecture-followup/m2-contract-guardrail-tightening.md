# M2: Contract Guardrail Tightening

## Outcome

Strengthen existing canonical backend/public contract guardrails without
changing messaging render semantics. The goal is fewer accidental regressions in
response envelopes, session iteration, audit records, field-change repair, and
compatibility aliases.

## Scope

In:

- Add focused tests for response envelope JSON safety, public outcome
  sanitization, apply eligibility consistency, diagnostic record boundaries, and
  session rehydrate baseline handling.
- Tighten compatibility-ledger checks for retained backend aliases.
- Adjust `contracts.py`, `session.py`, or `audit.py` only where tests reveal a
  real boundary gap.

Out:

- `panel_thread.js` changes.
- Transcript/detail selector or rendering changes.
- Broad backend package moves.

## Locked Decisions

- `contracts.py` owns response envelopes, public outcomes, failure
  classification, diagnostics records, and field-change repair.
- `session.py` owns durable state and turn iteration.
- `audit.py` owns diagnostic persistence.
- `edit.py` may orchestrate but should not define competing canonical shapes.

## Done Criteria

- Contract tests capture the canonical behavior.
- Compatibility aliases retained by backend code are documented and covered.
- No user-facing contract behavior changes without tests and ledger updates.

## Touchpoints

- `vibecomfy/comfy_nodes/agent/contracts.py`
- `vibecomfy/comfy_nodes/agent/session.py`
- `vibecomfy/comfy_nodes/agent/audit.py`
- `tests/test_pristine_architecture_guardrails.py`
- `tests/test_agent_edit_compatibility_ledger.py`
- `tests/test_comfy_nodes_agent_contracts.py`
- `tests/test_comfy_nodes_agent_backend_spine.py`

## Validation

```bash
.venv/bin/python -m pytest -q tests/test_pristine_architecture_guardrails.py tests/test_agent_edit_compatibility_ledger.py tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_backend_spine.py
git diff --check origin/main...HEAD
```
