#!/usr/bin/env python3
"""Generate a deterministic M11 no-debt receipt from attested test shards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SHARD_SCHEMA = "m11.test-shard-receipt.v1"
AGGREGATE_SCHEMA = "m11.no-debt-aggregate.v1"
OUTPUT_SCHEMA = "m11.no-debt-receipt.v1"
KINDS = {"full_suite", "semantic_carrier"}
COUNT_KEYS = {
    "collected",
    "passed",
    "failed",
    "errors",
    "skipped",
    "xfailed",
    "xpassed",
    "deselected",
    "debt",
}
ZERO_KEYS = COUNT_KEYS - {"collected", "passed"}
DEBT_KEYS = {"xfail", "xpass", "skip", "unresolved"}
SOURCE_KEYS = {
    "kind",
    "content_sha256",
    "command",
    "inventory_count",
    "inventory_sha256",
    "custody_receipt_sha256",
    "terminal_receipt_sha256",
}
RECEIPT_KEYS = {
    "schema",
    "aggregate_sha256",
    "revision",
    "runtime",
    "source_receipts",
    "inventory_count",
    "inventory_sha256",
    "counts",
    "debt",
    "passed",
    "content_sha256",
}


class NoDebtError(ValueError):
    """The supplied evidence cannot prove the M11 no-debt claim."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NoDebtError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise NoDebtError(f"JSON root must be an object: {path}")
    return value


def _validate_hash(value: Mapping[str, Any], *, label: str) -> str:
    observed = value.get("content_sha256")
    unhashed = dict(value)
    unhashed.pop("content_sha256", None)
    expected = _digest(unhashed)
    if observed != expected:
        raise NoDebtError(f"{label} content hash mismatch")
    return expected


def _sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != len("sha256:") + 64
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise NoDebtError(f"{label} must be a canonical sha256 digest")
    return value


def _exact_keys(
    value: Mapping[str, Any], expected: set[str], *, label: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise NoDebtError(
            f"{label} schema fields differ: "
            f"missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}"
        )


def _strings(value: Any, *, label: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise NoDebtError(f"{label} must be a list of non-empty strings")
    if nonempty and not value:
        raise NoDebtError(f"{label} must not be empty")
    if value != sorted(value) or len(value) != len(set(value)):
        raise NoDebtError(f"{label} must be sorted and duplicate-free")
    return list(value)


def _mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise NoDebtError(f"{label} must be a non-empty object")
    return dict(value)


def _command(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise NoDebtError(f"{label} must be a non-empty argv list")
    return list(value)


def _validate_shard(value: dict[str, Any], *, label: str) -> dict[str, Any]:
    _exact_keys(
        value,
        {
            "schema",
            "kind",
            "command",
            "exit_code",
            "revision",
            "runtime",
            "inventory",
            "counts",
            "debt",
            "custody_receipt_sha256",
            "terminal_receipt_sha256",
            "exact_inventory",
            "content_sha256",
        },
        label=label,
    )
    if value["schema"] != SHARD_SCHEMA:
        raise NoDebtError(f"{label} schema mismatch")
    if value["kind"] not in KINDS:
        raise NoDebtError(f"{label} kind is not recognized")
    _validate_hash(value, label=label)
    command = _command(value["command"], label=f"{label}.command")
    revision = _mapping(value["revision"], label=f"{label}.revision")
    runtime = _mapping(value["runtime"], label=f"{label}.runtime")
    inventory = _strings(
        value["inventory"], label=f"{label}.inventory", nonempty=True
    )
    counts = value["counts"]
    if not isinstance(counts, dict) or set(counts) != COUNT_KEYS:
        raise NoDebtError(f"{label}.counts has the wrong schema")
    if any(type(counts[key]) is not int or counts[key] < 0 for key in COUNT_KEYS):
        raise NoDebtError(f"{label}.counts must contain non-negative integers")
    if value["exit_code"] != 0:
        raise NoDebtError(f"{label} command did not exit zero")
    if value["exact_inventory"] is not True:
        raise NoDebtError(f"{label} did not execute its exact frozen inventory")
    for field in ("custody_receipt_sha256", "terminal_receipt_sha256"):
        _sha256(value[field], label=f"{label}.{field}")
    if counts["collected"] != len(inventory) or counts["passed"] != len(inventory):
        raise NoDebtError(f"{label} counts do not exactly match inventory")
    if any(counts[key] != 0 for key in ZERO_KEYS):
        raise NoDebtError(f"{label} contains skip, xfail/xpass, failure, or debt")
    if value["debt"] != []:
        raise NoDebtError(f"{label}.debt must be an empty list")
    return {
        **value,
        "command": command,
        "revision": revision,
        "runtime": runtime,
        "inventory": inventory,
        "counts": dict(counts),
    }


def generate_no_debt_receipt(
    *, aggregate: Mapping[str, Any], shard_receipts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Validate an exact shard partition and return its deterministic receipt."""

    aggregate_value = dict(aggregate)
    _exact_keys(
        aggregate_value,
        {
            "schema",
            "revision",
            "runtime",
            "expected_inventory",
            "receipts",
            "content_sha256",
        },
        label="aggregate",
    )
    if aggregate_value["schema"] != AGGREGATE_SCHEMA:
        raise NoDebtError("aggregate schema mismatch")
    aggregate_hash = _validate_hash(aggregate_value, label="aggregate")
    revision = _mapping(aggregate_value["revision"], label="aggregate.revision")
    runtime = _mapping(aggregate_value["runtime"], label="aggregate.runtime")
    expected_inventory = _strings(
        aggregate_value["expected_inventory"],
        label="aggregate.expected_inventory",
        nonempty=True,
    )
    expected_entries = aggregate_value["receipts"]
    if not isinstance(expected_entries, list) or not expected_entries:
        raise NoDebtError("aggregate.receipts must be a non-empty list")
    expected_by_hash: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(expected_entries):
        if not isinstance(raw, dict):
            raise NoDebtError(f"aggregate.receipts[{index}] must be an object")
        _exact_keys(
            raw,
            {"kind", "content_sha256", "command", "inventory"},
            label=f"aggregate.receipts[{index}]",
        )
        if raw["kind"] not in KINDS:
            raise NoDebtError(f"aggregate.receipts[{index}] kind is not recognized")
        digest = raw["content_sha256"]
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise NoDebtError(f"aggregate.receipts[{index}] hash is invalid")
        if digest in expected_by_hash:
            raise NoDebtError("aggregate contains a duplicate receipt hash")
        expected_by_hash[digest] = {
            "kind": raw["kind"],
            "content_sha256": digest,
            "command": _command(
                raw["command"], label=f"aggregate.receipts[{index}].command"
            ),
            "inventory": _strings(
                raw["inventory"],
                label=f"aggregate.receipts[{index}].inventory",
                nonempty=True,
            ),
        }

    supplied = [
        _validate_shard(dict(value), label=f"shard[{index}]")
        for index, value in enumerate(shard_receipts)
    ]
    supplied_by_hash: dict[str, dict[str, Any]] = {}
    seen_inventory: set[str] = set()
    kinds: set[str] = set()
    for shard in supplied:
        digest = shard["content_sha256"]
        if digest in supplied_by_hash:
            raise NoDebtError("duplicate supplied receipt")
        supplied_by_hash[digest] = shard
        expected = expected_by_hash.get(digest)
        if expected is None:
            raise NoDebtError("supplied receipt is absent from aggregate")
        for field in ("kind", "command", "inventory"):
            if shard[field] != expected[field]:
                raise NoDebtError(f"shard {field} differs from aggregate")
        if shard["revision"] != revision or shard["runtime"] != runtime:
            raise NoDebtError("shard revision/runtime differs from aggregate")
        overlap = seen_inventory.intersection(shard["inventory"])
        if overlap:
            raise NoDebtError(f"shard inventories overlap: {sorted(overlap)!r}")
        seen_inventory.update(shard["inventory"])
        kinds.add(shard["kind"])

    if set(supplied_by_hash) != set(expected_by_hash):
        raise NoDebtError("missing or unexpected shard receipts")
    if kinds != KINDS:
        raise NoDebtError("both full_suite and semantic_carrier receipts are required")
    if sorted(seen_inventory) != expected_inventory:
        raise NoDebtError("shard inventory union differs from aggregate")

    sources = [
        {
            "kind": shard["kind"],
            "content_sha256": shard["content_sha256"],
            "command": shard["command"],
            "inventory_count": len(shard["inventory"]),
            "inventory_sha256": _digest(shard["inventory"]),
            "custody_receipt_sha256": shard["custody_receipt_sha256"],
            "terminal_receipt_sha256": shard["terminal_receipt_sha256"],
        }
        for shard in sorted(supplied, key=lambda item: item["content_sha256"])
    ]
    output = {
        "schema": OUTPUT_SCHEMA,
        "aggregate_sha256": aggregate_hash,
        "revision": revision,
        "runtime": runtime,
        "source_receipts": sources,
        "inventory_count": len(expected_inventory),
        "inventory_sha256": _digest(expected_inventory),
        "counts": {
            key: sum(shard["counts"][key] for shard in supplied)
            for key in sorted(COUNT_KEYS)
        },
        "debt": {
            "xfail": 0,
            "xpass": 0,
            "skip": 0,
            "unresolved": 0,
        },
        "passed": True,
    }
    output["content_sha256"] = _digest(output)
    return output


def validate_no_debt_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the one canonical no-debt receipt consumed by M11 acceptance."""

    receipt = dict(value)
    _exact_keys(receipt, RECEIPT_KEYS, label="receipt")
    if receipt["schema"] != OUTPUT_SCHEMA:
        raise NoDebtError("receipt schema mismatch")
    _validate_hash(receipt, label="receipt")
    _sha256(receipt["aggregate_sha256"], label="receipt.aggregate_sha256")
    _sha256(receipt["inventory_sha256"], label="receipt.inventory_sha256")
    revision = _mapping(receipt["revision"], label="receipt.revision")
    runtime = _mapping(receipt["runtime"], label="receipt.runtime")

    sources = receipt["source_receipts"]
    if not isinstance(sources, list) or not sources:
        raise NoDebtError("receipt.source_receipts must be a non-empty list")
    normalized_sources: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    kinds: set[str] = set()
    source_inventory_count = 0
    for index, raw in enumerate(sources):
        if not isinstance(raw, dict):
            raise NoDebtError(f"receipt.source_receipts[{index}] must be an object")
        label = f"receipt.source_receipts[{index}]"
        _exact_keys(raw, SOURCE_KEYS, label=label)
        if raw["kind"] not in KINDS:
            raise NoDebtError(f"{label}.kind is not recognized")
        digest = _sha256(raw["content_sha256"], label=f"{label}.content_sha256")
        if digest in seen_hashes:
            raise NoDebtError("receipt contains a duplicate source receipt")
        seen_hashes.add(digest)
        kinds.add(raw["kind"])
        inventory_count = raw["inventory_count"]
        if type(inventory_count) is not int or inventory_count <= 0:
            raise NoDebtError(f"{label}.inventory_count must be a positive integer")
        source_inventory_count += inventory_count
        normalized_sources.append({
            **raw,
            "command": _command(raw["command"], label=f"{label}.command"),
            "content_sha256": digest,
            "inventory_count": inventory_count,
            "inventory_sha256": _sha256(
                raw["inventory_sha256"], label=f"{label}.inventory_sha256"
            ),
            "custody_receipt_sha256": _sha256(
                raw["custody_receipt_sha256"],
                label=f"{label}.custody_receipt_sha256",
            ),
            "terminal_receipt_sha256": _sha256(
                raw["terminal_receipt_sha256"],
                label=f"{label}.terminal_receipt_sha256",
            ),
        })
    if kinds != KINDS:
        raise NoDebtError(
            "receipt requires full_suite and semantic_carrier source receipts"
        )
    if [item["content_sha256"] for item in normalized_sources] != sorted(seen_hashes):
        raise NoDebtError("receipt.source_receipts must be content-hash sorted")

    inventory_count = receipt["inventory_count"]
    if type(inventory_count) is not int or inventory_count <= 0:
        raise NoDebtError("receipt.inventory_count must be a positive integer")
    if inventory_count != source_inventory_count:
        raise NoDebtError("receipt source inventory counts do not match total")

    counts = receipt["counts"]
    if not isinstance(counts, dict) or set(counts) != COUNT_KEYS:
        raise NoDebtError("receipt.counts has the wrong schema")
    if any(type(counts[key]) is not int or counts[key] < 0 for key in COUNT_KEYS):
        raise NoDebtError("receipt.counts must contain non-negative integers")
    if counts["collected"] != inventory_count or counts["passed"] != inventory_count:
        raise NoDebtError("receipt counts do not exactly match inventory")
    if any(counts[key] != 0 for key in ZERO_KEYS):
        raise NoDebtError("receipt contains skip, xfail/xpass, failure, or debt")

    debt = receipt["debt"]
    if not isinstance(debt, dict) or set(debt) != DEBT_KEYS:
        raise NoDebtError("receipt.debt has the wrong schema")
    if any(type(debt[key]) is not int or debt[key] != 0 for key in DEBT_KEYS):
        raise NoDebtError("receipt.debt must contain exact zero counts")
    if receipt["passed"] is not True:
        raise NoDebtError("receipt is not passed")
    return {
        **receipt,
        "revision": revision,
        "runtime": runtime,
        "source_receipts": normalized_sources,
        "counts": dict(counts),
        "debt": dict(debt),
    }


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--shard", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = generate_no_debt_receipt(
        aggregate=_load(args.aggregate),
        shard_receipts=[_load(path) for path in args.shard],
    )
    _atomic_write(args.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
