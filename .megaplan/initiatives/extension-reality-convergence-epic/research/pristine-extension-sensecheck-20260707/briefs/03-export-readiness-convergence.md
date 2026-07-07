# Codex Sense-Check: Export Readiness Convergence

Repo: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

Run read-only. Do not edit files.

## Task

Investigate the current threat and best next move for export readiness convergence.

The criticism to evaluate:

> Make render-planner blockers the only thing that decides export readiness, so the user-facing story stops being "supported here, mysterious blocker there."

## What To Inspect

Prioritize current code:

- `src/tools/video-editor/runtime/renderPlanner.ts`
- `src/tools/video-editor/runtime/renderPlanner.test.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- `src/tools/video-editor/runtime/exportGuard.ts`
- `src/tools/video-editor/runtime/exportGuard.test.ts`
- `src/tools/video-editor/lib/renderRouter.ts`
- `src/tools/video-editor/render/**`
- `src/tools/video-editor/compositions/**`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/outputFormatRegistry.ts`
- `src/tools/video-editor/runtime/processCommandRegistration.ts`
- `src/tools/video-editor/shaders/**`
- docs under `docs/extensions/**`, `docs/video-editor/shader-execution-model.md`, `docs/video-editor/provider-compatibility-matrix.md`
- examples/canaries related to output formats, shaders, live data, effects, transitions, clip types

## Questions

1. What currently decides export readiness?
2. Are render planner blockers already authoritative anywhere?
3. What legacy/export guard paths can produce user-visible blockers outside planner vocabulary?
4. Is it feasible to make render-planner blockers the sole export readiness gate now, or should this be a staged convergence?
5. What would a pristine export-readiness model look like?

## Output

Markdown under 1800 words:

# Export Readiness Convergence
## Verdict
Say whether the criticism is valid and how severe the threat is.
## Current Code Reality
Concrete files and facts.
## Pristine End State
What export readiness should become.
## Recommended Work
Ranked actions, with "now" vs "later".
## Tests / Gates
Specific tests/scripts/docs checks needed.
## Biggest Trap
The tempting but wrong thing to do.

