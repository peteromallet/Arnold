# M3: TimelinePatch, Atomic Ops, Proposals

## Outcome

Build the semantic timeline mutation layer that makes temporal extension edits safe: `TimelinePatch`, atomic `TimelineOps`, proposal preview/accept/reject, optimistic concurrency, checkpoints, rollback, and ghost preview rendering.

## Execution Posture

This is the timeline mutation constitution, not the constitution for every creative primitive. Prefer a small semantic vocabulary with strong validation, replay, undo, and preview guarantees over broad escape hatches; when a timeline vocabulary is missing something, extend it deliberately instead of leaking provider internals. Non-timeline primitives follow the same discipline through their own host-owned ops/proposals when they become public.

## Scope

IN:
- Define public semantic `TimelinePatch` operations.
- Wrap existing mutation engine/command facade behind stable `TimelineOps`.
- Implement `validate`, `apply`, `checkpoint`, `rollback`, and narrow helpers such as `setAllTracksMuted`.
- Add `ProposalRuntime` with `baseVersion`, preview, accept, reject, and source metadata.
- Add `ProposalRuntime.replaceForSource(sourceId, proposalInput)` or an equivalent atomic create option that replaces pending proposals from the same compiler/tool/source without proposal spam.
- Add `proposals.subscribe(listener)` for pending/accepted/rejected/stale state changes.
- Add ghost/preview timeline rendering for proposed clips/changes.
- Add a proposal UI surface for pending proposals with preview, accept, reject, and diagnostic state.
- Add host-owned proposal diff rendering for `TimelineDiff` payloads and source-map navigation between code panel/source ranges and affected timeline objects.
- Add structured validation errors and diagnostics.
- Adapt one existing local extension example to mutate through patches/proposals.
- Add golden patch replay fixtures that validate/apply/undo/replay representative patch batches against at least two provider modes where feasible.
- Add provider compatibility matrix rows for settings, extension requirements, proposal base versions, diagnostics, missing extension references, and patch replay behavior.
- Define patch/operation extension mechanism for later contribution kinds: namespaced operation families, validation ownership, replay semantics, previewability contract, migration/version rules, and how new operations enter the public SDK without exposing raw provider mutation. The mechanism must allow non-timeline primitive ops without forcing them into clip/track semantics.
- Define a small patch-backed extension-owned project data namespace for portable JSON state such as DSL source documents, review annotations, consent/provenance notes, and source-to-output mappings. This is not a large blob store or arbitrary database; publish explicit V1 per-entry and per-extension limits so authors know when to use assets/artifacts/provider-backed repositories instead.
- Define `TimelineSnapshot`/`TimelineReader` read contracts for timeline tools and compilers: stable project/timeline IDs, version/baseVersion, selected clips/assets, normalized clip/track/asset summaries, extension requirement metadata, and render/export-relevant contribution summaries. Raw provider internals remain hidden.
- Define how `TimelineSnapshot` plugs into the broader `CreativeContext` reserved in M1 so agents, exporters, asset tools, and process integrations can request timeline context only when they need temporal composition.
- Define `SourceMapEntry` and generated-object metadata for compiler/DSL workflows: source URI, 1-based range, target object kind/ID/version, stale flag, generated object ID/version, owner extension/source, and bidirectional navigation hooks.
- Define optional `TimelineDiff` proposal metadata for sparse before/after change summaries used by review and proposal UI.

OUT:
- CRDT sync.
- Arbitrary JSON Patch.
- Direct extension access to internal mutation engine.
- AI edge migration, except where needed for contract tests.

## Locked Decisions

- `TimelinePatch` is semantic, not raw JSON Patch.
- Extension mutation is transactional: validate first, apply atomically, create undo/checkpoint behavior.
- Risky AI/compiler changes should use proposals, not direct mutation.
- Proposal acceptance rejects or regenerates when base timeline version has changed.
- Initial patch vocabulary is `clip.insert`, `clip.update`, `clip.delete`, relative/fractional clip move/reorder, `track.update`, `asset.update`, and constrained namespaced `app.update`.
- Initial vocabulary also includes or explicitly reserves `clip.split`/slice semantics for dataset/export workflows. If implementation defers execution, the patch extension mechanism must name the operation family and diagnostics.
- Do not make absolute `clip.reorder: clipIds[]` the only reorder primitive; use a sync-compatible relative/fractional ordering representation from the start.
- `baseVersion` comes from the provider timeline version where available; local providers that cannot enforce versions must report that limitation and still provide a monotonic local version for proposal invalidation.
- Preview rendering must support proposed clips/changes as a ghost layer without mutating the canonical timeline; if a patch type cannot preview safely, it is diagnosed as non-previewable.
- Tombstone/envelope compatibility must be considered in patch shapes even though CRDT sync is deferred.
- `TimelineReader` exposes a current `version`/`baseVersion` snapshot so extension authors can create proposals without reading provider internals.
- Proposal UI is host-owned: status count plus panel/dialog listing proposals by source, label, previewability, and stale status.
- Proposal metadata includes human-readable rationale/explanation, source document/tool IDs, optional source-to-output mapping, and affected object references so copilots/compilers can explain changes before acceptance.
- Proposal UI renders visual ghost previews where possible and a structured diff view for non-visual changes. Diffs link to affected objects and source maps when present.
- Stale source maps produce visible timeline badges, code-panel gutter/status indicators, and diagnostic entries navigable from the diagnostic panel.
- Managed-object overwrite warnings are host-owned confirmation dialogs naming the owning extension/source, last generation timestamp when known, and actions such as cancel, edit anyway/detach, or open source.
- Generated/managed content may carry owner/source metadata so the host can warn before manual edits overwrite extension-managed clips, keyframes, or annotations.
- Fractional ordering uses a stable ordered-position field or equivalent lexicographically sortable key; relative move patches specify clip, target track, and before/after anchors rather than full absolute arrays.
- `TimelineOps.apply()` and `ProposalRuntime.accept()` create undo entries through the existing history system; this milestone must not create a parallel undo stack.
- `TimelineOps.validate()` publishes validation diagnostics under source `timeline-patch`; non-previewable patches are visible in the proposal UI and diagnostics panel.
- `setAllTracksMuted` is included only as the example bulk helper for the first command/demo; general bulk operations should compose ordinary patch batches.
- Proposals are provider-scoped and in-memory in this milestone. Refreshing the page drops unaccepted proposals; persisted proposal queues are deferred.
- Patch semantics are documented in a table covering merge/replace behavior for `clip.update`, `track.update`, `asset.update`, `app.update`, reorder/move anchors, and validation of contribution IDs.
- M3 is a hard gate for timeline patch semantics: no later contribution kind may bypass host-owned ops/proposals or raw provider protections because a desired mutation is missing from the initial vocabulary. Missing timeline vocabulary becomes an explicit M3 follow-up or a later patch extension; non-timeline primitives get their own host-owned read/ops/proposal contracts rather than raw provider access.
- `app.update` is not the pressure valve for arbitrary extension data. New contribution-specific mutation needs must use the patch extension mechanism with validation/replay/preview rules.
- Extension-owned project data updates use explicit namespaced operations with concrete size/schema limits and must remain replayable. V1 limits are 64 KB per entry, 1 MB per extension, and 128 entries per extension. The limit policy is part of the public contract: oversized payloads produce validation diagnostics that point authors to assets, `RenderMaterial` refs, render artifacts, provider-backed extension repositories, or package resources.
- Compiler/DSL proposals can mark generated objects with stable generated object IDs and versions. Recompile flows should propose add/update/delete/cleanup for the compiler's own generated objects without deleting unrelated user-authored timeline content.

## Constraints

- Existing editor commands must keep working.
- Internal mutation shapes may evolve; the public SDK must not expose them.
- Patch validation must reject unknown top-level timeline mutations and any asset/project mutations not explicitly owned by this milestone's operation vocabulary.

## Done Criteria

- Extension authors can safely insert/update/delete/reorder clips and update tracks/assets through `TimelineOps`.
- Proposal preview shows without mutating the real timeline.
- Accept/reject behavior is tested, including stale base version rejection.
- Undo/rollback behavior is covered for patch batches.
- Relative/fractional ordering is covered by tests and documented for future sync.
- Proposal UI is covered by tests for previewable, non-previewable, accepted, rejected, and stale proposals.
- Local/Astrid provider version behavior is tested, including monotonic local invalidation where strict expected-version enforcement is unavailable.
- Rapid compiler iteration is tested: replacing a proposal from the same source rejects/replaces the prior pending proposal atomically.
- Golden patch replay tests prove representative patch batches validate, apply, undo/rollback, serialize, and replay consistently across at least two provider modes where feasible.
- Provider compatibility matrix is updated with concrete pass/defer notes for patch/proposal behavior.
- Patch extension mechanism is documented and tested with at least one namespaced no-op/example extension operation that validates, serializes, rejects invalid payloads, and remains previewability-aware.
- Tests cover extension-owned project data persistence/replay for a tiny DSL or annotation document, oversized payload rejection with actionable diagnostics, plus proposal rationale/source mapping display in the proposal UI.
- Tests cover a tiny DSL/compiler canary that reads `CreativeContext.timeline`, stores source/source-map data in the namespaced project namespace, and emits a `TimelineProposal` rather than touching provider internals.
- Tests cover source-to-timeline and timeline-to-source navigation metadata, stale source maps after source edits, generated-object cleanup proposals, and typed project-data limit diagnostics.
- Tests cover proposal diff rendering, source-map navigation from diff/diagnostic UI, stale source-map badges, and managed-object overwrite confirmation.
- Tests cover `clip.split`/slice reservation or implementation and managed-content warning metadata.

## Touchpoints

- `timeline-mutation-engine.ts`
- `useTimelineState.types.ts`
- Timeline canvas/preview rendering
- Data provider save/version paths
- SDK types
