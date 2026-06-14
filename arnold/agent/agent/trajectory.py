import sys as _sys
import importlib as _importlib
_real = _importlib.import_module("arnold.pipelines.megaplan.agent.agent.trajectory")
_sys.modules[__name__] = _real
