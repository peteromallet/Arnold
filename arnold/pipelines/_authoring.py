"""Package-authoring types and structural protocol for Arnold pipeline packages.

This module defines the canonical types that package authors implement
and the structural protocol that discovery/validation tooling uses to
inspect them.  It is derived from the in-process reference package and
the planning-driver reference package, and formalizes the divergences
observed between them:

* **evidence_pack** declares a plain ``str`` driver, a ``module:name``
  entrypoint, aliases ``build_pipeline``, exports ``EvidencePackHooks``,
  ``resume_evidence_pack``, and ``build_continuation_pipeline``, but
  omits ``default_profile`` and ``supported_modes`` entirely.
* The planning-driver reference declares a ``tuple[str, str]`` driver, a bare-name
  entrypoint, ``default_profile=None``, and ``supported_modes``, but
  keeps hooks and resume internal (no module-level exports for either).

The package-authoring contract treats ``default_profile`` and
``supported_modes`` as recommended (``NotRequired`` in the TypedDict),
while the static manifest reader in
``arnold/pipeline/discovery/manifest.py`` treats them as required.
Packages that omit them will pass runtime validation but fail static
manifest-first discovery — authors should declare both (even as
``None`` / empty tuple) to satisfy both paths.

The ``PipelinePackage`` Protocol is ``@runtime_checkable`` and
describes the *optional* extension surface: hooks, resume, and
``build_continuation_pipeline``.  The validator uses ``isinstance``
checks against this protocol at runtime.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, NotRequired, Protocol, TypedDict, runtime_checkable

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.types import Pipeline


class PackageMetadata(TypedDict):
    """TypedDict capturing the metadata surface of an Arnold pipeline package module.

    This is the canonical shape that discovery and validation tooling
    expects.  Required fields mirror the authoring contract's required
    columns; recommended fields use :data:`typing.NotRequired`.

    Friction documented from the two reference packages:

    * ``evidence_pack`` uses a bare string for ``driver``
      (``"in_process"``) and a ``module:name`` string for
      ``entrypoint`` (``"arnold.pipelines.evidence_pack:build_pipeline"``).
      It omits ``default_profile`` and ``supported_modes``.
    * The planning-driver reference uses a tuple for ``driver``
      (for example, a package name plus driver mode) and a bare name for ``entrypoint``
      (``"build_pipeline"``).  It declares ``default_profile=None`` and
      ``supported_modes=("code", "doc", "creative", "joke")``.
    """

    driver: str | tuple[str, ...]
    """Execution driver identity.

    Accepts a plain string (evidence_pack style) or a tuple of strings
    (planning-driver style).  The registry uses this to route pipeline
    execution to the correct driver adapter.
    """

    entrypoint: str
    """Pipeline factory callable reference.

    Two formats are accepted:

    * **bare name** — a module-level callable name resolved via
      ``getattr(module, entrypoint)`` (planning-driver style).
    * **module:name** — a colon-delimited string where the part before
      the colon is a fully-qualified module name and the part after is
      the bare callable name (evidence_pack style).
    """

    default_profile: NotRequired[str]
    """Default profile name when the caller does not specify one.

    Recommended per the authoring contract, **required** by the static
    manifest reader.  May be ``None``.

    The in-process reference omits this field; the planning-driver reference
    declares it as ``None``.
    """

    supported_modes: NotRequired[tuple[str, ...]]
    """Modes explicitly supported by this pipeline package.

    Recommended per the authoring contract, **required** by the static
    manifest reader.  May be an empty tuple.

    The in-process reference omits this field; the planning-driver reference
    declares explicit supported modes.
    """


@runtime_checkable
class PipelinePackage(Protocol):
    """Structural protocol for optional extension hooks on an Arnold pipeline package.

    This protocol describes the **optional** extension surface that a
    pipeline package module *may* expose.  The validator uses
    ``isinstance(module, PipelinePackage)`` at runtime to detect and
    catalogue these capabilities.

    The protocol is deliberately minimal and permissive — it only
    requires module-level attributes that are *observable* via
    ``getattr``.  Implementations may provide any subset.

    Friction documented from the two reference packages:

    * **evidence_pack** exports ``EvidencePackHooks`` (a
      ``NullExecutorHooks`` subclass), ``resume_evidence_pack`` (a
      resume driver), ``EvidencePackResumeError``, and
      ``EvidencePackResumeResult`` at module level, plus
      ``build_continuation_pipeline``.  All are directly importable.
    * The planning-driver reference keeps hooks and resume internal; neither is
      importable from its package root.  The module
      provides no ``build_continuation_pipeline``.  These are all
      legitimate design choices — the protocol must not penalize a
      package for keeping internals opaque.
    """

    hooks: Any | None
    """Optional module-level hooks class or instance.

    When present, should be a subclass of
    :class:`arnold.pipeline.hooks.ExecutorHooks` (or
    :class:`arnold.pipeline.hooks.NullExecutorHooks`) that
    implements lifecycle callbacks for the canonical executor.

    The in-process reference exposes ``EvidencePackHooks``; the planning-driver
    reference does not
    expose hooks at module level.
    """

    resume: Any | None
    """Optional module-level resume driver.

    When present, should be a callable that accepts a suspension
    artifact and returns a resume result.

    evidence_pack exposes ``resume_evidence_pack``,
    ``EvidencePackResumeError``, and ``EvidencePackResumeResult``;
    The planning-driver reference does not expose resume at module level.
    """

    build_continuation_pipeline: Any | None
    """Optional nullary callable returning a continuation ``Pipeline``.

    When present, enables the CLI ``resume`` command and the
    registry to construct a pipeline graph for resuming a
    previously suspended run without re-running completed stages.

    The in-process reference exports this; the planning-driver reference does not.
    """


# ── Package validator ─────────────────────────────────────────────────────


def validate_package_module(module: Any) -> list[str]:
    """Validate an already-imported package module against the authoring contract.

    Required checks (absent/missing → ``\"error:\"`` prefix):
      * ``name`` — non-empty string.
      * ``description`` — non-empty string.
      * ``driver`` — ``str`` or ``tuple[str, ...]``.
      * ``entrypoint`` — bare name or ``\"module:name\"`` string that
        resolves to a callable.
      * ``arnold_api_version`` — non-empty string.
      * ``capabilities`` — non-empty ``tuple[str, ...]``.
      * ``build_pipeline`` — nullary/effectively-nullary callable that
        returns a :class:`Pipeline`.

    The entrypoint is resolved at runtime:
      * Bare name (planning-driver style): ``getattr(module, entrypoint)``.
      * ``module:name`` (evidence_pack style): the part before the colon
        is imported via :func:`importlib.import_module`, then the part
        after the colon is resolved via ``getattr``.

    After resolving ``build_pipeline()``, the resulting :class:`Pipeline`
    is passed to :func:`arnold.pipeline.validator.validate`.  Any graph
    defects are reported as ``\"error:\"`` lines.

    Recommended fields whose absence is reported as ``\"info:\"``:
      * ``default_profile``
      * ``supported_modes``
      * ``hooks``
      * ``resume``
      * ``build_continuation_pipeline``

    Returns a list of diagnostic strings, empty iff every required check
    passes and the built pipeline graph is defect-free.
    """
    messages: list[str] = []

    # ── required field checks ────────────────────────────────────────
    _check_required_str(module, "name", messages)
    _check_required_str(module, "description", messages)
    _check_required_str(module, "arnold_api_version", messages)

    # driver: str | tuple[str, ...]
    driver = getattr(module, "driver", None)
    if driver is None:
        messages.append("error: missing required field 'driver'")
    elif not isinstance(driver, (str, tuple)):
        messages.append(
            "error: field 'driver' must be str or tuple[str, ...], "
            f"got {type(driver).__name__}"
        )

    # capabilities: non-empty tuple[str, ...]
    capabilities = getattr(module, "capabilities", None)
    if capabilities is None:
        messages.append("error: missing required field 'capabilities'")
    elif not isinstance(capabilities, tuple) or not capabilities:
        messages.append(
            "error: field 'capabilities' must be a non-empty tuple[str, ...], "
            f"got {type(capabilities).__name__}"
        )
    elif not all(isinstance(c, str) for c in capabilities):
        messages.append("error: all 'capabilities' items must be str")

    # ── entrypoint resolution ────────────────────────────────────────
    entrypoint_raw = getattr(module, "entrypoint", None)
    if entrypoint_raw is None:
        messages.append("error: missing required field 'entrypoint'")
    elif not isinstance(entrypoint_raw, str):
        messages.append(
            "error: field 'entrypoint' must be a str, "
            f"got {type(entrypoint_raw).__name__}"
        )
    else:
        _resolve_entrypoint(module, entrypoint_raw, messages)

    # ── build_pipeline resolution ────────────────────────────────────
    build_pipeline_fn = getattr(module, "build_pipeline", None)
    if build_pipeline_fn is None:
        messages.append("error: missing required callable 'build_pipeline'")
    elif not callable(build_pipeline_fn):
        messages.append(
            "error: 'build_pipeline' must be callable, "
            f"got {type(build_pipeline_fn).__name__}"
        )
    else:
        # Attempt to build the pipeline and validate the graph.
        try:
            pipeline_obj = build_pipeline_fn()
        except Exception as exc:
            messages.append(
                f"error: build_pipeline() raised {type(exc).__name__}: {exc}"
            )
        else:
            if pipeline_obj is None:
                messages.append("error: build_pipeline() returned None")
            else:
                from arnold.pipeline.validator import validate

                diag = validate(pipeline_obj)
                for defect in diag.defects:
                    messages.append(f"error: {defect}")

    # ── recommended field checks (info-level) ────────────────────────
    _check_recommended(module, "default_profile", messages)
    _check_recommended(module, "supported_modes", messages)
    _check_recommended(module, "hooks", messages)
    _check_recommended(module, "resume", messages)
    _check_recommended(module, "build_continuation_pipeline", messages)

    return messages


def _check_required_str(module: Any, field: str, messages: list[str]) -> None:
    """Validate a required string field is present and non-empty."""
    value = getattr(module, field, None)
    if value is None:
        messages.append(f"error: missing required field {field!r}")
    elif not isinstance(value, str):
        messages.append(
            f"error: field {field!r} must be str, got {type(value).__name__}"
        )
    elif not value.strip():
        messages.append(f"error: field {field!r} must be a non-empty str")


def _check_recommended(module: Any, field: str, messages: list[str]) -> None:
    """Report absence of a recommended field as an info-level diagnostic."""
    if not hasattr(module, field):
        messages.append(f"info: recommended field {field!r} is not declared")


def _resolve_entrypoint(
    module: Any, entrypoint: str, messages: list[str]
) -> Any:
    """Resolve an entrypoint string to a callable.

    Two formats are accepted:
      * Bare name → ``getattr(module, name)``.
      * ``module:name`` → import the module portion, then ``getattr`` the name.
    """
    if ":" in entrypoint:
        mod_name, _, attr_name = entrypoint.partition(":")
        mod_name = mod_name.strip()
        attr_name = attr_name.strip()
        if not mod_name:
            messages.append(
                f"error: entrypoint {entrypoint!r} has empty module part before ':'"
            )
            return None
        if not attr_name:
            messages.append(
                f"error: entrypoint {entrypoint!r} has empty name part after ':'"
            )
            return None
        try:
            target_mod = import_module(mod_name)
        except Exception as exc:
            messages.append(
                f"error: entrypoint module {mod_name!r} could not be imported: {exc}"
            )
            return None
        fn = getattr(target_mod, attr_name, None)
        if fn is None:
            messages.append(
                f"error: entrypoint {entrypoint!r}: module {mod_name!r} "
                f"has no attribute {attr_name!r}"
            )
            return None
    else:
        fn = getattr(module, entrypoint, None)
        if fn is None:
            messages.append(
                f"error: entrypoint {entrypoint!r} not found on module"
            )
            return None

    if not callable(fn):
        messages.append(
            f"error: entrypoint {entrypoint!r} resolved but is not callable "
            f"(got {type(fn).__name__})"
        )
        return None

    return fn


# ── Skeleton pipeline builder ─────────────────────────────────────────────


def build_skeleton_pipeline(
    name: str, description: str = ""
) -> Pipeline:
    """Build a minimal valid :class:`Pipeline` with a single no-op step.

    Uses :class:`PipelineBuilder` to construct a pipeline containing one
    inline no-op implementation.  The step always halts, producing a valid,
    instantly-terminating graph.

    This helper is intended for package-authoring templates (e.g. a
    ``_template.py`` that package authors can copy and customise) and for
    unit tests that need a known-valid pipeline fixture.
    """
    from arnold.pipeline.types import Edge, Stage, StepResult

    class _NoOpStep:
        """Inline no-op step that always halts immediately."""

        name: str = "noop"
        kind: str = "noop"

        def run(self, ctx):
            return StepResult(next="halt")

    builder = PipelineBuilder(name=name, description=description)
    stage = Stage(
        name="noop",
        step=_NoOpStep(),
        edges=(Edge(label="halt", target="halt"),),
    )
    builder.add_stage(stage)
    return builder.build()
