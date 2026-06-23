from __future__ import annotations

import importlib
import os

# Keep the lightweight submodules accessible without eagerly importing the
# heavy orchestration modules (edit, runtime, worker, etc.).  This lets CLI and
# audit consumers import ``session``/``contracts`` without pulling ComfyUI/torch.
from . import contracts
from . import session

# routes.py imports aiohttp/server at module level (guarded by VIBECOMFY_HEADLESS).
# In headless mode we skip the import so vibecomfy.comfy_nodes.agent remains
# importable without a ComfyUI server.
if os.environ.get("VIBECOMFY_HEADLESS") != "1":
    from . import routes


def __getattr__(name: str):
    """Lazy-load remaining agent submodules on first attribute access."""
    lazy_names = {
        "audit",
        "diagnostics",
        "edit",
        "fixture_provider",
        "gates",
        "provider",
        "runtime",
        "runtime_code",
        "worker",
    }
    if name in lazy_names:
        module = importlib.import_module(f"vibecomfy.comfy_nodes.agent.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
