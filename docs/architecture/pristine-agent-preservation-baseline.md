# Pristine Agent Preservation Baseline

M1 is a preservation audit, not an implementation milestone. Its baseline is the
current `origin/main` architecture surface plus the chain brief files already in
the branch diff. Later work may improve these artifacts, but must not delete or
weaken them without a same-commit replacement that is demonstrably better.

## Must-Preserve Files

- `docs/architecture/agent_panel.md`
- `docs/architecture/ARTIFACTS.md`
- `docs/architecture/compatibility-ledger.md`
- `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`
- `vibecomfy/comfy_nodes/web/frontend_ownership_map.md`
- `tests/test_pristine_architecture_guardrails.py`
- `tests/test_agent_edit_compatibility_ledger.py`
- `Makefile` root hygiene policy: `root-clean`, `post-root-clean`, and
  `prune-empty-runtime-root`

## Current Validity Status

- Architecture docs: present and tracked. `agent_panel.md` records the agent
  panel boundary; `ARTIFACTS.md` catalogs owned architecture artifacts.
- Compatibility ledger: present and tracked. It keeps compatibility paths tied
  to owner, caller evidence, fixture coverage, and deletion trigger.
- Backend ownership map: present and tracked in
  `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`.
- Frontend ownership map: present and tracked in
  `vibecomfy/comfy_nodes/web/frontend_ownership_map.md`.
- Guardrail tests: present and tracked. The pristine architecture guardrails and
  compatibility ledger tests are the regression surface for this baseline.
- Root-clean policy: present in `Makefile`. Runtime logs are not source
  artifacts and should not be added to the root allowlist.
- Candidate-action ownership: still an intended preserved boundary, but
  `vibecomfy/comfy_nodes/web/agent_candidate_actions.js` is absent at this audit
  point. Documentation reconciliation belongs to the follow-up batch, not this
  artifact.

## Ownership Boundary

Follow-up owns non-message architecture hardening:

- Backend contract, session, audit, CLI debug, and guardrail coverage.
- Frontend status polling, composer ownership outside message rendering, and
  candidate-action extraction/ownership.
- Compatibility-ledger accuracy and artifact hygiene.
- Documentation that preserves the current-main architecture surface.

Messaging Boundary Cleanup V2 owns transcript/detail/event safety:

- Transcript and detail render semantics.
- Raw execution data exclusion from normal UI render paths.
- Event rehydration/projection safety for message rendering.

## Preservation Criteria

- Do not delete a must-preserve doc, ownership map, guardrail test, or root
  hygiene target unless the same commit adds a replacement with equal or better
  coverage and clearer ownership.
- Do not remove compatibility ledger entries unless the removal includes owner,
  caller evidence, fixture coverage, and deletion-trigger reasoning.
- Do not replay old M1-M7 branches or use dirty M7 state as source authority.
- Do not change transcript/detail/event render semantics in this follow-up
  scope.
- Do not change model/provider routing or weaken profile model selections.
- Do not create generated runtime state as committed root source material.
- Keep M1-owned edits to audit documentation and narrow hygiene only.

## Validation Findings

- T1 dependency context did not provide a recorded baseline failure list; the
  harness remains the authoritative post-execute regression check.
- `git status --short` currently reports untracked root logs:
  `chain_run.log` and `chain_run_trusted.log`.
- `git diff --check origin/main...HEAD` currently fails on trailing blank EOF
  lines in added `.megaplan/briefs/...` markdown files.
- `make root-clean` is expected to fail while the root logs remain present; the
  correct cleanup is deletion or relocation, not Makefile allowlist broadening.
- Targeted guardrails were reported during planning as passing with
  `python -m pytest -q tests/test_pristine_architecture_guardrails.py
  tests/test_agent_edit_compatibility_ledger.py`; final validation is reserved
  for the later validation batch and harness.
