from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.wheel_smoke
def test_m6_deleted_public_imports_fail_in_installed_wheel(tmp_path: Path) -> None:
    """A clean install of the wheel must not expose the deleted public surfaces."""
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip = venv_dir / "bin" / "pip"
    python = venv_dir / "bin" / "python"

    subprocess.run(
        [str(pip), "install", "--no-deps", str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )

    probe = (
        "import importlib\n"
        "for name in (\"megaplan\", \"arnold.pipelines.megaplan\"):\n"
        "    try:\n"
        "        importlib.import_module(name)\n"
        "    except ModuleNotFoundError:\n"
        "        pass\n"
        "    else:\n"
        "        raise SystemExit(f\"deleted module {name!r} is still importable\")\n"
        "from arnold.pipeline import Pipeline, StepContext\n"
        "for name in (\"Stage\", \"Edge\", \"ParallelStage\", \"PipelineBuilder\", \"run_pipeline\"):\n"
        "    try:\n"
        "        exec(f\"from arnold.pipeline import {name}\")\n"
        "    except ImportError:\n"
        "        pass\n"
        "    else:\n"
        "        raise SystemExit(f\"deleted symbol {name!r} is still importable\")\n"
        "print(\"ok\")\n"
    )
    result = subprocess.run(
        [str(python), "-c", probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_source_tree_lacks_deleted_paths() -> None:
    """Deleted source roots are absent from the working tree."""
    deleted = [
        REPO_ROOT / "arnold" / "pipelines" / "megaplan",
        REPO_ROOT / "arnold" / "pipelines" / "jokes",
        REPO_ROOT / "arnold" / "pipelines" / "creative",
        REPO_ROOT / "arnold" / "pipelines" / "doc",
        REPO_ROOT / "arnold" / "pipelines" / "live_supervisor",
        REPO_ROOT / "arnold" / "pipelines" / "select_tournament",
        REPO_ROOT / "arnold" / "pipelines" / "writing_panel_strict.py",
        REPO_ROOT / "arnold" / "pipelines" / "writing_panel_strict",
        REPO_ROOT / "arnold" / "pipelines" / "evidence_pack",
        REPO_ROOT / "arnold" / "pipelines" / "_template",
        REPO_ROOT / "arnold" / "pipelines" / "_authoring.py",
        REPO_ROOT / "arnold" / "pipelines" / "__init__.py",
        REPO_ROOT / "scripts" / "backfill_step_receipts.py",
        REPO_ROOT / "scripts" / "m4_oracle_bisect.py",
        REPO_ROOT / "scripts" / "record_oracle_traces.py",
        REPO_ROOT / "scripts" / "silent_failure_census.py",
        REPO_ROOT / "tools" / "m4_oracle_bisect.py",
        REPO_ROOT / "_gen_corpus.py",
        REPO_ROOT / "_gen_golden_traces.py",
    ]
    missing = [str(p.relative_to(REPO_ROOT)) for p in deleted if p.exists()]
    assert not missing, f"deleted paths still present: {missing}"
