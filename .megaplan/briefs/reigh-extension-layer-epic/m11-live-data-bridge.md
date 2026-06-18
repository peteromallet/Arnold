# M11: Live Data Bridge, Ring Buffers, Bake

## Outcome

Make live/generative media possible without polluting timeline mutation history: live source lifecycle, ring buffers, frame reads, bake semantics, permission helpers, and a canary workflow such as webcam or live diffusion preview.

## Execution Posture

Live data is allowed to be ephemeral in preview, never ambiguous in export. Keep samples out of timeline history, make bake/remove decisions explicit, and turn runtime streams into deterministic artifacts before claiming portability.

## Scope

IN:
- Define `DataSourceContribution` lifecycle: activate, deactivate, dispose, status, error/reconnect.
- Define `LiveChannel` for generated frames/samples.
- Define source kinds for browser/live inputs and generated streams, including camera, microphone/audio analysis, MIDI/controller, serial/device, and generated-frame streams. Unsupported kinds produce diagnostics rather than bespoke APIs.
- Add a performance/recording posture for live sources: start/stop recording, recording status, source-to-parameter mapping, learn-style controller binding where feasible, quantization/downsampling, clock/timeline sync metadata, and diagnostics.
- Add ring-buffer sample delivery outside `TimelinePatch` and undo history.
- Add synchronous frame-read bridge compatible with current React/Remotion rendering.
- Use the live-data source IDs reserved in M9 renderer props; do not introduce a second addressing model for clip/effect reads.
- Define live-source binding semantics for clips/effects: source ID, channel/sample type, frame/time sampling mode, placeholder behavior before activation, and bake target.
- Add host permission helpers for browser-gated APIs like camera, serial, Bluetooth, MIDI where feasible.
- Define `bake()` or host `ctx.ops.bake...` semantics for converting ephemeral samples into deterministic assets, keyframes, clips, automation clips, or `RenderMaterial` refs.
- Define progressive generated-frame semantics: pending/refining/final sample states, replacement policy for improved frames, cancellation behavior, and how the timeline placeholder reflects generation progress.
- Define steering/reconfigure semantics for long-running generated streams: which inputs can change while running, how changes are diagnosed, and whether prior samples remain, are superseded, or fork a new generation.
- Activate `GenerationSession` sample delivery for live/generative work.
- Define partial/range bake semantics for frames, time ranges, sample indices, and accepted takes.
- Define live-source-to-uniform binding vocabulary for M13 shader uniforms and other param-driven preview consumers.
- Add export-blocked/bake-or-remove UX for live sources.
- Add webcam or live-diffusion canary proving permission -> stream -> preview -> bake -> deterministic asset or `RenderMaterial` -> exportable composition.
- Add live source UI surfaces for connection status, permission prompts, preview health, and bake actions.
- Add host-owned `GenerationSessionPanel`, steering surface, partial-bake range selector, recording pass surface, mapping table, learn-mode indicator, basic audio-analysis overlay, and take-review player.

OUT:
- Treating every sample as a timeline mutation.
- Worker/export support for unbaked live streams.
- Production sidecar execution.
- Full external frame-source render lifecycle.

## Locked Decisions

- Live data stays outside mutation/history systems.
- Live/generating clips are preview-only until baked.
- Baking converts ephemeral runtime data into deterministic timeline data, asset registry entries, or `RenderMaterial` refs.
- Export guard must detect active live sources and offer bake/remove actions.
- `DataSourceStatus` is a sealed state machine: idle, requesting-permission, active, paused, reconnecting, error, disposed.
- Frame reads are synchronous and non-blocking; async reads are forbidden from render paths.
- Bake destination is explicit per source: video/image/audio asset, keyframes, automation clip, standard clip, metadata sidecar, or `RenderMaterial` ref. Bake failures publish diagnostics and leave live source unchanged.
- Multiple sources compose by source ID; clips/effects declare which live source IDs they read.
- Source IDs are stable, provider-scoped runtime IDs, and baked outputs must replace live references with deterministic asset/keyframe/clip/material references.
- Bake targets are explicit by source kind: generated/camera frames can bake to video/image assets, clips, or frame/video `RenderMaterial` refs; audio/controller/device streams can bake to keyframes/automation clips, audio-analysis materials, or metadata sidecars.
- Basic audio analysis sources expose raw sample buffers, RMS/amplitude, FFT bins, and simple onset-style events where feasible. Advanced beat tracking/pitch/model analysis stays extension/process-owned.
- `LiveChannel` steering uses a host-visible supersede-or-fork posture. Samples carry generation index, steer-params hash, parent refs where applicable, producer version, and extension-owned tags for prompt/model/seed provenance.
- Partial bake accepts frame/time/sample ranges or take IDs and leaves the source active outside the baked range. Mixed live/materialized regions remain previewable and export-blocked until resolved by the planner.
- A recording pass is a host-owned grouping of armed sources, parameter mappings, transport start/stop, and takes. Takes can be reviewed, discarded, or accepted before baking.
- Learn mode is a host API for source-to-parameter mapping: the next source sample becomes a candidate mapping with timeout, visual feedback, and cancellation. The host owns mapping table schema; extensions own source-specific interpretation.
- The steering surface renders steerable parameters through `SchemaForm`, shows whether a change will supersede or fork, displays hot/non-hot parameter diagnostics, and links attempts/forks through session metadata. Batch/attempt galleries are allowed as generic session views, not diffusion-specific surfaces.

## Done Criteria

- Live data example updates preview from a ring buffer.
- Timeline mutation/history does not grow per sample.
- Bake creates deterministic data: video/image/audio asset, keyframes, automation clips, standard clips, sidecars, or `RenderMaterial` refs.
- Export is blocked before bake and follows normal route after bake when output is a standard asset or resolved `RenderMaterial`.
- Lifecycle cleanup works on unmount, provider change, HMR, and permission failure.
- Frontend shows permission, active/error, export-blocked, and bake-ready states for the canary source.
- Tests prove clips/effects reading reserved live-source IDs show diagnostics before source activation and deterministic references after bake.
- Tests cover progressive generated-frame replacement, cancellation, timeline placeholder state, and bake into deterministic assets or `RenderMaterial` refs.
- Tests cover microphone/MIDI/device-style sample streams baking into deterministic keyframes or automation clips without per-sample timeline mutations.
- Tests cover steering/reconfigure diagnostics and live-source-to-uniform binding metadata.
- Tests cover `GenerationSession` live sample delivery, supersede/fork metadata, partial bake mixed-state diagnostics, recording pass take acceptance, and learn-mode mapping timeout/cancel.
- Tests cover session panel rendering across agent/live/process origins, steering fork/supersede UI, partial-bake range selection, recording strip, mapping table validation, learn-mode indicator, audio-analysis overlay empty/error states, and take-review accept/discard.

## Touchpoints

- Clip type/render path
- Playback loop
- Asset ingestion
- Export guard/router
- Extension services and permissions helpers
