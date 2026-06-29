import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("arnold.agent.costing.token_cost")
_sys.modules[__name__] = _real
