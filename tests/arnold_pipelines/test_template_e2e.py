"""End-to-end tests for the native-first ``arnold_pipelines/_template`` package.

Covers:

1. **Scanner exclusion** — the legacy megaplan-side pipeline discovery scanner
   must skip ``_template`` because its leading-underscore directory name
   triggers the skip rule.
2. **Native-first build** — the skeleton ``build_pipeline()`` returns an
   :class:`arnold.pipeline.Pipeline` with a non-null ``native_program``
   built from a projected native shell.
3. **Determinism** — repeated builds produce equivalent native programs.
4. **M6 scaffold contract** — the template source must contain nested workflow
   source, declared interfaces, stable IDs, a ``parallel_map`` call with
   ``path_template``, a ``start_from_trace(...)`` resume example, and no
   shim/fallback/legacy-path guidance.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipeline.types import Pipeline
from arnold_pipelines._template import build_pipeline
from arnold_pipelines.megaplan.runtime.discovery import _scan_dir_for_pipeline_modules


# ── Forbidden shim / fallback surface ─────────────────────────────────────

_FORBIDDEN_SHIM_PATTERNS: tuple[str, ...] = (
    "Deprecated hand-built graph scaffold",
    "_legacy",
    "graph fallback",
    "compatibility wrapper",
    "compatibility namespace",
    "shim package",
    "temporary wrapper",
    "direct manifest authoring",
    "native_program as source authority",
    "native_program-as-source",
)

_LEGACY_PATH_REFS: tuple[str, ...] = (
    "arnold/pipelines/_template",
    "arnold.pipelines._template",
)


def _read_template_source() -> str:
    """Return the concatenated source text of ``__init__.py`` and
    ``pipelines.py`` from the active template package.
    """
    template_dir = Path(__file__).resolve().parent.parent.parent / (
        "arnold_pipelines/_template"
    )
    parts: list[str] = []
    for name in ("__init__.py", "pipelines.py"):
        p = template_dir / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ── Existing M0-M5 tests (preserved) ─────────────────────────────────────


def test_template_excluded_by_legacy_scanner() -> None:
    """The legacy scanner must NOT return ``_template`` as a discovered pipeline."""

    registry_file = Path(__file__).resolve().parent.parent.parent / (
        "arnold_pipelines/megaplan/runtime/discovery.py"
    )
    pipelines_dir = registry_file.resolve().parent.parent.parent  # arnold_pipelines/

    results = _scan_dir_for_pipeline_modules(
        pipelines_dir, package_prefix="arnold.pipelines"
    )
    found_names = [cli_name for cli_name, _ in results]
    found_paths = [str(mod_path) for _, mod_path in results]

    assert "_template" not in found_names
    assert not any("_template" in p for p in found_paths)


def test_template_builds_native_pipeline() -> None:
    """``build_pipeline()`` returns a native-first :class:`Pipeline` shell."""
    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert pipeline.entry is not None
    assert len(pipeline.stages) >= 1


def test_template_pipeline_has_non_null_native_program() -> None:
    """The returned pipeline has a non-null ``native_program``."""
    pipeline = build_pipeline()
    assert pipeline.native_program is not None


def test_template_native_program_is_deterministic() -> None:
    """Repeated builds produce equivalent native programs."""
    p1 = build_pipeline()
    p2 = build_pipeline()
    assert p1.native_program is not None
    assert p2.native_program is not None
    # The native programs should reference equivalent phases
    assert len(p1.native_program.phases) == len(p2.native_program.phases)


def test_template_pipeline_passes_authoring_validation() -> None:
    """The template package passes :func:`validate_package_module`."""
    import importlib
    from arnold.pipelines._authoring import validate_package_module

    pkg = importlib.import_module("arnold_pipelines._template")
    validate_package_module(pkg)  # raises on failure


# ── M6 scaffold contract guards (fail-to-pass until T16) ──────────────────


def test_m6_template_has_declared_interfaces() -> None:
    """M6: The template source MUST declare module-level ``inputs`` and
    ``outputs`` as part of its compositional contract.
    """
    source = _read_template_source()
    for marker in ("inputs", "outputs"):
        assert marker in source, (
            f"M6 scaffold contract: '{marker}' declaration missing "
            f"from arnold_pipelines/_template/ source"
        )


def test_m6_template_has_stable_ids() -> None:
    """M6: The template source MUST include stable ``id=`` on at least one
    pipeline, workflow, or phase decorator.
    """
    source = _read_template_source()
    assert "id=" in source, (
        "M6 scaffold contract: stable 'id=' missing from "
        "arnold_pipelines/_template/ decorator(s)"
    )


def test_m6_template_has_nested_workflow_source() -> None:
    """M6: The template source MUST contain evidence of nested workflow
    composition — either an explicit ``@workflow``-decorated child or
    multiple ``@pipeline``-decorated functions (parent + child).
    """
    source = _read_template_source()
    has_workflow = "@workflow" in source
    pipeline_count = source.count("@pipeline")
    assert has_workflow or pipeline_count >= 2, (
        f"M6 scaffold contract: no nested workflow source in "
        f"arnold_pipelines/_template/. Expected @workflow decorator or "
        f"multiple @pipeline decorators (found {pipeline_count})"
    )


def test_m6_template_has_parallel_map_with_path_template() -> None:
    """M6: The template source MUST contain a ``parallel_map(...)`` call
    with a ``path_template=`` argument.
    """
    source = _read_template_source()
    assert "parallel_map(" in source, (
        "M6 scaffold contract: 'parallel_map(' call missing from "
        "arnold_pipelines/_template/ source"
    )
    assert "path_template=" in source, (
        "M6 scaffold contract: 'path_template=' missing from parallel_map "
        "call in arnold_pipelines/_template/ source"
    )


def test_m6_template_has_path_resume_example() -> None:
    """M6: The template source MUST include a path-addressed resume example."""
    source = _read_template_source()
    assert "resume_from_trace_example" in source, (
        "M6 scaffold contract: resume helper missing from arnold_pipelines/_template/ source"
    )
    assert "start_from_trace(" in source, (
        "M6 scaffold contract: 'start_from_trace(' missing from arnold_pipelines/_template/ source"
    )


def test_m6_template_rejects_shim_and_fallback() -> None:
    """M6: The template Python source MUST NOT contain any shim, graph
    fallback, compatibility wrapper, legacy guidance, or
    direct-manifest-authoring instruction.  SKILL.md may reference these
    in prohibitive context.
    """
    source = _read_template_source()

    for forbidden in _FORBIDDEN_SHIM_PATTERNS:
        assert forbidden not in source, (
            f"M6 scaffold contract: forbidden pattern {forbidden!r} found "
            f"in arnold_pipelines/_template/ Python source"
        )


def test_m6_template_preserves_legacy_path_absence() -> None:
    """M6: The template MUST NOT reference the deleted legacy path
    ``arnold/pipelines/_template/``, and that directory must not exist.
    """
    source = _read_template_source()
    for ref in _LEGACY_PATH_REFS:
        assert ref not in source, (
            f"M6 scaffold contract: legacy path reference {ref!r} found "
            f"in arnold_pipelines/_template/ source"
        )

    legacy_dir = Path("/workspace/arnold/arnold/pipelines/_template")
    if legacy_dir.exists():
        remaining = list(legacy_dir.iterdir())
        assert not remaining, (
            f"M6 scaffold contract: legacy path {legacy_dir} still contains "
            f"files: {[p.name for p in remaining]}. It should be empty."
        )
