from __future__ import annotations

import os

# Make the sub-modules accessible as attributes of the agent package,
# e.g. `from vibecomfy.comfy_nodes.agent import contracts`
from . import audit
from . import contracts
from . import diagnostics
from . import edit
from . import fixture_provider
from . import gates
from . import runtime
from . import worker
from . import provider

# routes.py imports aiohttp/server at module level (guarded by VIBECOMFY_HEADLESS).
# In headless mode we skip the import so vibecomfy.comfy_nodes.agent remains
# importable without a ComfyUI server.
if os.environ.get("VIBECOMFY_HEADLESS") != "1":
    from . import routes

from . import runtime_code
from . import session
