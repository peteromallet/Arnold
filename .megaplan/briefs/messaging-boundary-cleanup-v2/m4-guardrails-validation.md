# M4: Guardrails And Merge Hygiene

## Outcome

Lock the messaging boundary with regression tests and minimal documentation so
the normal UI cannot regress to rendering raw execution/audit data.

## Scope

In:

- Add sentinel tests covering collapsed chat, expanded details,
  below-thread/history mount, rehydrate, and explicit audit/debug separation.
- Add static or fixture checks where stable enough to avoid brittle false
  positives.
- Update architecture docs and compatibility ledger for retained mirrors.
- Keep docs edits minimal to reduce conflicts with the architecture follow-up.

Out:

- Broad architecture rewrites.
- Cosmetic docs churn.
- Deleting compatibility paths without caller evidence.

## Locked Decisions

- A retained mirror is allowed only with owner, caller evidence, fixture
  coverage, and deletion trigger.
- This milestone should not expand scope into status/composer/candidate module
  cleanup.

## Done Criteria

- Full browser smoke passes.
- Targeted backend contract tests pass.
- Compatibility ledger names every retained raw-data or mirror path.
- `make root-clean` passes.

## Touchpoints

- `tests/test_pristine_architecture_guardrails.py`
- `tests/test_agent_edit_compatibility_ledger.py`
- `docs/architecture/agent_panel.md`
- `docs/architecture/compatibility-ledger.md`
- `tests/browser/*.mjs`

## Validation

```bash
node --test tests/browser/*.mjs
.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_agent_edit_compatibility_ledger.py tests/test_pristine_architecture_guardrails.py
make root-clean
make browser-smoke
git diff --check origin/main...HEAD
```
