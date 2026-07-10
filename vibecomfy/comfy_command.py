from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


def comfyui_command() -> tuple[str, ...]:
    try:
        has_comfy_module = importlib.util.find_spec("comfy.cmd.main") is not None
    except ModuleNotFoundError:
        has_comfy_module = False
    if has_comfy_module:
        return (sys.executable, "-m", "comfy.cmd.main")
    executable = shutil.which("comfyui")
    if executable and Path(executable).is_file():
        return (executable,)
    sibling = Path(sys.executable).with_name("comfyui")
    if sibling.is_file():
        return (str(sibling),)
    return ("comfyui",)


def has_comfyui_runtime() -> bool:
    command = comfyui_command()
    if len(command) >= 3 and command[1] == "-m":
        return True
    executable = Path(command[0])
    return executable.is_file() or shutil.which(command[0]) is not None
