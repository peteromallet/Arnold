from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from vibecomfy.comfy_command import comfyui_command, has_comfyui_runtime


def runtime_fingerprint(server_url: str | None = None) -> str:
    if server_url:
        source = f"server:{server_url.rstrip('/')}"
    elif has_comfyui_runtime():
        command = comfyui_command()
        source = "embedded:" + " ".join(command)
        if len(command) == 1:
            path = Path(command[0])
            try:
                stat = path.stat()
                source = f"embedded:{path}:{stat.st_mtime_ns}:{stat.st_size}"
            except OSError:
                source = f"embedded:{path}"
    else:
        source = f"embedded:missing:{sys.executable}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def object_info_cache_path(
    *,
    server_url: str | None = None,
    cache_dir: str | Path = "out/cache",
) -> Path:
    return Path(cache_dir) / f"object_info.{runtime_fingerprint(server_url)}.json"


def load_object_info_cache(path: str | Path) -> dict[str, Any] | None:
    cache_path = Path(path)
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_object_info_cache(path: str | Path, data: dict[str, Any]) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
