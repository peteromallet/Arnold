# Foundation Closure Assessment

**Epic:** `reigh-foundation-closure` — M4 Release Readiness Gate  
**Date:** 2026-06-24  
**Status:** M4 complete; broad Phase 4 family implementation remains blocked.

## Objective

Close the Reigh extension foundation gaps identified in `NORTHSTAR.md` and the `foundation-contract-ledger.md` blocking rows. The M4 gate makes readiness a release-quality gate: every blocking foundation contract has runnable evidence, `quality:check` includes readiness, proposal reload semantics are explicit and tested, the contract ledger is closed, and the trust posture is documented without overclaim.

## Contracts Satisfied

| Contract | Evidence command | Status |
|---|---|---|
| Public proposal import (M1) | `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/lib/proposal-runtime.test.ts` | Satisfied |
| Agent proposal vertical (M2) | `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/hooks/useAgentSession.proposal-vertical.test.tsx` | Satisfied |
| Settings runtime write-through (M3) | `npx vitest run --config config/testing/vitest.config.ts src/sdk/extensionSettingsService.test.ts` <br> `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx` <br> `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx` <br> `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/runtime/extensionSettingsNotification.test.ts` | Satisfied |
| M5 lifecycle, diagnostics, inventory, and readiness rows | `npm run test:readiness` | Satisfied |
| Proposal reload semantics (M4) | `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/lib/proposal-runtime.test.ts` | Satisfied |

## Evidence

- `npm run test:readiness` passes in strict mode. It validates that every cleared M5 readiness row in `docs/extensions/phase4-readiness.md` has resolvable code and test anchors, and that cleared non-e2e rows are wired into the fast release test command.
- `npm run quality:check` now includes `npm run test:readiness` as its final step, so the readiness gate is enforced by the release-quality command.
- `docs/extensions/foundation-contract-ledger.md` has no blocking rows; every foundation contract is either satisfied or explicitly waived.
- Proposal reload semantics are documented and tested: the runtime hydrates only `pending` proposals from the persistence provider; terminal history (accepted, rejected, stale, expired) is intentionally not reloaded.

## Phase 4 Family Work

Broad Phase 4 family implementation is **not cleared**. Each contribution family (asset parser, effect, transition, clip type, keyframes, agent tool, live data, render material, process/sidecar, shader/WebGL) remains blocked until it passes the checklist in `docs/extensions/phase4-readiness.md` and participates in render planning through `planRender()` with visible requirements and failure states.

## Trust Posture

The current posture remains **trusted/unsandboxed local packages only**:

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime enforcement, sandbox isolation, code signing, a permission broker, marketplace review, or safe third-party execution.
- No sandbox, permission broker, marketplace, remote install, or signing claims are made in the docs, examples, or manager surfaces.

M4 closes the foundation gate; it does not authorize public promotion of arbitrary Phase 4 families.
