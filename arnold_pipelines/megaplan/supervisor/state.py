"""Persistence helpers for supervisor orchestration state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan._core import atomic_write_json, slugify
from arnold_pipelines.megaplan.supervisor.model import SupervisorState, SupervisorVariantKind
from arnold_pipelines.megaplan.types import CliError


def supervisor_state_root(root: Path) -> Path:
    """Return the persisted supervisor state directory for a project root."""

    return Path(root).resolve() / ".megaplan" / "plans" / ".supervisor"


def supervisor_state_path(root: Path, state_id: str) -> Path:
    """Return the canonical state path for one supervisor run."""

    normalized = _normalize_state_id(state_id)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return supervisor_state_root(root) / f"{slugify(Path(normalized).stem)}-{digest}.json"


def load_supervisor_state(root: Path, state_id: str) -> SupervisorState | None:
    """Load persisted supervisor state, returning ``None`` when absent."""

    state_path = supervisor_state_path(root, state_id)
    if not state_path.exists():
        return None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(
            "invalid_supervisor_state",
            f"supervisor state is invalid JSON: {exc}",
        ) from exc
    if not isinstance(raw, dict):
        raise CliError(
            "invalid_supervisor_state",
            "supervisor state must be a JSON object",
        )
    state = SupervisorState.from_dict(raw)
    validate_supervisor_state(state)
    return state


def save_supervisor_state(root: Path, state_id: str, state: SupervisorState) -> Path:
    """Persist supervisor state with atomic JSON replacement."""

    validate_supervisor_state(state)
    state_path = supervisor_state_path(root, state_id)
    atomic_write_json(state_path, state.to_dict())
    return state_path


def validate_supervisor_state(state: SupervisorState) -> None:
    """Validate supervisor state invariants before load/save."""

    node_positions: dict[str, int] = {}
    for index, node in enumerate(state.run_nodes):
        if node.node_id in node_positions:
            raise CliError(
                "invalid_supervisor_state",
                f"duplicate supervisor node_id {node.node_id!r}",
            )
        node_positions[node.node_id] = index

    for assertion in state.dependency_assertions:
        node_index = node_positions.get(assertion.node_id)
        if node_index is None:
            raise CliError(
                "invalid_supervisor_state",
                f"dependency assertion references unknown node {assertion.node_id!r}",
            )
        for dependency_id in assertion.depends_on:
            dependency_index = node_positions.get(dependency_id)
            if dependency_index is None:
                raise CliError(
                    "invalid_supervisor_state",
                    f"dependency assertion for {assertion.node_id!r} references unknown node {dependency_id!r}",
                )
            if (
                state.variant == SupervisorVariantKind.CHAIN
                and dependency_index >= node_index
            ):
                raise CliError(
                    "invalid_supervisor_state",
                    f"chain node {assertion.node_id!r} depends on {dependency_id!r}, but chain dependencies must point to earlier nodes",
                )


def _normalize_state_id(state_id: str) -> str:
    normalized = str(state_id).strip()
    if not normalized:
        raise CliError("invalid_supervisor_state", "state_id must be a non-empty string")
    return normalized


__all__ = [
    "load_supervisor_state",
    "save_supervisor_state",
    "supervisor_state_path",
    "supervisor_state_root",
    "validate_supervisor_state",
]
