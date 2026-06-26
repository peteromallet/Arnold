"""Re-export shim: arnold_pipelines.megaplan.agent.honcho_integration.session → arnold.agent.honcho_integration.session."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.honcho_integration.session")
print(f"SHIM-DEBUG session: __name__={__name__} _real.__name__={_real.__name__} _real is already megaplan={_real.__name__==__name__}", flush=True)
_sys.modules[__name__] = _real
print(f"SHIM-DEBUG session: after assignment sys.modules[__name__].__name__={_sys.modules[__name__].__name__}", flush=True)
