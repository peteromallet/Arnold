"""Re-export shim: arnold_pipelines.megaplan.agent.tools.environments.base → arnold.agent.tools.environments.base."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.tools.environments.base")
_sys.modules[__name__] = _real
