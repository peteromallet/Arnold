"""Re-export shim: arnold_pipelines.megaplan.agent.hermes_time → arnold.agent.hermes_time.

The SSoT lives in arnold.agent.hermes_time.
"""
import sys as _sys
import importlib as _importlib
_real = _importlib.import_module("arnold.agent.hermes_time")
_sys.modules[__name__] = _real
