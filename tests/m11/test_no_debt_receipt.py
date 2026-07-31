from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.generate_m11_no_debt import (
    AGGREGATE_SCHEMA,
    SHARD_SCHEMA,
    NoDebtError,
    _digest,
    generate_no_debt_receipt,
    validate_no_debt_receipt,
)


REVISION = {"git_commit": "a" * 40, "tree_sha256": "sha256:tree"}
RUNTIME = {
    "python": "/workspace/runtime/venv/bin/python",
    "python_sha256": "sha256:python",
    "projection_sha256": "sha256:projection",
}


def _shard(kind: str, inventory: list[str], selector: str) -> dict:
    value = {
        "schema": SHARD_SCHEMA,
        "kind": kind,
        "command": ["python", "-P", "-m", "pytest", "-q", selector],
        "exit_code": 0,
        "revision": REVISION,
        "runtime": RUNTIME,
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


def _aggregate(shards: list[dict]) -> dict:
    value = {
        "schema": AGGREGATE_SCHEMA,
        "revision": REVISION,
        "runtime": RUNTIME,
        "expected_inventory": sorted(
            nodeid for shard in shards for nodeid in shard["inventory"]
        ),
        "receipts": [
            {
                "kind": shard["kind"],
                "content_sha256": shard["content_sha256"],
                "command": shard["command"],
                "inventory": shard["inventory"],
            }
            for shard in shards
        ],
    }
    value["content_sha256"] = _digest(value)
    return value


def _valid() -> tuple[dict, list[dict]]:
    shards = [
        _shard(
            "full_suite",
            ["tests/a.py::test_a", "tests/b.py::test_b"],
            "tests/full",
        ),
        _shard(
            "semantic_carrier",
            ["tests/m11/test_semantics.py::test_contract"],
            "tests/m11/test_semantics.py",
        ),
    ]
    return _aggregate(shards), shards


def _rehash(value: dict) -> dict:
    value["content_sha256"] = _digest(
        {key: item for key, item in value.items() if key != "content_sha256"}
    )
    return value


def test_emits_deterministic_receipt_matching_exact_aggregate() -> None:
    aggregate, shards = _valid()
    first = generate_no_debt_receipt(
        aggregate=aggregate, shard_receipts=list(reversed(shards))
    )
    second = generate_no_debt_receipt(
        aggregate=aggregate, shard_receipts=shards
    )
    assert first == second
    assert first["schema"] == "m11.no-debt-receipt.v1"
    assert first["aggregate_sha256"] == aggregate["content_sha256"]
    assert first["inventory_count"] == 3
    assert first["counts"]["collected"] == 3
    assert first["counts"]["passed"] == 3
    assert first["passed"] is True
    unhashed = {key: value for key, value in first.items() if key != "content_sha256"}
    assert first["content_sha256"] == _digest(unhashed)
    assert validate_no_debt_receipt(first) == first


def test_canonical_receipt_validator_rejects_tampering_and_legacy_schema() -> None:
    aggregate, shards = _valid()
    receipt = generate_no_debt_receipt(
        aggregate=aggregate, shard_receipts=shards
    )

    legacy = deepcopy(receipt)
    legacy["schema"] = "m11.no-debt.v1"
    _rehash(legacy)
    with pytest.raises(NoDebtError, match="schema mismatch"):
        validate_no_debt_receipt(legacy)

    nonzero = deepcopy(receipt)
    nonzero["counts"]["skipped"] = 1
    _rehash(nonzero)
    with pytest.raises(NoDebtError, match="skip"):
        validate_no_debt_receipt(nonzero)

    missing_source = deepcopy(receipt)
    missing_source["source_receipts"] = missing_source["source_receipts"][:1]
    missing_source["inventory_count"] = 2
    missing_source["counts"]["collected"] = 2
    missing_source["counts"]["passed"] = 2
    _rehash(missing_source)
    with pytest.raises(NoDebtError, match="full_suite and semantic_carrier"):
        validate_no_debt_receipt(missing_source)


def test_rejects_missing_and_duplicate_receipts() -> None:
    aggregate, shards = _valid()
    with pytest.raises(NoDebtError, match="missing"):
        generate_no_debt_receipt(
            aggregate=aggregate, shard_receipts=shards[:1]
        )
    with pytest.raises(NoDebtError, match="duplicate supplied"):
        generate_no_debt_receipt(
            aggregate=aggregate, shard_receipts=[*shards, shards[0]]
        )


def test_rejects_inventory_overlap_even_when_aggregate_repeats_it() -> None:
    _, shards = _valid()
    overlapping = deepcopy(shards[1])
    overlapping["inventory"] = ["tests/a.py::test_a"]
    overlapping["counts"]["collected"] = 1
    overlapping["counts"]["passed"] = 1
    _rehash(overlapping)
    aggregate = _aggregate([shards[0], overlapping])
    aggregate["expected_inventory"] = sorted(set(aggregate["expected_inventory"]))
    _rehash(aggregate)
    with pytest.raises(NoDebtError, match="overlap"):
        generate_no_debt_receipt(
            aggregate=aggregate, shard_receipts=[shards[0], overlapping]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("skipped", 1, "skip"),
        ("xfailed", 1, "xfail"),
        ("xpassed", 1, "xpass"),
        ("failed", 1, "failure"),
        ("errors", 1, "failure"),
        ("debt", 1, "debt"),
    ],
)
def test_rejects_every_nonzero_debt_or_nonpass_count(
    field: str, value: int, message: str
) -> None:
    aggregate, shards = _valid()
    changed = deepcopy(shards[0])
    changed["counts"][field] = value
    _rehash(changed)
    aggregate = _aggregate([changed, shards[1]])
    with pytest.raises(NoDebtError, match=message):
        generate_no_debt_receipt(
            aggregate=aggregate, shard_receipts=[changed, shards[1]]
        )


def test_rejects_hash_command_revision_runtime_and_inventory_drift() -> None:
    aggregate, shards = _valid()
    bad_hash = deepcopy(shards[0])
    bad_hash["command"] = [*bad_hash["command"], "-x"]
    with pytest.raises(NoDebtError, match="content hash mismatch"):
        generate_no_debt_receipt(
            aggregate=aggregate, shard_receipts=[bad_hash, shards[1]]
        )

    for field, replacement, message in [
        ("command", ["python", "-P", "-m", "pytest", "other"], "command"),
        ("revision", {"git_commit": "b" * 40}, "revision/runtime"),
        ("runtime", {"python": "/other/python"}, "revision/runtime"),
    ]:
        changed = deepcopy(shards[0])
        changed[field] = replacement
        _rehash(changed)
        changed_aggregate = deepcopy(aggregate)
        changed_aggregate["receipts"][0]["content_sha256"] = changed[
            "content_sha256"
        ]
        _rehash(changed_aggregate)
        with pytest.raises(NoDebtError, match=message):
            generate_no_debt_receipt(
                aggregate=changed_aggregate,
                shard_receipts=[changed, shards[1]],
            )

    changed_aggregate = deepcopy(aggregate)
    changed_aggregate["expected_inventory"].append("tests/z.py::test_z")
    changed_aggregate["expected_inventory"].sort()
    _rehash(changed_aggregate)
    with pytest.raises(NoDebtError, match="inventory union"):
        generate_no_debt_receipt(
            aggregate=changed_aggregate, shard_receipts=shards
        )


def test_rejects_nonempty_debt_and_schema_drift() -> None:
    aggregate, shards = _valid()
    changed = deepcopy(shards[0])
    changed["debt"] = ["TODO"]
    _rehash(changed)
    aggregate = _aggregate([changed, shards[1]])
    with pytest.raises(NoDebtError, match="empty"):
        generate_no_debt_receipt(
            aggregate=aggregate, shard_receipts=[changed, shards[1]]
        )

    changed = deepcopy(shards[0])
    changed["unexpected"] = True
    _rehash(changed)
    with pytest.raises(NoDebtError, match="schema fields"):
        generate_no_debt_receipt(
            aggregate=_aggregate(shards),
            shard_receipts=[changed, shards[1]],
        )
