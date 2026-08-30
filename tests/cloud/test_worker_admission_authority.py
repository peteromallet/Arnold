from __future__ import annotations

from scripts.check_worker_admission_authority import check_files


def test_repository_doors_have_no_forbidden_raw_preflight() -> None:
    result = check_files()
    assert result["ok"], result["diagnostics"]


def test_checker_resolves_import_aliases(tmp_path) -> None:
    door = tmp_path / "door.py"
    door.write_text(
        "from arnold_pipelines.megaplan.cloud.runtime_attestation import require_configured_runtime_launch as gate\n"
        "def launch():\n    return gate('worker')\n",
        encoding="utf-8",
    )
    result = check_files([door])
    assert any(item["code"] == "raw_runtime_preflight" for item in result["diagnostics"])
