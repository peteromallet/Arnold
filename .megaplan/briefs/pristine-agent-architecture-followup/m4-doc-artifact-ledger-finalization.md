# M4: Doc Artifact Ledger Finalization

## Outcome

Finalize architecture docs, artifact manifest, compatibility ledger, and root
cleanup policy against the actual final code after the parallel cleanup work.

## Scope

In:

- Update architecture docs to match final module owners and data-flow rules.
- Update artifact manifest and compatibility ledger for retained aliases,
  mirrors, and debug/audit surfaces.
- Preserve and verify `clean-artifacts` / root-clean policy.
- Remove only confirmed stale generated runtime artifacts from committed inputs.

Out:

- Large code refactors.
- Messaging boundary implementation.
- Deleting current-main architecture artifacts without replacement.

## Locked Decisions

- `docs/architecture/agent_panel.md` is the architecture source of truth.
- `docs/architecture/ARTIFACTS.md` is the artifact policy source.
- `docs/architecture/compatibility-ledger.md` records every retained
  compatibility path with owner, caller evidence, fixture coverage, and deletion
  trigger.

## Done Criteria

- Docs match code ownership.
- Root-clean and clean-artifacts checks pass.
- Compatibility ledger is complete for retained aliases and mirrors.
- No generated nested `.megaplan` runtime state is committed as source material.

## Touchpoints

- `docs/architecture/agent_panel.md`
- `docs/architecture/ARTIFACTS.md`
- `docs/architecture/compatibility-ledger.md`
- `Makefile`
- `tests/test_agent_edit_compatibility_ledger.py`

## Validation

```bash
make root-clean
make browser-smoke
.venv/bin/python -m pytest -q tests/test_pristine_architecture_guardrails.py tests/test_agent_edit_compatibility_ledger.py tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_cli_debug_contract.py
git diff --check origin/main...HEAD
```
