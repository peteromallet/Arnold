# M3: Proposal Spine And Agent Policy

## Outcome

Make destructive extension/agent workflows proposal-first when policy asks for it. Proposal envelopes should be public, persisted, versioned, expirable, reload-safe, and applied through the existing command/proposal path rather than a second mutation engine.

## Scope

In:

- Define public `TimelinePatch`, `TimelinePatchOp`, preview/result/conflict envelope types.
- Keep proposals as envelopes over existing command runner/dry-run/apply behavior.
- Persist proposal envelopes through the provider storage foundation from M2.
- Add TTL/expiry and stale-proposal cleanup semantics.
- Preserve stale-version rejection before mutation.
- Wire frontend `proposal_policy` through the Supabase edge function to backend `timelineMutationMode`.
- Send `proposal_policy` on the first invoke, not only auto-continuation.
- Return proposal responses from the edge function to the client.
- Aggregate proposal data out of tool results so the edge response can carry pending proposals.
- Add client accept/reject flow that applies through `applyTimelineProposal` or the same proposal apply semantics.
- Audit direct-mutation agent paths, especially `create_shot`, so they cannot bypass policy when classified as timeline mutations.
- Deliberately classify non-timeline side effects such as generation task creation instead of treating every tool call as timeline proposal scope.

Out:

- New timeline mutation engine.
- Full extension-contributed agent tools.
- Live data/bake workflows.
- Manager UI.
- Broad undo/redo rewrite.

## Locked Decisions

- `TimelinePatch` is a public review/preview envelope, not an executor.
- Agent destructive operations must be able to return proposals without mutating immediately.
- Expired or stale proposals reject before mutation.
- Existing command/proposal tests should remain the behavioral source of truth.

## Open Questions

- Exact proposal table name and payload shape.
- Whether proposals belong to a command-specific repository or a broader extension proposal repository.
- Default TTL duration and cleanup cadence.
- Whether accepted/rejected/expired proposal history remains queryable or is pruned.
- Exact client surface for accepting agent-generated proposals.

## Constraints

- Do not let edge function success responses imply a mutation occurred when proposal mode returned a pending proposal.
- Do not persist large proposal payloads in localStorage.
- Do not bypass proposal policy in agent shortcut paths.
- Do not silently apply stale or expired proposals.
- Do not expose a second apply path that skips conflict checks.

## Done Criteria

- Public proposal envelope types are exported and contract-checked.
- Proposal persistence survives reload.
- Proposal TTL/expiry is enforced.
- Stale proposals reject before mutation.
- `proposal_policy: 'always'` reaches backend `timelineMutationMode`.
- `proposal_policy: 'always'` is sent on the first user invoke and every relevant continuation.
- Edge function returns a non-null proposal response in proposal mode.
- Timeline config version does not change immediately in proposal mode.
- Client can accept the returned proposal through the same proposal apply semantics.
- Direct timeline mutation paths, including `create_shot` if kept in scope, respect proposal policy.
- Non-timeline side-effect tools are explicitly classified and tested as in-scope or out-of-scope.

## Touchpoints

- `src/tools/video-editor/extension.ts`
- `src/tools/video-editor/commands/types.ts`
- `src/tools/video-editor/commands/proposals.ts`
- `src/tools/video-editor/commands/editorCommandRegistry.ts`
- `src/tools/video-editor/hooks/useTimelineCommands.ts`
- `src/tools/video-editor/hooks/useAgentSession.ts`
- `src/tools/video-editor/components/ProposalReviewDialog.tsx`
- `src/tools/video-editor/data/DataProvider.ts`
- provider repository files from M2
- `supabase/functions/ai-timeline-agent/index.ts`
- `supabase/functions/ai-timeline-agent/types.ts`
- `supabase/functions/ai-timeline-agent/loop.ts`
- `supabase/functions/ai-timeline-agent/tools/registry.ts`
- `supabase/functions/ai-timeline-agent/tools/timeline.ts`
- `supabase/migrations/*`

## Required Tests

- Unit: proposal type creation, stale rejection, expiry rejection.
- Repository: save/load/accept/reject/expire proposal envelope.
- Frontend/edge integration: `proposal_policy: 'always'` returns proposal, does not mutate immediately.
- Client: accept applies proposal through existing command apply path.
- Agent commands: `set_params`, `set_theme`, `set_theme_overrides` remain proposal-safe through the command path.
- Agent direct paths: `create_shot` and any other direct database timeline mutation respect proposal policy or are explicitly blocked in proposal mode.
- Negative: unsupported providers gate proposal persistence UI with diagnostics.
