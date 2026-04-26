# Runtime Profile

Local profile from `comfyui env check` on 2026-04-25:

- Python: `3.11.11`
- ComfyUI: `0.18.2`
- Torch: `2.11.0`
- Platform: `macOS-15.4-arm64-arm-64bit`
- Device: `mps`
- RAM: 16 GB
- NVIDIA GPU: no
- AMD GPU: no
- Local model directories: mostly missing
- Custom-node directory: present
- Official workflow template packages: `comfyui-workflow-templates==0.9.62`

RunPod profile target:

- Storage volume: `Peter`, configured through `VIBECOMFY_RUNPOD_STORAGE`
- GPU: `NVIDIA GeForce RTX 4090`, configured through `VIBECOMFY_RUNPOD_GPU`
- Validation script: `scripts/runpod_validate.py`
- Launcher repository: sibling `runpod-lifecycle`

The RunPod validation script launches a pod, waits for SSH, checks `nvidia-smi`, uploads VibeComfy, installs dependencies, runs tests, runs runtime smoke, executes five cheap end-to-end workflows, and terminates the launched pod in `finally`.
