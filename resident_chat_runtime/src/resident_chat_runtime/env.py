from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

EnvType = Literal["str", "int", "bool"]


@dataclass(frozen=True)
class EnvSetting:
    name: str
    required: bool = False
    default: Any = None
    value_type: EnvType = "str"
    secret: bool = False


@dataclass(frozen=True)
class EnvStatus:
    name: str
    configured: bool
    required: bool
    secret: bool
    value: Any = None
    error: str | None = None

    def safe_value(self) -> Any:
        if not self.configured:
            return None
        if self.secret:
            return "<configured>"
        return self.value


def _coerce_value(raw: str, value_type: EnvType) -> Any:
    if value_type == "str":
        return raw
    if value_type == "int":
        return int(raw)
    if value_type == "bool":
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
        raise ValueError(f"expected bool-like value, got {raw!r}")
    raise ValueError(f"unsupported env type: {value_type}")


def read_env_settings(
    specs: list[EnvSetting],
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[EnvStatus]]:
    source = os.environ if environ is None else environ
    values: dict[str, Any] = {}
    statuses: list[EnvStatus] = []

    for spec in specs:
        raw = source.get(spec.name)
        configured = raw not in (None, "")
        if not configured:
            if spec.default is not None:
                values[spec.name] = spec.default
            statuses.append(
                EnvStatus(
                    name=spec.name,
                    configured=False,
                    required=spec.required,
                    secret=spec.secret,
                    value=spec.default,
                    error="missing" if spec.required else None,
                )
            )
            continue

        try:
            value = _coerce_value(str(raw), spec.value_type)
        except ValueError as exc:
            statuses.append(
                EnvStatus(
                    name=spec.name,
                    configured=True,
                    required=spec.required,
                    secret=spec.secret,
                    error=str(exc),
                )
            )
            continue

        values[spec.name] = value
        statuses.append(
            EnvStatus(
                name=spec.name,
                configured=True,
                required=spec.required,
                secret=spec.secret,
                value=value,
            )
        )

    return values, statuses
