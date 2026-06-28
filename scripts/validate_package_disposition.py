#!/usr/bin/env python3
"""Validate docs/arnold/package-disposition.yaml coverage and schema."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. Install with: pip install pyyaml")


EXPECTED_DISPOSITIONS = [
    "arnold-core",
    "arnold-service-interface",
    "arnold-adapter",
    "arnold-shared-leaf",
    "megaplan-plugin",
    "product-app",
    "legacy-hold",
    "delete-merge",
    "split-required",
]

EXPECTED_GRANULARITIES = ["directory", "file", "symbol", "split"]

TOP_LEVEL_KEYS = {
    "schema_version",
    "valid_dispositions",
    "valid_granularities",
    "coverage_exclusions",
    "rows",
    "parity_gates",
    "runtime_settings_gates",
    "deferral_ledger",
}

ROW_REQUIRED_FIELDS = {
    "source",
    "target",
    "granularity",
    "disposition",
    "reason",
    "blockers",
    "allowed_imports",
    "forbidden_imports",
    "vocabulary_owned",
    "string_policy",
    "extraction_prerequisite",
    "first_extraction_unit",
    "tests_gates",
    "configurable_seams",
}


@dataclass(frozen=True)
class Row:
    index: int
    source: str
    target: str
    granularity: str
    disposition: str
    data: dict[str, Any]

    @property
    def label(self) -> str:
        return f"row {self.index} ({self.granularity} {self.source})"


def _normalize_path(raw: str, *, allow_glob: bool) -> str:
    if not isinstance(raw, str):
        raise ValueError("must be a string")
    text = raw.strip().replace("\\", "/")
    if not text:
        raise ValueError("must not be empty")
    if text.startswith("/"):
        raise ValueError("must be repo-relative, not absolute")

    normalized_parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("must not escape the repo root")
        normalized_parts.append(part)

    if not normalized_parts:
        raise ValueError("must not resolve to '.'")

    normalized = "/".join(normalized_parts)
    if not allow_glob and any(ch in normalized for ch in "*?[]"):
        raise ValueError("must not contain glob syntax")
    return normalized


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must parse to a YAML mapping")
    return data


def _tracked_python_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git", "ls-files", "--",
            "arnold_pipelines/megaplan/*.py", "arnold_pipelines/megaplan/**/*.py",
            "arnold/pipeline/*.py", "arnold/pipeline/**/*.py",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(line for line in result.stdout.splitlines() if line)


def _canonical_source_path(raw: str, *, target: str = "") -> str:
    """Map legacy source prefixes to their M5 relocated paths."""
    if raw == "megaplan/_pipeline":
        return "arnold/pipeline"
    if raw.startswith("megaplan/_pipeline/"):
        suffix = raw.removeprefix("megaplan/_pipeline/")
        if "arnold/pipeline" in target:
            return "arnold/pipeline/" + suffix
        return "arnold_pipelines/megaplan/" + suffix
    if raw.startswith("megaplan/"):
        return "arnold_pipelines/" + raw
    return raw


def _is_legacy_manifest_source(raw: str) -> bool:
    return raw.startswith("megaplan/")


def _expect_string_list(
    errors: list[str],
    value: Any,
    *,
    field: str,
    owner: str,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{owner} field '{field}' must be a list[str]")
        return []
    normalized: list[str] = []
    for idx, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{owner} field '{field}' item {idx} must be a non-empty string")
            continue
        normalized.append(item)
    return normalized


def _validate_object_list(
    errors: list[str],
    value: Any,
    *,
    field: str,
    owner: str,
    required_keys: set[str],
) -> None:
    if not isinstance(value, list):
        errors.append(f"{owner} field '{field}' must be a list[object]")
        return
    for idx, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            errors.append(f"{owner} field '{field}' item {idx} must be an object")
            continue
        missing = sorted(required_keys - set(item))
        if missing:
            errors.append(
                f"{owner} field '{field}' item {idx} missing keys: {', '.join(missing)}"
            )


def _matches(pattern: str, tracked_files: list[str]) -> list[str]:
    if any(ch in pattern for ch in "*?[]"):
        return [path for path in tracked_files if fnmatch.fnmatchcase(path, pattern)]
    return [pattern] if pattern in tracked_files else []


def _directory_members(path: str, tracked_files: list[str]) -> list[str]:
    prefix = f"{path}/"
    return [tracked for tracked in tracked_files if tracked.startswith(prefix)]


def _validate_top_level(data: dict[str, Any], errors: list[str]) -> None:
    keys = set(data)
    missing = sorted(TOP_LEVEL_KEYS - keys)
    unexpected = sorted(keys - TOP_LEVEL_KEYS)
    if missing:
        errors.append(f"manifest missing top-level keys: {', '.join(missing)}")
    if unexpected:
        errors.append(f"manifest has unexpected top-level keys: {', '.join(unexpected)}")

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    if data.get("valid_dispositions") != EXPECTED_DISPOSITIONS:
        errors.append(
            "valid_dispositions must exactly match the approved enum list in order"
        )
    if data.get("valid_granularities") != EXPECTED_GRANULARITIES:
        errors.append(
            "valid_granularities must exactly match [directory, file, symbol, split]"
        )

    for field in ("coverage_exclusions", "rows", "parity_gates", "runtime_settings_gates"):
        if not isinstance(data.get(field), list):
            errors.append(f"top-level field '{field}' must be a list")


def _parse_rows(data: dict[str, Any], tracked_files: list[str], errors: list[str]) -> list[Row]:
    rows: list[Row] = []
    seen = set()
    for index, raw_row in enumerate(data.get("rows") or [], start=1):
        owner = f"row {index}"
        if not isinstance(raw_row, dict):
            errors.append(f"{owner} must be a mapping")
            continue

        missing = sorted(ROW_REQUIRED_FIELDS - set(raw_row))
        unexpected = sorted(set(raw_row) - ROW_REQUIRED_FIELDS)
        if missing:
            errors.append(f"{owner} missing required fields: {', '.join(missing)}")
            continue
        if unexpected:
            errors.append(f"{owner} has unexpected fields: {', '.join(unexpected)}")

        try:
            raw_source = _normalize_path(raw_row["source"], allow_glob=False)
            source = _canonical_source_path(
                raw_source,
                target=str(raw_row.get("target", "")),
            )
        except ValueError as exc:
            errors.append(f"{owner} source {raw_row.get('source')!r} invalid: {exc}")
            continue

        target = raw_row.get("target")
        if not isinstance(target, str) or not target.strip():
            errors.append(f"{owner} target must be a non-empty string")
            continue

        granularity = raw_row.get("granularity")
        if granularity not in EXPECTED_GRANULARITIES:
            errors.append(
                f"{owner} granularity {granularity!r} is invalid; expected one of "
                f"{', '.join(EXPECTED_GRANULARITIES)}"
            )
            continue

        disposition = raw_row.get("disposition")
        if disposition not in EXPECTED_DISPOSITIONS:
            errors.append(
                f"{owner} disposition {disposition!r} is invalid; expected one of "
                f"{', '.join(EXPECTED_DISPOSITIONS)}"
            )
            continue

        reason = raw_row.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{owner} reason must be a non-empty string")

        _expect_string_list(errors, raw_row.get("blockers"), field="blockers", owner=owner)
        _expect_string_list(
            errors, raw_row.get("allowed_imports"), field="allowed_imports", owner=owner
        )
        _expect_string_list(
            errors,
            raw_row.get("forbidden_imports"),
            field="forbidden_imports",
            owner=owner,
        )
        _expect_string_list(
            errors,
            raw_row.get("extraction_prerequisite"),
            field="extraction_prerequisite",
            owner=owner,
        )
        _expect_string_list(errors, raw_row.get("tests_gates"), field="tests_gates", owner=owner)
        _validate_object_list(
            errors,
            raw_row.get("vocabulary_owned"),
            field="vocabulary_owned",
            owner=owner,
            required_keys={"kind", "owner", "terms"},
        )
        _validate_object_list(
            errors,
            raw_row.get("string_policy"),
            field="string_policy",
            owner=owner,
            required_keys={"category", "owner", "policy"},
        )
        _validate_object_list(
            errors,
            raw_row.get("configurable_seams"),
            field="configurable_seams",
            owner=owner,
            required_keys={
                "declaration_site",
                "inherits_via",
                "override_mechanism",
                "meaning_owner",
                "supported_state",
            },
        )

        first_extraction_unit = raw_row.get("first_extraction_unit")
        if first_extraction_unit is not None and not (
            isinstance(first_extraction_unit, str) and first_extraction_unit.strip()
        ):
            errors.append(f"{owner} first_extraction_unit must be a non-empty string or null")

        if granularity != "symbol":
            seen.add((source, granularity))

        if granularity in {"file", "symbol"} and source not in tracked_files:
            # Legacy M-stage rows are migration inventory. They remain useful as
            # advisory history even when the concrete source moved or was
            # deleted; coverage below is enforced against current tracked files.
            if source.startswith("arnold_pipelines/megaplan/") and not _is_legacy_manifest_source(raw_source):
                errors.append(
                    f"{owner} source {source!r} must be an exact tracked file from "
                    "`git ls-files -- 'arnold_pipelines/megaplan/**/*.py'`"
                )
        if granularity == "directory" and source in tracked_files:
            errors.append(
                f"{owner} source {source!r} is a tracked file; directory rows must point to directories"
            )
        if granularity in {"directory", "split"} and source not in tracked_files:
            members = _directory_members(source, tracked_files)
            if not members and granularity == "directory" and not _is_legacy_manifest_source(raw_source):
                errors.append(
                    f"{owner} directory source {source!r} does not contain tracked files"
                )
            if not members and granularity == "split" and not _is_legacy_manifest_source(raw_source):
                errors.append(
                    f"{owner} split source {source!r} must be either a tracked file "
                    "or a directory containing tracked files"
                )

        rows.append(
            Row(
                index=index,
                source=source,
                target=target.strip(),
                granularity=granularity,
                disposition=disposition,
                data=raw_row,
            )
        )

    return rows


def _validate_gates(data: dict[str, Any], errors: list[str]) -> None:
    parity_statuses = {"already-tested", "needs-new-smoke-test", "static-gate-only"}
    for index, gate in enumerate(data.get("parity_gates") or [], start=1):
        owner = f"parity_gates[{index}]"
        if not isinstance(gate, dict):
            errors.append(f"{owner} must be a mapping")
            continue
        for field in ("name", "description", "status"):
            if not isinstance(gate.get(field), str) or not gate[field].strip():
                errors.append(f"{owner} field '{field}' must be a non-empty string")
        if gate.get("status") not in parity_statuses:
            errors.append(
                f"{owner} status {gate.get('status')!r} invalid; expected one of "
                f"{', '.join(sorted(parity_statuses))}"
            )
        _expect_string_list(errors, gate.get("tests"), field="tests", owner=owner)

    for index, gate in enumerate(data.get("runtime_settings_gates") or [], start=1):
        owner = f"runtime_settings_gates[{index}]"
        if not isinstance(gate, dict):
            errors.append(f"{owner} must be a mapping")
            continue
        for field in (
            "name",
            "description",
            "declaration_site",
            "inherits_via",
            "override_mechanism",
            "meaning_owner",
            "supported_state",
        ):
            if not isinstance(gate.get(field), str) or not gate[field].strip():
                errors.append(f"{owner} field '{field}' must be a non-empty string")
        _expect_string_list(errors, gate.get("tests"), field="tests", owner=owner)


def _validate_exclusions(
    data: dict[str, Any],
    tracked_files: list[str],
    errors: list[str],
) -> dict[str, list[str]]:
    exclusion_matches: dict[str, list[str]] = {}
    for index, entry in enumerate(data.get("coverage_exclusions") or [], start=1):
        owner = f"coverage_exclusions[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{owner} must be a mapping")
            continue
        missing = sorted({"source", "reason", "evidence"} - set(entry))
        if missing:
            errors.append(f"{owner} missing required fields: {', '.join(missing)}")
            continue
        for field in ("reason", "evidence"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{owner} field '{field}' must be a non-empty string")
        try:
            pattern = _normalize_path(entry["source"], allow_glob=True)
        except ValueError as exc:
            errors.append(f"{owner} source {entry.get('source')!r} invalid: {exc}")
            continue
        matches = _matches(pattern, tracked_files)
        if not matches:
            errors.append(
                f"{owner} source {pattern!r} does not match any tracked "
                "`arnold_pipelines/megaplan/**/*.py` file"
            )
            continue
        exclusion_matches[owner] = matches
    return exclusion_matches


def _validate_coverage(
    rows: list[Row],
    exclusions: dict[str, list[str]],
    tracked_files: list[str],
    errors: list[str],
) -> None:
    rows_by_source = {(row.source, row.granularity): row for row in rows}
    split_parents = [row for row in rows if row.granularity == "split"]

    for row in rows:
        if row.granularity == "symbol":
            if _is_legacy_manifest_source(str(row.data.get("source", ""))):
                continue
            if row.source not in tracked_files:
                continue
            has_parent = (row.source, "split") in rows_by_source or any(
                parent.source != row.source
                and row.source.startswith(f"{parent.source}/")
                for parent in split_parents
                if parent.source not in tracked_files
            )
            if not has_parent:
                errors.append(
                    f"{row.label} must refine a split row for the same file or an ancestor directory"
                )

    for row in split_parents:
        if _is_legacy_manifest_source(str(row.data.get("source", ""))):
            continue
        if row.source in tracked_files:
            children = [child for child in rows if child.source == row.source and child.granularity == "symbol"]
            if not children:
                errors.append(
                    f"{row.label} is split-required for a file and needs symbol child rows"
                )
            continue

        descendants = [
            child
            for child in rows
            if child.source.startswith(f"{row.source}/")
            and child.granularity in {"file", "directory", "split", "symbol"}
        ]
        if not descendants:
            if not _is_legacy_manifest_source(str(row.data.get("source", ""))):
                errors.append(
                    f"{row.label} is split-required for a directory and needs descendant child rows"
                )

    owners: dict[str, list[str]] = {path: [] for path in tracked_files}

    # Row coverage takes precedence; exclusions only fill gaps.
    for row in rows:
        if row.granularity == "symbol":
            continue
        if row.granularity == "file":
            covered = [row.source]
        elif row.granularity == "directory":
            covered = _directory_members(row.source, tracked_files)
        elif row.granularity == "split" and row.source in tracked_files:
            covered = [row.source]
        else:
            covered = []
        for path in covered:
            if path in owners:
                owners[path].append(row.label)

    for exclusion_owner, covered_paths in exclusions.items():
        for path in covered_paths:
            if path in owners and not owners[path]:
                owners[path].append(exclusion_owner)

    for path, path_owners in owners.items():
        if not path_owners:
            errors.append(
                f"tracked file {path!r} is uncovered; add a file/directory/split row or explicit exclusion"
            )
            continue


def validate_manifest(data: dict[str, Any], tracked_files: list[str]) -> list[str]:
    errors: list[str] = []
    _validate_top_level(data, errors)
    _validate_gates(data, errors)
    rows = _parse_rows(data, tracked_files, errors)
    exclusions = _validate_exclusions(data, tracked_files, errors)
    _validate_coverage(rows, exclusions, tracked_files, errors)
    return errors


def render_summary(data: dict[str, Any], tracked_files: list[str]) -> str:
    rows = [
        row
        for row in _parse_rows(data, tracked_files, [])
        if row.disposition in EXPECTED_DISPOSITIONS
    ]
    exclusions = _validate_exclusions(data, tracked_files, [])
    disposition_counts = Counter(row.disposition for row in rows)
    target_counts = Counter(row.target for row in rows)
    excluded_count = len({path for paths in exclusions.values() for path in paths})

    lines = [
        f"Tracked files: {len(tracked_files)}",
        f"Rows: {len(rows)}",
        f"Excluded files: {excluded_count}",
        "Disposition counts:",
    ]
    for disposition in EXPECTED_DISPOSITIONS:
        lines.append(f"  {disposition}: {disposition_counts.get(disposition, 0)}")
    lines.append("Target package counts:")
    for target, count in sorted(target_counts.items()):
        lines.append(f"  {target}: {count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="docs/arnold/package-disposition.yaml",
        help="Path to the YAML manifest to validate.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for git ls-files coverage checks.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print disposition and target-package counts.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()

    try:
        tracked_files = _tracked_python_files(repo_root)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or str(exc), file=sys.stderr)
        return 1

    try:
        data = _load_yaml(manifest_path)
    except FileNotFoundError:
        print(f"manifest file not found: {manifest_path}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"failed to parse YAML: {exc}", file=sys.stderr)
        return 1

    errors = validate_manifest(data, tracked_files)
    if args.summary:
        print(render_summary(data, tracked_files))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        f"Validated {manifest_path.relative_to(repo_root)} against "
        f"{len(tracked_files)} tracked megaplan/**/*.py files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
