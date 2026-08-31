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


def _codes(tmp_path, source):
    door = tmp_path / "door.py"
    door.write_text(source, encoding="utf-8")
    return {item["category"] for item in check_files([door])["diagnostics"]}


def test_checker_catches_aliased_process_run(tmp_path) -> None:
    assert "direct_process_construction" in _codes(
        tmp_path,
        "import subprocess as process\n"
        "def launch():\n    return process.run(['x'])\n",
    )


def test_checker_catches_assignment_and_callable_aliases(tmp_path) -> None:
    assert "direct_process_construction" in _codes(
        tmp_path,
        "import subprocess\nrunner = subprocess.run\n"
        "def worker():\n    return runner(['x'])\n",
    )


def test_checker_catches_multiline_absent_wbc_delegation(tmp_path) -> None:
    assert "absent_wbc_legacy_delegation" in _codes(
        tmp_path,
        "def launch(wbc_dispatch):\n"
        "    if wbc_dispatch is None:\n"
        "        return final_launch(\n"
        "            None\n"
        "        )\n",
    )


def test_checker_catches_nested_double_admission(tmp_path) -> None:
    assert "nested_double_admission" in _codes(
        tmp_path,
        "def outer():\n"
        "    dispatch_with_admission(req, launch)\n"
        "    def inner():\n"
        "        return dispatch_with_admission(req, launch)\n",
    )


def test_checker_catches_aliased_raw_final_launch(tmp_path) -> None:
    assert "raw_final_launch_access" in _codes(
        tmp_path,
        "from worker import final_launch as invoke\n"
        "def launch():\n    return invoke()\n",
    )


def test_checker_catches_wbc_before_admission(tmp_path) -> None:
    assert "wbc_before_admission" in _codes(
        tmp_path,
        "def launch(wbc_dispatch):\n"
        "    return wbc_dispatch.run(final_launch)\n",
    )

def test_checker_emits_each_frozen_category_with_context(tmp_path) -> None:
    cases = (
        ("raw_authority_call", "from runtime import require_configured_runtime_launch as gate\n\ndef launch():\n    return gate('worker')\n", ""),
        ("chain_local_preflight", "def launch():\n    return worker_launch_preflight()\n", ""),
        ("direct_chain_launch", "from chain import run_managed_command\n\ndef launch():\n    return run_managed_command()\n", "chain"),
        ("absent_wbc_legacy_delegation", "from worker import final_launch as invoke\n\ndef launch(wbc_dispatch):\n    if (\n        None\n        is wbc_dispatch\n    ):\n        return invoke()\n", ""),
        ("wbc_before_admission", "def launch(wbc_dispatch):\n    return wbc_dispatch.run(final_launch)\n", ""),
        ("nested_double_admission", "def outer():\n    dispatch_with_admission(req, launch)\n    def inner():\n        return dispatch_with_admission(req, launch)\n", ""),
        ("raw_final_launch_access", "from worker import final_launch as invoke\n\ndef launch():\n    return invoke()\n", ""),
    )
    for category, source, subdir in cases:
        directory = tmp_path / subdir if subdir else tmp_path
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{category}.py"
        path.write_text(source, encoding="utf-8")
        diagnostics = check_files([path])["diagnostics"]
        matches = [item for item in diagnostics if item.get("category") == category]
        assert matches, (category, diagnostics)
        for item in matches:
            assert item["path"] == str(path)
            assert isinstance(item["line"], int) and item["line"] > 0
            assert item["enclosing_symbol"] != "<module>"
            assert item["category"] == category
            assert item["code"]
            assert item["reason"]


def test_checker_detects_qualified_getattr_call_alias(tmp_path) -> None:
    path = tmp_path / "door.py"
    path.write_text(
        "import runtime_attestation as runtime\n"
        "def launch():\n"
        "    return getattr(runtime, 'require_configured_runtime_launch')('worker')\n",
        encoding="utf-8",
    )
    diagnostics = check_files([path])["diagnostics"]
    assert any(item["code"] == "raw_runtime_preflight" for item in diagnostics)


def test_checker_detects_reversed_multiline_absent_wbc_delegation(tmp_path) -> None:
    path = tmp_path / "door.py"
    path.write_text(
        "from worker import final_launch as invoke\n"
        "def launch(wbc_dispatch):\n"
        "    if (\n"
        "        None\n"
        "        is wbc_dispatch\n"
        "    ):\n"
        "        return invoke(\n"
        "            None\n"
        "        )\n",
        encoding="utf-8",
    )
    diagnostics = check_files([path])["diagnostics"]
    assert any(item["category"] == "absent_wbc_legacy_delegation" for item in diagnostics)


def test_checker_detects_aliased_process_and_raw_launch(tmp_path) -> None:
    path = tmp_path / "door.py"
    path.write_text(
        "import subprocess as process\n"
        "from worker import final_launch as invoke\n"
        "spawn = getattr(process, 'Popen')\n"
        "def launch():\n"
        "    return spawn(['x']), invoke()\n",
        encoding="utf-8",
    )
    categories = {item["category"] for item in check_files([path])["diagnostics"]}
    assert "direct_process_construction" in categories
    assert "raw_final_launch_access" in categories


def test_checker_detects_aliased_double_admission(tmp_path) -> None:
    path = tmp_path / "door.py"
    path.write_text(
        "from worker_dispatch import dispatch_with_admission as admit\n"
        "again = admit\n"
        "def launch():\n"
        "    admit(req, run)\n"
        "    return again(req, run)\n",
        encoding="utf-8",
    )
    diagnostics = check_files([path])["diagnostics"]
    assert any(item["category"] == "nested_double_admission" for item in diagnostics)


def test_checker_scans_arbitrary_door_symbols_and_falsey_wbc_forms(tmp_path) -> None:
    path = tmp_path / "door.py"
    path.write_text(
        "import subprocess as process\n"
        "from worker import final_launch as invoke\n"
        "def execute():\n"
        "    if not wbc_dispatch:\n"
        "        invoke()\n"
        "    if (False == bool(wbc_dispatch)):\n"
        "        invoke()\n"
        "    return process.Popen(['x'])\n",
        encoding="utf-8",
    )
    diagnostics = check_files([path])["diagnostics"]
    categories = {item["category"] for item in diagnostics}
    assert "direct_process_construction" in categories
    assert "absent_wbc_legacy_delegation" in categories
    assert "raw_final_launch_access" in categories
    assert all(item["enclosing_symbol"] == "execute" for item in diagnostics)
