"""Tests for ``arnold.pipeline.resources`` (M3a T6)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold.pipeline.resources import (
    PipelineResourceBundle,
    PromptSource,
    prompt_lookup_candidates,
    resolve_prompt,
    resolve_bundle_prompt,
)
from arnold.pipeline.types import StepContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(**overrides: Any) -> StepContext:
    kwargs: dict[str, Any] = {
        "artifact_root": "/tmp/test",
        "state": {},
        "inputs": {},
        **overrides,
    }
    return StepContext(**kwargs)


# ---------------------------------------------------------------------------
# PipelineResourceBundle
# ---------------------------------------------------------------------------


class TestPipelineResourceBundle:
    def test_constructor_sets_fields(self) -> None:
        base = Path("/tmp/base")
        prompt = Path("/tmp/base/prompts")
        resources = {"model": "gpt-4"}
        bundle = PipelineResourceBundle(
            base_dir=base,
            prompt_dir=prompt,
            resources=resources,
        )
        assert bundle.base_dir == base
        assert bundle.prompt_dir == prompt
        assert bundle.resources == resources

    def test_default_resources_is_empty(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp"),
            prompt_dir=Path("/tmp/prompts"),
        )
        assert bundle.resources == {}
        assert bundle.prompts == {}

    def test_from_module_resolves_relative_prompt_dir(self) -> None:
        bundle = PipelineResourceBundle.from_module(
            "/some/pkg/pipeline.py",
            prompt_dir="prompts",
        )
        assert bundle.base_dir == Path("/some/pkg")
        assert bundle.prompt_dir == Path("/some/pkg/prompts")

    def test_from_module_custom_resources(self) -> None:
        bundle = PipelineResourceBundle.from_module(
            "/some/pkg/pipeline.py",
            prompt_dir="my_prompts",
            resources={"key": "val"},
            prompts={"critique": "Be sharp."},
        )
        assert bundle.prompt_dir == Path("/some/pkg/my_prompts")
        assert bundle.resources == {"key": "val"}
        assert bundle.prompts == {"critique": "Be sharp."}

    def test_resolve_prompt_path(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp"),
            prompt_dir=Path("/tmp/prompts"),
        )
        path = bundle.resolve_prompt_path("critique.md")
        assert path == Path("/tmp/prompts/critique.md")


# ---------------------------------------------------------------------------
# resolve_prompt
# ---------------------------------------------------------------------------


class TestResolvePrompt:
    def test_callable_source(self) -> None:
        def my_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
            return f"Hello from {params.get('who', 'world')}"

        result = resolve_prompt(my_prompt, _ctx(), {"who": "test"})
        assert result == "Hello from test"

    def test_callable_source_default_params(self) -> None:
        def simple(ctx: StepContext, params: Mapping[str, Any]) -> str:
            return "static"

        result = resolve_prompt(simple, _ctx())
        assert result == "static"

    def test_inline_string_source(self) -> None:
        result = resolve_prompt("You are a helpful assistant.", _ctx())
        assert result == "You are a helpful assistant."

    def test_md_file_source_found_via_inputs(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Test Prompt\nBe concise.")
            md_path = f.name

        try:
            ctx = _ctx(inputs={"test_prompt": md_path})
            result = resolve_prompt("test_prompt.md", ctx)
            assert result == "# Test Prompt\nBe concise."
        finally:
            Path(md_path).unlink()

    def test_md_file_source_found_absolute(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Absolute prompt")
            md_path = f.name

        try:
            result = resolve_prompt(md_path, _ctx())
            assert result == "# Absolute prompt"
        finally:
            Path(md_path).unlink()

    def test_md_file_source_not_found(self) -> None:
        result = resolve_prompt("nonexistent.md", _ctx())
        assert "[prompt file not found:" in result

    def test_non_string_non_callable_fallback(self) -> None:
        # This shouldn't happen with the type alias, but resolve_prompt
        # is defensive.
        result = resolve_prompt(42, _ctx())  # type: ignore[arg-type]
        assert result == "42"


class TestBundlePromptResolution:
    def test_prompt_lookup_candidates_match_legacy_precedence(self) -> None:
        assert prompt_lookup_candidates(
            "critique", mode="doc", pipeline="alpha"
        ) == (
            "alpha/critique:doc",
            "alpha/critique",
            "critique:doc",
            "critique",
        )

    def test_resolve_prompt_source_prefers_pipeline_and_mode(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp/base"),
            prompt_dir=Path("/tmp/base/prompts"),
            prompts={
                "alpha/critique:doc": "PIPELINE+MODE",
                "alpha/critique": "PIPELINE",
                "critique:doc": "MODE",
                "critique": "DEFAULT",
            },
        )

        source = bundle.resolve_prompt_source(
            "critique", mode="doc", pipeline="alpha"
        )
        assert source == "PIPELINE+MODE"

    def test_resolve_prompt_source_falls_through_precedence(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp/base"),
            prompt_dir=Path("/tmp/base/prompts"),
            prompts={
                "alpha/critique": "PIPELINE",
                "critique:doc": "MODE",
                "critique": "DEFAULT",
            },
        )

        assert (
            bundle.resolve_prompt_source("critique", mode="doc", pipeline="alpha")
            == "PIPELINE"
        )
        assert (
            bundle.resolve_prompt_source("critique", mode="doc", pipeline="beta")
            == "MODE"
        )
        assert bundle.resolve_prompt_source("critique", mode="code") == "DEFAULT"

    def test_resolve_bundle_prompt_renders_callable_from_bundle(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp/base"),
            prompt_dir=Path("/tmp/base/prompts"),
            prompts={
                "alpha/revise:doc": lambda ctx, params: (
                    f"{ctx.mode}:{params.get('flag', 'none')}"
                )
            },
        )
        ctx = _ctx(mode="doc", inputs={"_pipeline": "alpha"})

        rendered = resolve_bundle_prompt(
            bundle,
            "revise",
            ctx,
            params={"flag": "tighten"},
        )
        assert rendered == "doc:tighten"

    def test_resolve_bundle_prompt_reads_markdown_relative_to_bundle(
        self, tmp_path: Path
    ) -> None:
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "critique.md").write_text(
            "Bundle markdown prompt", encoding="utf-8"
        )
        bundle = PipelineResourceBundle(
            base_dir=tmp_path,
            prompt_dir=prompt_dir,
            prompts={"critique": "critique.md"},
        )
        ctx = _ctx()
        rendered = resolve_bundle_prompt(bundle, "critique", ctx)
        assert rendered == "Bundle markdown prompt"

    def test_render_prompt_method_uses_bundle_mapping(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp/base"),
            prompt_dir=Path("/tmp/base/prompts"),
            prompts={"critique": "Bundle default"},
        )

        assert bundle.render_prompt("critique", _ctx()) == "Bundle default"

    def test_missing_bundle_prompt_key_raises(self) -> None:
        bundle = PipelineResourceBundle(
            base_dir=Path("/tmp/base"),
            prompt_dir=Path("/tmp/base/prompts"),
        )
        with pytest.raises(KeyError, match="no prompt registered"):
            bundle.resolve_prompt_source("unknown", mode="doc", pipeline="alpha")


# ---------------------------------------------------------------------------
# Boundary
# ---------------------------------------------------------------------------


class TestResourcesBoundary:
    def test_resources_module_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "resources.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"resources.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"resources.py imports from megaplan: {node.module!r}"
                    )

    def test_resources_module_has_no_forbidden_literals(self) -> None:
        import ast
        from pathlib import Path as P

        forbidden = frozenset(
            {"planning", "proceed", "iterate", "tiebreaker", "escalate"}
        )
        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "resources.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in forbidden, (
                    f"resources.py contains forbidden literal: {node.value!r}"
                )
