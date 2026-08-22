"""Compatibility loader for the legacy runtime's terminal tool implementation.

The native agent registry still expects ``arnold.agent.tools.terminal_tool`` to
provide the terminal schema, handler, environment cache, and requirement check.
Those implementations currently live in the bundled legacy runtime tree.  Load that
file under this canonical module name so registry state and tool imports share
one runtime module.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


_TOOLS_PACKAGE = importlib.import_module("arnold.agent.tools")

_MINISWEAGENT_PATH = importlib.import_module(
    "arnold.agent.minisweagent_path"
)

_CANONICAL_PATH = (
    Path(__file__).resolve().parents[3]
    / "arnold_pipelines"
    / "megaplan"
    / "agent"
    / "tools"
    / "terminal_tool.py"
)

_SPEC = importlib.util.spec_from_file_location(__name__, _CANONICAL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load Hermes terminal tool from {_CANONICAL_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[__name__] = _MODULE
setattr(_TOOLS_PACKAGE, "terminal_tool", _MODULE)
_previous_tools = sys.modules.get("tools")
_previous_terminal = sys.modules.get("tools.terminal_tool")
_previous_minisweagent_path = sys.modules.get("minisweagent_path")
try:
    # The bundled legacy runtime module uses its historical top-level import names.
    # Expose those aliases only while executing it; leaving ``tools`` globally
    # rebound corrupts unrelated imports according to test/runtime order.
    sys.modules["tools"] = _TOOLS_PACKAGE
    sys.modules["tools.terminal_tool"] = _MODULE
    sys.modules["minisweagent_path"] = _MINISWEAGENT_PATH
    _SPEC.loader.exec_module(_MODULE)
finally:
    if _previous_tools is None:
        sys.modules.pop("tools", None)
    else:
        sys.modules["tools"] = _previous_tools
    if _previous_terminal is None:
        sys.modules.pop("tools.terminal_tool", None)
    else:
        sys.modules["tools.terminal_tool"] = _previous_terminal
    if _previous_minisweagent_path is None:
        sys.modules.pop("minisweagent_path", None)
    else:
        sys.modules["minisweagent_path"] = _previous_minisweagent_path
globals().update(_MODULE.__dict__)
