"""Re-export shim: arnold.agent.hermes_cli.env_loader → arnold.agent.providers.env_loader.

The SSoT lives in arnold.agent.providers.env_loader (T9).  This shim avoids the
unnecessary megaplan hop so that arnold.agent.hermes_cli.env_loader resolves
directly to the canonical module.
"""
import sys as _sys
import importlib as _importlib
_real = _importlib.import_module("arnold.agent.providers.env_loader")
_sys.modules[__name__] = _real
