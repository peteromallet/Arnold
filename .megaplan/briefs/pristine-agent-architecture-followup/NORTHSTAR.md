# North Star: Pristine Agent Architecture Follow-Up

The VibeComfy agent architecture should preserve the useful cleanup already on
current main while hardening contracts, ownership boundaries, docs, and
guardrails. It should not replay old branches or resurrect destructive dirty
state.

## End State

- Current-main architecture artifacts remain present and accurate:
  `docs/architecture/agent_panel.md`, `ARTIFACTS.md`,
  `compatibility-ledger.md`, backend ownership docs, frontend ownership maps,
  and guardrail tests.
- Backend contracts, session state, audit records, CLI debug behavior, status
  polling, composer rendering, and candidate-action ownership have explicit
  owners and regression coverage.
- `vibecomfy_roundtrip.js` remains an orchestration shell for non-message
  concerns and does not re-accumulate duplicated status/composer/candidate logic.
- Compatibility paths are listed with owner, caller evidence, fixture coverage,
  and deletion trigger.
- Root/artifact hygiene checks pass and no generated runtime state becomes
  committed source material.

## Non-Negotiables

- Do not use the old dirty M7 checkout as a base.
- Do not delete current-main architecture docs, ownership maps, or guardrail
  tests without a same-commit replacement that is demonstrably better.
- Do not change transcript/detail render semantics owned by the messaging
  boundary epic.
- Do not change model/provider routing.
- Do not weaken profile model selections while completing the chain.

## Parallel Boundary

This epic owns non-message architecture hardening: backend contract guardrails,
session/audit/CLI debug ownership, status/composer/candidate frontend ownership,
docs, artifact hygiene, and compatibility-ledger policy. Messaging Boundary
Cleanup V2 owns transcript/detail/event safety and raw execution data exclusion
from normal UI render paths.
