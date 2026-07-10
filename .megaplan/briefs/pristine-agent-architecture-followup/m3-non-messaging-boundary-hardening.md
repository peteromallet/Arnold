# M3: Non-Messaging Boundary Hardening

## Outcome

Preserve and harden the architecture cleanup outside transcript/detail safety:
status polling, composer/settings/developer rendering, candidate-action
selectors, session/audit ownership, and CLI debug boundaries.

## Scope

In:

- Verify `vibecomfy_roundtrip.js` remains orchestration-only for status,
  composer, candidate action, and event wiring responsibilities.
- Tighten ownership checks for `agent_status_poller.js`, `panel_composer.js`,
  `agent_candidate_actions.js`, `agent_edit_lifecycle.js`, and backend
  ownership maps.
- Preserve CLI debug behavior through session/audit owners.
- Add tests for ownership regressions where practical.

Out:

- Changing transcript/detail rendering semantics.
- Raw `ExecutionEvent` separation.
- Messaging sentinel test ownership.

## Locked Decisions

- Messaging-boundary-cleanup v2 owns `panel_thread.js`, `agent_turn_feed.js`,
  normal chat/detail sentinels, and execution-event separation.
- This milestone may touch `vibecomfy_roundtrip.js` only for non-message
  orchestration, import wiring, and ownership checks.

## Done Criteria

- Status/composer/candidate responsibilities have one owner each.
- Browser status and roundtrip smoke tests pass.
- Ownership docs match actual imports and responsibilities.

## Touchpoints

- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/agent_status_poller.js`
- `vibecomfy/comfy_nodes/web/panel_composer.js`
- `vibecomfy/comfy_nodes/web/agent_candidate_actions.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`
- `vibecomfy/commands/_agent_edit_debug.py`
- `tests/browser/agent_status_poller.test.mjs`
- `tests/browser/roundtrip_smoke.test.mjs`

## Validation

```bash
node --test tests/browser/agent_status_poller.test.mjs tests/browser/roundtrip_smoke.test.mjs
.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_backend_spine.py tests/test_cli_debug_contract.py
git diff --check origin/main...HEAD
```
