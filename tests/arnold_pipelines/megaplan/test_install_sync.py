"""Tests for the T-0301 content-addressed dependency-generation module
(``cloud.install_sync`` — the retired editable-install sync path's
successor)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.install_sync import (
    EditableInstallRetiredError,
    GenerationError,
    apply_install_sync,
    compute_venv_digest,
    ensure_dependency_generation,
    frozen_requirements,
    frozen_spec_sha256,
    generation_dir,
    generation_interpreter,
    verify_generation,
)


def _proc(
    command: list[str],
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)


def _frozen_spec_project(tmp_path: Path, **overrides: str) -> Path:
    """A project dir carrying the frozen spec pair (pyproject.toml +
    uv.lock); *overrides* replaces file contents (None deletes the file)."""
    project = tmp_path / "project"
    if not project.exists():
        project.mkdir(parents=True)
    pyproject = overrides.get(
        "pyproject.toml",
        '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = []\n',
    )
    lock = overrides.get(
        "uv.lock",
        'version = 1\nrequires-python = ">=3.9"\n'
        "\n[[package]]\nname = \"demo\"\nversion = \"0.1.0\"\n"
        'source = { editable = "." }\n',
    )
    if pyproject is not None:
        (project / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if lock is not None:
        (project / "uv.lock").write_text(lock, encoding="utf-8")
    return project


def test_frozen_spec_sha256_requires_both_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(GenerationError, match="frozen spec"):
        frozen_spec_sha256(project)
    (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    with pytest.raises(GenerationError, match="uv.lock"):
        frozen_spec_sha256(project)
    (project / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    assert frozen_spec_sha256(project)


def test_frozen_spec_sha256_is_content_addressed(tmp_path: Path) -> None:
    a = _frozen_spec_project(tmp_path)
    b = tmp_path / "other"
    b.mkdir()
    (b / "pyproject.toml").write_text((a / "pyproject.toml").read_text(), encoding="utf-8")
    (b / "uv.lock").write_text((a / "uv.lock").read_text(), encoding="utf-8")
    # identical spec bytes -> identical address
    assert frozen_spec_sha256(a) == frozen_spec_sha256(b)
    # any spec change -> NEW address
    (b / "uv.lock").write_text(
        (a / "uv.lock").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    assert frozen_spec_sha256(a) != frozen_spec_sha256(b)


def test_frozen_requirements_only_registry_sources() -> None:
    lock = (
        'version = 1\n'
        "[[package]]\nname = \"requests\"\nversion = \"2.31.0\"\n"
        'source = { registry = "https://pypi.org/simple" }\n'
        "\n"
        "[[package]]\nname = \"demo\"\nversion = \"0.1.0\"\n"
        'source = { editable = "." }\n'
        "\n"
        "[[package]]\nname = \"tool\"\nversion = \"1.0.0\"\n"
        'source = { git = "https://github.com/x/tool.git" }\n'
        "\n"
        "[[package]]\nname = \"widget\"\nversion = \"3.0.0\"\n"
    )
    assert frozen_requirements(lock) == ["requests==2.31.0", "widget==3.0.0"]


def test_compute_venv_digest_reflects_installed_metadata(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    site = venv / "lib" / "python3.11" / "site-packages"
    site.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    dist = site / "requests-2.31.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: requests\nVersion: 2.31.0\n", encoding="utf-8"
    )
    interpreter = venv / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    interpreter.chmod(0o755)

    digest = compute_venv_digest(interpreter)
    # deterministic
    assert digest == compute_venv_digest(interpreter)
    # a content change (another package installed) changes the digest
    extra = site / "urllib3-2.0.0.dist-info"
    extra.mkdir()
    (extra / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: urllib3\nVersion: 2.0.0\n", encoding="utf-8"
    )
    assert compute_venv_digest(interpreter) != digest
    # pyvenv.cfg (base interpreter identity) participates too
    (venv / "pyvenv.cfg").write_text("home = /elsewhere\n", encoding="utf-8")
    assert compute_venv_digest(interpreter) != digest


def test_verify_generation_reports_reasons_never_raises(tmp_path: Path) -> None:
    verdict = verify_generation(tmp_path / "missing", deep=False)
    assert verdict["ok"] is False
    assert any("missing" in reason for reason in verdict["reasons"])

    gen = tmp_path / "generation"
    gen.mkdir()
    (gen / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    (gen / "bin").mkdir()
    (gen / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    (gen / "bin" / "python").chmod(0o755)
    # no proof file -> not ok
    assert verify_generation(gen, deep=False)["ok"] is False
    (gen / ".generation.json").write_text("{not json", encoding="utf-8")
    assert verify_generation(gen, deep=False)["ok"] is False
    (gen / ".generation.json").write_text(
        json.dumps(
            {
                "id": "a" * 64,
                "frozen_spec_sha256": "a" * 64,
                "interpreter_path": str(gen / "bin" / "python"),
                "venv_digest": "b" * 64,
                "created": "2026-08-12T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    # proof validates and the id matches the dir name only when the dir name
    # IS the id — a mismatched name is refused
    assert verify_generation(gen, deep=False)["ok"] is False
    named = tmp_path / ("a" * 64)
    (gen / ".generation.json").write_text(
        json.dumps(
            {
                "id": "a" * 64,
                "frozen_spec_sha256": "a" * 64,
                "interpreter_path": str(gen / "bin" / "python"),
                "venv_digest": "b" * 64,
                "created": "2026-08-12T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    # deep verification recomputes the digest: b*64 is not the venv's digest
    deep = verify_generation(gen, deep=True)
    assert deep["ok"] is False
    assert any("venv_digest mismatch" in reason for reason in deep["reasons"])


def test_ensure_dependency_generation_builds_verifies_and_refuses_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _frozen_spec_project(tmp_path)
    gen_root = tmp_path / "venvs"
    monkeypatch.setenv("ARNOLD_GENERATION_BUILD_STRATEGY", "pip")
    proof = ensure_dependency_generation(project, gen_root)
    assert proof["id"] == frozen_spec_sha256(project)
    assert proof["frozen_spec_sha256"] == proof["id"]
    gen_dir = generation_dir(gen_root, proof["id"])
    assert gen_dir.is_dir()
    assert (gen_dir / ".generation.json").is_file()
    assert generation_interpreter(gen_dir).is_file()
    # re-verification returns the SAME proof (immutable, content-addressed)
    assert ensure_dependency_generation(project, gen_root) == proof
    # an existing but corrupted generation is NEVER reused or overwritten
    (gen_dir / "pyvenv.cfg").write_text("home = /tampered\n", encoding="utf-8")
    with pytest.raises(GenerationError, match="failed verification"):
        ensure_dependency_generation(project, gen_root)
    # a genuinely missing generation for a NEW spec builds fresh
    other = _frozen_spec_project(
        tmp_path,
        **{
            "uv.lock": 'version = 1\n[[package]]\nname = "demo"\nversion = "0.2.0"\n'
            'source = { editable = "." }\n'
        },
    )
    other_proof = ensure_dependency_generation(other, gen_root)
    assert other_proof["id"] != proof["id"]


def test_apply_install_sync_is_retired_fail_closed() -> None:
    with pytest.raises(EditableInstallRetiredError) as exc_info:
        apply_install_sync(source_root="/workspace/arnold", incident_id="inc-1")
    assert exc_info.value.code == "editable_install_retired"
    assert "pip install -e" not in getattr(exc_info.value, "command", "")
