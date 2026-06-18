# M0: Workspace And SDK Scaffold

## Outcome

Create the mechanical package boundary the rest of the epic depends on: stable import paths, build wiring, and profile/run configuration that let the chain start cleanly.

## Execution Posture

This is scaffolding, not product design. Keep it boring, stable, and future-proof: public import paths, test harness locations, and build wiring should make later milestones easier without freezing SDK semantics prematurely.

## Scope

IN:
- Add or confirm the workspace/package structure needed for public SDK imports.
- Create `@reigh/editor-sdk` as a stable TypeScript entrypoint, initially backed by a Vite/TS path alias if a full workspace package is not yet appropriate.
- Create or reserve the `@banodoco/timeline-schema` package boundary for shared timeline/patch types.
- Add TypeScript path aliases, export maps, and build/test config needed for those imports to compile.
- Add a placeholder `src/sdk/index.ts` that exports only minimal scaffolding and throws no runtime opinions into the editor.
- Add or reserve shared test-harness locations for SDK import/type tests, fake extension fixtures, and timeline-schema contract tests.

OUT:
- Provider injection.
- Extension runtime normalization.
- Final SDK type surface.
- Package publishing.
- Marketplace/installable packs.

## Locked Decisions

- M0 is mechanical. It should not make product API decisions beyond import paths and package boundaries.
- If a full monorepo package setup would create unnecessary churn, use path aliases first. The import path still must be the future-proof public path.
- `@reigh/editor-sdk` and `@banodoco/timeline-schema` are public boundary names; editor internals are not public imports.
- M0 may create empty/placeholder test harness files only where they prevent later milestones from inventing incompatible fixture locations.

## Done Criteria

- A test/example file can import from `@reigh/editor-sdk` and `@banodoco/timeline-schema` without importing editor internals.
- Typecheck/build config recognizes both public import paths.
- Test config can run SDK boundary/type tests without importing editor internals.
- The chain uses built-in `partnered-3`, `partnered-4`, and `partnered-5` profiles without project-local overrides that accidentally shadow their model mix.
- M1 can focus on runtime/provider work rather than package scaffolding.

## Touchpoints

- TypeScript/Vite config
- Package/workspace config
- `src/sdk/index.ts`
