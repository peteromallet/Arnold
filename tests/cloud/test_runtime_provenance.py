from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import arnold_pipelines.megaplan.cloud.runtime_provenance as provenance_module
from arnold_pipelines.megaplan.cloud.runtime_provenance import runtime_provenance


def test_runtime_provenance_rejects_wrong_expected_root(tmp_path: Path) -> None:
    payload = runtime_provenance(expected_root=tmp_path)
    assert payload["ok"] is False
    assert "import_root_mismatch" in payload["errors"]


def test_runtime_provenance_rejects_wrong_expected_revision() -> None:
    source = Path(__file__).parents[2].resolve()
    payload = runtime_provenance(
        expected_root=source,
        expected_revision="0" * 40,
    )
    assert payload["ok"] is False
    assert "source_revision_mismatch" in payload["errors"]


def test_runtime_source_is_valid_when_git_metadata_is_a_worktree_file() -> None:
    source = Path(__file__).parents[2].resolve()
    assert (source / ".git").is_file()
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--git-dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_editable_subprocess_uses_pinned_source_despite_cwd_shadow(tmp_path: Path) -> None:
    source = Path(__file__).parents[2].resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True
    )
    python = venv / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "-e", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    target = tmp_path / "target"
    (target / "arnold_pipelines").mkdir(parents=True)
    (target / "arnold_pipelines" / "__init__.py").write_text(
        "raise RuntimeError('cwd shadow imported')\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source)
    result = subprocess.run(
        [
            str(python),
            "-P",
            "-m",
            "arnold_pipelines.megaplan.cloud.runtime_provenance",
            "--expected-root",
            str(source),
            "--expected-revision",
            revision,
        ],
        cwd=target,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["import_root"] == str(source)
    assert payload["editable_root"] == str(source)
    assert payload["source_revision"] == revision
    assert payload["runtime_revision"] == revision
    assert payload["pth"]
    assert {
        entry
        for record in payload["pth"]
        for entry in record["entries"]
    } == {str(source)}


def test_runtime_provenance_rejects_stale_editable_pth(
    monkeypatch,
) -> None:
    source = Path(__file__).parents[2].resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    monkeypatch.setattr(
        provenance_module,
        "_direct_url_identity",
        lambda: (source, {"dir_info": {"editable": True}, "url": source.as_uri()}),
    )
    monkeypatch.setattr(
        provenance_module,
        "_pth_identity",
        lambda: [
            {
                "path": "/venv/site-packages/_editable_impl_arnold.pth",
                "entries": [str(source), "/workspace/stale-arnold"],
                "readable": True,
            }
        ],
    )

    payload = runtime_provenance(
        expected_root=source,
        expected_revision=revision,
    )

    assert payload["ok"] is False
    assert "editable_pth_mismatch" in payload["errors"]
