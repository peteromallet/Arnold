# Codex Sense-Check: Composition Spine Authority

Repo: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

Run read-only. Do not edit files.

## Task

Investigate the current threat and best next move for landing the composition spine and retiring legacy authority paths.

The criticism to evaluate:

> The composition spine's beauty payoff only arrives if old authority paths are deleted, not wrapped. Prove the planner no longer reads legacy-only facts.

## What To Inspect

Prioritize current code and the staged epic:

- `.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md`
- `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md`
- `.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml`
- `src/sdk/index.ts`
- `src/sdk/video/**` if present
- `src/tools/video-editor/runtime/**`
- `src/tools/video-editor/runtime/renderPlanner.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- `src/tools/video-editor/lib/renderRouter.ts`
- `src/tools/video-editor/lib/**`
- `src/tools/video-editor/commands/**`
- `src/tools/video-editor/hooks/useTimelineCommands.ts`
- `src/tools/video-editor/compositions/**`
- docs under `docs/extensions/**` and `docs/video-editor/**` that discuss composition, render planner, target paths, shaders, live data, materials, output formats

## Questions

1. What graph/composition-spine concepts exist in current code, and what is only planned?
2. Which fact families are still legacy-authoritative?
3. Where does planner/export/preview behavior still read legacy-only facts?
4. Is "delete old authority paths" feasible now, or should the next step be a fact-family-by-fact-family authority ratchet?
5. What would a pristine migration plan look like without breaking existing timelines?

## Output

Markdown under 2000 words:

# Composition Spine Authority
## Verdict
Say whether the criticism is valid and how severe the threat is.
## Current Code Reality
Concrete files and facts.
## Pristine End State
What authority convergence should mean.
## Recommended Work
Ranked actions, with "now" vs "later".
## Tests / Gates
Specific tests proving planner/export no longer read legacy-only facts.
## Biggest Trap
The tempting but wrong thing to do.

