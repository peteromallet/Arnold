"""Re-export shim: arnold_pipelines.megaplan.agent.hermes_cli.auth → arnold.agent.hermes_cli.auth."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.hermes_cli.auth")
_sys.modules[__name__] = _real
