"""Minimal configured pipeline registry for Arnold.

This module provides a policy-free :class:`PipelineRegistry` that stores
builder callables, metadata, and discovery hooks.  It is parameterised
via explicit constructor inputs — ``scan_roots``, ``package_prefixes``,
``alias_map``, ``trust_policy``, and ``resource_path_policy`` — so that
every Megaplan opinion (discovery paths, budget authority, operation
fallbacks, planning override catalogs) is injected by the consumer rather
than baked in.

The 1131-line ``megaplan/_pipeline/registry.py`` remains the authority
for Megaplan-specific discovery, budget reservation, operation-registry
fallbacks, and planning override catalogs.  That module wraps (or
subclasses) this core as its bridge.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, runtime_checkable

from arnold.pipeline.types import Pipeline

#: Signature for builder callables stored in the registry.
PipelineBuilder = Callable[[], Pipeline]

RegistrationKind = Literal["native", "graph_compatibility", "unknown"]
"""Classification for a registered pipeline's execution contract."""


# ---------------------------------------------------------------------------
# Pluggable policy Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class TrustPolicy(Protocol):
    """Protocol for trust-tier classification of a pipeline source path.

    Implementations return a trust tier string (e.g. ``"blessed"``,
    ``"auto_exec"``, ``"quarantined"``) for a given module file path.
    The registry core stores the policy but never interprets the
    returned tier — interpretation belongs to the consuming runtime.
    """

    def classify(self, module_file: Path, *, blessed_allowlist: frozenset[str]) -> str:
        ...


@runtime_checkable
class ResourcePathPolicy(Protocol):
    """Protocol for resolving resource-relative paths from a module file.

    Implementations return a resource directory (e.g. prompts, profiles)
    given a module file and a resource label.  The registry stores the
    policy but never calls it directly — consumers invoke it when
    resolving bundle paths.
    """

    def resolve(self, module_file: Path, label: str) -> Path | None:
        ...


# ---------------------------------------------------------------------------
# Lazy discovery hook
# ---------------------------------------------------------------------------

DiscoveryHook = Callable[["PipelineRegistry"], None]
"""A callable that populates *registry* with discovered pipelines.

Called once, lazily, on first access to :meth:`PipelineRegistry.get`,
:meth:`PipelineRegistry.names`, or :meth:`PipelineRegistry.metadata_for`.
The hook receives the registry instance so it can call
:meth:`PipelineRegistry.register` for each discovered entry.
"""


# ---------------------------------------------------------------------------
# PipelineRegistry
# ---------------------------------------------------------------------------


@dataclass
class PipelineRegistry:
    """Map pipeline names → builder callables → :class:`Pipeline` values.

    Builders return a :class:`Pipeline`; the registry calls them on demand
    so a registered pipeline is not materialised until requested.  This
    keeps import cost flat regardless of how many pipelines exist.

    Discovery is delegated to an optional *discovery_hook* — a callable
    that the consuming runtime supplies.  The hook is invoked lazily on
    first access and is responsible for calling :meth:`register` for
    each discovered pipeline.

    Every Megaplan opinion (scan roots, budget reservation, operation
    fallbacks, override catalogs) is injected via the constructor::

        registry = PipelineRegistry(
            alias_map={"planning": "megaplan"},
            trust_policy=my_trust_classifier,
            resource_path_policy=my_resource_resolver,
            discovery_hook=scan_and_register_megaplan_pipelines,
        )
    """

    # ── storage ──────────────────────────────────────────────────────────

    builders: dict[str, PipelineBuilder] = field(default_factory=dict)
    """Name → builder callable."""

    descriptions: dict[str, str] = field(default_factory=dict)
    """Name → human-readable description."""

    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Name → opaque metadata dict (description, profile, modes, …)."""

    registration_kinds: dict[str, RegistrationKind] = field(default_factory=dict)
    """Name → execution-contract classification for registered pipelines."""

    _module_files: dict[str, Path] = field(default_factory=dict, init=False)
    """Name → source module file path (set by discovery hook)."""

    # ── discovery ────────────────────────────────────────────────────────

    discovery_hook: DiscoveryHook | None = None
    """Optional lazy-discovery callable.  Invoked once on first access."""

    _discovered: bool = field(default=False, init=False)
    """Has the discovery hook been invoked?"""

    # ── configuration ────────────────────────────────────────────────────

    scan_roots: tuple[Path, ...] = ()
    """Root directories scanned by the discovery hook."""

    package_prefixes: tuple[str, ...] = ()
    """Dotted package prefixes for in-tree module resolution."""

    alias_map: Mapping[str, str] = field(default_factory=dict)
    """Legacy-name → canonical-name mapping (e.g. ``{"planning": "megaplan"}``)."""

    trust_policy: TrustPolicy | None = None
    """Pluggable trust-tier classifier for source paths."""

    resource_path_policy: ResourcePathPolicy | None = None
    """Pluggable resolver for resource directories (prompts, profiles, …)."""

    # ── methods ──────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        builder: PipelineBuilder,
        *,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
        module_file: Path | None = None,
        registration_kind: RegistrationKind = "unknown",
    ) -> None:
        """Register a pipeline by *name*.

        Raises ``ValueError`` when *name* is already registered.
        """
        name = self._canonical_name(name)
        if name in self.builders:
            raise ValueError(f"pipeline {name!r} already registered")
        self.builders[name] = builder
        self.registration_kinds[name] = registration_kind
        if description:
            self.descriptions[name] = description
        meta: dict[str, Any] = {}
        if description:
            meta["description"] = description
        if metadata:
            meta.update(metadata)
        if meta:
            self.metadata[name] = meta
        if module_file is not None:
            self._module_files[name] = module_file

    def _canonical_name(self, name: str) -> str:
        """Resolve *name* through the alias map."""
        return self.alias_map.get(name, name)

    def _ensure_discovered(self) -> None:
        """Invoke the discovery hook once (idempotent)."""
        if self._discovered:
            return
        self._discovered = True
        if self.discovery_hook is not None:
            self.discovery_hook(self)

    # ── query methods ────────────────────────────────────────────────────

    def get(self, name: str) -> Pipeline | None:
        """Return a built :class:`Pipeline` for *name*.

        Returns ``None`` when the pipeline is not registered.  Discovery
        runs lazily on first call.
        """
        name = self._canonical_name(name)
        self._ensure_discovered()
        builder = self.builders.get(name)
        if builder is None:
            return None
        return builder()

    def names(self) -> tuple[str, ...]:
        """Return the sorted tuple of registered pipeline names."""
        self._ensure_discovered()
        return tuple(sorted(self.builders))

    def describe(self, name: str) -> str:
        """Return the human-readable description for *name* (or ``""``)."""
        name = self._canonical_name(name)
        self._ensure_discovered()
        return self.descriptions.get(name, "")

    def metadata_for(self, name: str) -> dict[str, Any]:
        """Return a copy of the per-pipeline metadata dict (empty if unknown)."""
        name = self._canonical_name(name)
        self._ensure_discovered()
        return dict(self.metadata.get(name, {}))

    def registration_kind_for(self, name: str) -> RegistrationKind | None:
        """Return the execution-contract classification for *name*, if known."""
        name = self._canonical_name(name)
        self._ensure_discovered()
        return self.registration_kinds.get(name)

    def module_file_for(self, name: str) -> Path | None:
        """Return the source module file path for *name*, or ``None``."""
        name = self._canonical_name(name)
        self._ensure_discovered()
        return self._module_files.get(name)

    def __contains__(self, name: str) -> bool:
        """``name in registry`` — has the pipeline been registered?"""
        name = self._canonical_name(name)
        self._ensure_discovered()
        return name in self.builders
