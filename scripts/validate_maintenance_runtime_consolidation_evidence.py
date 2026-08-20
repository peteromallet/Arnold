#!/usr/bin/env python3
"""Validate the T0.3 maintenance-consolidation evidence contract.

The JSON schema validates record shape; this module validates custody, cross-record
references, ordering, routing, and artifact digests.  Errors are deliberately
ordered by code, then record location, so CI and downstream agents can consume
stable output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import jsonschema
except ImportError:  # pragma: no cover - the semantic validator remains usable
    jsonschema = None

SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SCHEMA_VERSION = "maintenance-runtime-consolidation-evidence.v1"
ROUTES = {
    "XHARD": "grok-4.6",
    "XHARD-REVIEW": "grok-4.6",
    "XHARD-REVISION": "grok-4.6",
    "JUDGMENT": "grok-4.6",
    "HARD": "gpt-5.6-luna",
    "HARD-REVIEW": "gpt-5.6-luna",
    "HARD-REVISION": "gpt-5.6-luna",
    "BRIEF": "gpt-5.6-luna",
    "WORKSPACE": "gpt-5.6-luna",
    "INTEGRATION": "gpt-5.6-luna",
    "VALIDATION": "gpt-5.6-luna",
    "REPORT": "gpt-5.6-luna",
}
ALLOWANCE_CATEGORIES = (
    "production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces"
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def _path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def _digest_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _issue(issues: list[ValidationIssue], code: str, path: str, message: str) -> None:
    issues.append(ValidationIssue(code, path, message))


def _items(manifest: dict[str, Any], key: str) -> list[Any]:
    value = manifest.get(key)
    return value if isinstance(value, list) else []


def _norm_role(value: Any) -> str:
    return str(value or "").strip().strip("[]").upper()


def expected_model(record: dict[str, Any]) -> str | None:
    role = _norm_role(record.get("role"))
    if role in ROUTES:
        return ROUTES[role]
    difficulty = _norm_role(record.get("difficulty"))
    return ROUTES.get(difficulty)


def _unique_ids(issues: list[ValidationIssue], values: list[Any], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(values):
        path = f"{label}[{index}]"
        if not isinstance(item, dict):
            _issue(issues, "MALFORMED_RECORD", path, "record must be an object")
            continue
        value = item.get(key)
        if not isinstance(value, str) or not value:
            _issue(issues, "MISSING_FIELD", f"{path}.{key}", "identifier is required")
            continue
        if value in result:
            _issue(issues, "DUPLICATE_ID", f"{path}.{key}", f"duplicate {key} {value!r}")
        else:
            result[value] = item
    return result


def _check_artifact(issues: list[ValidationIssue], root: Path, record: dict[str, Any], location: str, *, digest_key: str = "sha256") -> None:
    path_value = record.get("path") or record.get("artifact_path") or record.get("file")
    digest = record.get(digest_key) or record.get("artifact_digest")
    path = _path(root, path_value)
    if path is None:
        _issue(issues, "MISSING_FILE", f"{location}.path", "required artifact path is missing")
        return
    if not path.is_file():
        _issue(issues, "MISSING_FILE", f"{location}.path", f"artifact does not exist: {path_value}")
        return
    actual = _digest_file(path)
    if not isinstance(digest, str) or not SHA256.fullmatch(digest or ""):
        _issue(issues, "DIGEST_MISMATCH", f"{location}.{digest_key}", "artifact digest is not a SHA-256")
    elif actual != digest:
        _issue(issues, "DIGEST_MISMATCH", location, f"expected {digest}, observed {actual}")


def _process_identity(record: dict[str, Any]) -> Any:
    return record.get("process_identity", record.get("child_process_identity"))


def _invocation_model(record: dict[str, Any]) -> str:
    return str(record.get("resolved_model") or record.get("model") or "")


def validate_manifest(manifest_path: str | Path) -> list[ValidationIssue]:
    path = Path(manifest_path).resolve()
    issues: list[ValidationIssue] = []
    root = path.parents[3] if len(path.parents) >= 4 else path.parent
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [ValidationIssue("MISSING_FILE", "manifest", f"manifest does not exist: {path}")]
    except (OSError, json.JSONDecodeError) as exc:
        return [ValidationIssue("MALFORMED_MANIFEST", "manifest", str(exc))]
    if not isinstance(manifest, dict):
        return [ValidationIssue("MALFORMED_MANIFEST", "manifest", "top-level value must be an object")]

    if manifest.get("schema") != "maintenance-runtime-consolidation-evidence" or manifest.get("schema_version") != SCHEMA_VERSION:
        _issue(issues, "SCHEMA_VERSION", "schema_version", f"expected {SCHEMA_VERSION}")
    schema_path = path.with_name("manifest.schema.v1.json")
    if jsonschema is not None and schema_path.is_file():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            for error in sorted(validator.iter_errors(manifest), key=lambda item: (".".join(map(str, item.path)), item.message)):
                location = ".".join(map(str, error.path)) or "manifest"
                _issue(issues, "SCHEMA_INVALID", location, error.message)
        except (OSError, json.JSONDecodeError) as exc:
            _issue(issues, "SCHEMA_INVALID", "schema", str(exc))

    integration = manifest.get("integration")
    if not isinstance(integration, dict):
        _issue(issues, "MISSING_RECORD", "integration", "integration identity record is required")
    else:
        for key in ("integration_base_sha", "integration_current_sha", "branch", "worktree"):
            if not integration.get(key):
                _issue(issues, "MISSING_FIELD", f"integration.{key}", "required integration identity is missing")
        for key in ("integration_base_sha", "integration_current_sha"):
            if integration.get(key) and not SHA40.fullmatch(str(integration[key])):
                _issue(issues, "MALFORMED_RECORD", f"integration.{key}", "must be a 40-character Git SHA")
        selection = integration.get("g0_selection_manifest")
        if not isinstance(selection, dict):
            _issue(issues, "MISSING_RECORD", "integration.g0_selection_manifest", "G0 selection manifest binding is required")
        else:
            _check_artifact(issues, root, selection, "integration.g0_selection_manifest", digest_key="sha256")

    source_inputs = _items(manifest, "source_inputs")
    if not source_inputs:
        _issue(issues, "MISSING_RECORD", "source_inputs", "at least one immutable source-input record is required")
    for index, record in enumerate(source_inputs):
        if isinstance(record, dict):
            _check_artifact(issues, root, record, f"source_inputs[{index}]")
            if record.get("provenance") != "read_only":
                _issue(issues, "CUSTODY_VIOLATION", f"source_inputs[{index}].provenance", "source input must be read_only")

    selected = _items(manifest, "selected_behaviors")
    for index, record in enumerate(selected):
        if not isinstance(record, dict) or not record.get("behavior_id"):
            _issue(issues, "MALFORMED_RECORD", f"selected_behaviors[{index}]", "behavior_id is required")
        task_ids = record.get("task_ids") if isinstance(record, dict) else None
        if not isinstance(task_ids, list) or len(task_ids) != 1 or not isinstance(task_ids[0], str):
            _issue(issues, "UNMAPPED_SELECTED_BEHAVIOR", f"selected_behaviors[{index}]", "each behavior must reference exactly one task")

    tasks = _items(manifest, "tasks")
    task_map = _unique_ids(issues, tasks, "task_id", "tasks")
    gates = _items(manifest, "gates")
    gate_map = _unique_ids(issues, gates, "gate_id", "gates")
    shards = _items(manifest, "shards")
    _unique_ids(issues, shards, "shard_id", "shards")
    findings = _items(manifest, "findings")
    finding_map = _unique_ids(issues, findings, "finding_id", "findings")
    judgments = _items(manifest, "material_judgments")
    judgment_map = _unique_ids(issues, judgments, "judgment_id", "material_judgments")
    for key in ("tasks", "gates", "shards", "allowances", "candidate_install_receipts", "live_state_snapshots", "canary_rollback_receipts", "broad_suite_receipts"):
        if not _items(manifest, key):
            _issue(issues, "MISSING_RECORD", key, f"required future record collection {key!r} is empty")

    invocations = _items(manifest, "invocation_receipts")
    invocation_map: dict[str, dict[str, Any]] = {}
    process_map: dict[str, str] = {}
    for index, record in enumerate(invocations):
        if not isinstance(record, dict):
            _issue(issues, "MALFORMED_RECORD", f"invocation_receipts[{index}]", "record must be an object")
            continue
        invocation_id = record.get("invocation_id")
        if not isinstance(invocation_id, str) or not invocation_id:
            _issue(issues, "MISSING_FIELD", f"invocation_receipts[{index}].invocation_id", "invocation_id is required")
        elif invocation_id in invocation_map:
            _issue(issues, "DUPLICATE_INVOCATION_ID", f"invocation_receipts[{index}].invocation_id", f"duplicate invocation_id {invocation_id!r}")
        else:
            invocation_map[invocation_id] = record
        identity = _process_identity(record)
        if isinstance(identity, str) and identity and identity != "unknown":
            if identity in process_map:
                _issue(issues, "DUPLICATE_PROCESS_IDENTITY", f"invocation_receipts[{index}].process_identity", "process identity is reused")
            else:
                process_map[identity] = str(invocation_id)
        if record.get("bootstrap_exception") is not True:
            for field in ("command_digest", "brief_digest", "stdout_digest", "stderr_digest"):
                if not SHA256.fullmatch(str(record.get(field) or "")):
                    _issue(issues, "DIGEST_MISMATCH", f"invocation_receipts[{index}].{field}", "receipt digest is invalid")
        for field in ("stdout_path", "stderr_path", "result_path"):
            if record.get(field):
                _check_artifact(issues, root, {"path": record[field], "sha256": record.get(field.replace("_path", "_digest"))}, f"invocation_receipts[{index}].{field}")

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        task_id = task.get("task_id")
        gate_id = task.get("gate_id")
        if task_id and gate_id not in gate_map:
            _issue(issues, "MISSING_REFERENCE", f"tasks[{index}].gate_id", f"task {task_id!r} does not map to a gate")
        allowance_id = task.get("complete_allowance_id")
        allowance_ids = [item.get("allowance_id") for item in _items(manifest, "allowances") if isinstance(item, dict)]
        if allowance_id not in allowance_ids:
            _issue(issues, "MISSING_ALLOWANCE", f"tasks[{index}].complete_allowance_id", "task has no complete allowance registry record")
        implementer = task.get("implementer") if isinstance(task.get("implementer"), dict) else task
        model = _invocation_model(implementer)
        expected = expected_model(task)
        if expected is None:
            _issue(issues, "UNCLASSIFIED_ROLE", f"tasks[{index}].role", "task role/difficulty is not classified")
        elif model and expected not in model:
            _issue(issues, "WRONG_MODEL_ROUTE", f"tasks[{index}].implementer.model", f"expected {expected}, observed {model}")
        inv_id = implementer.get("invocation_id")
        if inv_id and inv_id not in invocation_map:
            _issue(issues, "MISSING_REFERENCE", f"tasks[{index}].implementer.invocation_id", "implementer receipt is missing")
        for receipt_index, receipt in enumerate(task.get("focused_test_receipts", [])):
            if isinstance(receipt, dict):
                _check_artifact(issues, root, receipt, f"tasks[{index}].focused_test_receipts[{receipt_index}]")

    review_invocations = _items(manifest, "review_invocations")
    review_by_task: dict[str, list[dict[str, Any]]] = {}
    for index, review in enumerate(review_invocations):
        if not isinstance(review, dict):
            continue
        task_id = str(review.get("task_id") or "")
        review_by_task.setdefault(task_id, []).append(review)
        expected = expected_model(review)
        model = _invocation_model(review)
        if expected is None:
            _issue(issues, "UNCLASSIFIED_ROLE", f"review_invocations[{index}].role", "review role is not classified")
        elif model and expected not in model:
            _issue(issues, "WRONG_MODEL_ROUTE", f"review_invocations[{index}].model", f"expected {expected}, observed {model}")
        if review.get("invocation_id") not in invocation_map:
            _issue(issues, "MISSING_REFERENCE", f"review_invocations[{index}].invocation_id", "review receipt is missing")

    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            continue
        reviewer = gate.get("reviewer") if isinstance(gate.get("reviewer"), dict) else gate
        task_refs = gate.get("task_ids") or ([gate.get("task_id")] if gate.get("task_id") else [])
        for task_id in task_refs:
            task = task_map.get(task_id)
            if task is None:
                _issue(issues, "MISSING_REFERENCE", f"gates[{index}].task_ids", f"unknown task {task_id!r}")
                continue
            impl = task.get("implementer") if isinstance(task.get("implementer"), dict) else task
            reviewer_id = _process_identity(reviewer)
            impl_id = _process_identity(impl)
            if reviewer_id and impl_id and reviewer_id != "unknown" and reviewer_id == impl_id:
                _issue(issues, "SELF_REVIEW", f"gates[{index}].reviewer.process_identity", "reviewer and implementer process identities are equal")
            if reviewer.get("invocation_id") and reviewer.get("invocation_id") == impl.get("invocation_id"):
                _issue(issues, "SELF_REVIEW", f"gates[{index}].reviewer.invocation_id", "reviewer and implementer invocation IDs are equal")
        expected = expected_model(reviewer)
        model = _invocation_model(reviewer)
        if expected and model and expected not in model:
            _issue(issues, "WRONG_MODEL_ROUTE", f"gates[{index}].reviewer.model", f"expected {expected}, observed {model}")

    for task_id, task in task_map.items():
        difficulty = _norm_role(task.get("difficulty") or task.get("role"))
        if difficulty == "XHARD":
            phases = [str(item.get("phase") or "") for item in review_by_task.get(task_id, [])]
            if phases != ["pre_review", "implementation", "post_review"]:
                _issue(issues, "WRONG_HARD_REVIEW_ORDER", f"tasks[{task_id}].review_invocations", "XHARD task requires ordered pre_review, implementation, post_review lifecycle")
        elif any(str(item.get("phase") or "") in {"pre_review", "post_review"} for item in review_by_task.get(task_id, [])):
            _issue(issues, "WRONG_HARD_REVIEW_ORDER", f"tasks[{task_id}].review_invocations", "ordinary task cannot claim XHARD lifecycle")

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        revision_class = str(finding.get("adjudicated_revision_class") or finding.get("proposed_revision_class") or "")
        if revision_class not in {"[HARD-REVISION]", "[XHARD-REVISION]"}:
            _issue(issues, "UNCLASSIFIED_REVIEW_REPAIR", f"findings[{index}].adjudicated_revision_class", "repair must be classified as HARD-REVISION or XHARD-REVISION")
        revision_id = finding.get("revision_invocation_id")
        rereview_id = finding.get("re_review_invocation_id")
        revision = invocation_map.get(revision_id)
        rereview = invocation_map.get(rereview_id)
        if not revision or not revision.get("commit"):
            _issue(issues, "INCOMPLETE_REVISION_CHAIN", f"findings[{index}]", "revision invocation and commit are required")
        if not rereview or not (rereview.get("verdict") or rereview.get("disposition")):
            _issue(issues, "INCOMPLETE_REVISION_CHAIN", f"findings[{index}]", "re-review invocation and verdict are required")
        if revision and revision_id in invocation_map and expected_model({"role": revision.get("role")}) not in _invocation_model(revision):
            _issue(issues, "WRONG_MODEL_ROUTE", f"findings[{index}].revision_invocation_id", "revision model route is wrong")

    for index, judgment in enumerate(judgments):
        if not isinstance(judgment, dict):
            continue
        model = _invocation_model(judgment)
        if "grok-4.6" not in model:
            _issue(issues, "WRONG_MODEL_ROUTE", f"material_judgments[{index}].model", "material judgment requires Grok 4.6")
        inv_id = judgment.get("invocation_id") or (judgment.get("grok_invocation") or {}).get("invocation_id")
        if not inv_id or inv_id not in invocation_map:
            _issue(issues, "MISSING_GROK_RECEIPT", f"material_judgments[{index}]", "material judgment must link a Grok invocation receipt")
    allowance_by_task: dict[str, int] = {}
    for allowance in _items(manifest, "allowances"):
        if isinstance(allowance, dict):
            task_id = str(allowance.get("task_id") or "")
            allowance_by_task[task_id] = allowance_by_task.get(task_id, 0) + 1
            if task_id and task_id not in task_map:
                _issue(issues, "MISSING_REFERENCE", "allowances", f"allowance references unknown task {task_id!r}")
    for task_id in task_map:
        if allowance_by_task.get(task_id, 0) != 1:
            _issue(issues, "MISSING_ALLOWANCE", f"tasks[{task_id}].complete_allowance_id", "exactly one allowance registry record is required per task")

    allowance_map = _unique_ids(issues, _items(manifest, "allowances"), "allowance_id", "allowances")
    active_paths: list[tuple[str, str]] = []
    for index, allowance in enumerate(_items(manifest, "allowances")):
        if not isinstance(allowance, dict):
            continue
        paths: list[str] = []
        for category in ALLOWANCE_CATEGORIES:
            values = allowance.get(category, [])
            if not isinstance(values, list):
                _issue(issues, "MALFORMED_RECORD", f"allowances[{index}].{category}", "allowance category must be a list")
                continue
            paths.extend(str(value) for value in values)
        if not paths or not allowance.get("lifecycle_state"):
            _issue(issues, "MISSING_ALLOWANCE", f"allowances[{index}]", "complete allowance categories and lifecycle_state are required")
        expected_digest = canonical_sha256({key: allowance.get(key, []) for key in (*ALLOWANCE_CATEGORIES, "lifecycle_state", "active")})
        if allowance.get("allowance_digest") != expected_digest:
            _issue(issues, "DIGEST_MISMATCH", f"allowances[{index}].allowance_digest", "allowance digest does not match canonical registry content")
        if allowance.get("active"):
            for path_value in paths:
                normalized = str(Path(path_value))
                for previous, previous_id in active_paths:
                    if normalized == previous or normalized.startswith(previous.rstrip("/") + "/") or previous.startswith(normalized.rstrip("/") + "/"):
                        _issue(issues, "OVERLAPPING_ALLOWANCE", f"allowances[{index}]", f"active allowance overlaps {previous_id}")
                active_paths.append((normalized, str(allowance.get("allowance_id"))))

    for index, shard in enumerate(shards):
        if isinstance(shard, dict):
            _check_artifact(issues, root, shard, f"shards[{index}]")
            for field in ("command", "source_sha", "interpreter", "runtime_digest", "spec_digest", "venv_digest", "disposable_root", "status"):
                if not shard.get(field):
                    _issue(issues, "MISSING_FIELD", f"shards[{index}].{field}", "required shard field is missing")

    for collection in ("candidate_install_receipts", "live_state_snapshots", "canary_rollback_receipts"):
        for index, receipt in enumerate(_items(manifest, collection)):
            if isinstance(receipt, dict):
                _check_artifact(issues, root, receipt, f"{collection}[{index}]")

    broad = _items(manifest, "broad_suite_receipts")
    authoritative = [item for item in broad if isinstance(item, dict) and item.get("authoritative", True)]
    if len(authoritative) > 1:
        _issue(issues, "SECOND_BROAD_SUITE", "broad_suite_receipts", "broad_suite_once_v1 permits one authoritative invocation")
    for index, receipt in enumerate(broad):
        if isinstance(receipt, dict):
            _check_artifact(issues, root, receipt, f"broad_suite_receipts[{index}]")

    for index, artifact in enumerate(_items(manifest, "required_artifacts")):
        if isinstance(artifact, dict):
            _check_artifact(issues, root, artifact, f"required_artifacts[{index}]")

    return sorted(issues, key=lambda item: (item.code, item.path, item.message))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    issues = validate_manifest(args.manifest)
    if issues:
        for issue in issues:
            print(json.dumps(issue.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps({"status": "valid", "manifest": str(args.manifest)}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
