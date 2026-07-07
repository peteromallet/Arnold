# M2: Composition Shader/Ref Authority Ratchet

## Outcome

Move shader/ref facts to CompositionGraph projection authority. Legacy timeline fields remain compatibility inputs, but planner/export readiness for shader/ref facts must consume graph-projected facts instead of direct legacy reads.

## Execution Posture

This is the first real authority migration. Keep the slice narrow and prove it hard. The goal is not to finish the entire composition spine; it is to establish the ratchet pattern with one important fact family.

## Scope

IN:
- Introduce or complete the minimal `CompositionGraph` contracts needed for shader/ref facts.
- Add a host projection path from current timeline/config/contribution inputs into graph facts.
- Represent shader assignment, postprocess shader assignment, contribution references, and reference resolution state as graph-owned facts.
- Move shader/ref planner and export blockers to graph-derived facts.
- Keep legacy fields such as `clip.app.shader` and `config.app.shaderPostprocess` as projector inputs only.
- Add tests proving legacy-only shader/ref facts do not count as authoritative when graph projection is disabled.
- Add static or targeted regression checks preventing new migrated shader/ref readiness code from reading raw legacy shader fields directly.

OUT:
- Full target-path schema.
- Live binding graph authority.
- Material status matrix beyond what shader/ref blockers need.
- Process runtime, sidecars, and full output-format route graphing.
- Deleting legacy storage fields.

## Constraints

- Preserve backward compatibility for existing timelines through projection.
- Do not wrap existing scanners in graph-shaped objects while leaving them authoritative.
- Do not make planner/export behavior depend on both graph facts and direct legacy reads for migrated facts.
- Keep diagnostic vocabulary canonical and structured enough for export readiness to consume.

## Done Criteria

- Planner/export shader/ref readiness fails if graph projection is absent for migrated facts.
- A fixture with raw legacy shader/ref fields but disabled projection proves those fields are no longer authority.
- Existing legacy timelines still work through the projector.
- New diagnostics identify missing, disabled, duplicate, inactive, invalid, or incompatible references through graph-derived state.
- Tests cover at least clip shader assignment, timeline postprocess shader assignment, contribution reference lookup, and package-state failures.

## Touchpoints

- `src/sdk/index.ts`
- `src/sdk/video/composition/**`
- `src/tools/video-editor/runtime/composition/**`
- `src/tools/video-editor/runtime/FamilyRuntimeAssembly.ts`
- `src/tools/video-editor/rendering/**`
- `src/tools/video-editor/lib/renderRouter.ts`
- `tests/**/video-editor/**`
- `docs/extensions/**`

