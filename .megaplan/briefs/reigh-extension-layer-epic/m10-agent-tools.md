# M10: Agent Tool Contributions And Proposal-Backed AI Workflows

## Outcome

Make AI/agent extensibility use the same safe host-owned primitive contracts as UI extensions: agent tools contribute schemas, receive explicit creative context, and return proposals, generated outputs, sessions, diagnostics, or timeline patches when the tool is actually editing temporal composition.

## Execution Posture

Agent tools are powerful collaborators, not privileged editors. Keep them schema-rendered, cancellable, diagnostic-rich, proposal-backed, and aligned with the future live/bake workflow without building a parallel runtime.

## Scope

IN:
- Define `AgentToolContribution`.
- Add host registry for agent tools.
- Validate tool inputs and outputs with standard schemas.
- Add forward-compatible progress/cancel channel shape for tools that start long-running generation but do not deliver samples through proposals.
- Define the `GenerationSession` handle shape that unifies tool progress, live sample delivery, cancellation, and eventual bake/material refs. M10 may return placeholder sample channels until M11 activates real live delivery.
- Reserve an `invokeProcess` stub that returns a structured not-available diagnostic until M12 activates process contributions.
- Support local browser/worker tool execution where feasible.
- Support edge-action shape as a deployment wrapper around the same contract.
- Convert timeline-editing tool outputs into `TimelinePatch[]` or `TimelineProposal`.
- Support non-timeline tool outputs in the explicit `ToolResult` union, grouped into stable families rather than feature-by-feature one-offs: mutation/proposal, generation/session, material/artifact, enrichment/search, export finding, process pending/result, UI summary, and diagnostic.
- Adapt at least one existing AI timeline/effect workflow to produce proposal-backed changes instead of direct mutation where appropriate.
- Add a thin flagship-workflow canary: a contributed agent tool starts a long-running fake generation, reports progress/cancel, produces a proposal, and returns a fake baked asset/reference through the typed result shape without implementing real live-data streaming.
- Add a copilot canary that reads a `TimelineSnapshot`, returns a proposal with rationale/explanation and affected object references, and demonstrates `replaceForSource` for iterative suggestions.
- Add an export-adjacent tool canary that reads the same snapshot contract and returns planner-compatible diagnostics/proposal metadata, proving tools do not need raw provider internals to reason about export-relevant state.
- Add diagnostics for tool lifecycle, validation, and proposal conversion.
- Add frontend invocation surface for contributed agent tools.
- Add a host-owned copilot prompt surface for freeform invocation of a registered copilot tool, plus pre-invocation context preview for explicit timeline/material/asset context.

OUT:
- Full autonomous local agent runtime.
- Cloud agent runtime.
- Marketplace tool permissions.
- AI-generated transitions before transition registry is stable.

## Locked Decisions

- Agents are not autonomous mutators of the data layer; they are host-mediated collaborators. Mutation contracts are primitive-specific host ops/proposals, with `TimelinePatch` only for temporal composition edits.
- Edge functions should return typed primitive results: patches/proposals when editing timeline, generation sessions or material refs when generating media, enrichment records when analyzing assets, sidecars/artifacts when exporting, and diagnostics when blocked.
- AI-generated effect resources remain compiled-string resources, not trusted local component effects.
- First adapted workflow is a low-risk AI timeline/effect workflow that already has validation coverage and can return a proposal without changing production persistence semantics.
- Edge tools receive explicit request context only: project identifiers, requested `CreativeContext` slices such as timeline/assets/materials/export/stage/writing, auth token metadata needed by existing gateways, and declared tool input. They do not receive raw provider internals.
- Extension-contributed edge actions use existing auth/rate-limit conventions through host gateways; tools declare network permission metadata but enforcement waits for sandboxing.
- Long-running generation uses live-channel handles for progress/sample delivery and proposals only for user-visible timeline changes.
- Agent tools that produce streaming media return a `GenerationSession` handle. The session shares one cancellation token across progress events, sample delivery, process invocation where applicable, and bake/finalize actions.
- Agent tools are discoverable through command palette and an agent-tools panel/section; tool input schemas render basic forms where possible.
- Freeform copilot prompt UI is host-owned and singular. It can route to registered copilot tools, attach selected timeline/material/asset context, show context preview before execution, and preserve an invocation history summary. Extensions contribute tools and schemas, not competing chat surfaces.
- Tool lifecycle states are visible: idle, validating, running, streaming/progress, proposal-ready, failed, cancelled.
- Tool cancellation is part of the host contract for long-running local/edge tools.
- Tool input forms use the M2 host-owned `SchemaForm` subset; unsupported schema shapes produce diagnostics rather than bespoke controls.
- Tool results use an explicit `ToolResult` union grouped by families: mutation/proposal (`patches`, `proposal`), generation/session (`generationSession`, `progressHandle`), material/artifact (`assetRefs`, `materialRefs`, `sidecars`), enrichment/search (`enrichmentRecords`), export (`exportPlanFinding`), process (`processInvocationPending`), UI summary (`uiResult`), and `diagnostic`. New result shapes must fit a family or justify a new family in an SDK review.
- The M10 canary intentionally models the future live-diffusion loop at the contract level only. M11 owns real live source buffers and bake internals; M10 must not implement a parallel live-data system.
- Tool outputs that create proposals should include rationale/explanation metadata and source-to-output references when available; the host displays them in proposal UI rather than treating AI suggestions as opaque patches.

## Constraints

- Tools must not bypass validation or proposal acceptance.
- Existing Supabase edge functions must keep working during migration.
- Tool failures must be attributable by extension/tool ID.

## Done Criteria

- Example agent tool produces a proposal and user can preview/accept/reject it.
- Adapted AI workflow has tests for validation, stale base rejection, and failure diagnostics.
- Tool registry is provider-scoped and HMR-safe.
- Live-channel handle is typed and diagnosed as preview-only until the live-data bridge milestone implements full streaming/bake.
- Tests cover frontend invocation, schema validation UI, progress/cancel, proposal creation, and failure diagnostics.
- Tests cover copilot prompt invocation, context preview trimming/confirmation, invocation history summary, and rejection of competing extension-owned chat surfaces.
- Tests cover unsupported schema diagnostics and the pre-M12 `invokeProcess` not-available diagnostic.
- Tests cover the fake long-running generation canary end to end: invoke, progress, cancel path, proposal-ready path, fake baked reference, and diagnostics.
- Tests cover a `GenerationSession` contract stub, including progress, cancellation, placeholder sample channel, and later bake/material result metadata.
- Tests cover the copilot canary reading a timeline snapshot and showing proposal rationale/affected-object metadata before acceptance.
- Tests cover the export-adjacent snapshot canary, including missing contribution/export blocker context in the explicit request payload rather than raw provider access.

## Touchpoints

- AI timeline agent functions
- Edge function client code
- Proposal runtime
- SDK agent types
- Diagnostics/status surfaces
