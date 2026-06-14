"""Re-export shim: arnold.agent.model_tools → arnold.agent.tools.model_tools.

The SSoT lives in arnold.agent.tools.model_tools (T5).  This shim preserves the
arnold.agent.model_tools import path that run_agent.py uses.
"""
import sys as _sys
import importlib as _importlib
_real = _importlib.import_module("arnold.agent.tools.model_tools")
_sys.modules[__name__] = _real
