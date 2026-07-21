from __future__ import annotations

from importlib.machinery import SourcelessFileLoader
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


def load_recovered_module(module: ModuleType, pyc_stem: str) -> None:
    """Populate ``module`` from a recovered ``.pyc`` artifact."""

    pyc_name = f"{pyc_stem}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
    recovered_path = Path(__file__).with_name("_recovered") / pyc_name
    pyc_path = recovered_path if recovered_path.exists() else Path(__file__).with_name("__pycache__") / pyc_name
    if not pyc_path.exists():
        raise ModuleNotFoundError(f"missing recovered custody module {pyc_path}")

    loader = SourcelessFileLoader(module.__name__, str(pyc_path))
    code = loader.get_code(module.__name__)
    if code is None:
        raise ModuleNotFoundError(f"could not load recovered custody module {pyc_path}")
    exec(code, module.__dict__)


def export_public(module_globals: dict[str, Any]) -> list[str]:
    return sorted(name for name in module_globals if not name.startswith("_"))
