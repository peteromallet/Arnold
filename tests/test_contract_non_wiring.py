from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.store import PlanRepository
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import validate_payload


def test_validate_payload_remains_key_presence_only_for_known_steps() -> None:
    validate_payload(
        "plan",
        {
            "plan": None,
            "questions": "not-a-list",
            "success_criteria": 7,
            "assumptions": {"still": "accepted"},
            "extra": object(),
        },
    )


def test_validate_payload_missing_required_keys_still_fail() -> None:
    with pytest.raises(CliError, match="plan output missing required keys: assumptions"):
        validate_payload(
            "plan",
            {
                "plan": "x",
                "questions": [],
                "success_criteria": [],
            },
        )


def test_validate_payload_unknown_steps_remain_noop() -> None:
    validate_payload("totally_new_step", {"anything": "goes"})


def test_validate_payload_execute_batch_shape_remains_accepted() -> None:
    validate_payload(
        "execute",
        {
            "task_updates": "still only checked for presence",
            "sense_check_acknowledgments": None,
            "unexpected": ["extra keys still ignored"],
        },
    )


def test_validate_payload_execute_missing_batch_keys_still_fail() -> None:
    with pytest.raises(CliError, match="Batch execute payloads may omit aggregate fields"):
        validate_payload("execute", {"output": "missing batch bookkeeping"})


def test_plan_repository_read_artifact_json_remains_plain_json_read(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "plan",
                "idea": "idea",
                "current_state": "initialized",
                "iteration": 1,
                "created_at": "2026-06-06T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )
    repo = PlanRepository.from_plan_dir(plan_dir)

    (plan_dir / "object.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (plan_dir / "array.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    (plan_dir / "scalar.json").write_text(json.dumps("plain-string"), encoding="utf-8")

    assert repo.read_artifact_json("object.json") == {"ok": True}
    assert repo.read_artifact_json("array.json") == [1, 2, 3]
    assert repo.read_artifact_json("scalar.json") == "plain-string"
    assert repo.read_artifact_json("missing.json") is None


# ---------------------------------------------------------------------------
# Static non-wiring guards: worker/stage files must not import or reference
# any M0b validator, registry, content-validation, or audit-policy module.
# ---------------------------------------------------------------------------

_M0B_MODULE_NAMES: tuple[str, ...] = (
    "contract_validation",
    "schema_registry",
    "content_validation",
    "audit_policy",
)

_NON_WIRING_PATHS: tuple[str, ...] = (
    "arnold/pipelines/megaplan/workers/shannon.py",
    "arnold/pipelines/megaplan/workers/hermes.py",
    "arnold/pipelines/megaplan/workers/_impl.py",
    "arnold/pipelines/megaplan/stages/critique.py",
    "arnold/pipelines/megaplan/stages/review.py",
    "arnold/pipelines/megaplan/stages/execute.py",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_source(rel_path: str) -> str:
    return (_repo_root() / rel_path).read_text(encoding="utf-8")


# --- text-level scan --------------------------------------------------------


@pytest.mark.parametrize("rel_path", _NON_WIRING_PATHS)
def test_no_m0b_import_or_call_in_source_text(rel_path: str) -> None:
    """Source text must not mention any M0b module in import statements."""
    source = _read_source(rel_path)
    lines = source.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for mod in _M0B_MODULE_NAMES:
            # Catch `import arnold.pipeline.<mod>` or `from arnold.pipeline import ... <mod> ...`
            if mod in line and ("import" in line or "from" in line):
                msg = (
                    f"{rel_path}:{lineno} references forbidden M0b module "
                    f"'{mod}' via import: {line.strip()!r}"
                )
                raise AssertionError(msg)
            # Catch bare `from arnold.pipeline.<mod> import ...`
            if f"arnold.pipeline.{mod}" in line:
                msg = (
                    f"{rel_path}:{lineno} references forbidden M0b module "
                    f"'{mod}' via dotted name: {line.strip()!r}"
                )
                raise AssertionError(msg)


@pytest.mark.parametrize("rel_path", _NON_WIRING_PATHS)
def test_no_m0b_function_call_in_source_text(rel_path: str) -> None:
    """Source text must not call known M0b public APIs directly."""
    source = _read_source(rel_path)
    forbidden_calls = (
        "validate_contract_result",
        "validate_payload_against_schema",
        "ContractSchemaRegistry",
        "ContentValidatorRegistry",
        "select_audit_mode",
        "AcceptedVersionRange",
        "ValidationDiagnostic",
        "ValidationResult",
    )
    lines = source.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for call_name in forbidden_calls:
            # Only flag actual calls/construction, not comments or strings
            if call_name in line and not line.lstrip().startswith(("#", '"', "'")):
                # Simple heuristic: name followed by ( means a call/construction
                idx = line.find(call_name)
                rest = line[idx + len(call_name):]
                if rest.lstrip().startswith("("):
                    msg = (
                        f"{rel_path}:{lineno} calls forbidden M0b API "
                        f"'{call_name}': {line.strip()!r}"
                    )
                    raise AssertionError(msg)


# --- AST-level scan --------------------------------------------------------


def _extract_import_names_ast(source: str, rel_path: str) -> set[str]:
    """Return the set of module/name paths referenced in import statements."""
    tree = ast.parse(textwrap.dedent(source))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                found.add(full)
    return found


@pytest.mark.parametrize("rel_path", _NON_WIRING_PATHS)
def test_no_m0b_import_via_ast(rel_path: str) -> None:
    """AST import nodes must not reference any M0b module."""
    source = _read_source(rel_path)
    import_names = _extract_import_names_ast(source, rel_path)
    for name in import_names:
        for mod in _M0B_MODULE_NAMES:
            if mod in name:
                msg = (
                    f"{rel_path} imports forbidden M0b module '{mod}' "
                    f"via AST import '{name}'"
                )
                raise AssertionError(msg)
