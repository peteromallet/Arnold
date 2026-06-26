"""Re-export shim: arnold_pipelines.megaplan.agent.tools.environments.persistent_shell → arnold.agent.tools.environments.persistent_shell."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.tools.environments.persistent_shell")
_sys.modules[__name__] = _real
