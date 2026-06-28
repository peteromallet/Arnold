"""M7: installed-wheel runtime conformance for Python-shaped authoring.

Builds a wheel and sdist, installs the wheel into a clean venv, and proves:

- The installed wheel contains the shipped Python-shaped workflow source,
  prompt resources, component metadata, and required package data.
- Deleted legacy surfaces are still absent from wheel, sdist, and installed venv.
- A Python-shaped workflow source file can be compiled and dry-run from the
  installed venv without repo-relative assumptions.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import textwrap
import venv
from pathlib import Path
from zipfile import ZipFile

import pytest

from arnold.conformance.deleted_surfaces import (
    DELETED_ARTIFACT_PATH_PREFIXES,
    DELETED_IMPORT_MODULES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _clean_venv_env(venv_dir: Path) -> dict[str, str]:
    return {
        "PATH": str(venv_dir / "bin"),
        "PYTHONNOUSERSITE": "1",
    }


def _run_installed_arnold_cli(
    python: Path,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    assert "PYTHONPATH" not in env
    return subprocess.run(
        [
            str(python),
            "-c",
            (
                "from arnold.cli import main; "
                "import sys; "
                "raise SystemExit(main(sys.argv[1:]))"
            ),
            *args,
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _build_sdist(repo_root: Path, sdist_dir: Path, tmp: Path) -> None:
    frontend_venv = tmp / "build-frontend"
    venv.create(frontend_venv, with_pip=True)
    frontend_pip = frontend_venv / "bin" / "pip"
    frontend_python = frontend_venv / "bin" / "python"
    subprocess.run(
        [str(frontend_pip), "install", "hatchling"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            str(frontend_python),
            "-c",
            (
                "import importlib, sys; "
                "backend = importlib.import_module('hatchling.build'); "
                "print(backend.build_sdist(sys.argv[1], {}))"
            ),
            str(sdist_dir),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.wheel_smoke
def test_installed_wheel_python_shaped_authoring_runtime_conformance() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        build_dir = tmp / "build"
        build_dir.mkdir()
        sdist_dir = tmp / "sdist"
        sdist_dir.mkdir()

        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(build_dir), str(REPO_ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )
        _build_sdist(REPO_ROOT, sdist_dir, tmp)

        wheels = list(build_dir.glob("*.whl"))
        assert wheels, "no wheel produced"
        wheel = wheels[0]

        sdists = list(sdist_dir.glob("*.tar.gz"))
        assert sdists, "no sdist produced"
        sdist = sdists[0]

        with ZipFile(wheel) as whl:
            names = whl.namelist()

            # Positive: required runtime artifacts are packaged.
            assert any(
                name.endswith("arnold_pipelines/megaplan/workflows/workflow.py") for name in names
            ), "missing shipped Python-shaped workflow source"
            assert any(
                name.endswith("arnold_pipelines/megaplan/workflows/planning.py") for name in names
            ), "missing shipped workflow planning bridge"
            assert any(
                name.endswith("arnold_pipelines/megaplan/workflows/components.py") for name in names
            ), "missing shipped workflow components"
            assert any(
                name.endswith("arnold_pipelines/megaplan/workflows/__init__.py") for name in names
            ), "missing shipped workflows package"
            assert any(
                "arnold_pipelines/megaplan/prompts/" in name and name.endswith(".py")
                for name in names
            ), "missing prompt resources"
            assert any(
                name.endswith("pipeline_ids.json") for name in names
            ), "missing component metadata"
            assert any(
                name.endswith("arnold_pipelines/megaplan/SKILL.md") for name in names
            ), "missing megaplan skill doc"

            # Negative: deleted legacy surfaces stay out of the wheel.
            for deleted in DELETED_ARTIFACT_PATH_PREFIXES:
                assert not any(deleted in name for name in names), (
                    f"wheel still contains deleted path: {deleted}"
                )

        with tarfile.open(sdist, "r:gz") as tar:
            sdist_names = tar.getnames()
            for deleted in DELETED_ARTIFACT_PATH_PREFIXES:
                assert not any(deleted in name for name in sdist_names), (
                    f"sdist still contains deleted path: {deleted}"
                )

        # Install into a clean venv and exercise Python-shaped authoring end-to-end.
        venv_dir = tmp / "venv"
        venv.create(venv_dir, with_pip=True)
        pip = venv_dir / "bin" / "pip"
        arnold = venv_dir / "bin" / "arnold"
        python = venv_dir / "bin" / "python"

        subprocess.run([str(pip), "install", str(wheel)], check=True, capture_output=True)

        # Create a tiny Python-shaped workflow package outside the repo.
        work_dir = tmp / "authoring"
        work_dir.mkdir()
        pkg_dir = work_dir / "m7_authoring"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "components.py").write_text(
            textwrap.dedent(
                '''\
                from __future__ import annotations

                from arnold.workflow.authoring import ComponentProvenance, StepComponent


                def _prov(name: str) -> ComponentProvenance:
                    return ComponentProvenance(
                        module="m7_authoring.components",
                        qualname=name,
                        export_name=name,
                    )


                plan = StepComponent(id="plan", provenance=_prov("plan"))
                execute = StepComponent(id="execute", provenance=_prov("execute"))
                review = StepComponent(id="review", provenance=_prov("review"))
                '''
            )
        )
        workflow_path = pkg_dir / "workflow.py"
        (workflow_path).write_text(
            textwrap.dedent(
                '''\
                from __future__ import annotations

                from arnold.workflow.authoring import workflow
                from .components import plan, execute, review


                @workflow(id="m7-installed-wheel", version="1.0")
                def flow(brief):
                    plan_output = plan(id="plan", brief=brief)
                    evidence = execute(id="execute", plan=plan_output)
                    review(id="review", evidence=evidence)
                '''
            )
        )

        bad_workflow_path = pkg_dir / "invalid_workflow.py"
        bad_workflow_path.write_text(
            textwrap.dedent(
                '''\
                from __future__ import annotations

                from arnold.workflow.authoring import workflow
                from .components import missing


                @workflow(id="m7-installed-wheel-invalid", version="1.0")
                def flow(brief):
                    missing(id="missing", brief=brief)
                '''
            )
        )

        env = _clean_venv_env(venv_dir)

        # CLI source commands work from the local project root without PYTHONPATH.
        source_arg = str(workflow_path.relative_to(work_dir))
        for subcommand, extra_args in (
            ("check", []),
            ("compile", []),
            ("inspect", ["--format", "json"]),
            ("explain", ["--format", "json"]),
            ("graph", ["--format", "json"]),
        ):
            result = _run_installed_arnold_cli(
                python,
                ["workflow", subcommand, source_arg, *extra_args],
                cwd=work_dir,
                env=env,
            )
            assert result.returncode == 0, (
                f"arnold workflow {subcommand} failed: {result.stderr}"
            )
            if subcommand == "check":
                assert "ok:" in result.stdout
            elif subcommand == "compile":
                assert "sha256:" in result.stdout, (
                    f"arnold workflow {subcommand} did not emit a manifest hash"
                )
            elif subcommand in {"inspect", "explain"}:
                assert "m7-installed-wheel" in result.stdout
            else:
                assert '"nodes"' in result.stdout

        failure = _run_installed_arnold_cli(
            python,
            [
                "workflow",
                "check",
                str(bad_workflow_path.relative_to(work_dir)),
                "--format",
                "json",
            ],
            cwd=work_dir,
            env=env,
        )
        assert failure.returncode == 1
        assert '"ok": false' in failure.stdout
        assert '"code": "AWF005_UNKNOWN_COMPONENT"' in failure.stdout
        assert str(bad_workflow_path.relative_to(work_dir)) in failure.stdout

        # Programmatic compile also works from the installed package.
        prog = subprocess.run(
            [
                str(python),
                "-c",
                "from arnold.workflow import compile_workflow_file; "
                f"m = compile_workflow_file({str(workflow_path)!r}); print(m.manifest_hash)",
            ],
            capture_output=True,
            text=True,
            cwd=work_dir,
            env=env,
        )
        assert prog.returncode == 0, prog.stderr
        assert prog.stdout.strip().startswith("sha256:")

        # A shipped pipeline can still be dry-run from the installed wheel.
        result = subprocess.run(
            [
                str(arnold),
                "workflow",
                "dry-run",
                "--module",
                "arnold_pipelines.megaplan.pipeline:build_pipeline",
            ],
            capture_output=True,
            text=True,
            cwd=tmp,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert "sha256:" in result.stdout

        # Deleted legacy surfaces remain unimportable in the installed venv.
        for deleted_module in DELETED_IMPORT_MODULES:
            result = subprocess.run(
                [str(python), "-c", f"import {deleted_module}"],
                capture_output=True,
                text=True,
                cwd=tmp,
                env=env,
            )
            assert result.returncode != 0, (
                f"deleted module {deleted_module} was importable in installed wheel"
            )
            assert isinstance(result.exc_info[1] if False else result.stderr, str)
            assert "ModuleNotFoundError" in result.stderr or "No module named" in result.stderr
