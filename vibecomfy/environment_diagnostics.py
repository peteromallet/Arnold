from __future__ import annotations

import importlib.metadata
import re
import sys
from typing import Any, Mapping


def metadata_environment_warnings(metadata: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    hardware = metadata.get("hardware")
    if isinstance(hardware, Mapping):
        warnings.extend(_hardware_warnings(hardware))
    python_env = metadata.get("python_env")
    if isinstance(python_env, Mapping):
        warnings.extend(_python_env_warnings(python_env))
    return warnings


def _hardware_warnings(hardware: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    min_vram = hardware.get("vram_gb_min")
    recommended_vram = hardware.get("vram_gb_recommended")
    if isinstance(min_vram, int):
        warnings.append(f"hardware requires at least {min_vram}GB VRAM; local GPU capacity was not probed offline")
    if isinstance(recommended_vram, int):
        warnings.append(f"hardware recommends {recommended_vram}GB VRAM; local GPU capacity was not probed offline")
    if hardware.get("requires_flash_attention") is True:
        warnings.append("hardware requires flash attention; local accelerator support was not probed offline")
    tested_on = hardware.get("tested_on")
    if isinstance(tested_on, list) and tested_on:
        labels = ", ".join(str(item) for item in tested_on)
        warnings.append(f"hardware was tested on: {labels}")
    return warnings


def _python_env_warnings(python_env: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    for package, constraint in sorted(python_env.items()):
        if not isinstance(constraint, str) or not constraint:
            continue
        if package == "python":
            actual = ".".join(str(part) for part in sys.version_info[:3])
        else:
            try:
                actual = importlib.metadata.version(_distribution_name(package))
            except importlib.metadata.PackageNotFoundError:
                warnings.append(f"python_env package {package!r} is not installed; expected {constraint}")
                continue
        if not _constraint_satisfied(actual, constraint):
            warnings.append(f"python_env {package} {actual} does not satisfy {constraint}")
    return warnings


def _distribution_name(package: str) -> str:
    return {"torch": "torch", "python": "python"}.get(package, package.replace("_", "-"))


def _constraint_satisfied(version: str, constraint: str) -> bool:
    clauses = [clause.strip() for clause in constraint.split(",") if clause.strip()]
    if not clauses:
        return True
    actual = _version_tuple(version)
    for clause in clauses:
        match = re.match(r"(>=|<=|==|>|<)\s*([A-Za-z0-9_.!+-]+)$", clause)
        if not match:
            continue
        op, expected_raw = match.groups()
        expected = _version_tuple(expected_raw)
        if op == ">=" and not actual >= expected:
            return False
        if op == "<=" and not actual <= expected:
            return False
        if op == ">" and not actual > expected:
            return False
        if op == "<" and not actual < expected:
            return False
        if op == "==" and not actual == expected:
            return False
    return True


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts[:4])


__all__ = ["metadata_environment_warnings"]
