from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ready_templates.image import z_image
from tools import _widget_schema as tools_widget_schema
from tools import format_as_python as tools_format_as_python
from vibecomfy.porting import emitter as porting_emitter
from vibecomfy.porting import loader as porting_loader
from vibecomfy.porting import widget_schema as porting_widget_schema


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_tools_format_as_python_reexports_packaged_emitter() -> None:
    assert tools_format_as_python.format_as_python is porting_emitter.format_as_python
    assert tools_format_as_python._build_workflow_for is porting_loader.build_workflow_for

    workflow = z_image.build()
    from_tools = tools_format_as_python.format_as_python(
        workflow,
        ready_metadata=dict(z_image.READY_METADATA),
        ready_requirements=dict(z_image.READY_REQUIREMENTS),
        template_id="image/z_image",
    )
    from_package = porting_emitter.format_as_python(
        workflow,
        ready_metadata=dict(z_image.READY_METADATA),
        ready_requirements=dict(z_image.READY_REQUIREMENTS),
        template_id="image/z_image",
    )

    assert from_tools == from_package
    assert from_tools.startswith("# vibecomfy: generated")


def test_tools_widget_schema_reexports_packaged_schema() -> None:
    assert tools_widget_schema.WIDGET_SCHEMA is porting_widget_schema.WIDGET_SCHEMA
    assert tools_widget_schema.resolve_widget_name is porting_widget_schema.resolve_widget_name
    assert porting_widget_schema.resolve_widget_name("KSampler", 1) is None
    assert porting_widget_schema.resolve_widget_name("KSampler", 2) == "steps"
    assert porting_widget_schema.resolve_widget_name("UnknownNode", 3) == "widget_3"


def test_tools_format_as_python_module_cli_smoke_for_ready_template() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.format_as_python",
            "ready_templates/image/z_image.py",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.stderr == ""
    assert result.stdout.startswith("# vibecomfy: generated")
    assert "def build() -> VibeWorkflow:" in result.stdout
    assert "READY_METADATA" in result.stdout


def test_convert_ready_templates_dry_run_reemits_representative_ready_templates() -> None:
    for template_id in ("image/z_image", "video/ltx2_3_t2v"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.convert_ready_templates",
                "--template",
                template_id,
                "--dry-run",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        assert template_id in result.stdout
        assert "parse  build  validate" in result.stdout
        assert " ok     ok     ok " in result.stdout
        assert "Converted 1/1" in result.stdout


def test_convert_ready_templates_all_dry_run_keeps_existing_templates_skipped() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.convert_ready_templates",
            "--all",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "image/z_image" in result.stdout
    assert "manual" in result.stdout
    assert " skip   skip   skip " in result.stdout
    assert "video/ltx2_3_t2v" in result.stdout
    assert "converted" in result.stdout
