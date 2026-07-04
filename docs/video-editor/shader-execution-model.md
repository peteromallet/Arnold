# Shader Execution Model RFC

Status: M13 V1 implementation note.

This RFC documents the shader/WebGL bridge that M13 adds to the video editor.
The model is intentionally browser-preview first. It gives extension authors a
dedicated shader contribution path, deterministic diagnostics, host-owned
uniform controls, and explicit export blockers. It does not introduce a render
graph or imply that previewed WebGL output can be exported.

## Contribution Ownership

Shaders are registered as dedicated `kind: 'shader'` contributions. They do not
route through component effect registration and they are not component effects
with a fragment-shader prop. A shader contribution declares:

- `shaderId`, label, pass, source, uniforms, textures, fallback, and optional
  materializer metadata.
- `source.kind: 'inline'` with fragment source and optional vertex source, or
  `source.kind: 'module'` for a future host-resolved module source.
- `ctx.shaders.registerShader(shaderId, source, options)` during activation.

The host owns the provider-scoped shader registry, diagnostics, picker entries,
timeline metadata, WebGL preview canvas lifecycle, and export-planner posture.
Extension code owns shader source and contribution metadata, but it does not own
the editor's WebGL context or persisted timeline metadata shape.

## Pass Ownership

The public SDK pass vocabulary is `clip`, `overlay`, and `postprocess`.

M13 V1 implements browser preview surfaces for:

- Clip-local shaders assigned to one clip through `clip.app.shader`.
- Timeline postprocess shaders assigned through `config.app.shaderPostprocess`.

Overlay remains part of the SDK vocabulary, but M13 does not ship an overlay
composition surface, overlay picker path, or overlay export materialization
path. Overlay contributions can still be represented as shader records and
diagnostics; they should not be treated as runnable V1 preview/export passes
until a later milestone assigns ownership for placement, ordering, and
composition.

## Frame Sources

The WebGL preview surface receives the current host frame and time from the
browser preview path:

- Clip-local shaders receive clip-local seconds and frame index from the visual
  clip preview.
- Postprocess shaders receive timeline seconds and frame index from the timeline
  renderer preview.
- Built-in uploads include resolution, frame, and time values for shader code
  that declares matching uniforms.

Frame inputs are preview-time host values. They are not stable export artifacts
and are not materialized unless a later materializer process writes
`RenderMaterial`.

## Texture Lifecycle

Textures are host-bound preview inputs. The supported V1 source kinds are:

- `clip-frame`
- `static-image-asset`
- `live-generated-frame`

Texture definitions map a logical texture name to a sampler uniform. A
`textureRef` uniform can provide the selected source kind and optional `ref`.
During preview, the WebGL surface resolves host-provided texture sources,
creates WebGL textures, uploads them before drawing, and releases preview-owned
WebGL resources on disposal or context loss.

Unsupported texture categories include external URLs, arbitrary DOM media not
provided through a supported host source, cubemaps, 3D textures, depth/stencil
textures, previous-frame feedback buffers, multipass FBO chains, render-graph
intermediate textures, audio/FFT textures, and worker-owned GPU resources. These
must produce diagnostics or be deferred behind a later explicit host contract;
they must not be silently approximated.

Required supported textures that are missing at preview time produce
`shader/texture-unavailable`. Unsupported source kinds produce
`shader/texture-unsupported`.

## Uniform Subset

M13 V1 supports host-rendered controls for these shader uniform types:

- `float`, `int`, `bool`
- `vec2`, `vec3`, `vec4`, `color`
- `enum`
- `frame`, `time`
- `textureRef`

Editable scalar, vector, color, enum, frame, and time values are persisted under
timeline shader metadata. `textureRef` values are host bindings, not raw form
inputs. The generic `SchemaForm` renders a diagnostic placeholder for
`textureRef`; the shader inspector persists texture defaults/bindings under the
shader metadata texture map and leaves full texture editing deferred.

**Shader-uniform keyframes (M4):** Uniform values can be animated over time
through graph-owned shader-uniform keyframes. Keyframe target paths use the
canonical `uniforms.<name>` format (e.g. `uniforms.intensity`,
`uniforms.tint`, `uniforms.center`). Keyframes are stored in the shader
summary under the host-owned keyframe map, interpolated at render time using
the same interpolation engine as clip automation parameters, and projected
as `animates` edges with `targetKind: 'shader-uniform'` in the composition
graph. Non-canonical (bare) uniform names are normalized to the
`uniforms.<name>` prefix during keyframe add/update/remove operations.

Unsupported uniform schemas produce `shader/uniform-unsupported` during shader
schema validation.

## Preview Bypass And A/B Posture

The inspector owns preview bypass state through shader metadata:

- `enabled: false` means the shader is bypassed.
- `metadata.inspectorCompareMode` stores the inspector's shader/bypass A/B
  intent.
- `metadata.uniformPreset` tracks whether persisted uniforms are defaults or
  custom edits.

Split-view comparison is explicitly deferred in M13. The inspector can store
A/B intent and apply bypass, but it does not create a second synchronized preview
pipeline.

## V1 Composition Limits

M13 V1 enforces one shader per runnable scope:

- One clip-local shader per clip.
- One timeline postprocess shader.

Adding a second shader to the same scope is a domain and planner error, not a
silent replacement and not an ordered stack. The user-facing messages are:

- `Cannot add shader "<incoming>" to clip "<clipId>" because shader "<existing>" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.`
- `Cannot add postprocess shader "<incoming>" because postprocess shader "<existing>" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.`

Ordered shader stacks, multipass composition, temporal feedback, previous-frame
inputs, transition shaders, and render-graph scheduling are deferred.

## Export And Materialization

Browser preview is not export support.

Timeline shader metadata emits shader materializer requirements for export
routes. If no materializer has produced `RenderMaterial`, the planner and export
guard block export with this exact blocker text:

`Shader "<id>" cannot export because no shader materializer produced RenderMaterial for <scope>.`

The concrete `<scope>` text is produced by the host:

- Clip shader example: `clip "clip-1"`.
- Postprocess shader example: `timeline postprocess`.

A shader contribution may declare materializer metadata so the planner can
discover a process route. Discovery changes the planner posture to a
materialization next action/progress state, but it still does not mean export is
ready. Export becomes available only after a supported renderer route or
materializer produces the required `RenderMaterial`.

## Non-Render-Graph V1 Posture

The V1 bridge is a narrow preview execution path:

- One fullscreen WebGL program per assigned scope.
- Host-owned canvas/context creation, resize, draw, `readPixels`-friendly
  deterministic rendering, and disposal.
- Context-loss handling that pauses preview, preserves shader source/uniform
  state, recompiles on restore, and resumes rendering.

It is not a render graph. There is no pass scheduler, no graph edge model, no
ordered dependency chain, no multipass FBO ownership, and no implicit export
capture.

## Diagnostics

Shader diagnostics use the existing host diagnostic surfaces. Important codes
include:

- `shader/compile-error`
- `shader/link-error`
- `shader/uniform-unsupported`
- `shader/texture-unsupported`
- `shader/texture-unavailable`
- `shader/webgl-unavailable`
- `shader/webgl-context-lost`

Invalid shader records can stay registered with error status so the picker,
inspector, diagnostics panel, and planner can explain the problem without
crashing the preview.

## Canary Coverage

M13 includes two browser-preview-only canaries:

- A clip-local shader canary.
- A timeline postprocess shader canary.

Both canaries use the same SDK contribution kind, `ctx.shaders` registration,
uniform schema subset, diagnostics path, renderability metadata, preview
surface, picker/selection contracts, and planner blocker/materializer posture.
