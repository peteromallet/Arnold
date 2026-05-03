"""Generic resident-chat runtime infrastructure."""

from .async_bridge import SameLoopBridgeError, run_coroutine_sync
from .coalescing import AsyncBurstCoalescer, BurstBatch
from .diagnostics import DiagnosticItem, build_startup_diagnostics
from .env import EnvSetting, EnvStatus, read_env_settings
from .health import CachedHealthCheck, HealthResult

__all__ = [
    "AsyncBurstCoalescer",
    "BurstBatch",
    "CachedHealthCheck",
    "DiagnosticItem",
    "EnvSetting",
    "EnvStatus",
    "HealthResult",
    "SameLoopBridgeError",
    "build_startup_diagnostics",
    "read_env_settings",
    "run_coroutine_sync",
]
