# M8: Dynamic Transition Contributions

## Outcome

Open transition authoring as a real extension surface: registered transitions appear in the existing transition UI, persist safely, render in preview/browser export where supported, and fail loudly when missing.

## Execution Posture

Transitions should feel like native timeline language. Preserve repairability and defaults, avoid silent fallback, and keep contributed transitions in the same picker, lifecycle, params, and renderability grammar as built-ins.

## Scope

IN:
- Define and implement `TransitionContribution`.
- Add provider-scoped `DynamicTransitionRegistry`.
- Replace closed transition map lookup with provider-scoped registry lookup.
- Add transition params/schema support.
- Add repair/defaulting for legacy clips and clips with missing transition params.
- Add transition picker integration in existing clip and bulk-edit panels.
- Add provenance/renderability badges for contributed transitions.
- Add one local extension transition example.
- Add export guard integration for missing or unsupported transition IDs.
- Add remove/reset/default controls for contributed transitions wherever built-in transitions can be cleared.

OUT:
- Clip-type renderer dispatch.
- Keyframe editor.
- Shader/WebGL transition model.
- Worker/Banodoco execution of contributed transition code.
- Full alternate timeline renderer.

## Locked Decisions

- Transitions start as pure progress-to-style or progress-to-render-prop functions.
- Contributed transitions use the same provider-scoped lifecycle and renderability metadata established in M5.
- Transition picker entries are inline with built-ins and visibly labeled by provenance.
- Missing contribution IDs produce visible timeline/inspector placeholders and export blockers, never silent fallback.
- Worker export remains blocked unless render capability metadata proves a supported route.
- Removing or disabling a contributed transition must leave clips in a valid explicit no-transition/default-transition state.

## Done Criteria

- Extension transition can be selected, configured, persisted, rendered, and repaired.
- Bulk transition editing works with contributed transitions.
- Missing transition IDs produce diagnostics and export blockers.
- Tests cover registry lifecycle, picker integration, params defaults, repair, bulk edit behavior, renderability, and export blockers.
- Tests cover remove/reset/default flows for contributed transitions from both clip panels and bulk edit panels.

## Touchpoints

- Transition utilities
- `VisualClip`
- Clip panels and bulk panels
- Provider-scoped registry/runtime
- Repair/validation code
- Render router/export guard
