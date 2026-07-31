from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Mapping

import pytest

from scripts.run_m11_validation_shard import (
    RUNTIME_SCHEMA,
    SHARD_SCHEMA,
    ValidationShardError,
    _digest,
    _parse_outcomes,
    _runtime_identity,
    build_aggregate,
    run_validation_shard,
)


def _git_project(
    tmp_path: Path,
    body: str,
    *,
    extra_files: Mapping[str, str] | None = None,
) -> tuple[Path, str, str]:
    root = tmp_path / "project"
    root.mkdir()
    (root / "test_sample.py").write_text(body, encoding="utf-8")
    for name, contents in (extra_files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"], check=True
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture"], check=True
    )
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    return root, revision, tree


def _python_sha() -> str:
    return "sha256:" + hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()


def _run(
    tmp_path: Path, root: Path, revision: str, tree: str, *, kind: str
) -> dict:
    return run_validation_shard(
        project_root=root,
        kind=kind,
        selectors=["test_sample.py"],
        ignores=[],
        expected_revision=revision,
        expected_tree=tree,
        expected_python_sha256=_python_sha(),
        output=tmp_path / f"{kind}.json",
        lock_path=tmp_path / "validation.lock",
        timeout_seconds=30,
    )


def test_run_persists_exact_self_hashed_custody_and_terminal_receipts(
    tmp_path: Path,
) -> None:
    root, revision, tree = _git_project(
        tmp_path, "def test_green():\n    assert True\n"
    )
    receipt = _run(tmp_path, root, revision, tree, kind="full_suite")
    assert receipt["schema"] == SHARD_SCHEMA
    assert receipt["exit_code"] == 0
    assert receipt["inventory"] == ["test_sample.py::test_green"]
    assert receipt["counts"]["passed"] == 1
    assert receipt["counts"]["collected"] == 1
    assert receipt["counts"]["debt"] == 0
    runtime_unhashed = dict(receipt["runtime"])
    runtime_hash = runtime_unhashed.pop("content_sha256")
    assert receipt["runtime"]["schema"] == RUNTIME_SCHEMA
    assert runtime_hash == _digest(runtime_unhashed)
    unhashed = dict(receipt)
    observed = unhashed.pop("content_sha256")
    assert observed == _digest(unhashed)

    custody = json.loads(
        (tmp_path / "full_suite.json.custody.json").read_text()
    )
    custody_unhashed = dict(custody)
    custody_hash = custody_unhashed.pop("content_sha256")
    assert custody_hash == _digest(custody_unhashed)
    assert custody["process_group_id"] is not None
    assert custody["command_hash"].startswith("sha256:")

    terminal = json.loads(
        (tmp_path / "full_suite.json.terminal.json").read_text()
    )
    terminal_unhashed = dict(terminal)
    terminal_hash = terminal_unhashed.pop("content_sha256")
    assert terminal_hash == _digest(terminal_unhashed)
    assert terminal["custody_receipt_sha256"] == custody_hash
    assert terminal["exact_inventory"] is True
    assert terminal["revision_before"] == terminal["revision_after"]
    assert terminal["runtime_before"] == terminal["runtime_after"]


def test_xfail_is_counted_as_debt_not_silently_passed(tmp_path: Path) -> None:
    root, revision, tree = _git_project(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.xfail(reason='owned debt')\n"
        "def test_debt():\n"
        "    assert False\n",
    )
    receipt = _run(
        tmp_path, root, revision, tree, kind="semantic_carrier"
    )
    assert receipt["exit_code"] == 0
    assert receipt["counts"]["xfailed"] == 1
    assert receipt["counts"]["debt"] == 1
    assert receipt["debt"] == ["xfailed:1"]


def test_skip_reason_rendering_is_counted_without_losing_exact_inventory(
    tmp_path: Path,
) -> None:
    root, revision, tree = _git_project(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.skip(reason='why is this dependency unavailable')\n"
        "def test_a_deliberately_long_name_that_overflows_pytest_status_columns():\n"
        "    assert False\n",
    )
    receipt = _run(
        tmp_path, root, revision, tree, kind="semantic_carrier"
    )
    assert receipt["exact_inventory"] is True
    assert receipt["counts"]["collected"] == 1
    assert receipt["counts"]["skipped"] == 1
    assert receipt["counts"]["debt"] == 1
    assert receipt["debt"] == ["skipped:1"]


def test_xpass_is_counted_as_debt_without_losing_exact_inventory(
    tmp_path: Path,
) -> None:
    root, revision, tree = _git_project(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.xfail(reason='unexpected recovery')\n"
        "def test_unexpected_pass():\n"
        "    assert True\n",
    )
    receipt = _run(
        tmp_path, root, revision, tree, kind="semantic_carrier"
    )
    assert receipt["exact_inventory"] is True
    assert receipt["counts"]["collected"] == 1
    assert receipt["counts"]["xpassed"] == 1
    assert receipt["counts"]["debt"] == 1
    assert receipt["debt"] == ["xpassed:1"]


def test_parametrized_nodeids_with_spaces_and_status_words_are_preserved_exactly(
    tmp_path: Path,
) -> None:
    root, revision, tree = _git_project(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.parametrize(\n"
        "    'value',\n"
        "    [1, 2, 3],\n"
        "    ids=[\n"
        "        'contains spaces',\n"
        "        'literal PASSED marker :: inside',\n"
        "        'punctuation !@#$%^&*()={}+,.',\n"
        "    ],\n"
        ")\n"
        "def test_opaque_nodeid(value):\n"
        "    assert value > 0\n",
    )
    receipt = _run(tmp_path, root, revision, tree, kind="full_suite")
    expected = [
        "test_sample.py::test_opaque_nodeid[contains spaces]",
        "test_sample.py::test_opaque_nodeid[literal PASSED marker :: inside]",
        "test_sample.py::test_opaque_nodeid[punctuation !@#$%^&*()={}+,.]",
    ]
    assert receipt["inventory"] == sorted(expected)
    assert receipt["counts"]["collected"] == len(expected)
    assert receipt["counts"]["passed"] == len(expected)
    assert receipt["exact_inventory"] is True


def test_inherited_test_provenance_preserves_frozen_nodeid(
    tmp_path: Path,
) -> None:
    root, revision, tree = _git_project(
        tmp_path,
        "from conformance_base import ConformanceBase\n"
        "\n"
        "class TestConcreteConformance(ConformanceBase):\n"
        "    pass\n",
        extra_files={
            "conformance_base.py": (
                "class ConformanceBase:\n"
                "    def test_inherited_contract(self):\n"
                "        assert True\n"
            )
        },
    )
    receipt = _run(tmp_path, root, revision, tree, kind="full_suite")
    assert receipt["inventory"] == [
        "test_sample.py::TestConcreteConformance::test_inherited_contract"
    ]
    assert receipt["counts"]["passed"] == 1
    assert receipt["exact_inventory"] is True


def test_outcome_parser_preserves_arrows_spaces_and_status_words() -> None:
    nodeid = (
        "test_sample.py::test_case[opaque <- text.py PASSED marker with spaces]"
    )
    counts, executed = _parse_outcomes(
        f"{nodeid} PASSED [100%]",
        expected_inventory=[nodeid],
    )
    assert executed == [nodeid]
    assert counts["passed"] == 1


def test_outcome_parser_accepts_inherited_provenance_after_opaque_arrow() -> None:
    nodeid = "test_sample.py::test_case[opaque <- token.py FAILED marker]"
    counts, executed = _parse_outcomes(
        f"{nodeid} <- tests/helpers/conformance_base.py PASSED [100%]",
        expected_inventory=[nodeid],
    )
    assert executed == [nodeid]
    assert counts["passed"] == 1


def test_outcome_parser_does_not_strip_arbitrary_arrow_suffix() -> None:
    nodeid = "test_sample.py::test_case"
    counts, executed = _parse_outcomes(
        f"{nodeid} <- not pytest provenance PASSED [100%]",
        expected_inventory=[nodeid],
    )
    assert executed == []
    assert counts["collected"] == 0


def test_outcome_parser_rejects_ambiguous_frozen_inventory_match() -> None:
    short = "test_sample.py::test_case"
    long = f"{short} PASSED opaque"
    with pytest.raises(ValidationShardError, match="ambiguous"):
        _parse_outcomes(
            f"{long} PASSED [100%]",
            expected_inventory=[short, long],
        )


def test_outcome_parser_rejects_direct_vs_provenance_ambiguity() -> None:
    inherited = "test_sample.py::test_case"
    opaque = f"{inherited} <- tests/helpers/base.py"
    with pytest.raises(ValidationShardError, match="ambiguous"):
        _parse_outcomes(
            f"{opaque} PASSED [100%]",
            expected_inventory=[inherited, opaque],
        )


def test_outcome_parser_rejects_duplicate_terminal_nodeid() -> None:
    nodeid = "test_sample.py::test_case[param with spaces]"
    output = "\n".join(
        [
            f"{nodeid} PASSED [ 50%]",
            f"{nodeid} PASSED [100%]",
        ]
    )
    with pytest.raises(ValidationShardError, match="duplicate terminal outcome"):
        _parse_outcomes(output, expected_inventory=[nodeid])


def test_outcome_parser_rejects_duplicate_inherited_terminal_nodeid() -> None:
    nodeid = "test_sample.py::TestConcrete::test_inherited"
    output = "\n".join(
        [
            f"{nodeid} <- tests/helpers/base.py PASSED [ 50%]",
            f"{nodeid} <- tests/helpers/base.py PASSED [100%]",
        ]
    )
    with pytest.raises(ValidationShardError, match="duplicate terminal outcome"):
        _parse_outcomes(output, expected_inventory=[nodeid])


def test_outcome_parser_accepts_skip_reason_glued_to_status() -> None:
    nodeid = "test_sample.py::test_case[param with spaces and PASSED marker]"
    counts, executed = _parse_outcomes(
        f"{nodeid} SKIPPEDy is this dependency unavailable [100%]",
        expected_inventory=[nodeid],
    )
    assert executed == [nodeid]
    assert counts["skipped"] == 1
    assert counts["collected"] == 1
    assert counts["debt"] == 1


def test_durable_slot_rejects_concurrent_runner(tmp_path: Path) -> None:
    root, revision, tree = _git_project(
        tmp_path, "def test_green():\n    assert True\n"
    )
    lock_path = tmp_path / "validation.lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValidationShardError, match="already held"):
            run_validation_shard(
                project_root=root,
                kind="full_suite",
                selectors=["test_sample.py"],
                ignores=[],
                expected_revision=revision,
                expected_tree=tree,
                expected_python_sha256=_python_sha(),
                output=tmp_path / "blocked.json",
                lock_path=lock_path,
                timeout_seconds=30,
            )


def _fake_shard(kind: str, inventory: list[str]) -> dict:
    runtime = {
        "schema": RUNTIME_SCHEMA,
        "python": "/venv/bin/python",
        "python_realpath": "/usr/bin/python3",
        "python_sha256": "sha256:python",
        "prefix": "/venv",
        "base_prefix": "/usr",
        "safe_path": True,
        "version": [3, 11, 0],
        "project_inputs": {
            "pyproject.toml": "sha256:project",
            "uv.lock": "sha256:lock",
        },
        "distributions": [
            {"name": "arnold", "version": "0.23.0"},
            {"name": "pytest", "version": "8.0.0"},
        ],
    }
    runtime["content_sha256"] = _digest(runtime)
    value = {
        "schema": SHARD_SCHEMA,
        "kind": kind,
        "command": ["python", "-P", "-m", "pytest", *inventory],
        "exit_code": 0,
        "revision": {"git_commit": "a" * 40, "git_tree": "b" * 40},
        "runtime": runtime,
        "inventory": inventory,
        "counts": {
            "collected": len(inventory),
            "passed": len(inventory),
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "deselected": 0,
            "debt": 0,
        },
        "debt": [],
        "custody_receipt_sha256": _digest("custody"),
        "terminal_receipt_sha256": _digest("terminal"),
        "exact_inventory": True,
    }
    value["content_sha256"] = _digest(value)
    return value


def test_preflight_builds_deterministic_exact_aggregate() -> None:
    from scripts.generate_m11_no_debt import generate_no_debt_receipt

    shards = [
        _fake_shard("full_suite", ["a::test_a"]),
        _fake_shard("semantic_carrier", ["b::test_b"]),
    ]
    first = build_aggregate(
        shard_receipts=list(reversed(shards)),
        expected_inventory=["a::test_a", "b::test_b"],
    )
    second = build_aggregate(
        shard_receipts=shards,
        expected_inventory=["b::test_b", "a::test_a"],
    )
    assert first == second
    assert first["schema"] == "m11.no-debt-aggregate.v1"
    unhashed = dict(first)
    observed = unhashed.pop("content_sha256")
    assert observed == _digest(unhashed)
    final = generate_no_debt_receipt(
        aggregate=first, shard_receipts=shards
    )
    assert final["schema"] == "m11.no-debt-receipt.v1"
    assert final["passed"] is True


def test_preflight_rejects_overlap_gaps_duplicates_and_vector_drift() -> None:
    full = _fake_shard("full_suite", ["a::test_a"])
    semantic = _fake_shard("semantic_carrier", ["a::test_a"])
    with pytest.raises(ValidationShardError, match="overlap"):
        build_aggregate(
            shard_receipts=[full, semantic],
            expected_inventory=["a::test_a"],
        )

    semantic = _fake_shard("semantic_carrier", ["b::test_b"])
    with pytest.raises(ValidationShardError, match="gaps"):
        build_aggregate(
            shard_receipts=[full, semantic],
            expected_inventory=["a::test_a", "b::test_b", "c::test_c"],
        )
    with pytest.raises(ValidationShardError, match="duplicate shard"):
        build_aggregate(
            shard_receipts=[full, full, semantic],
            expected_inventory=["a::test_a", "b::test_b"],
        )

    drifted = deepcopy(semantic)
    drifted["runtime"] = {**drifted["runtime"], "python": "/other"}
    drifted["runtime"]["content_sha256"] = _digest(
        {
            key: value
            for key, value in drifted["runtime"].items()
            if key != "content_sha256"
        }
    )
    drifted["content_sha256"] = _digest(
        {key: value for key, value in drifted.items() if key != "content_sha256"}
    )
    with pytest.raises(ValidationShardError, match="revision/runtime"):
        build_aggregate(
            shard_receipts=[full, drifted],
            expected_inventory=["a::test_a", "b::test_b"],
        )


def test_runtime_identity_retains_invoked_venv_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    real_python = tmp_path / "python-real"
    real_python.write_bytes(b"same interpreter bytes")
    first = tmp_path / "venv-a" / "bin" / "python"
    second = tmp_path / "venv-b" / "bin" / "python"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.symlink_to(real_python)
    second.symlink_to(real_python)
    monkeypatch.setattr(
        "scripts.run_m11_validation_shard.importlib.metadata.distributions",
        lambda: [],
    )

    monkeypatch.setattr(sys, "executable", str(first))
    first_identity = _runtime_identity(root)
    monkeypatch.setattr(sys, "executable", str(second))
    second_identity = _runtime_identity(root)

    assert first_identity["python"] == str(first)
    assert second_identity["python"] == str(second)
    assert first_identity["python_realpath"] == second_identity["python_realpath"]
    assert first_identity["python_sha256"] == second_identity["python_sha256"]
    assert first_identity["content_sha256"] != second_identity["content_sha256"]


def test_runtime_identity_hashes_project_lock_and_distribution_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeDistribution:
        def __init__(
            self, name: str, version: str, direct_url: dict | None = None
        ) -> None:
            self.metadata = {"Name": name}
            self.version = version
            self._direct_url = direct_url

        def read_text(self, filename: str) -> str | None:
            if filename != "direct_url.json" or self._direct_url is None:
                return None
            return json.dumps(self._direct_url)

    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (root / "uv.lock").write_text("version = 1\n")
    base = [
        FakeDistribution(
            "Arnold",
            "0.23.0",
            {
                "url": "file:///workspace/arnold-a",
                "dir_info": {"editable": True},
            },
        ),
        FakeDistribution("pytest", "8.0.0"),
    ]
    monkeypatch.setattr(
        "scripts.run_m11_validation_shard.importlib.metadata.distributions",
        lambda: base,
    )
    base_identity = _runtime_identity(root)

    monkeypatch.setattr(
        "scripts.run_m11_validation_shard.importlib.metadata.distributions",
        lambda: [*base, FakeDistribution("psycopg", "3.2.0")],
    )
    db_identity = _runtime_identity(root)
    assert base_identity["project_inputs"]["pyproject.toml"].startswith("sha256:")
    assert base_identity["project_inputs"]["uv.lock"].startswith("sha256:")
    assert base_identity["distributions"][0]["direct_url"]["url"] == (
        "file:///workspace/arnold-a"
    )
    assert base_identity["content_sha256"] != db_identity["content_sha256"]

    changed_target = [
        FakeDistribution(
            "Arnold",
            "0.23.0",
            {
                "url": "file:///workspace/arnold-b",
                "dir_info": {"editable": True},
            },
        ),
        FakeDistribution("pytest", "8.0.0"),
    ]
    monkeypatch.setattr(
        "scripts.run_m11_validation_shard.importlib.metadata.distributions",
        lambda: changed_target,
    )
    assert _runtime_identity(root)["content_sha256"] != base_identity[
        "content_sha256"
    ]


def test_aggregate_rejects_base_vs_db_extra_distribution_drift() -> None:
    full = _fake_shard("full_suite", ["a::test_a"])
    db_extra = _fake_shard("semantic_carrier", ["b::test_b"])
    db_extra["runtime"]["distributions"].append(
        {"name": "psycopg", "version": "3.2.0"}
    )
    db_extra["runtime"]["distributions"].sort(
        key=lambda row: json.dumps(row, sort_keys=True)
    )
    db_extra["runtime"]["content_sha256"] = _digest(
        {
            key: value
            for key, value in db_extra["runtime"].items()
            if key != "content_sha256"
        }
    )
    db_extra["content_sha256"] = _digest(
        {
            key: value
            for key, value in db_extra.items()
            if key != "content_sha256"
        }
    )
    with pytest.raises(ValidationShardError, match="revision/runtime"):
        build_aggregate(
            shard_receipts=[full, db_extra],
            expected_inventory=["a::test_a", "b::test_b"],
        )
