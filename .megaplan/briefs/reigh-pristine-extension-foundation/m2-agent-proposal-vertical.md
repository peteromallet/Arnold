# M2: Agent Proposal Vertical

## Outcome

Make proposal-mode agent output user-visible and safe end to end: edge returns canonical proposals, `useAgentSession` imports them into the provider-scoped runtime, the production editor mounts the proposal UI in the extension activity region, users can accept/reject through existing apply semantics, pending proposals survive reload, and `mutation_applied`/`proposal_policy` semantics are truthful.

## Scope

In scope:

- Update the Supabase edge agent response path to emit or adapt to the canonical proposal envelope from M1.
- Update `useAgentSession` success handling to validate/import returned proposals into the provider-scoped `ProposalRuntime`.
- Mount `ProposalPanel` in the named extension activity region with empty, populated, import-error, persistence-error, accept, reject, stale, and expired behavior.
- Ensure imported proposals persist through initialized provider storage and reload into the runtime/UI.
- Fix `mutation_applied` so it means actual timeline mutation, not "no proposal was emitted."
- Implement or remove/demote durable `proposal_policy` session persistence according to M1's decision.
- Add end-to-end or high-level integration coverage for proposal-mode invoke -> imported proposal -> visible panel -> accept/reject -> timeline apply semantics.

Out of scope:

- Do not redesign the proposal accept state machine unless concrete bugs appear.
- Do not add all agent tool UI surfaces.
- Do not add new proposal-backed contribution families.
- Do not solve non-timeline side effects beyond documenting/test-covering the boundary.

## Locked Decisions

- M1 owns the canonical import/persistence contract; this milestone consumes it.
- Proposal mode must not change timeline config until user acceptance.
- Production UI must make pending proposals discoverable; importing into runtime alone is not enough.

## Open Questions To Resolve

- Exact UI placement and responsive behavior of the activity region in current editor shell layout.
- How to surface proposal import and persistence diagnostics without overloading the proposal list.
- How to represent edge commands that cannot become timeline proposals and produce no mutation.

## Constraints

- Preserve existing timeline apply semantics.
- Keep read-only/blocked proposal-mode agent paths from invalidating timeline as though a mutation happened.
- Avoid broad agent-session refactors unrelated to proposal import.
- Avoid making non-timeline side effects pretend to be timeline proposals.

## Done Criteria

- A mocked or real proposal-mode edge response imports into `ProposalRuntime`.
- `ProposalPanel` is mounted in a production editor surface and shows pending imported proposals.
- Accept/reject works through the same runtime apply semantics.
- Pending imported proposals survive reload.
- Proposal mode does not mutate timeline config until acceptance.
- Read-only and blocked paths report `mutation_applied: false`.
- Durable `proposal_policy` behavior is tested if the column remains; otherwise dead storage is removed/demoted and documented.

## Touchpoints

- `supabase/functions/ai-timeline-agent/index.ts`
- `supabase/functions/ai-timeline-agent/loop.ts`
- `supabase/functions/ai-timeline-agent/db.ts`
- `src/tools/video-editor/hooks/useAgentSession.ts`
- `src/tools/video-editor/lib/proposal-runtime.ts`
- `src/tools/video-editor/components/ProposalPanel/ProposalPanel.tsx`
- Editor shell/activity region components.
- Proposal, agent-session, and browser/editor tests.

## Anti-Scope

- No marketplace/install/update.
- No new agent tool contribution family.
- No full `AgentToolsPanel` or `DiagnosticPanel` requirement.
- No broad timeline operation refactor.

