# ComfyScript Spike

Status: Historical spike. Current authoring guidance lives in
[`../authoring.md`](../authoring.md), and the current public import/export
surface is recorded in [`../api/m6-public-api.md`](../api/m6-public-api.md).

Decision: `learn` for milestone one.

ComfyScript is useful evidence and may become an adapter later, but it is not the core VibeComfy abstraction for the first milestone.

## Evidence

The transpiler requires a live Comfy server because it calls `/object_info`. Running it offline fails before useful output.

With a live HiddenSwitch Comfy server at `http://127.0.0.1:8190/`, the spike attempted five workflows:

- `image_flux2_klein_text_to_image`: failed on `MarkdownNote`, a UI-only node.
- `api_flux2`: succeeded and generated a 14-line Python script.
- `api_openai_image_1_inpaint`: failed on `MarkdownNote`.
- `03_video_wan2_2_14B_i2v_subgraphed`: failed on `MarkdownNote`.
- `wanvideo_2_2_5B_T2V_controlnet_example`: failed on missing `MiDaS-DepthMapPreprocessor` in the active runtime.

The success case is readable, but it emits ComfyScript-specific calls rather than VibeComfy's internal `VibeWorkflow` edit model.

## Implication

Use ComfyScript as a reference and possible import/export adapter after the core path works. Do not block official-template ingestion, scratchpad editing, or execution on ComfyScript transpilation.
