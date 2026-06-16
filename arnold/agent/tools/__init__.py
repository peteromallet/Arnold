"""Compatibility package for the vendored Hermes ``tools`` namespace."""

import importlib as _importlib
import importlib.machinery as _machinery
from pathlib import Path as _Path
import sys as _sys
import types as _types


def _install_legacy_tools_namespace() -> None:
    """Expose vendored Hermes tools for legacy absolute ``tools.*`` imports."""
    if "tools" in _sys.modules:
        return

    package = _types.ModuleType("tools")
    package.__package__ = "tools"
    package.__path__ = [
        str(_Path(__file__).resolve().parent),
        str(_Path(__file__).resolve().parents[2] / "pipelines" / "megaplan" / "agent" / "tools"),
    ]
    spec = _machinery.ModuleSpec("tools", loader=None, is_package=True)
    spec.submodule_search_locations = package.__path__
    package.__spec__ = spec
    _sys.modules["tools"] = package


# Import the vendored agent package first. Its __init__.py inserts the agent
# directory into sys.path so legacy absolute imports like
# ``from agent.auxiliary_client import ...`` resolve correctly.
_importlib.import_module("arnold.pipelines.megaplan.agent")

_install_legacy_tools_namespace()


def _alias_real_module(name: str):
    real = _importlib.import_module(f"arnold.pipelines.megaplan.agent.tools.{name}")
    globals()[name] = real
    return real
