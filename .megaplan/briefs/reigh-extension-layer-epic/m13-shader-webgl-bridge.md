# M13: Shader And WebGL Bridge

## Outcome

Ship the first honest shader/WebGL authoring track: browser preview first, inspector-driven uniforms, deterministic diagnostics, and explicit export limitations through the M12 capability planner.

## Execution Posture

Do not smuggle a render graph in through an effect picker. Prove the shader execution model with canaries, keep uniforms host-rendered, make GPU/context failures boring and diagnosable, and label export limitations without apology.

## Scope

IN:
- Add provider-scoped `ShaderEffectRegistry`.
- Define shader/WebGL contribution shape experimentally:
  - fragment/vertex shader source or module reference;
  - uniform schema and frame bindings;
  - texture/input bindings;
  - pass type: clip, overlay, or postprocess;
  - alpha/color-space expectations;
  - fallback behavior.
- Compile shader source at registration time and publish structured diagnostics.
- Add shader entries to the same picker/inspector flow as component effects with `Shader` and renderability badges.
- Map uniform schema to inspector controls where possible.
- Define the first supported uniform subset explicitly: float, int, bool, vec2, vec3, vec4, color, enum, texture input reference, and frame/time bindings.
- Add shader authoring affordance contracts: source editing via code panel or shader editor surface, compile diagnostics mapped to source ranges, uniform presets/defaults, and extension-owned library/gallery integration through host picker/status conventions.
- Add WebGL/canvas preview surface with frame-accurate lifecycle and context-loss recovery.
- Assign shader frontend surface ownership explicitly: code panel/shader editor for source, inspector section for clip-local shader preview/uniforms/materialize action, timeline overlay badge for postprocess shader scope, and export planner surface for materializer blockers.
- Add one browser-preview-only shader example with deterministic frontend preview.
- Add a shader execution model note/RFC in the milestone output covering pass ownership, frame source, texture binding, lifecycle, and why V1 is not a full render graph.
- Add two shader canaries: one clip-local shader and one timeline/postprocess shader. Both must use the same uniform/diagnostic/renderability contracts before the picker shape is considered stable.
- Add deterministic pixel tests for a simple shader path.
- Integrate shader capability reports into M12 planner/export UI.
- Define shader materialization posture: shader export requires either a supported renderer route or an explicit shader materializer that produces a `RenderMaterial`; otherwise export blocks honestly.
- Define whether V1 shader materialization is implemented through a browser capture materializer or honestly deferred behind a planner blocker. Do not leave materialization as an unnamed miracle between preview and export.

OUT:
- Promise of worker/Banodoco shader execution unless implementation proves it.
- Shader transitions.
- Full render graphs/FBO chains.
- Node editor.
- Production sidecar/headless GPU hosting.

## Locked Decisions

- Shader/WebGL is a dedicated track, not hidden in component effects.
- Browser preview can arrive before worker/cloud export, but export UI must say exactly what is blocked and why.
- Shader preview is not export support. A shader becomes exportable only through a proven renderer route or a materialized pass represented as `RenderMaterial`.
- Unsupported uniform/texture shapes produce diagnostics and disable apply.
- Invalid shaders are registered with error status and hidden/disabled in picker by default.
- Shader transitions remain out of scope until clip/overlay/postprocess passes are stable.
- Texture inputs are limited to host-provided clip/source textures in V1; arbitrary FBO graphs and multipass dependencies remain deferred.
- V1 texture input categories are explicit: clip frame, static image asset, live-source/generated frame where supported, and unsupported kind diagnostics. Self-referential buffers, cubemaps, and multipass feedback remain deferred.
- V1 shader composition limits are explicit: document one shader per clip/postprocess scope unless implementation proves ordered stacking. Multi-shader stacks, render graphs, feedback buffers, and temporal multipass effects remain deferred unless a narrow previous-frame texture is deliberately implemented and tested.
- Register `textureRef` and shader-specific uniform widgets through the M2 schema capability registry. Preview canvas includes host-owned bypass/A-B toggle where feasible; split-view may be deferred explicitly.
- Picker/inspector integration follows the execution model; if clip-local and postprocess canaries need different UI affordances, the milestone documents the split instead of forcing both through the component-effect picker abstraction.

## Done Criteria

- Shader example renders correctly in browser preview and exposes configurable uniforms in the inspector.
- Shader execution model note/RFC is checked in with the implementation and backed by clip-local and postprocess canaries.
- Invalid shader source produces structured diagnostics without crashing preview.
- Tests cover shader registration, compile diagnostics, picker selection, uniform editing, context-loss fallback, deterministic preview pixels, and blocked export reporting.
- Tests cover blocked export when no renderer route/materializer exists, plus a stub materializer capability finding where feasible.
- Tests cover documented V1 composition limits and the exact planner message when shader materialization is unavailable.
- Tests cover shader preview surface placement, textureRef widget diagnostics, materialize action placement/progress, postprocess timeline badge selection, and shader bypass/A-B preview affordance or explicit deferral.
- Tests cover every supported uniform type plus diagnostics for unsupported uniform and texture shapes.
- Tests cover shader source range diagnostics and uniform preset/default persistence.

## Touchpoints

- Effect picker and inspector panels
- Effect/clip render layers
- Diagnostic panel
- M12 render capability planner
- SDK shader types
