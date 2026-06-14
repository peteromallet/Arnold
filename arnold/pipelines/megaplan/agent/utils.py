"""Re-export shim: arnold.pipelines.megaplan.agent.utils → arnold.agent.utils.

The SSoT lives in arnold.agent.utils.
"""
import sys as _sys
import importlib as _importlib
_real = _importlib.import_module("arnold.agent.utils")
_sys.modules[__name__] = _real
