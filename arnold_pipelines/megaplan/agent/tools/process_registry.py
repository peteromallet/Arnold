"""Re-export shim: arnold_pipelines.megaplan.agent.tools.process_registry → arnold.agent.tools.process_registry."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.tools.process_registry")
_sys.modules[__name__] = _real
