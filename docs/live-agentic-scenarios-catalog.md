# Live Agentic Scenarios — Catalog (100 total)

Generated categorization of the live-agentic test suite: **23 existing** scenarios in
`tests/live_agentic_harness/scenarios/` (auto-run by the harness) plus **77 new** scenarios
staged in this directory (NOT auto-run).

## How discovery & activation work

- The runner (`tests/live_agentic_harness/runner.py:18`) globs **every** `*.json` in
  `tests/live_agentic_harness/scenarios/`. No manifest, no registration — `id` defaults to
  the filename stem. **Anything dropped in that folder runs on the next suite.**
- The 77 new scenarios live in this **sibling directory, outside the repo**, so they do
  **not** auto-run and (importantly) so the running `live_agentic_watchdog`'s git-tree
  safety gate cannot sweep them — it treats new files under `tests/` as off-limits and
  reverts/cleans them.
- **To activate any subset:** copy its `.json` into
  `tests/live_agentic_harness/scenarios/`. Each `workflow_path` is repo-relative and
  resolves when the harness runs from the repo root.

## Dimensions

- **Modality:** image · video · 3d · audio · multi (multi-image / multi-video / mixed)
- **Query type:** `edit` (targeted change/tweak) · `big_adjustment` (structural: swap backbone,
  add/split a stage, reroute) · `research` (investigate options, no change) · `diagnose`
  (find the root cause, don't edit) · `explain` (understand the graph, no change)
- **Abstraction:** `low` (specific node/param/value) · `med` (named technique/component) ·
  `high` (vague goal/symptom — agent must interpret & decide)
- **Complexity:** `low` (1–2) · `med` (3) · `high` (4–5), from the manifest's own rating

## Distribution summary (all 100)

| Dimension | Values |
|---|---|
| Modality | {'3d': 9, 'audio': 10, 'image': 29, 'multi': 24, 'video': 28} |
| Query type | {'edit': 44, 'big_adjustment': 19, 'explain': 12, 'research': 13, 'diagnose': 12} |
| Abstraction | {'high': 42, 'low': 27, 'med': 31} |
| Complexity | {'high': 41, 'med': 28, 'n/a': 3, 'low': 28} |

### Modality × Query-type matrix (all 100)

| modality | edit | big_adjustment | research | diagnose | explain | total |
|---|---|---|---|---|---|---|
| image | 14 | 6 | 8 | 0 | 1 | 29 |
| video | 11 | 0 | 1 | 8 | 8 | 28 |
| multi | 7 | 7 | 3 | 4 | 3 | 24 |
| audio | 6 | 3 | 1 | 0 | 0 | 10 |
| 3d | 6 | 3 | 0 | 0 | 0 | 9 |

### Complexity × Query-type matrix (all 100)

| complexity | edit | big_adjustment | research | diagnose | explain | total |
|---|---|---|---|---|---|---|
| low | 28 | 0 | 0 | 0 | 0 | 28 |
| med | 6 | 0 | 11 | 0 | 11 | 28 |
| high | 9 | 19 | 1 | 12 | 0 | 41 |
| n/a | 1 | 0 | 1 | 0 | 1 | 3 |

## A. Existing 23 (in-repo, auto-run)

Note the skew: **edit-heavy (symptom fixes), high-abstraction, zero diagnose, one research,
one explain** — the gaps the 77 new scenarios are designed to fill.

| # | id | modality | query type | abstraction | complexity | ref |
|---|---|---|---|---|---|---|
| 1 | `3d-converts-image-to-3d-model` | 3d | edit | high | high | …b3530ba884ac4625.json |
| 2 | `3d-generates-a-3d-mesh-from` | 3d | edit | high | med | …2bdbaf79a96182c4.json |
| 3 | `audio-transcribes-audio-appends-text-regenerates` | audio | edit | high | med | …9a7ef22a9d947e9f.json |
| 4 | `audio-tts-narration-using-indextts-2` | audio | edit | high | high | …0d470a47b5d7c601.json |
| 5 | `hotshot-16-frames-agent-edit` | image | edit | low | n/a | …hotshot_base_unsaved_workflow_4.json |
| 6 | `image-animatediff-video-from-images-with` | image | edit | high | high | …001cd1f527f7f288.json |
| 7 | `image-generates-a-2x2-seed-variation` | image | edit | low | high | …cdb8167d4eccd0a8.json |
| 8 | `image-image-editing-with-qwen-image` | image | edit | high | med | …465726d60a145b19.json |
| 9 | `image-sdxl-txt2img-cat-in-spacesuit` | image | edit | high | low | …38375c38c1d2e6de.json |
| 10 | `image-style-transfer-using-ip-adapter` | image | edit | high | low | …c226f6c5faae34de.json |
| 11 | `image-two-stage-qwen-image-generation` | image | big_adjustment | high | high | …8ac746c940b127b4.json |
| 12 | `live-graph-explanation-smoke` | image | explain | med | n/a | inline |
| 13 | `multi-crops-face-previews-it-sets` | multi | edit | high | low | …d7363d65465708f5.json |
| 14 | `multi-image-to-video-generation-with-2` | multi | big_adjustment | high | high | …8d606b5c56f1243a.json |
| 15 | `multi-image-to-video-generation-with` | multi | edit | low | high | …5f41ffe9e1194aed.json |
| 16 | `multi-image-to-video-with-llm` | multi | edit | high | high | …0099685f34b68456.json |
| 17 | `multi-video-based-character-replacement-using` | multi | edit | high | high | …8e5619299bafee56.json |
| 18 | `multi-wan-vace-video-retargeting-driven` | multi | big_adjustment | high | high | …498ca31ad99591da.json |
| 19 | `speed-distillation-research` | image | research | med | n/a | inline |
| 20 | `video-generates-a-video-from-a` | video | edit | low | low | …59502aed6ad75d87.json |
| 21 | `video-ltx-video-upscaling-and-enhancement` | video | edit | high | high | …0043c6cb3d3d011f.json |
| 22 | `video-video-frame-by-frame-style` | video | edit | high | low | …b6ae778fc2b1cd3d.json |
| 23 | `video-video-generation-from-resized-image` | video | edit | high | high | …6c1e9f2b110470fa.json |

## B. New 77 (staged here, not auto-run)

Each query is **DeepSeek-authored** (model: `deepseek-v4-pro` for 48, `deepseek-v4-flash`
for 29). For every workflow, DeepSeek brainstormed 5 candidate queries spanning simple →
ambitious complexity, then picked the single best one grounded in the workflow's real
metadata (nodes, techniques, flags) — never generic boilerplate. `desired` rubrics are
attached to `edit`/`big_adjustment` scenarios to ground the LLM intent judge on outcomes
(not exact nodes). Workflows are drawn from the `external_workflows` corpus (2,735 real
workflows; Hivemind-searchable via `vibecomfy/executor/research.py` for even more recent ones).

> Authoring split: **48 by DeepSeek-V4-Pro**, **29 by DeepSeek-V4-Flash** (Flash filled
> gaps where Pro's reasoning starved the output budget). `_tags.authored_by` records which.

### edit (26)

| id | mod | cx | abst | auth | task | query |
|---|---|---|---|---|---|---|
| `3d-3d-model-generation-and-rigging-from-image-352066` | 3d | low | low | flash | other | The generated model's rig has the knees bending backward. Correct the joint orientation so the legs bend forward naturally. |
| `3d-3d-model-generation-and-rigging-workflow-90a1d5` | 3d | med | med | flash | other | Increase the geometric detail level in the refinement step to capture more surface features like wrinkles and folds, without increasing the polygon count. |
| `3d-3d-model-load-edit-and-export-workflow-d66a66` | 3d | low | low | pro | other | Change the texture edit prompt to 'aged bronze statue with verdigris patina' and ensure the model exports as GLB with embedded textures. |
| `3d-3d-shape-generation-and-export-workflow-8800a9` | 3d | med | med | pro | other | Lower the shape refinement strength to 0.4 so the final mesh stays closer to the input coarse mesh. |
| `audio-acestep-audio-generation-with-ksampler-e8c20a` | audio | low | low | pro | text_to_image | Change the sampling steps to 30 and switch the scheduler to 'karras'. |
| `audio-acestep-audio-generation-workflow-2a31ec` | audio | low | low | flash | other | Load a different AceStep base model checkpoint: use 'acestep-sft-v2.safetensors' instead of the current one. |
| `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` | audio | low | low | flash | other | Change the output audio format from MP3 to WAV. |
| `audio-audio-processing-with-voice-tts-and-noise-remo-b80848` | audio | med | med | pro | other | The processed audio has a faint robotic buzz after TTS. Can you make it cleaner? |
| `image-animatediff-video-generation-with-vae-d20410` | image | low | low | pro | image_to_video | Reduce the number of frames from 16 to 8 for quicker test renders. |
| `image-auraflow-image-generation-with-qwen-clip-9a3109` | image | low | low | flash | text_to_image | Increase the number of inference steps from 20 to 30 to get more detailed images. |
| `image-background-removal-and-grid-composition-54a681` | image | low | low | pro | upscaling | The preview grid looks too small and blurry. Make each image in the 2x2 grid 512x512 pixels before compositing. |
| `image-image-to-image-with-controlnet-and-dwpreproces-49d057` | image | low | low | pro | controlnet | Change the ControlNet strength to 0.8 so the pose guidance is more subtle. |
| `image-image-to-image-with-stable-zero123-and-backgro-def5b5` | image | low | low | pro | image_to_image | Set the number of sampling steps to 30 to speed up generation without drastically affecting quality. |
| `image-inpainting-with-differential-diffusion-and-rea-1d414c` | image | low | low | pro | inpainting | The inpainted area isn't blending seamlessly; increase the mask blur to 16 and reduce the padding to 32 pixels. |
| `image-llama-cpp-instruct-image-preview-and-save-5b54bf` | image | low | low | flash | other | Adjust the LLaMA instruct parameters: set temperature to 0.8 and max tokens to 512. |
| `image-sd3-image-generation-with-controlnet-19d221` | image | low | low | pro | controlnet | Lower the ControlNet strength to 0.5 so the text prompt has more influence over the final image than the control image edges. |
| `multi-3d-preview-and-image-output-workflow-d93baf` | multi | low | low | pro | other | Switch the first preview to a top‑down view of the 3D model. |
| `multi-image-to-3d-object-generation-with-background-1a7f84` | multi | low | low | pro | image_to_video | Make the background removal actually produce a transparent background, so the 3D object is isolated on an alpha channel in the final output video. |
| `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` | multi | low | low | pro | animation | Can you make the static PNG output save the first frame of the generated video instead of a separate placeholder image? |
| `video-anime-video-to-video-with-controlnet-and-openp-cb5cd2` | video | low | low | pro | controlnet | The generated anime video doesn't follow the poses closely enough. Can you increase the ControlNet conditioning strength? |
| `video-image-to-video-conversion-with-moonvalley-d7853c` | video | low | low | flash | other | The video output is way too short; I need it to be at least 5 seconds long. Increase the frame count accordingly and adjust the frame rate to keep motion smo… |
| `video-svd-image-to-video-generation-fc240f` | video | low | low | pro | image_to_image | The generated video looks almost like a still image. Can you increase the motion_bucket_id to add more visible motion? |
| `video-video-combine-with-image-loading-5b31ce` | video | low | low | pro | image_to_video | I want the video to be 10 seconds long, with each of the two images shown for exactly 5 seconds. |
| `video-video-inpainting-with-spline-based-cut-and-dra-485ff2` | video | low | low | pro | inpainting | Lower the inpainting denoising strength to 0.6 to preserve more original image details around the dragged region |
| `video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20` | video | low | low | pro | animation | Lower the LoRA model strength to 0.5 to reduce the intensity of the stylization effect |
| `video-wan2-2-text-to-video-with-dual-unet-and-model-03fced` | video | low | low | pro | text_to_image | Change the number of sampling steps for both UNETs to 25 each. |

### big_adjustment (16)

| id | mod | cx | abst | auth | task | query |
|---|---|---|---|---|---|---|
| `3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2` | 3d | high | high | flash | inpainting | Instead of using the back-projection inpainting method, I want to use the SDXL inpainting model directly on the masked areas, but I also want the ControlNet … |
| `3d-3d-model-generation-and-preview-workflow-cc0df7` | 3d | high | high | pro | other | Swap the Rodin3D generation model from Rodin Large to Rodin Fusion and ensure all downstream nodes (detailing, smoothing, preview) remain connected and funct… |
| `3d-3d-model-generation-and-retargeting-workflow-f65774` | 3d | high | high | pro | other | Replace the Tripo texture node with a procedural PBR material generator and ensure the rigged model's materials are correctly applied in the final preview. |
| `audio-acestep-audio-generation-and-processing-workfl-1b1360` | audio | high | high | flash | text_to_image | Integrate a spectral-gating noise reduction pass before the audio separation step, then route the cleaned audio into both the vocal removal and the separatio… |
| `audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676` | audio | high | high | flash | compositing | Restructure the workflow to combine the separated vocals and background after separate decoding stages instead of before decoding, then save each as separate… |
| `audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf` | audio | high | high | flash | image_to_video | Replace the MelBand RoFormer audio sampler with AudioLDM2 for audio generation, integrating it with the LTX video generation pipeline and LoRA, so that audio… |
| `image-face-detection-and-cropping-workflow-949658` | image | high | high | flash | image_to_image | Replace the YOLOv8 face detection with a different face detection model like MTCNN or RetinaFace, and update the cropping logic accordingly. |
| `image-flux-image-inpainting-and-compositing-with-con-00444a` | image | high | high | flash | controlnet | Restructure the pipeline to first generate a base image with Flux, then use the inpainted region as a condition for ControlNet-driven style transfer to the e… |
| `image-image-comparison-and-enhancement-with-florence-007018` | image | high | high | flash | compositing | Restructure the blending logic so that instead of a single composite, the user can adjust the contribution of each filter (saturation, invert, high-pass, sha… |
| `image-kolors-image-generation-with-segs-detailer-and-d813fe` | image | high | med | flash | image_to_video | Replace the Ultralytics detector with GroundingDINO for mask generation, and adjust the pipeline so that SAM segmentation still receives valid SEGS input fro… |
| `image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5` | image | high | high | pro | animation | Convert this video generation pipeline from text-to-video to image-to-video: take a single input image as the first frame, encode it through the Wan2.2 pipel… |
| `multi-animatediff-video-face-swapping-with-deflicker-506ebd` | multi | high | high | pro | controlnet | Replace the AnimateDiff motion module with a more recent v3 variant and restructure the pipeline to include a ControlNet stage for pose-guided animation as a… |
| `multi-deforum-stable-diffusion-animation-with-ip-ada-78afac` | multi | high | high | pro | other | Replace the IP‑Adapter conditioning with a ControlNet depth estimator, keeping the same Deforum animation schedule. Use the ControlNet output to drive the co… |
| `multi-image-to-video-with-upscaling-and-color-matchi-359848` | multi | high | high | flash | animation | Replace the SVD img2vid conditioning with AnimateDiff motion module to enable longer, more controllable video generation while preserving the existing upscal… |
| `multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457` | multi | high | high | pro | image_to_video | Swap the Wan2.2 model for a Stable Video Diffusion (SVD) based animation model. Also, remove the SAM2 segmentation branch and replace it with a simple foregr… |
| `multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56` | multi | high | high | pro | inpainting | Restructure the video inpainting pipeline so that SAM2 segmentation is applied to each frame before Florence2 runs object detection, then use those segmentat… |

### research (12)

| id | mod | cx | abst | auth | task | query |
|---|---|---|---|---|---|---|
| `audio-acestep-audio-generation-with-detail-daemon-f0859f` | audio | med | med | pro | text_to_image | The DetailDaemon sampler is used for enhancing audio detail. How does it work compared to standard audio diffusion samplers, and what settings would you reco… |
| `image-animatediff-image-to-video-with-latent-composi-17dc9b` | image | med | med | flash | image_to_video | How does the latent compositing approach here compare to using an init image directly in the video latent space? Which gives better temporal coherence? |
| `image-dual-checkpoint-xl-image-generation-with-refin-c9df19` | image | med | med | pro | text_to_image | I'm running this dual-checkpoint XL pipeline with juggernautXL as the base and sd_xl_refiner as the refiner. Are there any newer, better refiner models I sho… |
| `image-gemini-prompt-splitter-and-text-display-workfl-caae97` | image | med | med | pro | other | This workflow uses Gemini to process and split prompts. I'd like to compare Gemini to Claude for generating complex, multi-part image prompts. What are the t… |
| `image-image-processing-with-sharpening-film-grain-an-9aa0f1` | image | med | med | pro | compositing | What alternative sharpening methods could replace the high pass filter in this workflow, and what are the tradeoffs in terms of edge halos vs. natural detail… |
| `image-image-to-image-with-ipadapter-and-controlnet-1999a9` | image | med | med | pro | controlnet | How can I balance the influence between the IPAdapter style reference and the Canny edge ControlNet strength to preserve more of the original image structure… |
| `image-llava-image-captioning-and-keyword-extraction-d38dc8` | image | med | med | pro | image_to_image | What alternative image captioning models could I replace LLaVA with to produce longer, more detailed prompts? Are there any that also extract keywords direct… |
| `image-qwen-image-inpainting-with-controlnet-09fc64` | image | med | med | pro | inpainting | For this Qwen Image inpainting workflow, I frequently get color mismatches between the inpainted area and the original image. Before editing anything, resear… |
| `multi-3d-gaussian-splatting-from-video-with-hunyuan-432652` | multi | med | med | pro | image_to_video | The 3D reconstruction has noticeable geometry flickering across frames, likely from inconsistent depth maps. Can you investigate this video-to-3D Gaussian Sp… |
| `multi-animatediff-video-generation-with-controlnet-a7e2af` | multi | med | med | flash | controlnet | My current workflow uses a standard UNet-based Stable Diffusion checkpoint with AnimateDiff. What would be the trade-offs if I switched to a DiT-based model … |
| `multi-svd-image-to-video-with-sdxl-conditioning-389d90` | multi | med | med | flash | animation | Can you explain how each stage of this workflow contributes to generating the final WEBP video, particularly the role of the CLIP text conditioning and how t… |
| `video-animatediff-video-with-controlnet-and-depth-89b02a` | video | high | high | pro | controlnet | What alternatives to Depth-Anything could I use as the depth estimator for better temporal consistency in my AnimateDiff video pipeline, and how would replac… |

### diagnose (12)

| id | mod | cx | abst | auth | task | query |
|---|---|---|---|---|---|---|
| `multi-ai-video-upscaling-with-detail-daemon-sampler-673197` | multi | high | high | flash | upscaling | I'm using the Detail Daemon Sampler with beta scheduling to upscale a low-res video. The output has strong color shifting compared to the input, and details … |
| `multi-flux2-image-and-video-generation-with-outpaint-435de2` | multi | high | high | pro | outpainting | The outpainted borders look noticeably brighter than the original image, even after color matching is applied. Why is the color matching node not aligning th… |
| `multi-svd-image-to-video-with-animation-builder-99e2a9` | multi | high | med | flash | animation | The generated video has severe flickering and jittery motion, with frames occasionally going black. What in the workflow could be causing this? |
| `multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6` | multi | high | high | pro | text_to_image | The generated video has a visible, frame‑varying flicker in the film grain overlay, giving it a disjointed look. Which part of the post‑processing stack is i… |
| `video-animatediff-video-with-ipadapter-and-controlne-4eebf3` | video | high | med | pro | controlnet | The output video has a persistent tiling grid pattern visible in uniform areas like sky or walls, as if the IPAdapter style is being applied in blocks rather… |
| `video-hunyuan-video-text-to-video-generation-265847` | video | high | med | pro | animation | The generated animated WEBP has severe flickering between frames, especially in high-motion areas, but the first frame looks fine. What in the workflow could… |
| `video-hunyuanvideo-image-to-video-generation-with-en-ff076a` | video | high | high | flash | outpainting | The generated video doesn't resemble my input image at all — the first frame is completely different, and the video looks like random noise. I suspect the im… |
| `video-ltx-video-with-audio-and-inpainting-b3ba8a` | video | high | high | flash | inpainting | The inpainted region looks sharp-edged and doesn't blend smoothly with the rest of the video, and the colors in that region are completely off (grayish). Wha… |
| `video-video-output-workflow-f855de` | video | high | high | pro | other | The final output video is unacceptably blurry and shows heavy banding in dark areas, even though no explicit blur or compression step is visible in the node … |
| `video-wan-video-generation-with-vace-and-multi-outpu-d1caec` | video | high | high | flash | image_to_video | The video output has severe temporal flickering and only the first image in my batch produces a coherent result — the rest are pure noise. What's causing this? |
| `video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9` | video | high | high | flash | text_to_image | The high-noise LoRA variant produces outputs that look identical to the low-noise variant — no difference in motion or texture. Also, the video appears to ha… |
| `video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9` | video | high | high | pro | animation | The animation looks great for the first 16 frames, but then the motion becomes erratic and the subject’s appearance shifts noticeably. What could be causing … |

### explain (11)

| id | mod | cx | abst | auth | task | query |
|---|---|---|---|---|---|---|
| `multi-animated-image-to-video-with-svd-and-lora-4ed6d9` | multi | med | med | flash | animation | Walk me through the entire pipeline of this workflow from loading the input image to generating the WEBP video. I want to understand why there are two KSampl… |
| `multi-audio-to-image-mel-band-roformer-workflow-b22937` | multi | med | med | pro | other | Can you explain step-by-step what this audio-to-image workflow does, how the MelBandRoFormer model fits in, and why it both saves an MP3 and outputs a previe… |
| `multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14` | multi | med | med | flash | text_to_image | Explain how the Wan2.2 Lightning model and LoRA adapters work together in this workflow. What is the purpose of having two LoRA strength settings? |
| `video-animatediff-video-to-video-with-controlnet-and-3c978e` | video | med | med | pro | controlnet | I'm trying to understand how this AnimateDiff video-to-video workflow keeps motion coherent across frames. Walk me through the pipeline end-to-end, focusing … |
| `video-image-to-video-with-svd-and-webp-output-1882aa` | video | med | med | pro | animation | Walk me through this workflow: how does it turn a static image into a moving video and save it as WebP? I'm especially curious how the Stable Video Diffusion… |
| `video-inpaint-and-video-composition-with-spline-path-0c2716` | video | med | med | pro | inpainting | What role does the spline editor play in this inpainting-and-compositing workflow? Explain how the path controls the inpainting mask over time and how the fi… |
| `video-seedvr2-video-upscaling-workflow-052e59` | video | med | med | flash | upscaling | Walk me through what each major stage does: how the video frames are loaded, what the VAE and DiT models contribute, and how the final upscaled video is asse… |
| `video-video-loading-and-saving-workflow-1c7ad8` | video | med | med | pro | other | This workflow loads a video and an image, applies boolean logic, and saves three separate video outputs. Explain what each boolean operation is doing and how… |
| `video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3` | video | med | med | flash | animation | Explain how this workflow uses the high and low noise variants of Wan2.2 differently. I'm confused about why there are two separate generation paths and how … |
| `video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a` | video | med | med | pro | text_to_image | Can you explain the dual-UNet staging in this Wan2.2 pipeline? Specifically, how do the high-noise and low-noise models divide the sampling work, and where d… |
| `video-wanvideo-text-to-video-generation-71f825` | video | med | med | pro | image_to_video | How does the WanVideo text-to-video pipeline turn a prompt into a video clip? Walk me through the flow from the T5 and CLIP encoders through sampling to the … |

---

## Activation & operations

- **Activate a subset:** `cp <files> tests/live_agentic_harness/scenarios/`
  (move them in to run; the runner picks them up automatically next suite).
- **Before scaling the live suite to ~100 all-run:** note the running watchdog reports
  ~25–30 min/round at 23 scenarios. 100 all-run would be ~2 h/round. Recommended path: keep
  a ~23-scenario **core** tag hammered each round and run the extended set on a slower
  cadence (the runner supports `--scenarios-dir` + `--tag`). The runner now executes scenarios
  concurrently with a per-scenario kill timeout, so a 100-scenario suite is feasible — but it is
  still multi-hour per full round, so a ~23 core tag per round + extended on a slower cadence is the
  recommended operating mode.
- **Reliability filter:** 2693/2735 workflows require custom nodes; only 42 are
  custom-node-free (all image). For trustworthy green scenarios, filter staged files by
  `_tags.requires_custom_nodes == false`.
- **Regenerate / retune:** `python3 _generator.py` (selection seed in the selector; query
  seed in the generator). Selection inputs live in `/tmp/agentic_selected.json`.

_Built from 23 existing + 77 staged = 100 scenarios._
