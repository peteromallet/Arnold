# Phase 4 Extension Readiness Gate

Date: 2026-06-23
Scope: readiness review before public contribution-family promotion.

This artifact is the Phase 4 gate requested by the extension manager milestone.
It reconciles current runtime behavior, render/export planning, trust posture,
and the roadmap/ticket backlog without editing the roadmap or ticket source
documents.

## Current Code Anchors

- The roadmap and ticket backlog still name
  `src/tools/video-editor/runtime/contributionFamilies.ts` as the contribution
  family matrix. That file is not present in this checkout. The current
  runtime family sources are `src/sdk/index.ts`, which defines
  `ContributionKind`, `KNOWN_CONTRIBUTION_KINDS`,
  `CONTRIBUTION_KIND_MILESTONE`, and `contributionKindNotYetBridged()`, and
  `src/tools/video-editor/runtime/extensionSurface.ts`, which normalizes active
  or reserved contributions into provider/runtime descriptors.
- `src/tools/video-editor/runtime/extensionSurface.ts` currently bridges or
  surfaces reserved descriptors for output formats, processes, shaders, and
  agent tools. Output formats are turned into planner metadata with route
  requirements, process requirements, blockers, next actions, sidecars, and
  capability metadata. Process descriptors are surfaced as planner-visible
  declarations without starting a runtime process.
- `src/tools/video-editor/lib/renderRouter.ts` remains the route decision
  adapter for user render clicks. It converts native, themed, generated
  Remotion module, and contributed clip content into `CapabilityRequirement`
  entries, calls `planRender()`, and returns a planner-backed route decision.
- `src/tools/video-editor/runtime/renderPlanner.ts` is the canonical render
  readiness reducer. It consumes timeline snapshot requirements, explicit
  requirements, output format descriptors, process descriptors, shader
  descriptors, material refs/statuses, render groups, request constraints, and
  diagnostics, then returns route plans, blockers, diagnostics, next actions,
  and `canBrowserExport`/`canWorkerExport`.

## Render Planner Participation Contract

Any Phase 4 family that can affect preview, export, generated artifacts, or
determinism must participate in planning through stable capability metadata
before it can be promoted to public support.

Required contract:

1. Each promoted family must expose provider-free planner inspection data. The
   planner must not import live registries, component implementations, provider
   stores, or extension package handles.
2. Each render-relevant contribution must declare one or more route-level
   `CapabilityRequirement` records or a descriptor that `planRender()` can
   convert into equivalent requirements.
3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
   process-dependent, missing-contribution, and route-unsupported states must
   produce actionable `RenderBlocker` records rather than silent fallback.
4. Route decisions must remain planner-backed. For clip routing,
   `renderRouter.ts` already indexes contributed clip records by `clipTypeId`,
   allows browser export only when the contribution explicitly declares a
   supported browser-export capability, and blocks worker conflicts for
   contributed code.
5. Output-format and process families must keep using planner descriptors
   rather than invoking providers directly from the planner. Current
   `extensionSurface.ts` output-format descriptors are the model: route
   requirements, process requirements, blockers, next actions, sidecars, and
   capability metadata are data, not execution.
6. Shader and render-material families must distinguish preview from export.
   Current `renderPlanner.ts` shader materializer handling discovers
   materializer routes, emits process-dependent blockers/next actions, and
   keeps unresolved material refs from silently exporting.
7. Diagnostics published from planner findings must remain source-scoped so
   Extension Manager and diagnostics surfaces can show package/family blockers
   without confusing them with extension-authored runtime diagnostics.

Promotion is blocked for any family whose content can render, mutate timeline
state, invoke processes, consume live data, or produce export artifacts without
planner-visible requirements and failure states.

## Trust And Sandbox Posture

Phase 4 must continue the current explicit trust posture:

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime
  enforcement, sandbox isolation, code signing, or a permission broker.
- The Extension Manager warning introduced in Phase 3 is therefore a product
  requirement, not just documentation. It must stay visible during loading,
  empty, populated, selected-package, and error states.
- Public promotion of arbitrary code families such as effects, transitions,
  clip types, agent tools, local processes, shaders, and sidecars is blocked
  until the accepted posture is either "trusted/signed local packages only" or
  a real sandbox/permission broker exists.
- If Phase 4 proceeds under trusted-local assumptions, every affected doc,
  manager surface, example, and compatibility table must avoid implying iframe
  isolation, runtime permission enforcement, marketplace review, or safe
  third-party execution.

## Per-Family Promotion Checklist

Apply this checklist to each family before changing compatibility status to
supported.

| Gate | Requirement |
| --- | --- |
| Manifest/schema | `config/contracts/reigh-extension.schema.json` accepts exactly the supported shape and rejects unknown or deferred fields. |
| Public SDK | `src/sdk/index.ts` exports stable types and public helpers only; examples do not import internals. |
| Runtime normalization | `extensionSurface.ts` or the owning runtime module converts manifest declarations into immutable provider-scoped descriptors with extension ID, contribution ID, order, disabled state, and diagnostics. |
| Lifecycle cleanup | Disable/unload unregisters renderers, commands, keybindings, diagnostics, settings-derived UI state, live channels, process handles, or shader resources owned by the extension. |
| Persistence posture | Any persisted state has provider-backed semantics or an explicit unsupported diagnostic. Settings/proposals must survive reload only where providers claim conformance. |
| Settings/parameters | Parameter schemas render through SchemaForm or an equivalent host-owned primitive, with unsupported shapes diagnosed and non-corrupting. |
| Diagnostics | Loader, runtime, planner, and extension-authored diagnostics are scoped by extension ID and contribution ID where applicable, bounded, and cleaned up. |
| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
| UI integration | Picker, inspector, manager, diagnostics, empty/loading/error/disabled states, and provenance labels are present where the family is visible. |
| Tests | Unit, provider/lifecycle, render planner, negative schema/runtime, and browser acceptance coverage prove supported and failure paths. |
| Docs/examples | Authoring, loading, compatibility, examples, and release gates agree on support status and trust posture. |

Family-specific readiness:

| Family | Minimum readiness before support |
| --- | --- |
| Asset parser | Permission/declaration checks, parser failure diagnostics, safe asset metadata enrichment, query/filter API boundaries, and export/bake posture. |
| Effect | Trusted/signed package decision, parameter SchemaForm, picker/inspector provenance, preview errors, serialization/reload, and planner blockers for preview-only or unsupported export. |
| Transition | Provider-scoped registry, selector/inspector parameters, missing/disabled repair behavior, serialization/reload, render coverage, and export blockers. |
| Clip type | Sequence-backed subset first, insertion/inspection/rendering, serialization/reload, duplicate/missing/blocked capability failures, and planner participation through `renderRouter.ts`/`planRender()`. |
| Keyframes | Minimal model, commands/proposals, migration, interpolation tests, and deterministic preview/export delivery. |
| Agent tool | Proposal-first destructive behavior, backend dispatch registry, permission declarations, result-family validation, persisted proposals, and disabled/failure diagnostics. |
| Live data | Source lifecycle, permission state, bounded ring buffer, bake-to-deterministic asset/material workflow, steering lineage, and unbaked export blockers. |
| Render material | Public material/capability declarations, artifact manifest integration, material status tracking, and planner blockers/next actions. |
| Process/sidecar | Trusted local process model, command/env/cwd policy, JSON-RPC protocol, health/log/cancel/shutdown behavior, manager health UI, and explicit trust warnings. |
| Shader/WebGL | Source/uniform/texture schema, compile diagnostics, deterministic preview canaries, context-loss fallback, materializer/export route posture, and honest export blockers. |

## Roadmap And Ticket Reconciliation

This table records what must be reconciled after review. It intentionally does
not edit `docs/extensions/reigh-extension-layer-roadmap-v2.md` or
`docs/extensions/reigh-extension-layer-tickets.md`.

| Source item | Current status | Reconciliation needed before Phase 4 |
| --- | --- | --- |
| Roadmap Phase 1 acceptance cites `runtime/contributionFamilies.ts` | Stale path in this checkout; contribution kind data currently lives in `src/sdk/index.ts`, and runtime descriptor normalization lives in `extensionSurface.ts`. | Update roadmap/ticket references after review, or restore a generated/owned contribution-family matrix file if that remains the intended gate. |
| Roadmap Phase 4 "Contribution Families And Render Hardening" | Correctly identifies asset parsers, effects, transitions, clip types, keyframes, agent tools, live data, render materials, sidecars/processes, and shaders as the next higher-power families. | Keep this sequencing, but require the checklist above and planner participation before any family moves to supported. |
| EXT-030 AssetParserContribution | Planned. | Add explicit render/export/bake posture and diagnostics requirements to the ticket if asset parser output can affect timeline materialization. |
| EXT-031 EffectContribution | Planned as trusted/signed packages. | Preserve trusted/signed wording, add manager trust warning coverage, and require planner blockers for preview-only effects. |
| EXT-032 TransitionContribution | Planned. | Add route capability metadata and fallback/repair behavior to prevent silent export differences. |
| EXT-033 ClipTypeContribution | Planned as a sequence-backed subset. | Keep subset scope; require `renderRouter.ts` contributed clip records and `planRender()` blockers before support. |
| EXT-034 Keyframes | Planned. | Treat as timeline data/model work first, not an extension family shortcut; require proposal/migration/render interpolation gates. |
| EXT-035 Render planner integration | Planned. | Promote this from a later hardening ticket to a prerequisite for every render-relevant family. |
| EXT-036 AgentToolContribution | Planned. | Block until proposal persistence and backend dispatch registry are stable; no direct destructive mutation by default. |
| EXT-037 Live data | Planned. | Block until bake/export semantics are accepted; unbaked live bindings must block export. |
| EXT-038 RenderMaterialContribution | Planned. | Tie directly to planner material refs/statuses, artifact manifests, and next actions. |
| EXT-039 Process/sidecar runtime | Planned as trusted local runtime. | Require separate trust approval, process policy, health UI, cancellation, and shutdown tests before public exposure. |
| EXT-040 Shader/WebGL bridge | Planned. | Keep behind render materialization posture and deterministic preview/export blocker tests. |
| EXT-041 Final docs/examples/validation | Planned. | Must include this readiness checklist as a closure matrix input, plus compatibility drift checks across schema, SDK, runtime, docs, examples, and tests. |

## Phase 4 Entry Decision

Phase 4 should not start as broad parallel family implementation. The next
accepted action should be either:

1. Fix the stale `contributionFamilies.ts` reference by restoring or replacing
   the family matrix gate, then update roadmap/ticket docs after review; or
2. Begin EXT-035-style render planner integration as a prerequisite slice for
   the first selected family, with this document as the acceptance checklist.

Until one of those paths is accepted, the readiness decision is: Phase 4 is
prepared but not cleared for public family promotion.
