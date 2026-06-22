"""Closed capability registry and worker discovery for verifiability contracts."""

from __future__ import annotations

from typing import Any

from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, effective_premium_vendor
from arnold_pipelines.megaplan.types import (
    format_agent_spec,
    resolve_premium_placeholder_spec,
)

CONTAINER_CAPABILITIES: frozenset[str] = frozenset({
    "run_shell",
    "read_files",
    "run_tests",
    "parse_diff",
    "read_build_output",
    "run_linter",
})

HUMAN_CAPABILITIES: frozenset[str] = frozenset({
    "drive_browser",
    "inspect_runtime_ui",
    "observe_runtime_logs",
    "subjective_judgment",
    "verify_physical_device",
})

ALL_CAPABILITIES: frozenset[str] = CONTAINER_CAPABILITIES | HUMAN_CAPABILITIES

DEFAULT_CONTAINER_CAPABILITIES: frozenset[str] = CONTAINER_CAPABILITIES
DEFAULT_HUMAN_CAPABILITIES: frozenset[str] = HUMAN_CAPABILITIES


def validate_capabilities(caps: list[str] | set[str]) -> list[str]:
    """Return unknown capability strings not in the closed registry."""
    return [c for c in caps if c not in ALL_CAPABILITIES]


def get_worker_capabilities(state: dict[str, Any]) -> dict[str, set[str]]:
    """Build worker-name → capabilities mapping from state config.

    Falls back to DEFAULT_CONTAINER_CAPABILITIES for agents listed in
    DEFAULT_AGENT_ROUTING that have no explicit config.
    """
    config = state.get("config", {})
    workers_cfg: dict[str, Any] = config.get("workers", {})

    result: dict[str, set[str]] = {}

    if workers_cfg:
        for name, wcfg in workers_cfg.items():
            verifies = wcfg.get("verifies", [])
            result[name] = set(verifies)
    else:
        vendor = effective_premium_vendor(config=config)
        seen_agents = {
            format_agent_spec(
                resolve_premium_placeholder_spec(spec, vendor)
            ).split(":", 1)[0]
            for spec in DEFAULT_AGENT_ROUTING.values()
        }
        for agent in seen_agents:
            result[agent] = set(DEFAULT_CONTAINER_CAPABILITIES)

    return result


def union_verifies(state: dict[str, Any]) -> set[str]:
    """Return the union of all workers' verifies sets."""
    caps = get_worker_capabilities(state)
    result: set[str] = set()
    for v in caps.values():
        result |= v
    return result
