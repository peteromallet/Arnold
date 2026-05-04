Video editor developer platform Sprint 6: asset and render pipeline hooks.

Depends on Sprints 1-5:
Use canonical domain, ports, clip descriptors, command bus, and capability manifest.

Goal:
Unlock developer control over how assets resolve/process and how timelines preview/export/render.

Primary outcomes:
- Formalize AssetResolver lifecycle hooks: onUpload, onTranscode, onResolve, onMissing, onProfileLoad.
- Formalize render provider/export target registry: browser Remotion, worker/Banodoco, external provider, preview-only fallback.
- Finish currently incomplete worker render routing from editor UI where applicable.
- Let clip descriptors declare render capabilities and fallback preview behavior.
- Add render pipeline events/middleware: beforeRender, afterRender, renderFailed, assetMaterialized.

Important constraints:
- Existing render flow remains working.
- Do not move to a new render backend by default.
- Cloud/worker-only clips must show clear preview limitations without blocking valid exports.

Success criteria:
- Swapping in a fake/local AssetResolver can preview/render fixture timelines without Supabase for supported assets.
- Render routing is capability-based rather than scattered hardcoded checks.
