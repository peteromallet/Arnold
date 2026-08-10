"""Compatibility import for Arnold's neutral mini-swe-agent path helpers."""

from arnold.agent.minisweagent_path import (
    discover_minisweagent_src,
    ensure_minisweagent_on_path,
)

__all__ = ["discover_minisweagent_src", "ensure_minisweagent_on_path"]
