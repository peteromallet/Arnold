# M3: Rehydrate Projection

## Outcome

Backend/session rehydrate must project through safe transcript/detail/session
contracts before browser consumption. Frontend sanitization is a second line of
defense, not the primary boundary.

## Scope

In:

- Trace chat/session rehydrate payload construction from persisted turn records
  through route output and browser ingestion.
- Ensure normal browser payloads use safe transcript/detail contracts and stable
  identifiers.
- Keep raw session/audit data available only through explicit debug/report
  surfaces.
- Add Python and browser fixture tests with sentinel raw fields.

Out:

- Replacing the session storage format wholesale.
- Removing audit artifacts.
- Changing model/provider routing.

## Locked Decisions

- `contracts.py` owns contract builders and safe projection helpers.
- `session.py` owns durable turn iteration.
- `edit.py` and `routes.py` orchestrate; they do not own new message shapes.
- Any legacy aliases retained for session compatibility go through named
  adapters and the compatibility ledger.

## Done Criteria

- Rehydrate fixture output cannot expose raw execution internals to normal UI.
- Persisted legacy sessions still replay through read-time projection.
- CLI/debug/report surfaces preserve necessary evidence.

## Touchpoints

- `vibecomfy/comfy_nodes/agent/contracts.py`
- `vibecomfy/comfy_nodes/agent/session.py`
- `vibecomfy/comfy_nodes/agent/edit.py`
- `vibecomfy/comfy_nodes/agent/routes.py`
- `tests/test_comfy_nodes_agent_contracts.py`
- `tests/test_comfy_nodes_agent_backend_spine.py`
- `tests/fixtures/payload_contracts/chat_rehydrate_response.json`

## Validation

```bash
.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_backend_spine.py
node --test tests/browser/payload_contracts.test.mjs tests/browser/agent_edit_lifecycle_transcript.test.mjs
```
