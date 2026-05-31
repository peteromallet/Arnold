"""Manifest reader: extract pipeline metadata without importing the module.

The manifest contract (briefs/m6/manifest-contract.md) requires that pipeline
metadata be readable at discovery time **without executing arbitrary module
code**. This reader uses ``ast.parse`` + ``ast.literal_eval`` to extract
module-level constant assignments, and verifies the by-convention
``SKILL.md`` sibling exists.

Failure modes return a ``ManifestError`` describing the rejection reason.
The caller is responsible for converting the error into a ``Disposition``
or raising/warning as appropriate.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

# The SDK's current major version. arnold_api_version must satisfy
# 1 <= major < CURRENT_MAJOR. Bumping the SDK to 2.x updates this.
CURRENT_MAJOR: int = 2

# Fields that every pipeline manifest MUST declare as module-level constants.
# ``default_profile`` may be ``None``, but the binding must exist.
REQUIRED_FIELDS: tuple[str, ...] = (
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "arnold_api_version",
    "capabilities",
)

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Manifest:
    """Static metadata extracted from a pipeline module without importing."""

    path: Path
    name: str
    description: str
    default_profile: str | None
    supported_modes: tuple[str, ...]
    driver: object
    arnold_api_version: str
    capabilities: tuple[str, ...]
    extras: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ManifestError:
    """A loud rejection produced when manifest reading fails."""

    path: Path
    reason: str
    traceback: str | None = None


def _derive_name(module_file: Path) -> str:
    if module_file.name == "__init__.py":
        return module_file.parent.name
    return module_file.stem


def _skill_md_sibling(module_file: Path) -> Path:
    return module_file.parent / "SKILL.md"


def _extract_top_level_constants(
    tree: ast.Module,
) -> tuple[dict[str, object], set[str], list[str]]:
    """Return (constants, top_level_symbols, literal_errors).

    Only ``Assign`` / ``AnnAssign`` nodes with a single ``Name`` target are
    considered. Values are resolved via ``ast.literal_eval`` (no execution).
    Non-literal RHS values are silently skipped from ``constants`` but their
    target names still appear in ``top_level_symbols`` so callers can tell
    "name absent" from "name bound to non-literal".
    """

    constants: dict[str, object] = {}
    top_level_symbols: set[str] = set()
    literal_errors: list[str] = []

    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level_symbols.add(node.name)
            continue
        else:
            continue

        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            top_level_symbols.add(target.id)
            if value is None:
                continue
            try:
                constants[target.id] = ast.literal_eval(value)
            except (ValueError, SyntaxError) as exc:
                literal_errors.append(f"{target.id}: {exc}")

    return constants, top_level_symbols, literal_errors


def _coerce_str_tuple(value: object) -> tuple[str, ...] | None:
    if isinstance(value, (list, tuple)) and all(isinstance(x, str) for x in value):
        return tuple(value)
    return None


def _validate_api_version(value: object) -> tuple[bool, str]:
    """Return (ok, reason). ``reason`` is non-empty when ``ok`` is False."""
    if not isinstance(value, str):
        return False, (
            f"field 'arnold_api_version' in manifest: expected str, "
            f"got {type(value).__name__}"
        )
    match = _SEMVER_RE.match(value)
    if not match:
        return False, (
            f"arnold_api_version '{value}' is not a valid semver major.minor"
        )
    major = int(match.group(1))
    if not (1 <= major < CURRENT_MAJOR):
        return False, (
            f"arnold_api_version {value} is outside supported range "
            f"[1.0, {CURRENT_MAJOR}.0)"
        )
    return True, ""


def read_manifest(module_file: Path) -> Union[Manifest, ManifestError]:
    """Read and validate a pipeline manifest from ``module_file``.

    The module is **never imported**. Metadata is extracted by parsing the
    source with ``ast.parse`` and resolving constant RHS values via
    ``ast.literal_eval``. A by-convention sibling ``SKILL.md`` is required.

    Returns a ``Manifest`` on success, or a ``ManifestError`` on any
    rejection (malformed Python, missing required field, wrong type,
    out-of-range API version, missing ``build_pipeline`` symbol, or missing
    ``SKILL.md``).
    """

    path = Path(module_file)

    try:
        source = path.read_bytes()
    except OSError as exc:
        return ManifestError(path=path, reason=f"unable to read module file: {exc}")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return ManifestError(
            path=path,
            reason=f"malformed Python in {path.name}: {exc.msg}",
            traceback=str(exc),
        )

    constants, top_level_symbols, literal_errors = _extract_top_level_constants(tree)

    if "build_pipeline" not in top_level_symbols:
        return ManifestError(
            path=path,
            reason="no top-level build_pipeline symbol declared in module",
        )

    for required in REQUIRED_FIELDS:
        if required not in constants:
            if required in top_level_symbols:
                hint = (
                    f" (it is bound to a non-literal expression and cannot be "
                    f"read without importing the module)"
                )
            else:
                hint = ""
            return ManifestError(
                path=path,
                reason=f"missing required field '{required}' in manifest{hint}",
                traceback="; ".join(literal_errors) or None,
            )

    description = constants["description"]
    if not isinstance(description, str):
        return ManifestError(
            path=path,
            reason=(
                f"field 'description' in manifest: expected str, "
                f"got {type(description).__name__}"
            ),
        )

    default_profile = constants["default_profile"]
    if default_profile is not None and not isinstance(default_profile, str):
        return ManifestError(
            path=path,
            reason=(
                f"field 'default_profile' in manifest: expected str or None, "
                f"got {type(default_profile).__name__}"
            ),
        )

    supported_modes = _coerce_str_tuple(constants["supported_modes"])
    if supported_modes is None:
        return ManifestError(
            path=path,
            reason="field 'supported_modes' in manifest: expected sequence of str",
        )

    capabilities = _coerce_str_tuple(constants["capabilities"])
    if capabilities is None:
        return ManifestError(
            path=path,
            reason="field 'capabilities' in manifest: expected sequence of str",
        )

    ok, reason = _validate_api_version(constants["arnold_api_version"])
    if not ok:
        return ManifestError(path=path, reason=reason)

    skill_md = _skill_md_sibling(path)
    if not skill_md.is_file():
        return ManifestError(path=path, reason="SKILL.md missing")

    extras: dict[str, object] = {
        k: v for k, v in constants.items() if k not in REQUIRED_FIELDS
    }

    return Manifest(
        path=path,
        name=_derive_name(path),
        description=description,
        default_profile=default_profile,
        supported_modes=supported_modes,
        driver=constants["driver"],
        arnold_api_version=constants["arnold_api_version"],  # type: ignore[arg-type]
        capabilities=capabilities,
        extras=extras,
    )
