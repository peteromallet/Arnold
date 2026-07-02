from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from arnold.pipeline import NativeProgram, Pipeline as NativePipeline
from arnold_pipelines.discovery import discover_shipped_pipelines


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_arnold_docs.py"


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_arnold_docs", GENERATOR_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _by_id() -> dict[str, object]:
    return {info.id: info for info in discover_shipped_pipelines()}


def _example_path(generator: ModuleType, pipeline_id: str) -> Path:
    slug = pipeline_id.replace(".", "-").replace("_", "-")
    return generator.DEFAULT_DOCS_ROOT / generator.EXAMPLES_DIR / f"{slug}.md"


def test_workflow_entries_still_validate_as_workflow_manifests() -> None:
    generator = _load_generator()
    info = _by_id()["evidence_pack_verifier"]

    # evidence_pack_verifier migrated to native in M6; validate as loadable-native
    assert info.load_state == "loadable-native"
    pipeline = generator._validate_native_builder(info)
    assert isinstance(pipeline, NativePipeline)
    assert isinstance(pipeline.native_program, NativeProgram)

    rendered_path, rendered = generator._render_example(info)
    assert rendered_path == _example_path(generator, "evidence_pack_verifier")
    assert "## Native builder report" in rendered
    assert "`build_pipeline()` returns `arnold.pipeline.Pipeline` with `NativeProgram`" in rendered


def test_loadable_native_entries_validate_through_native_pipeline_contract() -> None:
    generator = _load_generator()
    info = _by_id()["creative"]

    pipeline = generator._validate_native_builder(info)
    assert isinstance(pipeline, NativePipeline)
    assert isinstance(pipeline.native_program, NativeProgram)

    rendered_path, rendered = generator._render_example(info)
    assert rendered_path == _example_path(generator, "creative")
    assert "## Native builder report" in rendered
    assert "`build_pipeline()` returns `arnold.pipeline.Pipeline` with `NativeProgram`" in rendered
    assert "| Builder target | arnold_pipelines.megaplan.pipelines.creative:build_pipeline|" in rendered


def test_deleted_epic_blitz_is_not_rendered_as_public_example() -> None:
    generator = _load_generator()

    assert "epic-blitz" not in _by_id()
    examples = generator.render_examples()
    assert _example_path(generator, "epic-blitz") not in examples


def test_required_public_examples_render_for_workflow_and_native_sources() -> None:
    generator = _load_generator()
    examples = generator.render_examples()

    required_ids = {
        "evidence_pack_verifier",
        "megaplan",
        "creative",
        "doc",
        "live-supervisor",
        "select-tournament",
        "writing-panel-strict",
    }
    missing = [pipeline_id for pipeline_id in required_ids if _example_path(generator, pipeline_id) not in examples]
    assert not missing


def test_workflow_template_example_renders_dry_run_report() -> None:
    generator = _load_generator()
    info = _by_id()["my-pipeline"]

    assert info.builder_contract == "native"
    assert info.load_state == "loadable-native"  # template migrated to native-first in M6

    rendered_path, rendered = generator._render_example(info)
    assert rendered_path == _example_path(generator, "my-pipeline")
    assert "## Source Pack" in rendered
    assert "| Contract | native|" in rendered
    assert "| Load state | loadable-native|" in rendered


def test_reference_registry_is_stable_and_reports_non_workflow_identities() -> None:
    generator = _load_generator()

    first = generator.render_reference()
    second = generator.render_reference()

    assert first == second
    assert "| megaplan.creative | creative | native:creative | arnold_pipelines/megaplan/pipelines/creative | keep|" in first
    # deliberation and folder_audit are public native packages with registry IDs; they appear in the reference
    assert "| deliberation | deliberation | native:deliberation | arnold/pipelines/deliberation | keep|" in first
    assert "| folder_audit | folder-audit | native:folder-audit | arnold/pipelines/folder_audit | keep|" in first
    assert "| evidence_pack.verifier | evidence_pack_verifier | native:evidence_pack |" in first


def test_composed_rules_require_workflow_first_authoring() -> None:
    generator = _load_generator()
    composed = generator.render_composed_rules()

    assert composed
    for path, text in composed.items():
        assert "native-first" in text
        assert "@pipeline" in text
        assert "NativeProgram" in text
        assert "shim packages" in text  # disallowed
        assert "workflow-first" not in text
