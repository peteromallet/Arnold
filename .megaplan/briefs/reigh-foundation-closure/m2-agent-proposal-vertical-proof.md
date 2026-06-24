# M2 - Agent Proposal Vertical Proof

## Outcome

Prove the user-facing agent proposal path end to end: a mocked edge proposal response is imported through `useAgentSession`, appears in the production-mounted `ProposalPanel`, can be accepted by the user, and applies through `TimelineOps.apply()` only after acceptance.

## Context

The previous chain landed many proposal pieces, but evidence remained sectional. The foundation needs one vertical behavioral test that would fail if the edge/client/runtime/panel/apply contract breaks.

## Scope

- Add a production-path test for edge-like proposal-mode response -> `useAgentSession` import -> pending proposal visible in `ProposalPanel`.
- Exercise the accept path through the same runtime/UI wiring used by the editor shell.
- Assert no timeline mutation happens before acceptance.
- Assert accepting the proposal calls the intended `TimelineOps.apply()` path and updates proposal state consistently.
- Include reject behavior if it can be covered without making the test brittle.
- Update the contract ledger with the exact vertical test evidence.

## Done Criteria

- One named test proves the vertical path in a way that would have caught the prior false confidence.
- The test does not mock away the proposal runtime or production panel boundary so heavily that it only proves helpers.
- Proposal import diagnostics remain visible/assertable when malformed edge proposals arrive.
- Contract ledger marks the agent proposal vertical satisfied only with this test command/path.

## Touchpoints

- `src/tools/video-editor/hooks/useAgentSession.ts`
- `src/tools/video-editor/hooks/useAgentSession.test.tsx`
- `src/tools/video-editor/components/ProposalPanel/ProposalPanel.tsx`
- `src/tools/video-editor/components/ProposalPanel/ProposalPanel.test.tsx`
- `src/tools/video-editor/components/TimelineEditorShellCore.tsx`
- `src/tools/video-editor/lib/proposal-runtime.ts`
- `docs/extensions/foundation-contract-ledger.md`

## Anti-Scope

- Do not introduce new proposal modes.
- Do not convert this into broad agent UX redesign.
- Do not mutate timeline state before explicit user acceptance.

