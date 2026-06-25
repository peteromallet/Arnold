# M1: Main Preservation Audit

## Outcome

Produce a concrete preservation baseline for current `origin/main`: what the
previous pristine architecture work already delivered, which artifacts must not
be deleted, and which remaining gaps belong to this follow-up versus the
messaging-boundary rerun.

## Scope

In:

- Inventory current main architecture artifacts, ownership maps, guardrail
  tests, compatibility ledger entries, and clean-artifacts policy.
- Confirm which M1/M3-M7 outputs are already present and still valid.
- Create or update a small audit artifact only if needed to guide later
  milestones.
- Define "must preserve" criteria for docs, tests, ownership maps, and Makefile
  targets.

Out:

- Code refactors.
- Messaging transcript/detail boundary changes.
- Replaying old M1-M7 branches.

## Locked Decisions

- The current dirty M7 checkout is negative evidence only.
- Current-main docs/tests/ownership maps are preserved unless replaced by a
  strictly better artifact in the same commit.
- Old nested `.megaplan` runtime state is not an input to completion.

## Done Criteria

- Preservation criteria are explicit enough for later milestones and review.
- No current-main architecture docs or guardrail tests are deleted.
- The chain has non-empty legitimate output, or a typed no-op waiver if this is
  intentionally documentation-only.

## Touchpoints

- `.megaplan/briefs/pristine-agent-architecture-followup/*`
- `docs/architecture/agent_panel.md`
- `docs/architecture/ARTIFACTS.md`
- `docs/architecture/compatibility-ledger.md`
- `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`
- `vibecomfy/comfy_nodes/web/frontend_ownership_map.md`
- `tests/test_pristine_architecture_guardrails.py`
- `tests/test_agent_edit_compatibility_ledger.py`

## Validation

```bash
make root-clean
.venv/bin/python -m pytest -q tests/test_pristine_architecture_guardrails.py tests/test_agent_edit_compatibility_ledger.py
git diff --check origin/main...HEAD
```
