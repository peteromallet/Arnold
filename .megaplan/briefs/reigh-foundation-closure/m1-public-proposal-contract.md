# M1 - Public Proposal Contract

## Outcome

Make proposal import a public typed extension-foundation contract. `ProposalRuntime` must expose the import capability used by edge/client proposal handoff, and proposal import tests must assert the current result shape rather than stale legacy behavior.

## Context

The prior foundation assessment found `importProposal()` exists on the concrete runtime, and `importEdgeProposals()` duck-types support for it, but the public SDK `ProposalRuntime` interface does not expose it. That violates the original M1 intent: proposal import should be a typed runtime capability, not an implementation detail.

## Scope

- Add the appropriate typed proposal import method to the public `ProposalRuntime` interface in `src/sdk/index.ts`.
- Update `importEdgeProposals()` and related call sites to depend on the public interface instead of duck-typing concrete runtime internals.
- Update stale proposal import tests that still expect the old bare-number return behavior; assert the current `ProposalImportResult` semantics.
- Add or update an SDK boundary test proving the public interface includes the import capability.
- Create/update `docs/extensions/foundation-contract-ledger.md` with at least the proposal-contract rows and evidence commands.

## Done Criteria

- TypeScript compiles with the public `ProposalRuntime` import contract.
- Tests prove `importEdgeProposals()` returns and reports `ProposalImportResult` correctly.
- A boundary test fails if `ProposalRuntime.importProposal` is removed.
- `docs/extensions/foundation-contract-ledger.md` records this contract as satisfied with exact test commands and paths.

## Touchpoints

- `src/sdk/index.ts`
- `src/sdk/__tests__/sdk-boundary.test.ts` or equivalent
- `src/tools/video-editor/lib/proposal-runtime.ts`
- `src/tools/video-editor/lib/proposal-runtime.test.ts`
- `docs/extensions/foundation-contract-ledger.md`

## Anti-Scope

- Do not broaden the proposal UX.
- Do not change proposal apply semantics except where typing forces a correction.
- Do not start Phase 4 contribution-family work.

