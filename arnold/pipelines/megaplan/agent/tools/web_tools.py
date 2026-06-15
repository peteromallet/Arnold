"""Re-export shim: arnold.pipelines.megaplan.agent.tools.web_tools → arnold.agent.tools.web_tools."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.tools.web_tools")
_sys.modules[__name__] = _real
