"""Re-export shim: arnold.agent.run_agent is the SSoT.

Replaces this module object in sys.modules with the canonical
arnold.agent.run_agent module so that both
  ``from arnold_pipelines.megaplan.agent.run_agent import AIAgent``
and the sys.path-based
  ``from run_agent import AIAgent``
resolve to the same module object, including all private names.
"""
import sys as _sys
import importlib as _importlib

_real = _importlib.import_module("arnold.agent.run_agent")
_sys.modules[__name__] = _real
