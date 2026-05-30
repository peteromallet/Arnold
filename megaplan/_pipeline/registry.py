"""Pipeline registry — feed in pipelines by name.

Asymmetric registration policy: the single built-in (``planning``) is
registered programmatically from its hardcoded ``_planning_builder``
callable at module import time; every other pipeline is discovered as
a Python module via :func:`discover_python_pipelines`.  Demo pipelines
(``doc-critique``, ``judges``) are not registered as built-ins; they
remain directly importable from their demo modules.

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
the registry surfaces them via :attr:`PipelineRegistry.metadata`. Any
attempt to discover a module whose CLI-visible name collides with a
hardcoded built-in is skipped with a warning (no override).

A new built-in is still three lines::

    from megaplan._pipeline.registry import register_pipeline
    register_pipeline("my-pipeline", build_my_pipeline,
                      description="…")
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from megaplan._pipeline.types import Pipeline


PipelineBuilder = Callable[[], Pipeline]


@dataclass
class Disposition:
    """Per-path result from :func:`scan_python_pipelines`.

    Fields
    ------
    path:
        Absolute path to the module file that was examined.
    origin:
        ``"in_tree"`` when the package_prefix is ``"megaplan.pipelines"``;
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


# Built-in pipeline names that discovery must never override.
_BUILTIN_NAMES: frozenset[str] = frozenset({"planning"})


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

    def register(
        self,
        name: str,
        builder: PipelineBuilder,
        *,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
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
        for name, builder, meta, source_path in discover_python_pipelines():
            if name in self.builders:
                # Either a built-in collision (caught and skipped at
                # discovery time too) or a programmatic re-register.
                continue
            self.builders[name] = builder
            description = str(meta.get("description", "") or "")
            if description:
                self.descriptions[name] = description
            self.metadata[name] = dict(meta)
            self.metadata[name].setdefault("source_path", str(source_path))
            self._module_files[name] = source_path

    def get(self, name: str) -> Pipeline:
        self._ensure_discovered()
        if name not in self.builders:
            raise KeyError(
                f"no pipeline named {name!r}; available: {sorted(self.builders)}"
            )
        return self.builders[name]()

    def names(self) -> tuple[str, ...]:
        self._ensure_discovered()
        return tuple(sorted(self.builders))

    def describe(self, name: str) -> str:
        self._ensure_discovered()
        return self.descriptions.get(name, "")

    def metadata_for(self, name: str) -> dict[str, Any]:
        """Return the per-pipeline metadata dict (empty if unknown)."""
        self._ensure_discovered()
        return dict(self.metadata.get(name, {}))

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
        * Built-ins → ``None``.
        """

        self._ensure_discovered()
        if name in _BUILTIN_NAMES:
            return None
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


def get_pipeline(name: str) -> Pipeline:
    return _GLOBAL_REGISTRY.get(name)


def registered_pipelines() -> tuple[str, ...]:
    return _GLOBAL_REGISTRY.names()


def describe_pipeline(name: str) -> str:
    return _GLOBAL_REGISTRY.describe(name)


def pipeline_metadata(name: str) -> dict[str, Any]:
    return _GLOBAL_REGISTRY.metadata_for(name)


def read_pipeline_skill_md(name: str) -> str | None:
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

    from megaplan._pipeline.executor import (
        run_pipeline,
        run_pipeline_with_policy,
    )
    from megaplan._pipeline.types import StepContext

    pipeline = get_pipeline(name)
    artifact_root = Path(artifact_root or plan_dir)
    inputs_dict: dict[str, Any] = dict(inputs or {})
    inputs_dict.setdefault("_pipeline", name)
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


def _scan_dir_for_pipeline_modules(
    pipelines_dir: Path,
    *,
    package_prefix: str | None,
) -> list[tuple[str, Path]]:
    """Return ``[(cli_name, module_file)]`` for pipelines under *pipelines_dir*.

    *package_prefix* is the dotted package path for installed packages
    (e.g. ``"megaplan.pipelines"``) or ``None`` for ad-hoc filesystem
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
            cli = _cli_name(entry.stem)
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
            cli = _cli_name(entry.name) if "_" in entry.name else entry.name
            if cli in seen:
                continue
            seen.add(cli)
            out.append((cli, init))
    return out


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
        f"megaplan._user_pipelines.{module_file.stem}"
        if module_file.name != "__init__.py"
        else f"megaplan._user_pipelines.{module_file.parent.name}"
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


def _module_metadata(module: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    description = getattr(module, "description", "")
    if isinstance(description, str) and description:
        meta["description"] = description
    default_profile = getattr(module, "default_profile", None)
    if isinstance(default_profile, str) and default_profile:
        meta["default_profile"] = default_profile
    supported_modes = getattr(module, "supported_modes", ())
    if isinstance(supported_modes, (list, tuple)):
        meta["supported_modes"] = tuple(supported_modes)
    recommended_profiles = getattr(module, "recommended_profiles", ())
    if isinstance(recommended_profiles, (list, tuple)):
        meta["recommended_profiles"] = tuple(recommended_profiles)
    return meta


_SCAN_ROOTS: list[tuple[Path, str | None]] = [
    (Path(__file__).resolve().parent.parent / "pipelines", "megaplan.pipelines"),
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
    * ``"in_tree"``  — the path came from the ``megaplan.pipelines`` scan
      root (``package_prefix == "megaplan.pipelines"``).
    * ``"user"``     — the path came from a user scan root (``package_prefix
      is None``).

    Statuses:
    * ``"discovered"``  — the module loaded successfully and exposes a
      callable ``build_pipeline``.
    * ``"rejected"``    — the module could not be loaded OR does not expose a
      callable ``build_pipeline``.
    * ``"skipped"``     — the module was excluded before loading (builtin
      name collision, duplicate in seen-set, etc.).
    """
    dispositions: list[Disposition] = []
    seen: set[str] = set()

    try:
        roots = _get_scan_roots()
    except Exception:
        return dispositions

    for pipelines_dir, package_prefix in roots:
        origin = "in_tree" if package_prefix == "megaplan.pipelines" else "user"

        try:
            dir_entries = list(_scan_dir_for_pipeline_modules(
                pipelines_dir, package_prefix=package_prefix,
            ))
        except Exception:
            continue

        for cli_name, module_file in dir_entries:
            # --- builtin collision ---
            if cli_name in _BUILTIN_NAMES:
                dispositions.append(Disposition(
                    path=module_file,
                    origin=origin,
                    status="skipped",
                    reason=f"cli_name {cli_name!r} collides with a built-in; skipping",
                    cli_name=cli_name,
                ))
                continue

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
    quads. Collisions with the hardcoded built-in name
    ``{'planning'}`` are skipped with a
    :class:`UserWarning`. Modules that do not expose a callable
    ``build_pipeline`` attribute are skipped silently.

    Implementation delegates to :func:`scan_python_pipelines` for the full
    scan, then raises an aggregate error if any **in-tree** module was
    rejected (collect-then-raise, NOT fail-on-first).  Rejected **user**
    modules emit a :class:`UserWarning` and do NOT raise.

    The return shape is back-compat: list of
    ``(cli_name, build_callable, metadata, source_path)`` quads.
    """
    dispositions = scan_python_pipelines()

    # Emit warnings for builtin collisions (preserve historical behaviour).
    for d in dispositions:
        if d.status == "skipped" and "collides with a built-in" in d.reason:
            warnings.warn(
                f"discovered pipeline module {d.path!s} would "
                f"override built-in {d.cli_name!r}; skipping",
                UserWarning,
                stacklevel=2,
            )

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

    # Aggregate raise for rejected in-tree modules (after full scan).
    if rejected_in_tree:
        lines = [f"  {d.path}: {d.reason}" for d in rejected_in_tree]
        raise RuntimeError(
            "In-tree pipeline discovery failed for the following modules "
            "(aggregate, collect-then-raise):\n" + "\n".join(lines)
        )

    # Build back-compat quad list from discovered dispositions only.
    out: list[tuple[str, PipelineBuilder, dict[str, Any], Path]] = []
    # Re-derive builders and metadata from discovered paths.
    # We need the actual module objects — re-import the discovered ones.
    # To avoid double-importing, we track the scan_roots mapping.
    seen: set[str] = set()
    for pipelines_dir, package_prefix in _get_scan_roots():
        for cli_name, module_file in _scan_dir_for_pipeline_modules(
            pipelines_dir, package_prefix=package_prefix,
        ):
            if cli_name in _BUILTIN_NAMES or cli_name in seen:
                continue
            module = _load_module_from_path(module_file, package_prefix=package_prefix)
            if module is None:
                continue
            build = getattr(module, "build_pipeline", None)
            if not callable(build):
                continue
            seen.add(cli_name)
            metadata = _module_metadata(module)
            out.append((cli_name, build, metadata, module_file))

    return out


# ---------------------------------------------------------------------------
# Built-in pipeline registered at import time.
# ---------------------------------------------------------------------------


def _planning_builder() -> Pipeline:
    from megaplan._pipeline.planning import compile_planning_pipeline
    return compile_planning_pipeline()


register_pipeline(
    "planning", _planning_builder,
    description="Production planning — runnable shape "
                "(prep→plan→critique→gate→…→review).",
)
