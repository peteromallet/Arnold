"""Re-export shim: arnold.pipelines.megaplan.agent.hermes_cli.config → arnold.agent.hermes_cli.config."""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.hermes_cli.config")
_sys.modules[__name__] = _real
