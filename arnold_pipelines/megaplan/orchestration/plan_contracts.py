"""Helpers for plan-stage Provides/Assumes contracts.

These helpers intentionally stay narrow: they normalize the contract schema
used by finalize/chain planning, render it for markdown surfaces, collect
provided paths for prep cross-reference, and compare downstream Assumes
against upstream Provides without introducing semantic analysis.
"""

from __future__ import annotations

import json
import posixpath
from pathlib import Path
from typing import Any, Iterable, Mapping


MATERIAL_CONTRACT_STATUSES = frozenset({"MISSING_UPSTREAM", "MISMATCH"})


def _trim_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_signature(value: Any) -> str:
    return _trim_string(value)


def _normalize_path(value: Any, *, root: Path) -> str:
    raw = _trim_string(value)
    if not raw:
        return ""
    if raw.startswith("~"):
        raw = str(Path(raw).expanduser())
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            raw = candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            raw = candidate.resolve().as_posix()
    else:
        raw = raw.replace("\\", "/")
    normalized = posixpath.normpath(raw.replace("\\", "/"))
    return "" if normalized == "." else normalized


def _normalize_interfaces(value: Any, *, root: Path) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    interfaces: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        interfaces.append(
            {
                "symbol": _trim_string(item.get("symbol")),
                "signature": _normalize_signature(item.get("signature")),
                "path": _normalize_path(item.get("path"), root=root),
            }
        )
    return interfaces


def normalize_contract_payload(
    payload: Any,
    *,
    root: Path | str | None = None,
) -> dict[str, list[Any]]:
    """Normalize the narrow Provides/Assumes schema for plan contracts."""

    root_path = Path(root).resolve() if root is not None else Path.cwd().resolve()
    raw = payload if isinstance(payload, Mapping) else {}

    provides: list[dict[str, Any]] = []
    for item in raw.get("provides", []):
        if not isinstance(item, Mapping):
            continue
        provides.append(
            {
                "name": _trim_string(item.get("name")),
                "description": _trim_string(item.get("description")),
                "interfaces": _normalize_interfaces(item.get("interfaces"), root=root_path),
            }
        )

    assumes: list[dict[str, Any]] = []
    for item in raw.get("assumes", []):
        if not isinstance(item, Mapping):
            continue
        assumes.append(
            {
                "name": _trim_string(item.get("name")),
                "upstream_milestone": _trim_string(item.get("upstream_milestone")),
                "interfaces": _normalize_interfaces(item.get("interfaces"), root=root_path),
            }
        )

    pre_existing: list[str] = []
    for item in raw.get("pre_existing", []):
        if isinstance(item, str) and item.strip():
            pre_existing.append(item.strip())

    return {"provides": provides, "assumes": assumes, "pre_existing": pre_existing}


def render_contract_markdown(contract: Any) -> str:
    """Render additive Provides/Assumes markdown sections for final.md."""

    normalized = normalize_contract_payload(contract)
    lines: list[str] = []

    if normalized["provides"]:
        lines.append("## Provides")
        lines.append("")
        for provide in normalized["provides"]:
            heading = f"- `{provide['name']}`" if provide["name"] else "- Unnamed provide"
            if provide["description"]:
                heading = f"{heading}: {provide['description']}"
            lines.append(heading)
            for interface in provide["interfaces"]:
                details = [
                    f"`{interface['symbol']}`" if interface["symbol"] else "`<unnamed>`",
                    f"path `{interface['path']}`" if interface["path"] else "path `<unknown>`",
                ]
                if interface["signature"]:
                    details.append(f"signature `{interface['signature']}`")
                lines.append(f"  - {', '.join(details)}")
        lines.append("")

    if normalized["assumes"]:
        lines.append("## Assumes")
        lines.append("")
        for assume in normalized["assumes"]:
            upstream = assume["upstream_milestone"] or "<unknown upstream>"
            heading = f"- `{assume['name']}` from `{upstream}`" if assume["name"] else f"- From `{upstream}`"
            lines.append(heading)
            for interface in assume["interfaces"]:
                details = [
                    f"`{interface['symbol']}`" if interface["symbol"] else "`<unnamed>`",
                    f"path `{interface['path']}`" if interface["path"] else "path `<unknown>`",
                ]
                if interface["signature"]:
                    details.append(f"signature `{interface['signature']}`")
                lines.append(f"  - {', '.join(details)}")
        lines.append("")

    return "\n".join(lines).rstrip()


def provided_paths_by_milestone(contracts: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Collect unique provided paths keyed by milestone label."""

    paths: dict[str, set[str]] = {}
    for item in contracts:
        if not isinstance(item, Mapping):
            continue
        label = (
            _trim_string(item.get("milestone_label"))
            or _trim_string(item.get("label"))
            or _trim_string(item.get("upstream_milestone"))
        )
        if not label:
            continue
        contract_payload = item.get("contract")
        if not isinstance(contract_payload, Mapping):
            contract_payload = {"provides": item.get("provides", [])}
        normalized = normalize_contract_payload(contract_payload)
        bucket = paths.setdefault(label, set())
        for provide in normalized["provides"]:
            for interface in provide["interfaces"]:
                if interface["path"]:
                    bucket.add(interface["path"])
    return {label: sorted(values) for label, values in sorted(paths.items())}


def _normalize_upstream_contracts(
    upstream_contracts: Any,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    if isinstance(upstream_contracts, Mapping):
        normalized: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for label, contract in upstream_contracts.items():
            if isinstance(label, str):
                normalized[label] = normalize_contract_payload(contract)
        return normalized
    if not isinstance(upstream_contracts, Iterable) or isinstance(upstream_contracts, (str, bytes)):
        return {}

    normalized = {}
    for item in upstream_contracts:
        if not isinstance(item, Mapping):
            continue
        label = _trim_string(item.get("milestone_label")) or _trim_string(item.get("label"))
        if not label:
            continue
        contract_payload = item.get("contract")
        if not isinstance(contract_payload, Mapping):
            contract_payload = {"provides": item.get("provides", [])}
        normalized[label] = normalize_contract_payload(contract_payload)
    return normalized


def diff_assumes_against_provides(
    downstream_contract: Any,
    upstream_contracts: Any,
    *,
    downstream_label: str = "",
) -> list[dict[str, str]]:
    """Compare downstream Assumes to upstream Provides row-by-row."""

    downstream = normalize_contract_payload(downstream_contract)
    upstream = _normalize_upstream_contracts(upstream_contracts)
    rows: list[dict[str, str]] = []

    for assume in downstream["assumes"]:
        upstream_label = assume["upstream_milestone"]
        upstream_contract = upstream.get(upstream_label)
        upstream_index: dict[str, dict[str, str]] = {}
        if upstream_contract is not None:
            for provide in upstream_contract["provides"]:
                for interface in provide["interfaces"]:
                    symbol = interface["symbol"]
                    if symbol and symbol not in upstream_index:
                        upstream_index[symbol] = interface

        for interface in assume["interfaces"]:
            symbol = interface["symbol"]
            actual = upstream_index.get(symbol, {})
            status = "OK"
            note = ""
            if upstream_contract is None or not actual:
                status = "MISSING_UPSTREAM"
                note = (
                    f"upstream contract `{upstream_label}` missing"
                    if upstream_contract is None
                    else f"symbol `{symbol}` missing upstream"
                )
            else:
                path_changed = actual.get("path", "") != interface["path"]
                signature_changed = actual.get("signature", "") != interface["signature"]
                if path_changed or signature_changed:
                    status = "MISMATCH"
                    if path_changed and signature_changed:
                        note = "path and signature changed"
                    elif path_changed:
                        note = "path changed"
                    else:
                        note = "signature changed"
            rows.append(
                {
                    "downstream_label": downstream_label,
                    "downstream_name": assume["name"],
                    "upstream_label": upstream_label,
                    "symbol": symbol,
                    "assumes_interface": symbol,
                    "provides_interface": actual.get("symbol", symbol),
                    "expected_path": interface["path"],
                    "actual_path": actual.get("path", ""),
                    "path": interface["path"],
                    "expected_signature": interface["signature"],
                    "actual_signature": actual.get("signature", ""),
                    "signature": interface["signature"],
                    "status": status,
                    "note": note,
                }
            )
    return rows


def contract_diff_fingerprint(diff_rows: Iterable[Mapping[str, Any]]) -> str:
    """Return a deterministic canonical fingerprint for material diff rows."""

    canonical_rows: list[dict[str, str]] = []
    for row in diff_rows:
        if not isinstance(row, Mapping):
            continue
        status = _trim_string(row.get("status"))
        if status not in MATERIAL_CONTRACT_STATUSES:
            continue
        canonical_rows.append(
            {
                "actual_path": _trim_string(row.get("actual_path")),
                "actual_signature": _normalize_signature(row.get("actual_signature")),
                "downstream_label": _trim_string(row.get("downstream_label")),
                "expected_path": _trim_string(row.get("expected_path")),
                "expected_signature": _normalize_signature(row.get("expected_signature")),
                "note": _trim_string(row.get("note")),
                "status": status,
                "symbol": _trim_string(row.get("symbol")),
                "upstream_label": _trim_string(row.get("upstream_label")),
            }
        )
    canonical_rows.sort(
        key=lambda row: (
            row["downstream_label"],
            row["upstream_label"],
            row["symbol"],
            row["status"],
            row["expected_path"],
            row["actual_path"],
            row["expected_signature"],
            row["actual_signature"],
            row["note"],
        )
    )
    return json.dumps(canonical_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def pre_existing_task_ids_from_contract(contract: Any) -> set[str]:
    """Return task IDs declared as pre-existing in a contract payload."""

    normalized = normalize_contract_payload(contract)
    return {
        task_id
        for task_id in normalized.get("pre_existing", [])
        if isinstance(task_id, str) and task_id
    }
