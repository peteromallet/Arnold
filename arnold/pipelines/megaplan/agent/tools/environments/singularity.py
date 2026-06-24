"""Re-export shim: arnold.pipelines.megaplan.agent.tools.environments.singularity → arnold.agent.tools.environments.singularity."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.tools.environments.singularity")
_sys.modules[__name__] = _real
