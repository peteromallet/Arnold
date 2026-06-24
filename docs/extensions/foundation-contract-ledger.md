# Foundation Contract Ledger

**Status:** Active
**Last updated:** 2026-06-24

This ledger records narrow closure evidence for foundation contracts. A row marked satisfied here closes only the named contract row; it does not imply broad Phase 4 readiness unless every blocking Phase 4 row is separately cleared.

| Contract | Owner files | Evidence commands | Status |
|---|---|---|---|
| Agent proposal vertical: edge `proposals[]` response imports through `useSendMessage`, renders in the shell-mounted production `ProposalPanel`, keeps `TimelineOps.apply()` uncalled before explicit accept, applies exactly once on accept, supports reject without mutation, and shows malformed import diagnostics. | `src/tools/video-editor/hooks/useAgentSession.proposal-vertical.test.tsx`; `src/tools/video-editor/lib/proposal-runtime.ts`; `src/tools/video-editor/lib/proposal-runtime.test.ts`; `src/tools/video-editor/components/TimelineEditorShellCore.tsx`; `src/tools/video-editor/components/ProposalPanel/ProposalPanel.tsx`; `src/tools/video-editor/hooks/useAgentSession.ts` | Primary: `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/hooks/useAgentSession.proposal-vertical.test.tsx` Supporting diagnostics contract: `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/lib/proposal-runtime.test.ts` Formatting check: `git diff --check -- src/tools/video-editor/hooks/useAgentSession.proposal-vertical.test.tsx` | Implemented with focused vertical and runtime-diagnostics coverage; local Vitest evidence commands were attempted by prior batches but failed before test execution because the sandbox cannot write `node_modules/.vite-temp/vitest.config.ts.timestamp-*.mjs` through the symlinked `node_modules` path. Pending authoritative harness verification; broad Phase 4 readiness is not claimed. |

