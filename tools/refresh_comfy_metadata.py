"""Capture local ComfyUI version/commit metadata for ready-template narration."""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "vibecomfy" / "comfy_metadata.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = capture_comfy_metadata()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.out}")
    return 0


def capture_comfy_metadata() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    module = _import_comfy()
    install_dir = _module_dir(module)
    commit = _git(["rev-parse", "HEAD"], cwd=install_dir) if install_dir else None
    version = getattr(module, "__version__", None) if module is not None else None
    if version is None and install_dir:
        version = _git(["describe", "--tags", "--always"], cwd=install_dir)
    return {
        "version": str(version) if version else "unknown",
        "commit": str(commit) if commit else "unknown",
        "captured_at": now,
        "tested_at": now,
        "status": "discovered" if module is not None or commit else "unavailable",
        "install_dir": str(install_dir) if install_dir else None,
    }


def _import_comfy() -> Any | None:
    vendor_roots = [
        REPO_ROOT / "vendor" / "ComfyUI",
        Path.home() / "Documents" / "reigh-workspace" / "vibecomfy" / "vendor" / "ComfyUI",
    ]
    for vendor_root in vendor_roots:
        if (vendor_root / "comfy").exists():
            sys.path.insert(0, str(vendor_root))
            try:
                return importlib.import_module("comfy")
            except Exception:
                pass
    for name in ("comfy", "ComfyUI.comfy"):
        try:
            return importlib.import_module(name)
        except Exception:
            continue
    session_path = _runtime_session_comfy_path()
    if session_path:
        sys.path.insert(0, str(session_path.parent))
        try:
            return importlib.import_module("comfy")
        except Exception:
            pass
    user_init = Path.home() / ".comfy" / "__init__.py"
    if user_init.exists():
        return type("ComfyMetadata", (), {"__file__": str(user_init), "__version__": None})()
    return None


def _runtime_session_comfy_path() -> Path | None:
    try:
        from vibecomfy.runtime import session
    except Exception:
        return None
    for attr in ("COMFY_ROOT", "DEFAULT_COMFY_ROOT"):
        value = getattr(session, attr, None)
        if value:
            path = Path(value)
            if (path / "comfy").exists():
                return path / "comfy"
    return None


def _module_dir(module: Any | None) -> Path | None:
    file_value = getattr(module, "__file__", None) if module is not None else None
    if not file_value:
        return None
    path = Path(file_value).resolve()
    for candidate in (path.parent, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return path.parent


def _git(args: list[str], *, cwd: Path | None) -> str | None:
    if cwd is None:
        return None
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    except OSError:
        return None
    return proc.stdout.strip() or None


if __name__ == "__main__":
    raise SystemExit(main())
