"""Re-export shim: arnold_pipelines.megaplan.agent.tools.environments.local → arnold.agent.tools.environments.local."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.tools.environments.local")
_sys.modules[__name__] = _real
