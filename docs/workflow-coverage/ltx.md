# LTX Workflow Coverage

VibeComfy treats LTX as a family of concrete workflow capabilities, not as one generic video template. The current corpus is based on three source streams:

- Official Lightricks ComfyUI-LTXVideo workflows under `example_workflows/2.3`.
- Discord `ltx_chatter` signals: image anchors, I2V, long videos, IC-LoRA, relight/HDR, custom audio, lip-sync, DWPose/motion transfer, and low-RAM upscaling were repeated themes in the sampled messages.
- Community workflow packs from `RuneXX/LTX-2.3-Workflows` and `IAMCCS/comfyui-iamccs-workflows`, used as coverage for workflows that need extra node packs or external services.

## Ready Templates

Ready templates are Python templates under `ready_templates/video/`. They are distinct from raw JSON:

```text
raw Comfy JSON -> normalize_to_api -> VibeWorkflow -> generated ready Python template
```

Runtime-gated official templates:

- `video/ltx2_3_t2v`: official single-stage text-to-video smoke.
- `video/ltx2_3_i2v`: official single-stage image-to-video smoke.
- `video/ltx2_3_lightricks_two_stage`: official two-stage workflow with latent spatial upscaling.
- `video/ltx2_3_lightricks_iclora_hdr`: official HDR IC-LoRA video-guide workflow.
- `video/ltx2_3_lightricks_iclora_motion_track`: official motion-track IC-LoRA image-anchor workflow.
- `video/ltx2_3_lightricks_iclora_union_control`: official union-control guide workflow with depth/pose preprocessing.
- `video/ltx2_3_lightricks_first_last_parity`: app-facing no-control LTX first/last parity template with named inputs and `LTXFirstLastTwoStageContract` local validation.
- `video/ltx2_3_first_last_frame_travel_iclora_control`: manual first/last-frame travel workflow with full-length raw/pose/depth/canny IC-LoRA guide branches.

Supplemental ready templates:

- `video/ltx2_3_runexx_first_last_frame`: supplemental Runexx first/last-frame image-anchor source; no-control app routes moved to `video/ltx2_3_lightricks_first_last_parity`.
- `video/ltx2_3_runexx_first_middle_last_frame`: first/middle/last-frame anchors.
- `video/ltx2_3_runexx_custom_audio`: custom-audio conditioning.
- `video/ltx2_3_runexx_video_to_video_extend`: video-to-video extension.
- `video/ltx2_3_runexx_lipsync_custom_audio`: custom-audio lip-sync / voice-to-video.
- `video/ltx2_3_runexx_motion_transfer_dwpose`: DWPose motion transfer.
- `video/ltx2_3_runexx_talking_avatar_qwen_tts`: Qwen TTS talking avatar.
- `video/ltx2_3_runexx_music_video_low_ram`: low-RAM multi-scene music video.
- `video/ltx2_3_iamccs_audio_image_to_video`: audio plus image-to-video.
- `video/ltx2_3_iamccs_long_i2v`: long low-VRAM image-to-video.
- `video/ltx2_3_iamccs_audio_extend_low_ram`: three-segment audio extension.

## Runtime Policy

The RunPod smoke path patches LTX workflows to a tiny but real generation shape:

- Use `ltx-2.3-22b-dev-fp8.safetensors` and `gemma_3_12B_it_fp4_mixed.safetensors`.
- Use the 1.1 Lightricks assets where applicable: `ltx-2.3-22b-distilled-lora-384-1.1.safetensors` and `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`.
- Use CFG `2.5` for smoke patches unless a workflow explicitly overrides it.
- Use official Lightricks custom nodes pinned by the corpus runner.
- Use low-VRAM checkpoint/audio loaders when available.
- Reduce smoke dimensions and frame counts.
- Remove audio edges from video save nodes unless the workflow under test is explicitly an audio runtime gate.
- Materialize small guide assets under `input/` for workflows that expect an image or guide video.
- Rewrite stale Video-Depth-Anything node class names to the current Kijai `DepthAnything_V2` classes during materialization and RunPod preparation.

This keeps smoke runs cheap enough to repeat while still requiring actual ComfyUI execution and actual media output.

For the no-control app route, local `vibecomfy-workflow-contract-ltx-parity`
batches 1-7 recorded the route move, lens/contract tests, template-index check,
worker route/adapter/live-matrix tests, and explicit deferral of fresh RunPod
validation to the orchestrator after local gates. Previous RunPod evidence for
`video/ltx2_3_runexx_first_last_frame` is not evidence for
`video/ltx2_3_lightricks_first_last_parity`.

## Source Notes

Kijai is currently used as a model/custom-node ecosystem source rather than an LTX workflow source: `Kijai/LTX2.3_comfy` exposes model assets, while `ComfyUI-KJNodes` supplies useful runtime nodes. The workflow corpus itself comes from Lightricks, RuneXX, IAMCCS, and official Comfy template sources.

### May 2026 Hivemind Signals

Recent Banodoco Discord/Hivemind searches reinforced two operational rules for
LTX 2.3 first/last and first/middle/last guide workflows:

- Use RuneXX first/last and FML workflows as practical community references
  when auditing guide topology. A directly relevant reference is RuneXX's
  `First-Last-Frame/LTX-2.3_-_FML2V_First_Middle_Last_Frame_guider.json`; a
  benchmark derivative is
  `https://github.com/fblissjr/ComfyUI-AudioLoopHelper/blob/main/example_workflows/benchmark_workflows/fml2v_var_d_audio_input.json`.
- On RTX 4090/Ada, guide-strength workflows are sensitive to masked-attention
  behavior. Kijai identified an LTX 2.3 guide attention-mask memory regression,
  and fredbliss validated `SageAttention-ada` v0.5.5 on a real 4090 RuneXX FML
  workflow with masked calls routed through the Ada fp8 CUDA path and zero
  fallbacks. For speed-parity validation, the `sage` RunPod profile should use
  CUDA 12.8/PyTorch cu128 plus `https://github.com/fblissjr/SageAttention-ada`
  rather than a generic forced SageAttention flag.
