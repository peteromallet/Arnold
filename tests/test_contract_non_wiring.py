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


@pytest.mark.parametrize(
    ("step", "payload"),
    [
        ("finalize", {"meta_commentary": "x"}),
        ("critique", {"verified_flag_ids": [], "disputed_flag_ids": []}),
        ("review", {"criteria": [], "issues": [], "rework_items": [], "summary": "ok", "task_verdicts": [], "sense_check_verdicts": []}),
        ("gate", {"rationale": "ok", "signals_assessment": "ok"}),
    ],
)
def test_validate_payload_rejects_migrated_step_names(step: str, payload: dict[str, object]) -> None:
    with pytest.raises(CliError, match=rf"retired for {step}"):
        validate_payload(step, payload)


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
# T1 characterization: inventory of handler-level validate_payload call
# sites for migrated vs long-tail steps.
#
# After m5, the critique handler line 672 and review handler line 932
# calls must be REMOVED (migrated sites). The critique handler line 727
# (revise) stays as the remaining long-tail legacy caller.
# ---------------------------------------------------------------------------

_MIGRATED_HANDLER_STEPS: tuple[str, ...] = ("critique", "review")


def test_critique_handler_calls_validate_payload_for_critique_step() -> None:
    """Characterization: critique handler currently calls validate_payload()
    for its own step output and for revise (long-tail).

    After m5, the critique-step call MUST be removed.  The revise-step
    call stays.  This test pins the current import-and-call relationship.
    """
    import ast
    from pathlib import Path

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/handlers/critique.py"
    )
    source = handler_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Verify validate_payload is imported
    imports_validate = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "arnold.pipelines.megaplan.workers"
        and any(alias.name == "validate_payload" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_validate, "critique handler must import validate_payload"

    # Find the actual call sites
    call_args: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "validate_payload"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    call_args.append(node.args[0].value)
    # Critique is migrated; only the revise long-tail call should remain.
    assert "critique" not in call_args, (
        f"critique handler must not call validate_payload('critique', ...); "
        f"found: {call_args}"
    )
    assert "revise" in call_args, (
        f"critique handler must still call validate_payload('revise', ...); "
        f"found: {call_args}"
    )
    assert len(call_args) == 1, (
        f"Expected exactly 1 validate_payload call for revise, found {len(call_args)}: {call_args}"
    )


def test_review_handler_no_longer_imports_or_calls_validate_payload_for_review_step() -> None:
    """Review handler merge paths must be off legacy validate_payload().

    The review handler should validate review-shaped payloads through seam
    schema audit only.
    """
    import ast
    from pathlib import Path

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/handlers/review.py"
    )
    source = handler_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports_validate = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "arnold.pipelines.megaplan.workers"
        and any(alias.name == "validate_payload" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not imports_validate, "review handler must not import validate_payload"

    call_args: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "validate_payload"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    call_args.append(node.args[0].value)
    assert "review" not in call_args, (
        f"review handler must not call validate_payload('review', ...); "
        f"found: {call_args}"
    )


def test_execute_handler_no_longer_imports_or_calls_validate_payload() -> None:
    """Execute is fully off legacy validate_payload().

    Its review stub remains a structural coupling to the review schema, but
    that coupling must now run through seam-owned schema audit.
    """
    import ast
    from pathlib import Path

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/handlers/execute.py"
    )
    source = handler_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports_validate = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "arnold.pipelines.megaplan.workers"
        and any(alias.name == "validate_payload" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not imports_validate, "execute handler must not import validate_payload"

    call_args: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "validate_payload"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    call_args.append(node.args[0].value)
    assert not call_args, (
        f"execute handler must not call validate_payload(...); found: {call_args}"
    )


def test_finalize_handler_does_not_call_validate_payload() -> None:
    """Characterization: finalize handler does NOT directly call
    validate_payload().  It uses _validate_finalize_payload() instead.
    This means finalize migration will focus on the write path and schema
    audit, not on removing a validate_payload call site."""
    import ast
    from pathlib import Path

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/handlers/finalize.py"
    )
    source = handler_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "validate_payload"
            ):
                raise AssertionError(
                    "finalize handler must NOT call validate_payload() directly"
                )
        if isinstance(node, ast.ImportFrom):
            if node.module == "arnold.pipelines.megaplan.workers":
                for alias in node.names:
                    if alias.name == "validate_payload":
                        raise AssertionError(
                            "finalize handler must NOT import validate_payload"
                        )


def test_gate_handler_does_not_call_validate_payload() -> None:
    """Characterization: gate handler does NOT directly call
    validate_payload()."""
    import ast
    from pathlib import Path

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/handlers/gate.py"
    )
    source = handler_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "validate_payload"
            ):
                raise AssertionError(
                    "gate handler must NOT call validate_payload() directly"
                )
        if isinstance(node, ast.ImportFrom):
            if node.module == "arnold.pipelines.megaplan.workers":
                for alias in node.names:
                    if alias.name == "validate_payload":
                        raise AssertionError(
                            "gate handler must NOT import validate_payload"
                        )


def test_recovery_helpers_do_not_call_validate_payload_for_migrated_steps() -> None:
    """Recovery keeps the legacy validator only behind the non-schema-audited branch.

    This AST ratchet proves the recovery helpers still reference validate_payload()
    only through the shared `step` variable, never by migrated literal step names.
    """
    source_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/workers/_impl.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    migrated_steps = {"finalize", "critique", "review", "gate"}
    recovery_functions = {"_recover_payload_from_candidates", "_recover_codex_payload_with_provenance"}
    seen_recovery_calls = 0

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in recovery_functions:
            continue
        for subnode in ast.walk(node):
            if not (
                isinstance(subnode, ast.Call)
                and isinstance(subnode.func, ast.Name)
                and subnode.func.id == "validate_payload"
            ):
                continue
            seen_recovery_calls += 1
            assert subnode.args, f"{node.name} calls validate_payload() without args"
            first_arg = subnode.args[0]
            assert isinstance(first_arg, ast.Name) and first_arg.id == "step", (
                f"{node.name} must only pass the dynamic step variable to validate_payload(); "
                f"found {ast.dump(first_arg, include_attributes=False)}"
            )
        for migrated_step in migrated_steps:
            assert f'validate_payload("{migrated_step}"' not in ast.get_source_segment(source, node), (
                f"{node.name} must not hard-code validate_payload('{migrated_step}', ...)"
            )

    assert seen_recovery_calls >= 2, "Expected recovery helpers to retain the legacy validate_payload() branch"


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
