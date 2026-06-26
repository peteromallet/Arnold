"""Compatibility loader for Hermes' terminal tool implementation.

The native agent registry still expects ``arnold.agent.tools.terminal_tool`` to
provide the terminal schema, handler, environment cache, and requirement check.
Those implementations currently live in the bundled Hermes tree.  Load that
file under this canonical module name so registry state and tool imports share
one runtime module.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


_TOOLS_PACKAGE = importlib.import_module("arnold.agent.tools")
sys.modules["tools"] = _TOOLS_PACKAGE

_MINISWEAGENT_PATH = importlib.import_module(
    "arnold_pipelines.megaplan.agent.minisweagent_path"
)
sys.modules["minisweagent_path"] = _MINISWEAGENT_PATH

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
sys.modules["tools.terminal_tool"] = _MODULE
setattr(_TOOLS_PACKAGE, "terminal_tool", _MODULE)
_SPEC.loader.exec_module(_MODULE)
globals().update(_MODULE.__dict__)
