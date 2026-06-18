# M9: Clip-Type Dispatch And Basic Keyframes

## Outcome

Let extensions introduce new deterministic clip types and keyframed procedural parameters without pretending those clips can export through unsupported worker routes.

## Execution Posture

Clip types are timeline primitives, so be stricter than with decorative UI. They must insert through normal workflows, render deterministically where claimed, expose host-owned interpolation/keyframe behavior, and degrade into clear placeholders when missing.

## Scope

IN:
- Define `ClipTypeContribution`.
- Bridge extension clip renderers and inspectors into runtime renderer dispatch.
- Add insertion through the normal add/insert clip UI, with command palette as an optional secondary route.
- Add basic deterministic `Keyframe<T>` schema.
- Add interpolation utilities exposed through the SDK for primitive values and parameter schemas.
- Add a minimal host-owned keyframe inspector editor: add/remove at playhead, edit value/easing, display current interpolated value.
- Add automation recording semantics for live/control sources that later M11 sources can use to bake microphone/MIDI/serial/DMX/controller values into deterministic keyframes.
- Define a host-owned automation clip contract for dense parameter-over-time data produced by recording/bake workflows.
- Add render props for extension clip renderers including timeline frame/time, duration, selected state, interpolated params, and reserved live-data source IDs.
- Add examples for one contributed clip type and one keyframed procedural parameter.
- Add export guard integration for missing or unsupported clip-type IDs.

OUT:
- Dynamic transitions.
- Live data sample delivery.
- Shader/WebGL clip renderer.
- Worker/Banodoco execution of contributed clip code.
- Full graph/node editor.

## Locked Decisions

- Extension clip types must be discoverable by renderer dispatch, not only declared in a manifest.
- Extension clip types must be user-discoverable in the same add-clip workflow as built-in clip types; command palette alone is not sufficient frontend closure.
- Basic keyframes are deterministic timeline data and land before live data/bake semantics.
- High-frequency control data must be downsampled, summarized, or baked into deterministic keyframes/automation clips before export; raw runtime streams are not timeline history.
- Keyframes support interpolation mode metadata, including at least linear and stepped/hold semantics, so automation/control data can avoid incorrect smoothing.
- Keyframe values are JSON-serializable and validated against the owning parameter schema.
- Automation clips are host-owned clip types that reference target parameters by contribution ID and parameter path, declare interpolation per curve, and override target values during playback/export. Extension effects/clip types/shaders declare automation-targetable parameters through their schemas.
- Extension renderers must receive interpolated params from the host; they should not reimplement timeline interpolation.
- Unsupported contributed render features remain browser-preview/browser-export guarded until render capability planning proves more.

## Done Criteria

- Extension clip type can be inserted, inspected, persisted, rendered, and guarded on export.
- Keyframed params persist and are read by extension renderers as interpolated values.
- Tests cover missing IDs, defaults, renderer dispatch, keyframe interpolation, insertion/selection/editing paths, and export blockers.
- Tests prove contributed clip types appear in the primary add-clip UI and produce a selected editable clip after insertion.
- A procedural clip example proves the keyframe schema and inspector loop end to end.
- Tests cover an automation-recording canary that converts sampled control values into deterministic keyframes without storing every runtime sample.
- Tests cover stepped/hold interpolation for control-style automation.
- Tests cover an automation clip targeting an extension parameter and overriding that parameter through host interpolation during preview/export.

## Touchpoints

- Clip type registry/runtime
- Timeline renderer
- Clip insertion flows
- Inspector panels
- SDK clip/keyframe types
- Render router/export guard
