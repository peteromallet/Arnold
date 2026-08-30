from __future__ import annotations

import pytest

from scripts.check_worker_admission_authority import check_files


def test_repository_doors_have_no_forbidden_raw_preflight() -> None:
    result = check_files()
    assert result["ok"], result["diagnostics"]


def test_synthetic_raw_launch_door_is_rejected(tmp_path) -> None:
    door = tmp_path / "door.py"
    door.write_text("import subprocess\ndef door():\n    return subprocess.Popen(['echo', 'bad'])\n", encoding="utf-8")
    result = check_files([door])
    assert not result["ok"]
    assert any(item["code"] == "raw_launch_access" for item in result["diagnostics"])


def test_checker_resolves_import_aliases(tmp_path) -> None:
    door = tmp_path / "door.py"
    door.write_text(
        "from arnold_pipelines.megaplan.cloud.runtime_attestation import require_configured_runtime_launch as gate\n"
        "def launch():\n    return gate('worker')\n",
        encoding="utf-8",
    )
    result = check_files([door])
    assert any(item["code"] == "raw_runtime_preflight" for item in result["diagnostics"])


@pytest.mark.parametrize(
    "source,code",
    [
        ("import subprocess as sp\ndef door():\n    return sp.Popen(['echo', 'bad'])\n", "raw_launch_access"),
        ("from subprocess import Popen as Spawn\ndef door():\n    return Spawn(['echo', 'bad'])\n", "raw_launch_access"),
        ("from arnold_pipelines.megaplan.cloud.worker_dispatch import dispatch_with_admission as admit\ndef door():\n    return admit(req, launch)\n", "dispatch_without_typed_worker_return"),
        ("from subprocess import Popen\ndef door():\n    spawn = Popen\n    return spawn(['echo', 'bad'])\n", "raw_launch_access"),
        ("import subprocess\ndef door():\n    spawn = getattr(subprocess, 'Popen')\n    return spawn(['echo', 'bad'])\n", "raw_launch_access"),
    ],
)
def test_checker_rejects_aliased_and_dynamic_launch_or_admission_bypass(tmp_path, source, code) -> None:
    door = tmp_path / "synthetic.py"
    door.write_text(source, encoding="utf-8")
    result = check_files([door])
    assert not result["ok"]
    assert any(item["code"] == code for item in result["diagnostics"])


def test_checker_rejects_raw_and_dynamic_launch_inside_canonical_door(tmp_path, monkeypatch) -> None:
    import scripts.check_worker_admission_authority as authority

    door = tmp_path / "canonical-door.py"
    door.write_text(
        "import subprocess as sp\n"
        "def launch():\n"
        "    spawn = getattr(sp, 'Popen')\n"
        "    return spawn(['echo', 'bad'])\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(authority, "CANONICAL_DOORS", frozenset({door}))
    result = authority.check_files([door])
    assert not result["ok"]
    assert any(item["code"] == "raw_launch_access" for item in result["diagnostics"])
