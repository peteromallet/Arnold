# M7: Trusted Component Effect Contributions

## Outcome

Make local vibe-coded effects a first-class workflow: trusted React/Remotion component effects from local source code appear in the picker, support params, hot reload, preview, and honest export blocking.

## Execution Posture

Make the first creative power feature feel real, not theoretical. Component effects must be fast to author, easy to find, safe to remove, honest about export limits, and visibly connected to the shared registry/planner vocabulary.

## Scope

IN:
- Define/activate `EffectContribution.component`.
- Add direct `registerComponent()` path for trusted local React effect components.
- Bridge contributed component effects into catalog, picker, parameter controls, validation, and rendering.
- Treat extension effects as read-only bundled code unless copied to a resource/draft.
- Add a polished local effect example.
- Add clear browser-preview/browser-export/worker-export capability labels.
- Add frontend picker/inspector affordances for component-effect provenance, params, and export limitation badges.
- Add remove/unapply/reset controls for contributed effects anywhere built-in effects can be removed.
- Add a pre-render/export-readiness scan that reports applied contributed effects by capability before export starts.

OUT:
- Shader/WebGL effects.
- Render graphs/FBO chains.
- Worker/Banodoco execution of contributed code.
- Node editor.

## Locked Decisions

- Component effects are the first public effect contribution path.
- Trusted local components bypass Sucrase/`new Function`.
- Browser preview can support extension component effects before worker export does.
- Shader/WebGL belongs to the render/shader milestone, not this component bridge.
- Component effect picker entries show source/provenance and renderability badges.
- Applying a browser-preview-only effect immediately surfaces export limitations in the inspector/status/export guard, not only at final export.
- Effect parameter schema reuses existing parameter controls; schema validation failures publish diagnostics and disable apply.
- Component effects default to browser-preview-only until a contribution declares and tests a stronger `RenderCapability`.
- M7 may ship feature-specific export guards for unsupported component effects; M12 later centralizes those guards in the planner.
- Component effect descriptors merge registry metadata, schema metadata, renderability, provenance, and diagnostics before reaching picker/inspector UI.

## Why Not Shaders Here

Shader/WebGL effects are not just another component prop. They need a GPU/canvas lifecycle, uniform and texture binding, deterministic frame reads, alpha/color-space semantics, fallback when WebGL context creation fails, and a render/export route that can reproduce the result outside the interactive browser preview. A `fragmentShader` field without those contracts would be a misleading API.

## Done Criteria

- Example extension contributes a component effect visible in picker and applicable to clips.
- Effect renders in preview and responds to Fast Refresh.
- Params are editable through existing parameter-schema UI.
- Export guard blocks unsupported worker export with a clear reason.
- Applied contributed effects can be removed, reset to defaults, and survive undo/redo without stale registry references.
- Tests cover HMR replacement, provenance, picker integration, params, renderability, and legacy compatibility.
- Tests cover frontend picker visibility, inspector param editing, export warning visibility, and invalid schema diagnostics.
- Tests cover unapply/reset flows and pre-render export-readiness diagnostics for unsupported component effects.

## Touchpoints

- Provider-scoped effect registry
- `wrapWithClipEffects`
- `EffectLayerSequence`
- Effect picker/creator panels
- Render router/export guard
- SDK effect types
