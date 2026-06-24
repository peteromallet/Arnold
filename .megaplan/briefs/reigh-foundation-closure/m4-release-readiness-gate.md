# M4 - Release Readiness Gate

## Outcome

Turn foundation readiness from narrative/anchor validation into executable release evidence. The closure chain can only clear the foundation if the blocking contract ledger rows are satisfied and the readiness command is wired into a normal quality or release path.

## Context

M5 created useful readiness docs and anchor validation, but that is not the same as proving the foundation. `test:readiness` was not part of `quality:check`, and anchor existence could pass while behavioral contracts remained incomplete.

## Scope

- Decide and document proposal reload semantics: pending-only reload or terminal history reload. If terminal history is required, implement and test it; otherwise document pending-only honestly.
- Update `scripts/quality/check-readiness.mjs` or related tests so cleared readiness rows point to executable passing evidence, not just anchors.
- Wire readiness into `quality:check` or a named release-quality command.
- Ensure browser/Playwright harness coverage is either part of the release gate or explicitly classified as a separate manual/slow gate with clear command.
- Complete `docs/extensions/foundation-contract-ledger.md`: every blocking foundation contract must be satisfied or explicitly waived.
- Add a final `docs/extensions/foundation-closure-assessment.md` that compares original foundation intent against current code/tests/docs and states whether Phase 4 family work is cleared.

## Done Criteria

- `npm run quality:check` or a named release command includes readiness evidence.
- Readiness checks fail when a cleared ledger/readiness row lacks a runnable evidence command/path.
- The proposal reload contract is explicit and tested.
- `foundation-closure-assessment.md` says either cleared or not cleared, with evidence; it must not mark the foundation cleared if any blocking ledger row is open.
- Contract ledger has no unresolved blocking rows.

## Touchpoints

- `package.json`
- `scripts/quality/check-readiness.mjs`
- `docs/extensions/phase4-readiness.md`
- `docs/extensions/foundation-contract-ledger.md`
- `docs/extensions/foundation-closure-assessment.md`
- `tests/e2e/extension-harness.spec.ts`
- `src/tools/video-editor/runtime/phase4ReadinessDocs.test.ts`

## Anti-Scope

- Do not start Phase 4 family implementation.
- Do not claim sandboxing, permission enforcement, signing, marketplace, remote install, or external SDK publication.
- Do not allow documentation-only evidence to clear a behavioral contract.

