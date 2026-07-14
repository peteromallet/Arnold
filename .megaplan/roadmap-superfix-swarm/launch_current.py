"""Temporary investigation-only shim for the current Arnold Hermes runtime."""

from __future__ import annotations

import runpy
import sys
import types


# The checked-out top-level ``megaplan`` compatibility package has no
# ``megaplan.agent``.  Seed the legacy probe so it reaches its accepted
# ``run_agent`` miss and falls through to ``arnold.agent`` without editing the
# shared launcher while other resident agents own that file.
sys.modules.setdefault("megaplan.agent", types.ModuleType("megaplan.agent"))
runpy.run_path(
    "/workspace/arnold/arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py",
    run_name="__main__",
)
