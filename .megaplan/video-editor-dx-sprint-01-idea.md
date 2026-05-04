Video editor developer platform Sprint 1: canonical timeline domain model.

Context:
The Reigh video editor under src/tools/video-editor has useful primitives, but it is not yet easy for developers or agents to build on top of. Current pain points include multiple timeline shapes (TimelineClip, ClipMeta, ResolvedTimelineClip, TimelineData rows/meta/clipOrder), inconsistent duration semantics across UI/render/agent paths, Reigh-specific dependencies mixed into editor provider/components, and mutation paths that require internal knowledge.

This sprint is the first two-week slice. It must preserve the current Reigh app behavior while establishing the domain foundation for later ports/adapters, headless core, clip-type plugins, command bus, render pipeline hooks, and UI slots.

Goal:
Create a canonical timeline domain layer that all current editor paths can use without changing user-visible functionality.

Primary outcomes:
- Establish one documented canonical interpretation of persisted TimelineConfig + AssetRegistry.
- Centralize repair/migration/canonicalization, duration calculation, validation, serialization, and structured errors.
- Remove or reduce divergent duration/shape logic between UI, Remotion renderer, import, and ai-timeline-agent paths.
- Prepare for agent-safe editing by defining validation/dry-run-friendly primitives, even if the full command bus ships in a later sprint.

Important constraints:
- Do not rewrite the video editor.
- Do not change visible editor behavior except to fix clear inconsistencies.
- Keep the existing Reigh editor page and shell working.
- Keep current tests passing; add targeted tests for canonical domain behavior.
- Avoid broad UI refactors in this sprint unless required to route through the domain layer.
- Do not make plugin registries or UI slots yet; only shape the domain layer so those later sprints are easier.

Areas to inspect:
- src/tools/video-editor/types/index.ts
- src/tools/video-editor/lib/timeline-data.ts
- src/tools/video-editor/lib/config-utils.ts
- src/tools/video-editor/lib/serialize.ts
- src/tools/video-editor/lib/migrate.ts
- src/tools/video-editor/hooks/useTimelineCommit.ts
- src/tools/video-editor/hooks/useTimelinePersistence.ts
- src/tools/video-editor/hooks/usePollSync.ts
- src/tools/video-editor/compositions/TimelineRenderer.tsx
- src/tools/video-editor/hooks/useDerivedTimeline.ts
- supabase/functions/timeline-import
- supabase/functions/ai-timeline-agent

Known issues to address or explicitly plan:
- UI load repairs/migrates before use, but ai-timeline-agent reads raw DB config.
- UI duration helpers and agent timeline tools can interpret clips with missing from/to differently.
- Some render paths compute sequence duration manually instead of using shared duration helpers.
- Import validation and editor serialization validation may accept/reject different shapes.
- Poll sync may advance configVersionRef before accepting polled data, potentially weakening conflict detection.
- Pinned shot group metadata is not maintained consistently by backend clip CRUD.

Success criteria:
- There is a canonical domain module/API for timeline normalization, duration, validation, and serialization.
- UI, renderer, import, and agent paths either use this API or have explicit follow-up tasks for remaining migration.
- Tests cover equivalent duration/canonicalization behavior across at least UI/domain and agent/import-adjacent helpers.
- Current editor functionality remains intact.
- The resulting API is understandable for a later command bus and agent edit layer.

Deliverable:
A code diff plus a concise notes section explaining the canonical domain boundary, remaining non-canonical call sites, and recommended Sprint 2 work.
