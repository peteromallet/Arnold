from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path

import pytest

from arnold.pipelines.megaplan import model_seam
from arnold.pipelines.megaplan.store import PlanRepository
from arnold.pipelines.megaplan.types import CliError


def _assert_validate_payload_not_importable() -> None:
    with pytest.raises(ImportError):
        exec("from arnold.pipelines.megaplan.workers._impl import validate_payload", {})


def test_loop_plan_native_audit_rejects_wrong_spec_updates_type() -> None:
    with pytest.raises(model_seam.ModelStructuralAuditError, match="/spec_updates"):
        model_seam.audit_step_payload(
            "loop_plan",
            {
                "spec_updates": [],
                "next_action": "continue",
                "reasoning": "wrong type",
            },
        )


def test_loop_plan_native_audit_requires_spec_updates() -> None:
    with pytest.raises(model_seam.ModelStructuralAuditError, match="spec_updates"):
        model_seam.audit_step_payload(
            "loop_plan",
            {
                "next_action": "continue",
                "reasoning": "missing spec updates",
            },
        )


def test_validate_payload_unknown_steps_are_not_authorized_by_orphan_path() -> None:
    _assert_validate_payload_not_importable()


def test_validate_payload_execute_batch_shape_is_retired() -> None:
    _assert_validate_payload_not_importable()


def test_validate_payload_execute_is_retired_for_any_payload() -> None:
    _assert_validate_payload_not_importable()


@pytest.mark.parametrize(
    ("step", "payload"),
    [
        ("finalize", {"meta_commentary": "x"}),
        ("critique", {"verified_flag_ids": [], "disputed_flag_ids": []}),
        ("review", {"criteria": [], "issues": [], "rework_items": [], "summary": "ok", "task_verdicts": [], "sense_check_verdicts": []}),
        ("gate", {"rationale": "ok", "signals_assessment": "ok"}),
        ("loop_plan", {"spec_updates": {}, "next_action": "continue", "reasoning": "ok"}),
        ("loop_execute", {"diagnosis": "x", "fix_description": "y", "files_to_change": [], "confidence": "low", "outcome": "continue", "should_pause": False}),
        (
            "tiebreaker_researcher",
            {
                "question": "Which option?",
                "evidence": [],
                "options": [],
                "preliminary_pick": {
                    "option_name": "A",
                    "rationale": "ok",
                    "what_im_least_sure_about": "tradeoffs",
                },
            },
        ),
        (
            "tiebreaker_challenger",
            {
                "measurements_vs_assumptions": "ok",
                "missing_options": [],
                "hard_cases": [],
                "reframings": [],
                "aging_analysis": "ok",
                "counter_recommendation": {
                    "option_name": "A",
                    "rationale": "ok",
                    "agrees_with_researcher": True,
                },
            },
        ),
    ],
)
def test_validate_payload_rejects_migrated_step_names(step: str, payload: dict[str, object]) -> None:
    _assert_validate_payload_not_importable()


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
    """Characterization: critique handler calls audit_step_payload() for revise.

    After m6-T5, revise is schema-audited via audit_step_payload, and the
    critique handler no longer imports validate_payload.
    """
    import ast
    from pathlib import Path

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/handlers/critique.py"
    )
    source = handler_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Verify validate_payload is NOT imported (revise migrated to native)
    imports_validate = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "arnold.pipelines.megaplan.workers"
        and any(alias.name == "validate_payload" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not imports_validate, "critique handler must no longer import validate_payload"

    # Verify audit_step_payload IS imported
    imports_audit = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "arnold.pipelines.megaplan.model_seam"
        and any(alias.name == "audit_step_payload" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_audit, "critique handler must import audit_step_payload"

    # Find the actual call sites
    call_args: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "audit_step_payload"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    call_args.append(node.args[0].value)
    assert "revise" in call_args, (
        "critique handler must call audit_step_payload('revise', ...); "
        f"found: {call_args}"
    )
    assert call_args.count("revise") == 1, (
        f"Expected exactly 1 audit_step_payload call for revise, "
        f"found {call_args.count('revise')}: {call_args}"
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


def test_megaplan_production_code_has_no_validate_payload_calls() -> None:
    package_root = Path(__file__).resolve().parents[1] / "arnold/pipelines/megaplan"
    violations: list[str] = []

    for path in sorted(package_root.rglob("*.py")):
        if "agent" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "validate_payload"
            ):
                violations.append(f"{path.relative_to(package_root.parent.parent)}:{node.lineno}")

    assert not violations, (
        "Production megaplan code must not call worker-level validate_payload(); "
        "use schema-backed capture/audit for model output and direct phase-result "
        f"validators for phase_result payloads. Found: {violations}"
    )


def test_recovery_helpers_do_not_call_validate_payload_for_migrated_steps() -> None:
    """Worker recovery helpers are deleted and seam recovery stays off validate_payload()."""
    worker_source_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/workers/_impl.py"
    )
    worker_source = worker_source_path.read_text(encoding="utf-8")
    assert "def _recover_codex_payload(" not in worker_source
    assert "def _recover_codex_payload_with_provenance(" not in worker_source

    seam_source_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/model_seam.py"
    )
    seam_source = seam_source_path.read_text(encoding="utf-8")
    tree = ast.parse(seam_source)
    migrated_steps = {"finalize", "critique", "review", "gate", "execute"}

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "_recover_payload_with_provenance":
            continue
        for subnode in ast.walk(node):
            if (
                isinstance(subnode, ast.Call)
                and isinstance(subnode.func, ast.Name)
                and subnode.func.id == "validate_payload"
            ):
                raise AssertionError("model_seam recovery must not call validate_payload()")
        for migrated_step in migrated_steps:
            assert f'validate_payload("{migrated_step}"' not in ast.get_source_segment(seam_source, node), (
                f"_recover_payload_with_provenance must not call validate_payload('{migrated_step}', ...)"
            )
        break
    else:
        raise AssertionError("model_seam must define _recover_payload_with_provenance")


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


# ---------------------------------------------------------------------------
# T2: Temporary long-tail allowlist for not-yet-migrated cohorts.
#
# All capture cohorts are now NATIVE, but the shared-helper deletion gate has
# not landed yet. Keep the symbol as an explicit ratchet until final cleanup
# removes the remaining legacy helper surface entirely.
# ---------------------------------------------------------------------------

_M6_LONG_TAIL_ALLOWLIST: tuple[str, ...] = ()


def test_long_tail_allowlist_is_empty_after_t7_capture_migration() -> None:
    assert _M6_LONG_TAIL_ALLOWLIST == (), (
        "T7 should migrate the remaining long-tail capture steps to NATIVE. "
        "Keep the symbol empty until the shared-helper deletion phase removes it."
    )


def test_migrated_steps_not_in_allowlist() -> None:
    """Steps already on the NATIVE path must NOT appear in the allowlist.

    The current migrated set in _COMPATIBILITY_MODE_BY_STEP = {
    execute, finalize, critique, review, gate, plan, prep,
    prep-triage, prep-distill, prep-research, feedback, critique_evaluator }.
    """
    migrated = {
        "finalize", "critique", "review", "gate", "execute",
        "plan", "prep", "prep-triage", "prep-distill", "prep-research",
        "feedback", "critique_evaluator", "revise",
    }
    in_allowlist = migrated & set(_M6_LONG_TAIL_ALLOWLIST)
    assert not in_allowlist, (
        f"Migrated step(s) incorrectly still in long-tail allowlist: {sorted(in_allowlist)}.  "
        f"Remove them from _M6_LONG_TAIL_ALLOWLIST."
    )


def test_allowlist_covers_all_known_legacy_steps() -> None:
    """Characterization: the allowlist must cover every step name that
    still routes through CompatibilityMode.LEGACY in model_seam.py.

    If this fails, a new step was added to LEGACY without updating the
    allowlist, or a migration task landed and a step moved from LEGACY
    to NATIVE without shrinking the allowlist.
    """
    from arnold.pipelines.megaplan.model_seam import CompatibilityMode, _compatibility_mode_for_step

    known_capture_keys = {
        "execute", "finalize", "critique", "review", "gate",
        "plan", "prep", "prep-triage", "prep-distill", "prep-research",
        "revise", "feedback", "critique_evaluator",
        "loop_plan", "loop_execute",
        "tiebreaker_researcher", "tiebreaker_challenger",
    }
    actual_legacy = {
        s for s in known_capture_keys
        if _compatibility_mode_for_step(s) == CompatibilityMode.LEGACY
    }
    assert actual_legacy == set(_M6_LONG_TAIL_ALLOWLIST), (
        f"Allowlist mismatch with model_seam._COMPATIBILITY_MODE_BY_STEP:\n"
        f"  Expected legacy steps (allowlist):  {sorted(set(_M6_LONG_TAIL_ALLOWLIST))}\n"
        f"  Actual LEGACY steps from model_seam: {sorted(actual_legacy)}\n"
        f"  In allowlist but not actually LEGACY: {sorted(set(_M6_LONG_TAIL_ALLOWLIST) - actual_legacy)}\n"
        f"  LEGACY but not in allowlist:         {sorted(actual_legacy - set(_M6_LONG_TAIL_ALLOWLIST))}"
    )


# ---------------------------------------------------------------------------
# T2: Provider dispatch f-string prompt assembly guards.
#
# The hermes and shannon workers must route prompt assembly through
# model_seam (render_prompt_for_dispatch / render_step_message) rather than
# building raw system/user message strings with f-strings or concatenation.
# ---------------------------------------------------------------------------

_DISPATCH_WORKER_PATHS: tuple[str, ...] = (
    "arnold/pipelines/megaplan/workers/hermes.py",
    "arnold/pipelines/megaplan/workers/shannon.py",
)


def test_hermes_worker_uses_render_prompt_for_dispatch() -> None:
    """Hermes worker must route prompt assembly through render_prompt_for_dispatch.

    This is the correct post-M5 path: prompt_override is passed as a string
    (per SD1), and render_prompt_for_dispatch wraps it into PromptComponents
    and renders through the model seam.
    """
    import ast

    source = _read_source("arnold/pipelines/megaplan/workers/hermes.py")
    tree = ast.parse(source)

    # Verify import from model_seam
    found_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "arnold.pipelines.megaplan.model_seam":
                for alias in node.names:
                    if alias.name == "render_prompt_for_dispatch":
                        found_import = True
    assert found_import, (
        "hermes worker must import render_prompt_for_dispatch from model_seam"
    )

    # Verify actual call
    found_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "render_prompt_for_dispatch"
            ):
                found_call = True
    assert found_call, (
        "hermes worker must call render_prompt_for_dispatch — "
        "raw f-string system/user prompt assembly is forbidden"
    )


def test_shannon_worker_uses_render_prompt_for_dispatch() -> None:
    """Shannon worker must route prompt assembly through render_prompt_for_dispatch.

    Loop and tiebreaker callers still hand Shannon plain string prompt_override
    values, but the worker must wrap those strings through model_seam so
    validation_step and schema metadata stay attached at dispatch time.
    """
    import ast

    source = _read_source("arnold/pipelines/megaplan/workers/shannon.py")
    tree = ast.parse(source)

    # Verify import from model_seam
    found_import_rpf = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "arnold.pipelines.megaplan.model_seam":
                for alias in node.names:
                    if alias.name == "render_prompt_for_dispatch":
                        found_import_rpf = True

    assert found_import_rpf, (
        "shannon worker must import render_prompt_for_dispatch from model_seam"
    )

    found_call = False
    found_schema_kw = False
    found_prompt_override_kw = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "render_prompt_for_dispatch"
            ):
                found_call = True
                kwarg_names = {kw.arg for kw in node.keywords if kw.arg is not None}
                found_schema_kw = found_schema_kw or "schema" in kwarg_names
                found_prompt_override_kw = (
                    found_prompt_override_kw or "prompt_override" in kwarg_names
                )
    assert found_call, (
        "shannon worker must call render_prompt_for_dispatch — "
        "raw f-string system/user prompt assembly is forbidden"
    )
    assert found_schema_kw, (
        "shannon render_prompt_for_dispatch calls must thread schema metadata"
    )
    assert found_prompt_override_kw, (
        "shannon render_prompt_for_dispatch calls must preserve string prompt_override inputs"
    )


def test_provider_workers_import_create_prompt_through_approved_module() -> None:
    """Provider workers may import create_*_prompt from arnold.pipelines.megaplan.prompts,
    but only for use as prompt_override strings passed into model_seam.

    This guard fails if a worker imports prompt builders from the legacy
    workers._impl module instead of the approved prompts module.
    """
    import ast

    for rel_path in _DISPATCH_WORKER_PATHS:
        source = _read_source(rel_path)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "arnold.pipelines.megaplan.workers._impl":
                    for alias in node.names:
                        if "prompt" in alias.name.lower():
                            raise AssertionError(
                                f"{rel_path} imports prompt builder "
                                f"'{alias.name}' from workers._impl "
                                f"instead of megaplan.prompts"
                            )


def test_provider_workers_do_not_import_direct_prompt_builders() -> None:
    """Provider workers should let model_seam build prompts when no override exists.

    Hermes and Shannon both dispatch through render_prompt_for_dispatch now.
    String prompt_override values still remain valid, but direct create_*_prompt
    imports are dead code at the worker boundary.
    """
    import ast

    for rel_path in _DISPATCH_WORKER_PATHS:
        source = _read_source(rel_path)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "arnold.pipelines.megaplan.prompts":
                    for alias in node.names:
                        if alias.name.startswith("create_") and alias.name.endswith("_prompt"):
                            raise AssertionError(
                                f"{rel_path} must not import {alias.name} directly; "
                                "dispatch should pass prompt_override=None into model_seam"
                            )


def test_loop_and_tiebreaker_capture_paths_thread_schema_metadata() -> None:
    """Loop/tiebreaker worker capture calls must include explicit schema metadata."""
    for rel_path in (
        "arnold/pipelines/megaplan/workers/_impl.py",
        "arnold/pipelines/megaplan/workers/hermes.py",
        "arnold/pipelines/megaplan/workers/shannon.py",
    ):
        source = _read_source(rel_path)
        assert '"validation_step": step,' in source, (
            f"{rel_path} must keep explicit validation_step metadata on capture"
        )
        assert '"schema": schema,' in source, (
            f"{rel_path} must thread schema metadata into capture_step_output"
        )
