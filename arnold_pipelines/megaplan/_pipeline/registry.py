"""Pipeline registry — megaplan-owned policy authority.

The neutral Arnold registry core lives at :mod:`arnold.pipeline.registry`.
This module supplies Megaplan-specific defaults (scan roots, legacy
alias, budget quota reservation, operation-registry fallbacks, planning
override catalogs) and wires the global singleton so existing consumers
continue working through the bridge.

Discovery scans (T9 / Step 8):

* ``megaplan/pipelines/<name>.py`` — sibling files exposing
  ``build_pipeline()``. The CLI-visible name is the file stem with
  ``_`` → ``-`` (e.g. ``writing_panel_strict.py`` →
  ``writing-panel-strict``). The hyphenated sibling directory
  ``megaplan/pipelines/<cli-name>/`` (when present) holds prompts,
  profiles, and ``SKILL.md``.
* ``megaplan/pipelines/<name>/__init__.py`` — package modules with the
  same ``build_pipeline()`` contract; ``SKILL.md`` lives alongside
  ``__init__.py``.
* ``~/.megaplan/pipelines/<name>.py`` — user-installed pipelines.

Discovered modules may expose module-level constants ``description``,
``default_profile``, ``supported_modes``, ``recommended_profiles`` —
the registry surfaces them via :attr:`PipelineRegistry.metadata`. If
multiple scan roots expose the same CLI-visible name, the earlier root
wins and later duplicates are skipped.

A programmatic registration is still available for tests and local extensions::

    from arnold_pipelines.megaplan._pipeline.registry import register_pipeline
    register_pipeline("my-pipeline", build_my_pipeline, description="…")
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from arnold.pipeline.registry import PipelineRegistry as ArnoldPipelineRegistry
from arnold.runtime.operations import (
    NullOperationRegistry,
    OperationKind,
    OperationRegistry,
    OperationRequest,
    OperationResult,
)
from arnold.pipeline.discovery.manifest import (
    Manifest,
    ManifestError,
    read_manifest,
)
from arnold_pipelines.megaplan._pipeline.discovery.trust import (
    BLESSED_ALLOWLIST,
    TrustGrade,
    classify,
    derive_tenant_id,
)
from arnold_pipelines.megaplan._pipeline.types import Pipeline


PipelineBuilder = Callable[[], Pipeline]
_OUT_OF_TREE_SUB_BUDGET_USD = 1.0


# ---------------------------------------------------------------------------
# Megaplan adapter — Arnold core with Megaplan defaults
# ---------------------------------------------------------------------------


def make_megaplan_registry() -> ArnoldPipelineRegistry:
    """Create an Arnold :class:`PipelineRegistry` configured with Megaplan defaults.

    Injects the Megaplan-specific scan roots (``megaplan/pipelines/``,
    ``~/.megaplan/pipelines/``), the legacy ``planning`` → ``megaplan``
    alias, and a discovery hook that delegates to this module's
    :func:`scan_python_pipelines` and :func:`discover_python_pipelines`.

    The returned registry uses the Arnold core for storage and query
    operations; Megaplan-specific methods (``operation_registry_for``,
    ``override_catalog_for``, ``read_skill_md``, quota reservation) are
    layered on top by the module-level :class:`PipelineRegistry` bridge.
    """
    from pathlib import Path

    _scan_roots = (
        Path(__file__).resolve().parent.parent / "pipelines",
        Path.home() / ".megaplan" / "pipelines",
    )

    def _discovery_hook(reg: ArnoldPipelineRegistry) -> None:
        """Populate *reg* from Megaplan scan roots."""
        # Use the megaplan-specific discovery logic.
        for name, builder, meta, source_path in discover_python_pipelines():
            name = canonical_pipeline_name(name)
            if name in reg:
                continue
            reg.register(
                name,
                builder,
                description=str(meta.get("description", "") or ""),
                metadata=meta,
                module_file=source_path,
            )

    return ArnoldPipelineRegistry(
        scan_roots=_scan_roots,
        package_prefixes=("arnold.pipelines", "arnold_pipelines.megaplan.pipelines"),
        alias_map=dict(LEGACY_PIPELINE_ALIASES),
        discovery_hook=_discovery_hook,
    )


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
    """Is manifest-first discovery turned on?

    Default OFF (M6 strangler). Mirrors the inline-env-read pattern
    used at ``_pipeline/runtime.py:191`` for ``MEGAPLAN_PIPELINE_AUTO``.
    """

    return os.environ.get("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0") == "1"


CANONICAL_BUILTIN_PIPELINE = "megaplan"
# Registry-maintained compatibility aliases for names persisted by older plans.
LEGACY_PIPELINE_ALIASES: dict[str, str] = {"planning": CANONICAL_BUILTIN_PIPELINE}
_NAME_ALIASES: dict[str, str] = dict(LEGACY_PIPELINE_ALIASES)

def canonical_pipeline_name(name: str) -> str:
    """Return the registry-canonical pipeline name for *name*."""

    return _NAME_ALIASES.get(name, name)


def _package_prefix_for_module_file(module_file: Path) -> str | None:
    normalised = str(module_file.resolve()).replace("\\", "/")
    arnold_megaplan_fragment = "/arnold/pipelines/megaplan/pipelines/"
    if arnold_megaplan_fragment in normalised or normalised.endswith("/arnold/pipelines/megaplan/pipelines"):
        return "arnold_pipelines.megaplan.pipelines"
    arnold_fragment = "/arnold/pipelines/"
    if arnold_fragment in normalised or normalised.endswith("/arnold/pipelines"):
        return "arnold.pipelines"
    megaplan_fragment = "/megaplan/pipelines/"
    if megaplan_fragment in normalised or normalised.endswith("/megaplan/pipelines"):
        return "arnold_pipelines.megaplan.pipelines"
    return None


def _load_trusted_pipeline_module(module_file: Path) -> Any | None:
    tier = classify(module_file, blessed_allowlist=BLESSED_ALLOWLIST)
    if tier not in (TrustGrade.AUTO_EXEC, TrustGrade.BLESSED):
        return None
    return _load_module_from_path(
        module_file,
        package_prefix=_package_prefix_for_module_file(module_file),
    )


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


def _override_catalog_from_module(module: Any) -> dict[str, Any]:
    factory = getattr(module, "override_catalog", None)
    if not callable(factory):
        return {}
    try:
        catalog = factory()
    except Exception:  # noqa: BLE001 - helper must fail closed
        return {}
    if isinstance(catalog, Mapping):
        return dict(catalog)
    return {}


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


def _reserve_out_of_tree_quota(name: str, module_file: Path, meta: dict[str, Any]) -> None:
    tenant_id = meta.get("tenant_id")
    sub_budget_usd = meta.get("sub_budget_usd")
    if not isinstance(tenant_id, str) or not isinstance(sub_budget_usd, (int, float)):
        return
    from arnold_pipelines.megaplan.runtime.budget_authority import reserve_tenant_quota

    ledger_dir = os.environ.get("MEGAPLAN_BUDGET_AUTHORITY_DIR")
    reserved = reserve_tenant_quota(
        tenant_id,
        float(sub_budget_usd),
        base_dir=Path(ledger_dir) if ledger_dir else None,
        flock=True,
        metadata={"pipeline": name, "source_path": str(module_file)},
    )
    meta["quota_reserved"] = True
    meta["sub_budget_usd"] = reserved.get("sub_budget_usd", sub_budget_usd)


@dataclass
class PipelineRegistry:
    """Map names → builder callables → Pipeline values.

    Builders return a Pipeline; the registry calls them on demand so a
    registered pipeline isn't materialised until requested. This keeps
    import cost flat regardless of how many pipelines exist.

    Discovery of Python-module pipelines runs lazily on first access
    (``get`` / ``names`` / ``describe`` / ``metadata_for`` /
    ``read_skill_md``); programmatic :meth:`register` calls bypass the
    discovery pass and stay available for tests.
    """

    builders: dict[str, PipelineBuilder] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    _discovered: bool = field(default=False, init=False)
    _module_files: dict[str, Path] = field(default_factory=dict, init=False)
    _operation_registries: dict[str, OperationRegistry] = field(default_factory=dict, init=False)
    _override_catalogs: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)

    def register(
        self,
        name: str,
        builder: PipelineBuilder,
        *,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        name = canonical_pipeline_name(name)
        if name in self.builders:
            raise ValueError(f"pipeline {name!r} already registered")
        self.builders[name] = builder
        if description:
            self.descriptions[name] = description
        meta: dict[str, Any] = {}
        if description:
            meta["description"] = description
        if metadata:
            meta.update(metadata)
        if meta:
            self.metadata[name] = meta

    def _ensure_discovered(self) -> None:
        if self._discovered:
            return
        # Set flag first to avoid recursive discovery if a build_pipeline
        # callable transitively imports the registry.
        self._discovered = True

        if _manifest_discovery_enabled():
            # Manifest-first path: consume Dispositions WITHOUT re-importing.
            # Register deferred-import builders so exec_module is gated to
            # PipelineRegistry.get(name) and to the trust-tier check there.
            for d in scan_python_pipelines():
                if d.status != "discovered" or d.cli_name is None or d.manifest is None:
                    continue
                name = canonical_pipeline_name(d.cli_name)
                if name in self.builders:
                    continue
                # Resolve package_prefix for deferred import (same logic as
                # _get_scan_roots): in_tree → derived from path, else None.
                package_prefix = _package_prefix_for_module_file(d.path)
                self.builders[name] = _make_deferred_builder(
                    d.path, package_prefix=package_prefix, cli_name=name,
                )
                meta = _manifest_metadata(name, d)
                if d.origin == "user":
                    _reserve_out_of_tree_quota(name, d.path, meta)
                description = str(meta.get("description", "") or "")
                if description:
                    self.descriptions[name] = description
                self.metadata[name] = meta
                self._module_files[name] = d.path
            return

        # Flag-OFF: legacy quad-list path (re-imports modules eagerly).
        for name, builder, meta, source_path in discover_python_pipelines():
            name = canonical_pipeline_name(name)
            if name in self.builders:
                # Either a duplicate discovered earlier or a programmatic
                # re-register.
                continue
            self.builders[name] = builder
            description = str(meta.get("description", "") or "")
            if description:
                self.descriptions[name] = description
            self.metadata[name] = dict(meta)
            self.metadata[name].setdefault("source_path", str(source_path))
            self._module_files[name] = source_path

    def get(self, name: str) -> Pipeline | None:
        """Return a built Pipeline for *name*.

        Under manifest-first discovery (M6 flag-ON), exec_module is gated
        on the path-derived trust tier: AUTO_EXEC or BLESSED proceed;
        QUARANTINED returns ``None`` and emits a UserWarning rather than
        executing arbitrary out-of-tree code. Built-ins and programmatically
        registered builders are unaffected (they bypass _ensure_discovered's
        deferred-builder path).
        """
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        builder_name = name
        if builder_name not in self.builders:
            for legacy_name, canonical_name in _NAME_ALIASES.items():
                if canonical_name == name and legacy_name in self.builders:
                    builder_name = legacy_name
                    break
        if builder_name not in self.builders:
            raise KeyError(
                f"no pipeline named {name!r}; available: {sorted(self.builders)}"
            )
        builder = self.builders[builder_name]
        # Trust-gate only when manifest discovery is on AND this builder
        # came from manifest-first discovery (deferred). Built-ins and
        # programmatic registrations bypass.
        if _manifest_discovery_enabled() and getattr(builder, "_m6_deferred", False):
            module_file = self._module_files.get(builder_name)
            if module_file is not None:
                tier = classify(module_file, blessed_allowlist=BLESSED_ALLOWLIST)
                if tier not in (TrustGrade.AUTO_EXEC, TrustGrade.BLESSED):
                    warnings.warn(
                        f"pipeline {name!r} at {module_file!s} is QUARANTINED "
                        f"(trust_tier={tier.value}); refusing to exec_module. "
                        f"Promote via BLESSED_ALLOWLIST to enable execution.",
                        UserWarning,
                        stacklevel=2,
                    )
                    return None
                if self.metadata.get(builder_name, {}).get("manifest_origin") == "user":
                    _reserve_out_of_tree_quota(
                        builder_name, module_file, self.metadata[builder_name]
                    )
        return builder()

    def names(self) -> tuple[str, ...]:
        self._ensure_discovered()
        return tuple(sorted(self.builders))

    def describe(self, name: str) -> str:
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        return self.descriptions.get(name, "")

    def metadata_for(self, name: str) -> dict[str, Any]:
        """Return the per-pipeline metadata dict (empty if unknown)."""
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        return dict(self.metadata.get(name, {}))

    def operation_registry_for(self, name: str) -> OperationRegistry:
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        cached = self._operation_registries.get(name)
        if cached is not None:
            return cached
        module_file = self._module_files.get(name)
        registry: OperationRegistry = NullOperationRegistry()
        if module_file is not None:
            module = _load_trusted_pipeline_module(module_file)
            if module is not None:
                registry = _operation_registry_from_module(module)
        self._operation_registries[name] = registry
        supported = _supported_operation_names(registry)
        if supported:
            self.metadata.setdefault(name, {})["supported_operations"] = supported
        return registry

    def supported_operations_for(self, name: str) -> frozenset[OperationKind]:
        registry = self.operation_registry_for(name)
        try:
            supported = registry.supported_operations()
        except Exception:  # noqa: BLE001 - helper must fail closed
            return frozenset()
        return _coerce_supported_operations(supported)

    def override_catalog_for(self, name: str) -> dict[str, Any]:
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        cached = self._override_catalogs.get(name)
        if cached is not None:
            return dict(cached)
        module_file = self._module_files.get(name)
        catalog: dict[str, Any] = {}
        if module_file is not None:
            module = _load_trusted_pipeline_module(module_file)
            if module is not None:
                catalog = _override_catalog_from_module(module)
        self._override_catalogs[name] = dict(catalog)
        return dict(catalog)

    def read_skill_md(self, name: str) -> str | None:
        """Return the SKILL.md contents for *name*, or ``None``.

        Returns ``None`` gracefully when no ``SKILL.md`` exists on
        disk — never raises ``FileNotFoundError`` (callers-2 /
        FLAG-READ-SKILL-MD-USER-PIPELINE).

        Layout:

        * Sibling-file modules → ``<module-parent>/<cli-name>/SKILL.md``
          (e.g. ``megaplan/pipelines/writing-panel-strict/SKILL.md``
          for ``writing_panel_strict.py``).
        * Package modules → ``<module-parent>/SKILL.md``.
        """

        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        module_file = self._module_files.get(name)
        if module_file is None:
            return None
        parent = module_file.parent
        if module_file.name == "__init__.py":
            skill_path = parent / "SKILL.md"
        else:
            skill_path = parent / name / "SKILL.md"
        try:
            return skill_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None


_GLOBAL_REGISTRY = PipelineRegistry()


def _builtin_megaplan_builder() -> Pipeline:
    from arnold_pipelines.megaplan.pipelines.planning import build_pipeline

    return build_pipeline()


def _ensure_builtin_pipelines_registered() -> None:
    """Reassert built-ins after tests or long-lived workers mutate global state."""

    if CANONICAL_BUILTIN_PIPELINE in _GLOBAL_REGISTRY.builders:
        return

    from arnold_pipelines.megaplan.pipelines import planning

    module_file = Path(planning.__file__).resolve()
    description = str(getattr(planning, "description", "") or "")
    metadata = {
        "description": description,
        "name": CANONICAL_BUILTIN_PIPELINE,
        "source_path": str(module_file),
        "supported_modes": tuple(getattr(planning, "supported_modes", ()) or ()),
        "capabilities": tuple(getattr(planning, "capabilities", ()) or ()),
        "arnold_api_version": str(getattr(planning, "arnold_api_version", "") or ""),
    }
    default_profile = getattr(planning, "default_profile", None)
    if default_profile:
        metadata["default_profile"] = default_profile
    if _manifest_discovery_enabled():
        manifest_result = read_manifest(module_file)
        if isinstance(manifest_result, Manifest):
            metadata.update(
                _manifest_metadata(
                    CANONICAL_BUILTIN_PIPELINE,
                    Disposition(
                        path=module_file,
                        origin="in_tree",
                        status="discovered",
                        reason="ok (manifest)",
                        cli_name=CANONICAL_BUILTIN_PIPELINE,
                        manifest=manifest_result,
                    ),
                )
            )

    _GLOBAL_REGISTRY.register(
        CANONICAL_BUILTIN_PIPELINE,
        _builtin_megaplan_builder,
        description=description,
        metadata=metadata,
    )
    _GLOBAL_REGISTRY._module_files[CANONICAL_BUILTIN_PIPELINE] = module_file


def register_pipeline(
    name: str,
    builder: PipelineBuilder,
    *,
    description: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _GLOBAL_REGISTRY.register(
        name, builder, description=description, metadata=metadata,
    )


def get_pipeline(name: str) -> Pipeline | None:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.get(name)


def registered_pipelines() -> tuple[str, ...]:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.names()


def describe_pipeline(name: str) -> str:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.describe(name)


def pipeline_metadata(name: str) -> dict[str, Any]:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.metadata_for(name)


def operation_registry_for(name: str) -> OperationRegistry:
    name = canonical_pipeline_name(name)
    _ensure_builtin_pipelines_registered()
    try:
        return _GLOBAL_REGISTRY.operation_registry_for(name)
    except RuntimeError:
        if name == CANONICAL_BUILTIN_PIPELINE:
            from arnold_pipelines.megaplan.pipelines.planning import operation_registry

            return operation_registry()
        raise


def supported_operations_for(name: str) -> frozenset[OperationKind]:
    name = canonical_pipeline_name(name)
    _ensure_builtin_pipelines_registered()
    try:
        return _GLOBAL_REGISTRY.supported_operations_for(name)
    except RuntimeError:
        if name == CANONICAL_BUILTIN_PIPELINE:
            from arnold_pipelines.megaplan.pipelines.planning import operation_registry

            return operation_registry().supported_operations()
        raise


def _unsupported_operation_result(kind: object) -> OperationResult:
    kind_value = kind.value if isinstance(kind, OperationKind) else str(kind)
    return OperationResult(ok=False, payload={}, errors=("unsupported", kind_value))


def dispatch_operation_for(
    plugin_id: str,
    request: OperationRequest,
) -> OperationResult:
    """Dispatch *request* through the canonical plugin operation registry.

    ``planning`` is only accepted as an explicit legacy alias for the
    canonical ``megaplan`` plugin identity. Unsupported operations fail
    closed with the exact neutral unsupported result rather than falling
    back to direct pipeline dispatch.
    """

    plugin_id = canonical_pipeline_name(plugin_id)
    supported = supported_operations_for(plugin_id)
    if request.kind not in supported:
        return _unsupported_operation_result(request.kind)
    payload = request.payload if isinstance(request.payload, Mapping) else {}
    return operation_registry_for(plugin_id).dispatch(
        OperationRequest(kind=request.kind, payload=dict(payload))
    )


def _bridge_payload(result: OperationResult, *, bridge_name: str) -> Mapping[str, Any]:
    payload = result.payload
    if not isinstance(payload, Mapping):
        raise ValueError(f"{bridge_name} requires OperationResult.payload to be a mapping")
    return payload


def _require_payload_key(
    payload: Mapping[str, Any],
    key: str,
    *,
    bridge_name: str,
) -> Any:
    if key not in payload:
        raise ValueError(f"{bridge_name} requires payload.{key}")
    return payload[key]


def _require_payload_str(
    payload: Mapping[str, Any],
    key: str,
    *,
    bridge_name: str,
) -> str:
    value = _require_payload_key(payload, key, bridge_name=bridge_name)
    if not isinstance(value, str):
        raise ValueError(f"{bridge_name} requires payload.{key} to be a string")
    return value


def _require_payload_int(
    payload: Mapping[str, Any],
    key: str,
    *,
    bridge_name: str,
) -> int:
    value = _require_payload_key(payload, key, bridge_name=bridge_name)
    if not isinstance(value, int):
        raise ValueError(f"{bridge_name} requires payload.{key} to be an int")
    return value


def phase_tuple_from_operation_result(result: OperationResult) -> tuple[int, str, str]:
    """Bridge an ``EXECUTE`` result back to the legacy tuple contract."""

    payload = _bridge_payload(result, bridge_name="phase_tuple_from_operation_result")
    return (
        _require_payload_int(
            payload, "exit_code", bridge_name="phase_tuple_from_operation_result"
        ),
        _require_payload_str(
            payload, "stdout", bridge_name="phase_tuple_from_operation_result"
        ),
        _require_payload_str(
            payload, "stderr", bridge_name="phase_tuple_from_operation_result"
        ),
    )


def resume_result_from_operation_result(
    result: OperationResult,
    *,
    plan: str,
    phase: str,
    resume_cursor: Mapping[str, Any],
    state: str | None = None,
) -> dict[str, Any]:
    """Bridge a ``RESUME`` result back to the legacy ``resume_plan()`` shape."""

    payload = dict(
        _bridge_payload(result, bridge_name="resume_result_from_operation_result")
    )
    args = _require_payload_key(
        payload, "args", bridge_name="resume_result_from_operation_result"
    )
    exit_code = _require_payload_int(
        payload, "exit_code", bridge_name="resume_result_from_operation_result"
    )
    stdout = _require_payload_str(
        payload, "stdout", bridge_name="resume_result_from_operation_result"
    )
    stderr = _require_payload_str(
        payload, "stderr", bridge_name="resume_result_from_operation_result"
    )
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError(
            "resume_result_from_operation_result requires payload.args to be a list[str]"
        )

    bridged: dict[str, Any] = {
        "success": result.ok and exit_code == 0,
        "step": "resume",
        "plan": plan,
        "phase": phase,
    }
    if bridged["success"]:
        bridged["command"] = list(args)
        if state is not None:
            bridged["state"] = state
    else:
        bridged["resume_cursor"] = dict(resume_cursor)
        bridged["exit_code"] = exit_code
        bridged["stdout"] = stdout
        bridged["stderr"] = stderr
    for key, value in payload.items():
        bridged.setdefault(key, value)
    return bridged


def control_status_result_from_operation_result(
    result: OperationResult,
    *,
    require_valid_targets: bool = False,
    require_recover_targets: bool = False,
) -> dict[str, Any]:
    """Bridge a ``STATUS_PROJECTION`` result for legacy control/status callers."""

    bridge_name = "control_status_result_from_operation_result"
    if not result.ok:
        raise ValueError(
            f"{bridge_name} requires ok=True, got errors={result.errors!r}"
        )
    payload = dict(_bridge_payload(result, bridge_name=bridge_name))
    _require_payload_key(payload, "binding", bridge_name=bridge_name)
    _require_payload_key(payload, "state_view", bridge_name=bridge_name)
    if require_valid_targets:
        _require_payload_key(payload, "valid_targets", bridge_name=bridge_name)
    if require_recover_targets:
        _require_payload_key(payload, "recover_targets", bridge_name=bridge_name)
    payload.setdefault("valid_targets", ())
    payload.setdefault("recover_targets", ())
    payload.setdefault("diagnostics", ())
    return payload


def override_catalog_for(name: str) -> dict[str, Any]:
    name = canonical_pipeline_name(name)
    _ensure_builtin_pipelines_registered()
    try:
        return _GLOBAL_REGISTRY.override_catalog_for(name)
    except RuntimeError:
        if name == CANONICAL_BUILTIN_PIPELINE:
            from arnold_pipelines.megaplan.pipelines.planning import override_catalog

            return override_catalog()
        raise


def read_pipeline_skill_md(name: str) -> str | None:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.read_skill_md(name)


def run_pipeline_by_name(
    name: str,
    *,
    plan_dir: Path,
    artifact_root: Path | None = None,
    profile: Any = None,
    mode: str = "code",
    inputs: Mapping[str, Path] | None = None,
    state: Mapping[str, Any] | None = None,
    policy: Any = None,
) -> dict[str, Any]:
    """Look up a registered pipeline and run it under the executor.

    When ``policy`` is set (a :class:`RuntimePolicy` instance), the
    walk uses ``run_pipeline_with_policy`` (stall + cost + escalate
    guarded). Otherwise the bare executor is used. Returns the
    executor's result dict (``{state, final_stage, halt_reason?}``).
    """

    from arnold_pipelines.megaplan._pipeline.executor import (
        run_pipeline,
        run_pipeline_with_policy,
    )
    from arnold_pipelines.megaplan._pipeline.types import StepContext

    pipeline = get_pipeline(name)
    artifact_root = Path(artifact_root or plan_dir)
    inputs_dict: dict[str, Any] = dict(inputs or {})
    inputs_dict.setdefault("_pipeline", canonical_pipeline_name(name))
    ctx = StepContext(
        plan_dir=Path(plan_dir),
        state=dict(state or {}),
        profile=profile,
        mode=mode,
        inputs=inputs_dict,
        budget=None,
    )
    if policy is None:
        return run_pipeline(pipeline, ctx, artifact_root=artifact_root)
    return run_pipeline_with_policy(
        pipeline, ctx, artifact_root=artifact_root, policy=policy,
    )


# ---------------------------------------------------------------------------
# Python-module pipeline discovery (T9 / Step 8)
# ---------------------------------------------------------------------------


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
        package_prefix in ("arnold.pipelines", "arnold_pipelines.megaplan.pipelines")
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


def _load_module_from_path(
    module_file: Path,
    *,
    package_prefix: str | None,
) -> Any | None:
    """Import the module at *module_file* and return the module object."""

    if package_prefix is not None and module_file.suffix == ".py" and module_file.name != "__init__.py":
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
        f"arnold_pipelines.megaplan._user_pipelines.{module_file.stem}"
        if module_file.name != "__init__.py"
        else f"arnold_pipelines.megaplan._user_pipelines.{module_file.parent.name}"
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


_SCAN_ROOTS: list[tuple[Path, str | None]] = [
    (Path(__file__).resolve().parent.parent.parent, "arnold.pipelines"),
    (Path(__file__).resolve().parent.parent / "pipelines", "arnold_pipelines.megaplan.pipelines"),
]

def _get_scan_roots() -> list[tuple[Path, str | None]]:
    """Return scan roots including the user home dir (evaluated at call time)."""
    return _SCAN_ROOTS + [(Path.home() / ".megaplan" / "pipelines", None)]


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
            if package_prefix in ("arnold.pipelines", "arnold_pipelines.megaplan.pipelines")
            else "user"
        )

        try:
            dir_entries = list(_scan_dir_for_pipeline_modules(
                pipelines_dir, package_prefix=package_prefix,
            ))
        except Exception:
            continue

        for cli_name, module_file in dir_entries:
            cli_name = canonical_pipeline_name(cli_name)
            # --- duplicate (earlier scan root wins) ---
            if cli_name in seen:
                dispositions.append(Disposition(
                    path=module_file,
                    origin=origin,
                    status="skipped",
                    reason=f"cli_name {cli_name!r} already discovered from an earlier scan root",
                    cli_name=cli_name,
                ))
                continue

            # --- manifest-first discovery (flag-gated, default OFF) ---
            if _manifest_discovery_enabled():
                manifest_result = read_manifest(module_file)
                if isinstance(manifest_result, ManifestError):
                    dispositions.append(Disposition(
                        path=module_file,
                        origin=origin,
                        status="rejected",
                        reason=f"manifest rejected: {manifest_result.reason}",
                        traceback=manifest_result.traceback,
                        cli_name=cli_name,
                        manifest=None,
                    ))
                    continue
                seen.add(cli_name)
                dispositions.append(Disposition(
                    path=module_file,
                    origin=origin,
                    status="discovered",
                    reason="ok (manifest)",
                    cli_name=cli_name,
                    manifest=manifest_result,
                ))
                continue

            # --- attempt to load ---
            tb_str: Optional[str] = None
            module: Any = None
            try:
                module = _load_module_from_path(module_file, package_prefix=package_prefix)
            except Exception:
                tb_str = traceback.format_exc()

            if module is None:
                if tb_str is None:
                    tb_str = "(module returned None — no callable build_pipeline or import failed silently)"
                dispositions.append(Disposition(
                    path=module_file,
                    origin=origin,
                    status="rejected",
                    reason="module could not be imported",
                    traceback=tb_str,
                    cli_name=cli_name,
                ))
                continue

            build = getattr(module, "build_pipeline", None)
            if not callable(build):
                dispositions.append(Disposition(
                    path=module_file,
                    origin=origin,
                    status="rejected",
                    reason=f"module loaded but build_pipeline is {type(build).__name__!r}, not callable",
                    cli_name=cli_name,
                ))
                continue

            seen.add(cli_name)
            dispositions.append(Disposition(
                path=module_file,
                origin=origin,
                status="discovered",
                reason="ok",
                cli_name=cli_name,
            ))

    return dispositions


def discover_python_pipelines() -> list[tuple[str, PipelineBuilder, dict[str, Any], Path]]:
    """Walk the in-tree + user pipeline directories and yield discovered pipelines.

    Returns a list of ``(cli_name, build_callable, metadata, source_path)``
    quads. Duplicate CLI names from later scan roots are skipped; modules
    that do not expose a callable ``build_pipeline`` attribute are skipped
    silently.

    Implementation delegates to :func:`scan_python_pipelines` for the full
    scan, then raises an aggregate error if any **in-tree** module was
    rejected (collect-then-raise, NOT fail-on-first).  Rejected **user**
    modules emit a :class:`UserWarning` and do NOT raise.

    The return shape is back-compat: list of
    ``(cli_name, build_callable, metadata, source_path)`` quads.
    """
    dispositions = scan_python_pipelines()

    # Collect rejected in-tree modules for aggregate error.
    rejected_in_tree = [d for d in dispositions if d.status == "rejected" and d.origin == "in_tree"]

    # Warn (but do not raise) for rejected user modules.
    for d in dispositions:
        if d.status == "rejected" and d.origin == "user":
            warnings.warn(
                f"user pipeline {d.path!s} could not be loaded: {d.reason}",
                UserWarning,
                stacklevel=2,
            )
        if d.status == "skipped" and d.origin == "user":
            warnings.warn(
                f"user pipeline {d.path!s} skipped: {d.reason}",
                UserWarning,
                stacklevel=2,
            )

    # Aggregate raise for rejected in-tree modules (after full scan).
    if rejected_in_tree:
        lines = [f"  {d.path}: {d.reason}" for d in rejected_in_tree]
        raise RuntimeError(
            "In-tree pipeline discovery failed for the following modules "
            "(aggregate, collect-then-raise):\n" + "\n".join(lines)
        )

    # Build back-compat quad list from discovered dispositions only.
    out: list[tuple[str, PipelineBuilder, dict[str, Any], Path]] = []

    # Flag-ON: honour manifest-first discipline — return deferred-import
    # builders sourced from Disposition.manifest rather than re-importing.
    # The :568 secondary loop is REPLACED under flag-ON so exec_module is
    # never invoked from this path.
    if _manifest_discovery_enabled():
        for d in dispositions:
            if d.status != "discovered" or d.cli_name is None or d.manifest is None:
                continue
            package_prefix = _package_prefix_for_module_file(d.path)
            builder = _make_deferred_builder(
                d.path, package_prefix=package_prefix, cli_name=d.cli_name,
            )
            meta = _manifest_metadata(d.cli_name, d)
            out.append((d.cli_name, builder, meta, d.path))
        return out

    # Flag-OFF: legacy re-import loop (preserves prior behaviour).
    # Re-derive builders and metadata from discovered paths.
    # We need the actual module objects — re-import the discovered ones.
    # To avoid double-importing, we track the scan_roots mapping.
    seen: set[str] = set()
    for pipelines_dir, package_prefix in _get_scan_roots():
        for cli_name, module_file in _scan_dir_for_pipeline_modules(
            pipelines_dir, package_prefix=package_prefix,
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
