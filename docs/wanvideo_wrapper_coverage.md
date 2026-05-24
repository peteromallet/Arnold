# WanVideoWrapper Coverage

Kijai's `ComfyUI-WanVideoWrapper` is treated as a separate Wan coverage source from the official Comfy templates. It exposes many workflows that are not covered by the official template library.

Representative ready templates currently curated from Kijai examples:

- `video/wanvideo_wrapper_21_14b_t2v`
- `video/wanvideo_wrapper_21_14b_i2v`
- `video/wanvideo_wrapper_21_14b_flf2v`
- `video/wanvideo_wrapper_22_5b_t2v_controlnet`
- `video/wanvideo_wrapper_22_5b_i2v`
- `video/wanvideo_wrapper_22_5b_i2v_controlnet`
- `video/wanvideo_wrapper_22_5b_ovi_audio_i2v`
- `video/wanvideo_wrapper_13b_control_lora`
- `video/wanvideo_wrapper_13b_vace`
- `video/wanvideo_wrapper_13b_recammaster`
- `video/wanvideo_wrapper_21_14b_fun_control`
- `video/wanvideo_wrapper_21_14b_fun_control_camera`
- `video/wanvideo_wrapper_21_14b_wanmove_i2v`
- `video/wanvideo_wrapper_21_14b_v2v_infinitetalk`
- `video/wanvideo_wrapper_wan_animate`
- `video/wanvideo_wrapper_22_s2v_context_window`
- `video/wanvideo_wrapper_22_s2v_framepack_pose`

These cover the main Kijai buckets: T2V, I2V, first/last-frame, ControlNet, control LoRA, VACE, ReCamMaster, Fun control, WanMove, InfiniteTalk, Ovi audio, S2V, and WanAnimate.

Current status:

- Raw JSON import: passing locally for the representative set.
- VibeWorkflow conversion: passing locally for the representative set.
- Ready Python template validation: passing locally for the representative set.
- RunPod runtime green so far: `wanvideo_wrapper_21_14b_t2v`, `wanvideo_wrapper_21_14b_i2v`, `wanvideo_wrapper_13b_control_lora`, and `wanvideo_wrapper_22_5b_i2v`.
- Remaining supplemental workflows still need the full node/model/input staging pass before they can be counted as runtime green.

Runtime harness policy:

- Do not pass generic `--prompt` or `--steps` overrides to WanVideoWrapper rows. The examples use custom Wan text-encoding and sampling nodes; generic override logic can fail before execution or mutate the wrong part of the graph.
- Keep a narrow `wan_wrapper_basic` RunPod scope for fast iteration: 21 14B T2V, 21 14B I2V, 22 5B I2V, and 1.3B control-LoRA.
- The `wan_wrapper_basic` scope installs only the basic runtime node pack: WanVideoWrapper, KJNodes, VideoHelperSuite, and Dynamic LoRA Scheduler. The broad supplemental node stack is reserved for full `wan_wrapper` runs.
- Treat broader Kijai workflows as supplemental ready templates until each has declared node packs, input media, and model staging.

Known systematic issues from the LTX/Wan work:

- Runtime model paths must match the custom node's expected folder exactly, not just Comfy's broad model categories.
- Guide media must be materialized for workflows that load videos/images by filename.
- Some custom nodes have runtime behavior that differs between the upstream server path and the HiddenSwitch pip fork.
- Runtime readiness is separate from conversion readiness. Ready templates can be valid Python/VibeWorkflow assets before the required model pack is fully staged.
- Avoid `comfyui run-workflow --all` for curated matrix runs. It triggers registry auto-install from workflow metadata and can fail on non-registry custom node names even when the node repos are already cloned.
- Pin or explicitly upgrade shared Python packages that custom nodes import transitively. The current Wan profile upgrades `pyparsing`, `matplotlib`, `onnx`, and headless OpenCV because system packages on the base image can shadow pip packages and break node discovery.
