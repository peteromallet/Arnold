"""Shim: arnold.pipelines.megaplan.agent.tools.environments → arnold.agent.tools.environments.

Submodule shims (base.py, local.py, etc.) use sys.modules replacement
to ensure identity with the SSoT. This __init__.py re-exports the same
symbols that the SSoT __init__.py exports.
"""
from arnold.agent.tools.environments.base import BaseEnvironment

__all__ = ["BaseEnvironment"]
