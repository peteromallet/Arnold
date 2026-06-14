import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("arnold.pipeline.token_cost")
_sys.modules[__name__] = _real
