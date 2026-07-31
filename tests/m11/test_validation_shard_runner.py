from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.run_m11_validation_shard import (
    SHARD_SCHEMA,
    ValidationShardError,
    _digest,
    build_aggregate,
    run_validation_shard,
)


def _git_project(tmp_path: Path, body: str) -> tuple[Path, str, str]:
    root = tmp_path / "project"
    root.mkdir()
    (root / "test_sample.py").write_text(body, encoding="utf-8")
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
    value = {
        "schema": SHARD_SCHEMA,
        "kind": kind,
        "command": ["python", "-P", "-m", "pytest", *inventory],
        "exit_code": 0,
        "revision": {"git_commit": "a" * 40, "git_tree": "b" * 40},
        "runtime": {
            "python": "/python",
            "python_sha256": "sha256:python",
            "safe_path": True,
            "version": [3, 11, 0],
        },
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
    drifted["content_sha256"] = _digest(
        {key: value for key, value in drifted.items() if key != "content_sha256"}
    )
    with pytest.raises(ValidationShardError, match="revision/runtime"):
        build_aggregate(
            shard_receipts=[full, drifted],
            expected_inventory=["a::test_a", "b::test_b"],
        )
