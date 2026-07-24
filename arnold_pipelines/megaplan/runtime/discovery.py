"""Pipeline discovery — megaplan-owned scan and load logic.

The neutral Arnold discovery primitives live at
:mod:`arnold.workflow.discovery`.  This module supplies Megaplan-specific
scan roots, the legacy ``planning`` → ``megaplan`` alias, manifest-first
discovery (M6 flag-gated), trust-tier classification, and the
``scan_python_pipelines`` / ``discover_python_pipelines`` entry points.

This module was extracted from :mod:`arnold_pipelines.megaplan._pipeline.registry`
during the M3 burn-down to separate generic pipeline discovery from
Megaplan-specific registry behaviour (global singleton, budget quotas,
operation dispatch).
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import re
import sys
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from arnold.workflow.discovery.manifest import (
    Manifest,
    ManifestError,
    read_manifest,
)
from arnold.workflow.discovery.trust import (
    BLESSED_ALLOWLIST,
    TrustGrade,
    derive_tenant_id,
)
from arnold.workflow.discovery.trust import classify as _arnold_classify
from arnold.pipeline.types import Pipeline
from arnold.execution.operations import (
    NullOperationRegistry,
    OperationKind,
    OperationRegistry,
)

PipelineBuilder = Callable[[], Pipeline]
_OUT_OF_TREE_SUB_BUDGET_USD = 1.0

# Megaplan-specific in-tree path fragments (mirrors
# arnold_pipelines.megaplan._pipeline.discovery.trust._IN_TREE_PATH_FRAGMENTS).
# ``arnold_pipelines`` is the plugin root; ``megaplan/pipelines`` remains
# supported for standalone development checkouts outside this package.
_IN_TREE_PATH_FRAGMENTS: tuple[str, ...] = ("arnold_pipelines", "megaplan/pipelines")


def classify(
    module_path: Path,
    *,
    blessed_allowlist: tuple[str, ...] = BLESSED_ALLOWLIST,
) -> TrustGrade:
    """Return the trust grade for *module_path*.

    Megaplan bridge: delegates to the neutral Arnold classifier with
    each in-tree path fragment.  The first matching fragment wins.

    Replicates the behaviour of
    :func:`arnold_pipelines.megaplan._pipeline.discovery.trust.classify`
    without importing the ``_pipeline`` package (avoids circular imports
    with ``_pipeline.registry``).
    """
    for fragment in _IN_TREE_PATH_FRAGMENTS:
        tier = _arnold_classify(
            module_path,
            blessed_allowlist=blessed_allowlist,
            in_tree_path_fragment=fragment,
        )
        if tier != TrustGrade.QUARANTINED:
            return tier
    return _arnold_classify(
        module_path,
        blessed_allowlist=blessed_allowlist,
        in_tree_path_fragment=None,
    )


# ---------------------------------------------------------------------------
# Naming / identity helpers
# ---------------------------------------------------------------------------

CANONICAL_BUILTIN_PIPELINE = "megaplan"
# Registry-maintained compatibility aliases for names persisted by older plans.
LEGACY_PIPELINE_ALIASES: dict[str, str] = {"planning": CANONICAL_BUILTIN_PIPELINE}
_NAME_ALIASES: dict[str, str] = dict(LEGACY_PIPELINE_ALIASES)


def canonical_pipeline_name(name: str) -> str:
    """Return the registry-canonical pipeline name for *name*."""
    return _NAME_ALIASES.get(name, name)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


@dataclass
class Disposition:
    """Per-path result from :func:`scan_python_pipelines`.

    Fields
    ------
    path:
        Absolute path to the module file that was examined.
    origin:
        ``"in_tree"`` when the package_prefix is the canonical in-tree pipeline package;
        ``"user"`` otherwise.
    status:
        One of ``"discovered"``, ``"rejected"``, or ``"skipped"``.
    reason:
        Human-readable explanation for the status.
    traceback:
        Full traceback string when the module raised during import; ``None``
        otherwise.
    cli_name:
        The CLI-visible name derived from the module path.  ``None`` when
        the path was skipped before a name could be derived.
    """

    path: Path
    origin: str
    status: str
    reason: str
    traceback: Optional[str] = None
    cli_name: Optional[str] = None
    manifest: Optional[Manifest] = None


def _manifest_discovery_enabled() -> bool:
    """Return True; manifest-first discovery is unconditional as of M1.

    The ``MEGAPLAN_M6_MANIFEST_DISCOVERY`` env var is no longer read or
    consulted — discovery is always enabled.  The function is retained as
    a compatibility shim for callers that still gate on it; it will be
    removed in M7 alongside the legacy graph runtime.
    """
    return True


def _package_prefix_for_module_file(module_file: Path) -> str | None:
    normalised = str(module_file.resolve()).replace("\\", "/")
    arnold_pipelines_megaplan_fragment = "/arnold_pipelines/megaplan/pipelines/"
    if arnold_pipelines_megaplan_fragment in normalised or normalised.endswith(
        "/arnold_pipelines/megaplan/pipelines"
    ):
        return "arnold_pipelines.megaplan.pipelines"
    arnold_pipelines_fragment = "/arnold_pipelines/"
    if arnold_pipelines_fragment in normalised or normalised.endswith("/arnold_pipelines"):
        return "arnold_pipelines"
    arnold_fragment = "/arnold/pipelines/"
    if arnold_fragment in normalised or normalised.endswith("/arnold/pipelines"):
        return "arnold.pipelines"
    megaplan_fragment = "/megaplan/pipelines/"
    if megaplan_fragment in normalised or normalised.endswith("/megaplan/pipelines"):
        return "arnold_pipelines.megaplan.pipelines"
    return None


def _load_module_from_path(
    module_file: Path,
    *,
    package_prefix: str | None,
) -> Any | None:
    """Import the module at *module_file* and return the module object."""

    def _safe_module_component(raw: str) -> str:
        candidate = re.sub(r"\W", "_", raw)
        if not candidate:
            return "_"
        if candidate[0].isdigit():
            candidate = f"_{candidate}"
        return candidate

    if (
        package_prefix is not None
        and module_file.suffix == ".py"
        and module_file.name != "__init__.py"
    ):
        # In-tree sibling file: importable as `<package_prefix>.<stem>`.
        dotted = f"{package_prefix}.{module_file.stem}"
        try:
            return importlib.import_module(dotted)
        except ImportError:
            return None

    if package_prefix is not None and module_file.name == "__init__.py":
        # In-tree package directory.
        dotted = f"{package_prefix}.{module_file.parent.name}"
        try:
            return importlib.import_module(dotted)
        except ImportError:
            return None

    # Out-of-tree (user) module: spec from file location.
    mod_name = (
        f"arnold_pipelines.megaplan._user_pipelines.{_safe_module_component(module_file.stem)}"
        if module_file.name != "__init__.py"
        else f"arnold_pipelines.megaplan._user_pipelines.{_safe_module_component(module_file.parent.name)}"
    )
    spec = importlib.util.spec_from_file_location(mod_name, module_file)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 — discovery is best-effort
        sys.modules.pop(mod_name, None)
        return None
    return module


def _load_trusted_pipeline_module(module_file: Path) -> Any | None:
    tier = classify(module_file, blessed_allowlist=BLESSED_ALLOWLIST)
    if tier not in (TrustGrade.AUTO_EXEC, TrustGrade.BLESSED):
        return None
    return _load_module_from_path(
        module_file,
        package_prefix=_package_prefix_for_module_file(module_file),
    )


def _cli_name(module_stem: str) -> str:
    """Translate a Python module identifier to its CLI-visible name."""
    return module_stem.replace("_", "-")


def _discovered_cli_name(
    entry: Path,
    *,
    package_prefix: str | None,
) -> str:
    """Return the CLI-visible name for a discovered pipeline entry."""

    if (
        package_prefix in ("arnold_pipelines", "arnold.pipelines", "arnold_pipelines.megaplan.pipelines")
        and entry.is_dir()
        and entry.name == "planning"
        and (entry / "__init__.py").exists()
    ):
        return CANONICAL_BUILTIN_PIPELINE
    return _cli_name(entry.stem if entry.is_file() else entry.name)


def _scan_dir_for_pipeline_modules(
    pipelines_dir: Path,
    *,
    package_prefix: str | None,
) -> list[tuple[str, Path]]:
    """Return ``[(cli_name, module_file)]`` for pipelines under *pipelines_dir*.

    *package_prefix* is the dotted package path for installed packages
    (e.g. ``"arnold_pipelines.megaplan.pipelines"``) or ``None`` for ad-hoc filesystem
    discovery (user pipelines in ``~/.megaplan/pipelines/``).
    """

    if not pipelines_dir.exists() or not pipelines_dir.is_dir():
        return []

    out: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for entry in sorted(pipelines_dir.iterdir()):
        if entry.name.startswith("_") or entry.name.startswith("."):
            continue
        # M5 discovery helper is not a pipeline module; skip it so the legacy
        # scanner does not reject it for lacking a ``build_pipeline`` callable.
        if entry.name == "discovery.py":
            continue
        if entry.is_file() and entry.suffix == ".py":
            cli = _discovered_cli_name(entry, package_prefix=package_prefix)
            if cli in seen:
                continue
            seen.add(cli)
            out.append((cli, entry))
        elif entry.is_dir():
            init = entry / "__init__.py"
            if not init.exists():
                continue
            # Skip package directories whose hyphenated CLI name shadows
            # a sibling file we've already seen — the file wins (the
            # hyphenated directory is treated as a resource bundle, not
            # a Python package).
            cli = _discovered_cli_name(entry, package_prefix=package_prefix)
            if cli in seen:
                continue
            seen.add(cli)
            out.append((cli, init))
    return out


def _make_deferred_builder(
    module_file: Path,
    *,
    package_prefix: str | None,
    cli_name: str,
) -> PipelineBuilder:
    """Build a deferred-import callable for a manifest-discovered pipeline.

    The returned callable defers ``exec_module`` until invoked. Calls into
    it are gated by :meth:`PipelineRegistry.get` on the path-derived trust
    tier — this closure trusts its caller to have already classified.
    """

    def _deferred() -> Pipeline:
        module = _load_module_from_path(module_file, package_prefix=package_prefix)
        if module is None:
            raise RuntimeError(
                f"pipeline {cli_name!r} at {module_file!s} failed to load",
            )
        build = getattr(module, "build_pipeline", None)
        if not callable(build):
            raise RuntimeError(
                f"pipeline {cli_name!r} at {module_file!s} has no callable build_pipeline",
            )
        return build()

    _deferred._m6_deferred = True  # type: ignore[attr-defined]
    return _deferred


def _coerce_supported_operations(value: object) -> frozenset[OperationKind]:
    if not isinstance(value, (set, frozenset, list, tuple)):
        return frozenset()
    supported: set[OperationKind] = set()
    for item in value:
        if isinstance(item, OperationKind):
            supported.add(item)
            continue
        if isinstance(item, str):
            try:
                supported.add(OperationKind(item))
            except ValueError:
                continue
    return frozenset(supported)


def _supported_operation_names(registry: OperationRegistry) -> tuple[str, ...]:
    try:
        supported = registry.supported_operations()
    except Exception:  # noqa: BLE001 - helper must fail closed
        return ()
    return tuple(sorted(kind.value for kind in _coerce_supported_operations(supported)))


def _operation_registry_from_module(module: Any) -> OperationRegistry:
    factory = getattr(module, "operation_registry", None)
    if not callable(factory):
        return NullOperationRegistry()
    try:
        registry = factory()
    except Exception:  # noqa: BLE001 - helper must fail closed
        return NullOperationRegistry()
    if isinstance(registry, OperationRegistry):
        return registry
    return NullOperationRegistry()


def _module_metadata(module: Any, *, source_path: Path | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    name = getattr(module, "name", "")
    if isinstance(name, str) and name:
        meta["name"] = name
    description = getattr(module, "description", "")
    if isinstance(description, str) and description:
        meta["description"] = description
    default_profile = getattr(module, "default_profile", None)
    if isinstance(default_profile, str) and default_profile:
        meta["default_profile"] = default_profile
    supported_modes = getattr(module, "supported_modes", ())
    if isinstance(supported_modes, (list, tuple)):
        meta["supported_modes"] = tuple(supported_modes)
    arnold_api_version = getattr(module, "arnold_api_version", "")
    if isinstance(arnold_api_version, str) and arnold_api_version:
        meta["arnold_api_version"] = arnold_api_version
    capabilities = getattr(module, "capabilities", ())
    if isinstance(capabilities, (list, tuple)):
        meta["capabilities"] = tuple(capabilities)
    recommended_profiles = getattr(module, "recommended_profiles", ())
    if isinstance(recommended_profiles, (list, tuple)):
        meta["recommended_profiles"] = tuple(recommended_profiles)
    if source_path is not None:
        tier = classify(source_path, blessed_allowlist=BLESSED_ALLOWLIST)
        if tier in (TrustGrade.AUTO_EXEC, TrustGrade.BLESSED):
            supported = _supported_operation_names(
                _operation_registry_from_module(module)
            )
            if supported:
                meta["supported_operations"] = supported
    return meta


def _manifest_metadata(name: str, disposition: Disposition) -> dict[str, Any]:
    manifest = disposition.manifest
    if manifest is None:
        return {}
    meta: dict[str, Any] = {"name": manifest.name}
    if manifest.description:
        meta["description"] = manifest.description
    if manifest.default_profile:
        meta["default_profile"] = manifest.default_profile
    meta["supported_modes"] = tuple(manifest.supported_modes)
    meta["driver"] = tuple(manifest.driver)
    meta["compatibility_classification"] = (
        "graph_compatibility"
        if manifest.driver and manifest.driver[0] == "graph" and "native" not in manifest.supported_modes
        else "native"
    )
    meta["arnold_api_version"] = manifest.arnold_api_version
    meta["capabilities"] = tuple(manifest.capabilities)
    manifest_hash = getattr(manifest, "manifest_hash", None)
    if isinstance(manifest_hash, str) and manifest_hash:
        meta["manifest_hash"] = manifest_hash
    meta["source_path"] = str(disposition.path)
    meta["manifest_origin"] = disposition.origin
    tier = classify(disposition.path, blessed_allowlist=BLESSED_ALLOWLIST)
    meta["trust_tier"] = tier.value
    if disposition.origin == "user":
        tenant_id = derive_tenant_id(name, disposition.path)
        meta["tenant_id"] = tenant_id
        meta["sub_budget_usd"] = _OUT_OF_TREE_SUB_BUDGET_USD
        meta["quota_reserved"] = False
    return meta


# ---------------------------------------------------------------------------
# Scan roots (Megaplan-specific paths)
# ---------------------------------------------------------------------------

_SCAN_ROOTS: list[tuple[Path, str | None]] = [
    (Path(__file__).resolve().parent.parent.parent, "arnold_pipelines"),
    (
        Path(__file__).resolve().parent.parent / "pipelines",
        "arnold_pipelines.megaplan.pipelines",
    ),
]


def _get_scan_roots() -> list[tuple[Path, str | None]]:
    """Return scan roots including the user home dir (evaluated at call time)."""
    return _SCAN_ROOTS + [(Path.home() / ".megaplan" / "pipelines", None)]


# ---------------------------------------------------------------------------
# Scan entry points
# ---------------------------------------------------------------------------


def scan_python_pipelines() -> list[Disposition]:
    """Walk all scan roots and return a :class:`Disposition` for EVERY path.

    This function NEVER raises and ALWAYS completes the full scan.  Every
    module file encountered — discovered, rejected, or skipped — is
    represented in the returned list.

    Origins:
    * ``"in_tree"``  — the path came from the canonical in-tree pipeline scan
      root.
    * ``"user"``     — the path came from a user scan root (``package_prefix
      is None``).

    Statuses:
    * ``"discovered"``  — the module loaded successfully and exposes a
      callable ``build_pipeline``.
    * ``"rejected"``    — the module could not be loaded OR does not expose a
      callable ``build_pipeline``.
    * ``"skipped"``     — the module was excluded before loading (duplicate
      in seen-set, etc.).
    """
    dispositions: list[Disposition] = []
    seen: set[str] = set()

    try:
        roots = _get_scan_roots()
    except Exception:
        return dispositions

    for pipelines_dir, package_prefix in roots:
        origin = (
            "in_tree"
            if package_prefix
            in ("arnold_pipelines", "arnold.pipelines", "arnold_pipelines.megaplan.pipelines")
            else "user"
        )

        try:
            dir_entries = list(
                _scan_dir_for_pipeline_modules(
                    pipelines_dir,
                    package_prefix=package_prefix,
                )
            )
        except Exception:
            continue

        for cli_name, module_file in dir_entries:
            cli_name = canonical_pipeline_name(cli_name)
            # --- duplicate (earlier scan root wins) ---
            if cli_name in seen:
                dispositions.append(
                    Disposition(
                        path=module_file,
                        origin=origin,
                        status="skipped",
                        reason=f"cli_name {cli_name!r} already discovered from an earlier scan root",
                        cli_name=cli_name,
                    )
                )
                continue

            # --- manifest-first discovery (flag-gated, default OFF) ---
            if _manifest_discovery_enabled():
                manifest_result = read_manifest(module_file)
                if isinstance(manifest_result, ManifestError):
                    dispositions.append(
                        Disposition(
                            path=module_file,
                            origin=origin,
                            status="rejected",
                            reason=f"manifest rejected: {manifest_result.reason}",
                            traceback=manifest_result.traceback,
                            cli_name=cli_name,
                            manifest=None,
                        )
                    )
                    continue
                seen.add(cli_name)
                dispositions.append(
                    Disposition(
                        path=module_file,
                        origin=origin,
                        status="discovered",
                        reason="ok (manifest)",
                        cli_name=cli_name,
                        manifest=manifest_result,
                    )
                )
                continue

            # --- attempt to load ---
            tb_str: Optional[str] = None
            module: Any = None
            try:
                module = _load_module_from_path(
                    module_file, package_prefix=package_prefix
                )
            except Exception:
                tb_str = traceback.format_exc()

            if module is None:
                if tb_str is None:
                    tb_str = "(module returned None — no callable build_pipeline or import failed silently)"
                dispositions.append(
                    Disposition(
                        path=module_file,
                        origin=origin,
                        status="rejected",
                        reason="module could not be imported",
                        traceback=tb_str,
                        cli_name=cli_name,
                    )
                )
                continue

            build = getattr(module, "build_pipeline", None)
            if not callable(build):
                dispositions.append(
                    Disposition(
                        path=module_file,
                        origin=origin,
                        status="rejected",
                        reason=f"module loaded but build_pipeline is {type(build).__name__!r}, not callable",
                        cli_name=cli_name,
                    )
                )
                continue

            seen.add(cli_name)
            dispositions.append(
                Disposition(
                    path=module_file,
                    origin=origin,
                    status="discovered",
                    reason="ok",
                    cli_name=cli_name,
                )
            )

    return dispositions


def discover_python_pipelines() -> list[
    tuple[str, PipelineBuilder, dict[str, Any], Path]
]:
    """Walk the in-tree + user pipeline directories and yield discovered pipelines.

    Returns a list of ``(cli_name, build_callable, metadata, source_path)``
    quads. Duplicate CLI names from later scan roots are skipped; modules
    that do not expose a callable ``build_pipeline`` attribute are skipped
    silently.

    Implementation delegates to :func:`scan_python_pipelines` for the full
    scan.  Rejected modules (both in-tree and user) emit a :class:`UserWarning`
    and are omitted from the returned list; this function does NOT raise.

    The return shape is back-compat: list of
    ``(cli_name, build_callable, metadata, source_path)`` quads.
    """
    dispositions = scan_python_pipelines()

    # Warn (but do not raise) for rejected or skipped modules.
    for d in dispositions:
        if d.status == "rejected":
            warnings.warn(
                f"{d.origin} pipeline {d.path!s} could not be loaded: {d.reason}",
                UserWarning,
                stacklevel=2,
            )
        if d.status == "skipped":
            warnings.warn(
                f"{d.origin} pipeline {d.path!s} skipped: {d.reason}",
                UserWarning,
                stacklevel=2,
            )

    # Build back-compat quad list from discovered dispositions only.
    out: list[tuple[str, PipelineBuilder, dict[str, Any], Path]] = []

    # Flag-ON: honour manifest-first discipline — return deferred-import
    # builders sourced from Disposition.manifest rather than re-importing.
    if _manifest_discovery_enabled():
        for d in dispositions:
            if d.status != "discovered" or d.cli_name is None or d.manifest is None:
                continue
            package_prefix = _package_prefix_for_module_file(d.path)
            builder = _make_deferred_builder(
                d.path,
                package_prefix=package_prefix,
                cli_name=d.cli_name,
            )
            meta = _manifest_metadata(d.cli_name, d)
            out.append((d.cli_name, builder, meta, d.path))
        return out

    # Flag-OFF: legacy re-import loop (preserves prior behaviour).
    seen: set[str] = set()
    for pipelines_dir, package_prefix in _get_scan_roots():
        for cli_name, module_file in _scan_dir_for_pipeline_modules(
            pipelines_dir, package_prefix=package_prefix
        ):
            cli_name = canonical_pipeline_name(cli_name)
            if cli_name in seen:
                continue
            module = _load_module_from_path(module_file, package_prefix=package_prefix)
            if module is None:
                continue
            build = getattr(module, "build_pipeline", None)
            if not callable(build):
                continue
            seen.add(cli_name)
            metadata = _module_metadata(module, source_path=module_file)
            out.append((cli_name, build, metadata, module_file))

    return out


__all__ = [
    "CANONICAL_BUILTIN_PIPELINE",
    "LEGACY_PIPELINE_ALIASES",
    "Disposition",
    "PipelineBuilder",
    "_SCAN_ROOTS",
    "_cli_name",
    "_get_scan_roots",
    "_load_module_from_path",
    "_load_trusted_pipeline_module",
    "_make_deferred_builder",
    "_manifest_discovery_enabled",
    "_manifest_metadata",
    "_module_metadata",
    "_package_prefix_for_module_file",
    "_scan_dir_for_pipeline_modules",
    "canonical_pipeline_name",
    "discover_python_pipelines",
    "scan_python_pipelines",
]
