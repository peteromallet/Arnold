# M1: Contracts And Proposal Spine

## Outcome

Freeze the foundation contracts needed before implementation fans out: canonical proposal envelope/import API, initialized proposal persistence ownership, proposal import diagnostics, proposal policy decision, settings source-of-truth decision, direct-extension inventory decision, and the named extension activity region contract. Implement the proposal runtime/persistence spine and failing anchors for the end-to-end proposal path.

## Scope

In scope:

- Make edge-imported proposals a public typed runtime capability, not a duck-typed implementation detail.
- Choose and document the canonical proposal wire shape: preferred contract is SDK `ProposalEnvelope` emitted by the edge and structurally validated on the client.
- Ensure proposal runtime persistence uses an initialized provider-owned storage path instead of a second uninitialized persistence service.
- Add import diagnostics for malformed envelopes, unsupported operations, payload mismatches, stale base versions, expired/terminal proposals, and missing runtime import support.
- Name and document the production extension activity region that will host proposal/agent/diagnostic status surfaces.
- Lock decisions for `proposal_policy`, settings source of truth, and manager direct-extension inventory semantics as documented contracts or TODO rows for later milestones.
- Add narrow failing tests/fixtures that prove the current proposal vertical is incomplete and that later milestones must satisfy it.

Out of scope:

- Do not wire the full edge -> `useAgentSession` -> UI vertical yet unless it falls out naturally after the contract work.
- Do not build new contribution families.
- Do not mount full `AgentToolsPanel` or `DiagnosticPanel`.
- Do not publish an external SDK package.
- Do not change manager settings UI yet.

## Locked Decisions

- One prerequisite epic remains the boundary; this milestone is the first sprint inside it.
- Preferred proposal contract: edge emits SDK `ProposalEnvelope`, client validates, runtime exposes public import.
- Proposal persistence must use initialized provider-owned storage.
- The activity surface should be near toolbar/timeline and should avoid disconnected status drawers.
- Marketplace/install/update/sandbox/published SDK are non-goals.

## Open Questions To Resolve

- Exact public import API name: `importEnvelope`, `importProposal`, or both with one deprecated/adapter path.
- Whether `proposal_policy` remains durable session state or becomes explicitly per-invocation with dead storage removed.
- Whether direct host-supplied extensions are synthesized into manager inventory or explicitly excluded with truthful copy.
- Exact activity region component name and minimum props/state contract.

## Constraints

- Preserve existing accept/reject/apply semantics for proposals.
- Avoid broad SDK cleanup beyond the proposal import contract.
- Do not create a parallel proposal persistence service that can hydrate stale or uninitialized state.
- Backward compatibility matters for existing localStorage/settings paths; do not migrate settings in this milestone.

## Done Criteria

- Public in-repo proposal runtime contract includes typed import capability.
- Proposal import has structural validation and host-visible diagnostics.
- Proposal persistence path is initialized and provider-owned.
- Foundation contract decisions are documented in code comments/docs where future implementers can find them.
- Tests or fixtures fail or pass in a way that anchors the later edge/client/UI vertical requirements.
- No new marketplace/sandbox/contribution-family scope is introduced.

## Touchpoints

- `docs/extensions/extension-layer-foundation-assessment.md`
- `src/sdk/index.ts`
- `src/tools/video-editor/lib/proposal-runtime.ts`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/runtime/extensionPersistenceCache.ts`
- `src/tools/video-editor/data/DataProvider.ts`
- Proposal runtime tests and provider/persistence tests.

## Anti-Scope

- No full Phase 4 contribution families.
- No published `@reigh/editor-sdk`.
- No broad SDK reorganization.
- No manager SchemaForm implementation.
- No cosmetic UI redesign beyond defining the activity region contract.

