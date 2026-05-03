from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .env import EnvStatus
from .health import HealthResult


@dataclass(frozen=True)
class DiagnosticItem:
    name: str
    ok: bool
    detail: str
    value: Any = None


def build_startup_diagnostics(
    *,
    env: list[EnvStatus] | tuple[EnvStatus, ...] = (),
    health: dict[str, HealthResult] | None = None,
) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for status in env:
        if status.error:
            detail = status.error
            ok = False
        elif status.configured:
            detail = "configured"
            ok = True
        else:
            detail = "missing optional"
            ok = True
        items.append(
            DiagnosticItem(
                name=f"env:{status.name}",
                ok=ok,
                detail=detail,
                value=status.safe_value(),
            )
        )

    for name, result in (health or {}).items():
        items.append(
            DiagnosticItem(
                name=f"health:{name}",
                ok=result.ok,
                detail=result.detail,
                value=result.metadata,
            )
        )
    return items
