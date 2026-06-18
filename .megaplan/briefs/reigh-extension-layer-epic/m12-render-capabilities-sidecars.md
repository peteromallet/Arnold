# M12: Render Capability Planning, Output Formats, And Processes

## Outcome

Replace ad hoc export checks with an explainable capability planner and add the process/sidecar contracts needed for local tools such as Blender MCP, render-dependent output formats, and future worker/cloud execution.

## Execution Posture

This is the export truth court. Be conservative, explainable, and user-actionable: every route claim must be proven, every blocker should name a next action, and local processes must remain trusted-local power with visible lifecycle and provenance.

## Scope

IN:
- Define `IntegrationCapabilities`.
- Define render capability inspection for extension features: component effects, shader effects, transitions, clip types, live sources, output formats, and processes.
- Add route planning that explains why a timeline can render in browser, worker, sidecar/process, or must be blocked.
- Make export guards use capability planning rather than ad hoc checks.
- Define render-dependent `OutputFormatContribution`.
- Extend the base `RenderArtifact` model with sidecars and multi-artifact export results.
- Define the planner's materialization step: resolve timeline state, resolve `RenderMaterialRef`s, detect missing/unbaked/stale materials, offer bake/materialize actions, then compile the route plan for Remotion/browser/worker/sidecar.
- Define `RenderArtifactManifest` metadata for deterministic outputs: producer extension/version, consumed `RenderMaterial` refs, input hashes where available, render route, process/tool versions, sidecars, diagnostics, and determinism status.
- Define frame/audio sampling vocabulary for export routes: ranges, fps/sample rate, clip slicing, thumbnails/frame extracts, per-item diagnostics, and manifest references.
- Define a host-validated sampling configuration schema for dataset/show-control exports: source refs, strategy, resolution/fps/sample-rate overrides, label/caption/provenance attachment rules, and per-item diagnostics.
- Prove the planner can consume the public `TimelineSnapshot`/`TimelineReader` contract for export-relevant context instead of reaching through provider internals.
- Activate the reserved `ProcessContribution` contract for trusted local processes.
- Add `LocalProcessRuntime` with stdio JSON-RPC. Websocket/http process protocols remain deferred until the trust model changes.
- Add process lifecycle UI/status: start, stop, restart, health diagnostics, dependency unavailable states.
- Add host-owned material browser/picker/detail UI, pending-material timeline placeholder rendering, roundtrip-results panel, process operation discovery, sidecar preview panel, and export configuration shell.
- Add `ctx.services.invokeProcess(processId, operation, input)` for agent tools, commands, and render/output-format integrations.
- Add one render-dependent output format example.
- Add one dataset/show-control style multi-artifact export canary that produces primary artifact plus metadata/sidecar manifest, proving frame/audio/sidecar export semantics without requiring cloud execution.
- Add one process roundtrip canary that returns a `RenderMaterial`, then uses a `TimelineProposal` to insert, replace, or attach a material-backed clip without mutating unrelated timeline state.
- Add SDK helper(s) for converting material/process roundtrip results into proposal-backed insert/replace/attach operations.
- Add one mock local process canary that proves lifecycle, IPC, diagnostics, and shutdown.

OUT:
- Shader/WebGL runtime.
- Production sidecar hosting.
- Cloud worker execution of extension code.
- Full Blender product workflow.
- Marketplace permission enforcement.

## Locked Decisions

- The planner is the source of truth for export claims. No route may claim support for code it cannot execute.
- Processes are trusted local only in V1.
- `ProcessContribution` is generic, not render-only, so Blender MCP and similar local tools do not have to masquerade as output formats.
- M12 extends M5's base `RenderArtifact` with a `RenderArtifactManifest` and `sidecars?: Array<{ filename, mimeType, data, kind }>` so exports can explain provenance, consumed materials, and determinism.
- Process failures create diagnostics and visible export/tool blockers; they do not crash the editor.
- Sidecar/process artifacts appear in export UI as individual downloads plus a "download all" bundle where applicable.
- `ProcessContribution` is a declarative `ProcessSpec`: ID, display name, command/args template, env schema, health check, supported operations, and declared render/tool capabilities.
- The stdio protocol uses newline-delimited JSON-RPC with correlation IDs, structured progress events, cancellation, and typed error payloads.
- `ProcessStatus` is a sealed union: not-installed, stopped, starting, ready, busy, degraded, failed, stopping.
- Process UI is visible from extension manager/status surfaces and shows commands, dependency guidance, health, logs summary, and operations that are currently blocking export/tools.
- Process operations are discoverable through command palette and process detail surfaces. Process env schemas register richer `SchemaForm` widgets for environment fields, paths, variable hints, and platform-specific defaults where feasible.
- Roundtrip results render in a host-owned panel listing returned materials, sidecars, previews, diagnostics, logs/metadata summaries, and actions: insert as clip, replace, attach, download sidecar, discard, or create proposal.
- Material browser/detail UI supports filtering by producer, media kind, pass name/render group, determinism, stale/missing state, source refs, and provenance/enrichment metadata. Material-backed clips render host-owned pending/materializing/failed/concrete timeline states.
- Export configuration shell is host-owned: source selection, sampling strategy forms, dry-run sample table, per-item diagnostics, sidecar previews, manifest preview, and download-all behavior. Extensions contribute output-format schemas and serializers, not full bespoke export wizards.
- Sidecar previews render safe-size JSON/tree, text/log snippets, cue lists, thumbnails, and provenance cards before download.
- Cue-list, timeline segment/caption, and batch-label widgets are generic host widgets for timecode-anchored sidecar editing; extensions own format-specific parsing/serialization.
- The M12 planner is the canonical export blocker surface. Earlier milestone badges/scans are convenience links into planner-compatible records, not separate competing export truth.
- Multi-artifact exports must include manifest provenance, consent/provenance metadata where present, sidecar roles, and route/process versions where applicable.
- Roundtrip operations declare input artifact refs, external operation IDs, returned artifact refs, sidecar roles, and replacement/attach behavior.
- Process outputs are artifacts, sidecars, diagnostics, or planner/tool results. They are not a direct timeline mutation channel; process-backed timeline changes must become `TimelinePatch`/`TimelineProposal` through the caller or host workflow.
- `RenderMaterial` includes optional source asset/material refs and inherited metadata. Direct asset bakes propagate provenance/consent/enrichment metadata; process/shader materials carry producer-returned metadata plus declared inputs. Final manifests include consumed material metadata and source chains.
- Multi-pass outputs use render groups: each composable pass is a `RenderMaterial` with `passName` and `renderGroupId`; non-composable outputs are sidecars. Missing/stale required passes block the group.
- `ProcessRoundtripRequest`/`ProcessRoundtripResult` fixtures define operation ID, input material/artifact refs, params, pass names, frame ranges, progress, returned materials, sidecars, diagnostics, and sealed sidecar roles such as metadata, thumbnail, scene-report, log, provenance, and rendered-pass.
- `RenderArtifactManifest` may include review provenance contributed by a review extension mapping from extension-owned project data. The host carries review records into manifests but does not own approval policy.
- Sampling configs are declarative, not a programmable query language.
- Pre-render/materialization is a planner route option, not the default render architecture. Deterministic component/Remotion routes should render directly; materialization is for live, process, GPU, generated, expensive, or otherwise unstable work crossing into stable composition.

## Done Criteria

- Render planner reports capabilities and blockers for native, component-effect, extension-transition, extension-clip, live-source, process-dependent, and output-format scenarios.
- Export UI surfaces clear reasons and next actions.
- Tests prove a component effect that blocks worker export downgrades to browser export or blocks with a structured reason.
- Tests cover artifact model compatibility, render-dependent output formats, mock process invocation, health failure, shutdown, and sidecar download UI.
- Tests cover artifact manifest provenance, input hash propagation where available, determinism status, and sidecar manifest consistency.
- Tests cover a multi-artifact dataset/show-control export with sidecar manifest, provenance metadata, and download-all behavior.
- Tests cover planner/export inspection using the public `TimelineSnapshot`/`TimelineReader` contract, including contribution requirements and missing-extension blockers, with no raw provider reads.
- Tests cover missing, stale, and resolved `RenderMaterialRef`s in planner reports and final artifact manifests.
- Tests cover frame/audio sampling manifest entries and process roundtrip attachment behavior.
- Tests cover material metadata propagation, render-group blocking, roundtrip request/result fixtures, material proposal helper output, review provenance manifest contribution, show-control cue sidecars, captions vs labels, and declarative sampling config validation.
- Tests cover material browser/detail filters, pending-material timeline placeholder states, process operation discovery, process env widgets, roundtrip results panel actions, sidecar previews, export dry-run table, cue-list editor, segment/caption editor, batch-label panel, and download-all UI.
- A mock MCP-style process can be invoked by a command/agent tool through `ctx.services.invokeProcess`.
- Tests cover JSON-RPC correlation, progress, cancellation, unavailable dependency diagnostics, and process status transitions in frontend UI.

## Touchpoints

- `renderRouter.ts`
- Render pipeline
- Export UI
- Diagnostics/status surfaces
- SDK render capability, output format, process, and artifact types
- Trusted local loader/runtime
