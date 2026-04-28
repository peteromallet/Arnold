from __future__ import annotations

import asyncio

from scripts.runpod_runner import REMOTE_ROOT, run_pod

EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "vendor/direct_templates", "out/runs", "output"}

REMOTE_SCRIPT = f"""
set -e
cd {REMOTE_ROOT}
python3 -m pip install -e '.[dev]'
python3 -m pip install 'comfyui@git+https://github.com/peteromallet/ComfyUI.git@fix/latentupscale-model-mmap-residency' 'comfy-script[default]'
python3 -m pytest -q tests
python3 -m vibecomfy.cli sources sync --official vendor/direct_templates --external examples
python3 -m vibecomfy.cli workflows list --limit 10
python3 -m vibecomfy.cli inspect image_flux2_klein_text_to_image
python3 -m vibecomfy.cli convert image_flux2_klein_text_to_image --out out/scratchpads/image_flux2_klein_text_to_image.py
python3 -m vibecomfy.cli validate out/scratchpads/image_flux2_klein_text_to_image.py
python3 -m vibecomfy.cli runtime doctor
python3 -m vibecomfy.cli runtime smoke --mode managed
python3 -m vibecomfy.cli run tests/smoke_fixtures/smoke_empty_image_red.json --runtime embedded --backend graphbuilder
python3 -m vibecomfy.cli run tests/smoke_fixtures/smoke_empty_image_green.json --runtime embedded --backend graphbuilder
python3 -m vibecomfy.cli run tests/smoke_fixtures/smoke_empty_image_blue.json --runtime embedded --backend graphbuilder
python3 -m vibecomfy.cli run tests/smoke_fixtures/smoke_empty_image_white.json --runtime embedded --backend graphbuilder
python3 -m vibecomfy.cli run tests/smoke_fixtures/smoke_empty_image_black.json --runtime embedded --backend graphbuilder
ls -lh output/vibecomfy_smoke_*_*.png
"""


async def main() -> int:
    return await run_pod(REMOTE_SCRIPT, name_prefix="vibecomfy", exclude=EXCLUDE_DIRS, timeout=900)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
