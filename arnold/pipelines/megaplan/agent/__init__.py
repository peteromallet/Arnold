"""Vendored hermes-agent subpackage.

Importing this module prepends its directory to sys.path so hermes's
original top-level imports resolve without rewriting vendored code.
Activated via `megaplan.workers.hermes._import_hermes_runtime()` only.
"""

import os as _os
import sys as _sys

_agent_dir = _os.path.dirname(__file__)
if _agent_dir not in _sys.path:
    _sys.path.insert(0, _agent_dir)
