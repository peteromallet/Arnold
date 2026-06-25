# North Star — Pristine SDK Boundary

## End state (M4)

`@reigh/editor-sdk` is a clean, externally compilable, package-evaluable boundary. It owns only portable contracts and generic family machinery; every video-specific family, timeline, rendering, asset, and export contract lives under `src/sdk/video/*`, while generic maturity/conformance/adapter contracts live under `src/sdk/core/*`.

The host (`src/tools/video-editor/*`) imports from the SDK but the SDK never imports host internals. `src/tools/video-editor/runtime/extensionSurface.ts` is a thin orchestrator over a host-side family adapter registry; families are honestly classified by the two-axis maturity registry in `src/sdk/video/families/familyDefinitions.ts`.

Authors consume a stable public barrel, can direct-import modality-owned modules, and the SDK validates in a temp external consumer with no repo aliases, no Vite context, and no host leakage. Docs, governance, and conformance gates are generated from the same canonical registry.

## Why this matters

This boundary is the foundation for safely adding new extension families and, eventually, new editor modalities. Get it wrong and every future family drags host internals back into the SDK. Get it right and the next modality starts from a clean core.
