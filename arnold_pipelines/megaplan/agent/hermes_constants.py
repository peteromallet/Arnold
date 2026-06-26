"""Re-export shim: arnold_pipelines.megaplan.agent.hermes_constants → arnold.agent.hermes_constants.

The SSoT lives in arnold.agent.hermes_constants.
"""
import sys as _sys
import importlib as _importlib
_real = _importlib.import_module("arnold.agent.hermes_constants")
_sys.modules[__name__] = _real
