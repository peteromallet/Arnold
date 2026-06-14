"""Re-export shim: arnold.pipelines.megaplan.agent.honcho_integration.client → arnold.agent.honcho_integration.client."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.honcho_integration.client")
_sys.modules[__name__] = _real
