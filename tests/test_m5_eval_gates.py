from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan.chain.m5_eval_gates import (
    assert_m5_eval_gates_before_calibration,
    check_better_join_is_pure,
    check_calibration_guard_targets,
    check_calibration_source_purity,
    check_no_bare_float_judgments,
    check_no_second_eval_journals,
    check_sdk_state_mechanism_purity,
    check_supervisor_source_purity,
    replay_oracle_corpus_marker,
    run_m5_eval_gates,
)


def _write(root: Path, rel_path: str, source: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_m5_eval_gate_passes_current_repo() -> None:
    result = run_m5_eval_gates()

    assert result.passed, "\n".join(
        f"{finding.path}:{finding.line}: {finding.code}: {finding.detail}"
        for finding in result.findings
    )


def test_m5_eval_gate_rejects_bare_float_judgment_in_new_eval_module(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from arnold.pipelines.megaplan._pipeline.types import PipelineVerdict

def run():
    return PipelineVerdict(score=0.72)
""",
    )

    findings = check_no_bare_float_judgments(tmp_path, paths=[rel_path])

    assert [finding.code for finding in findings] == [
        "M5_EVAL_BARE_FLOAT_JUDGMENT"
    ]


def test_m5_eval_gate_allows_old_path_bare_float_surface(tmp_path):
    rel_path = "megaplan/_pipeline/demo_judges.py"
    _write(
        tmp_path,
        rel_path,
        """
from arnold.pipelines.megaplan._pipeline.types import PipelineVerdict

def run():
    return PipelineVerdict(score=0.72)
""",
    )

    assert check_no_bare_float_judgments(tmp_path, paths=[rel_path]) == ()


def test_m5_eval_gate_allows_evaluand_record_score_literals(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from arnold.pipelines.megaplan.observability import EvaluandRecord

def run():
    return EvaluandRecord(
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
        score=0.72,
        piece_version="piece-v1",
    )
""",
    )

    assert check_no_bare_float_judgments(tmp_path, paths=[rel_path]) == ()


def test_m5_eval_gate_rejects_second_eval_specific_journal(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from pathlib import Path

def write(plan_dir):
    (Path(plan_dir) / "evaluand.ndjson").write_text("{}\\n")
""",
    )

    findings = check_no_second_eval_journals(tmp_path, paths=[rel_path])

    assert [finding.code for finding in findings] == ["M5_EVAL_SECOND_JOURNAL"]


def test_m5_eval_gate_allows_events_ndjson_path(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from pathlib import Path

def write(plan_dir):
    return Path(plan_dir) / "events.ndjson"
""",
    )

    assert check_no_second_eval_journals(tmp_path, paths=[rel_path]) == ()


def test_m5_eval_gate_rejects_better_cost_import_judge_call_and_vendor_heuristic(
    tmp_path,
):
    rel_path = "megaplan/observability/evaluand.py"
    _write(
        tmp_path,
        rel_path,
        """
def better(*, plan_dir, judge):
    from arnold.pipelines.megaplan.observability.cost import _classify_vendor

    vendor = _classify_vendor("claude-opus")
    return judge(plan_dir, vendor)
""",
    )

    findings = check_better_join_is_pure(tmp_path, rel_path=rel_path)
    codes = {finding.code for finding in findings}

    assert "M5_EVAL_BETTER_COST_IMPORT" in codes
    assert "M5_EVAL_BETTER_LIVE_JUDGE_CALL" in codes
    assert "M5_EVAL_BETTER_VENDOR_HEURISTIC" in codes


def test_replay_oracle_corpus_marker_matches_guarded_fixture() -> None:
    assert replay_oracle_corpus_marker() == 4


def test_calibration_guard_passes_current_repo() -> None:
    assert_m5_eval_gates_before_calibration()


def test_calibration_guard_rejects_guarded_target_without_markers(tmp_path) -> None:
    rel_path = "megaplan/observability/cost.py"
    _write(
        tmp_path,
        rel_path,
        """
from arnold.pipelines.megaplan.observability import better

def route(plan_dir):
    return better("a", "b", plan_dir=plan_dir, judge_version="j", rubric_version="r", input_set_hash="i")
""",
    )
    _write(
        tmp_path,
        "megaplan/observability/evaluand.py",
        """
def better(*, plan_dir, judge_version, rubric_version, input_set_hash):
    return plan_dir, judge_version, rubric_version, input_set_hash
""",
    )
    _write(
        tmp_path,
        "megaplan/_pipeline/eval_judge_wrapper.py",
        """
from arnold.pipelines.megaplan._pipeline.types import PipelineVerdict

def run():
    return PipelineVerdict(score=0.72)
""",
    )

    findings = check_calibration_guard_targets(tmp_path)
    codes = {finding.code for finding in findings}

    assert "M5_EVAL_CALIBRATION_GUARD_GREP_GATE" in codes
    assert "M5_EVAL_CALIBRATION_GUARD_REPLAY_MARKER" in codes


def test_calibration_guard_allows_guarded_target_once_gate_and_marker_exist(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/observability/cost.py",
        """
from arnold.pipelines.megaplan.observability import better

def route(plan_dir):
    return better("a", "b", plan_dir=plan_dir, judge_version="j", rubric_version="r", input_set_hash="i")
""",
    )
    _write(
        tmp_path,
        "megaplan/observability/evaluand.py",
        """
def better(*, plan_dir, judge_version, rubric_version, input_set_hash):
    return {
        "plan_dir": plan_dir,
        "judge_version": judge_version,
        "rubric_version": rubric_version,
        "input_set_hash": input_set_hash,
    }
""",
    )
    _write(
        tmp_path,
        "tests/oracles/test_evaluand_replay_oracle.py",
        """
REPLAY_ORACLE_CORPUS_SIZE = 4
""",
    )

    assert check_calibration_guard_targets(tmp_path) == ()
    assert_m5_eval_gates_before_calibration(tmp_path)


# ---------------------------------------------------------------------------
# T12 — calibration source purity gate tests
# ---------------------------------------------------------------------------


def test_calibration_source_purity_passes_current_repo() -> None:
    """The current calibration source tree must be clean."""
    findings = check_calibration_source_purity()
    assert findings == (), (
        "Calibration source purity violations: "
        + "; ".join(f"{f.code}:{f.path}:{f.line}" for f in findings)
    )


def test_calibration_gate_catches_bare_numeric_outcome_assignment(
    tmp_path,
) -> None:
    """Detect ``outcome = 0.72`` in calibration sources."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "outcome = 0.72\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_BARE_NUMERIC_OUTCOME" in codes


def test_calibration_gate_catches_bare_numeric_outcome_constructor(
    tmp_path,
) -> None:
    """Detect ``CapabilityClaim(outcome=0.72)`` in calibration sources."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "from arnold.pipelines.megaplan.calibration import CapabilityClaim\n"
        "claim = CapabilityClaim(outcome=0.72, task_signature='x', model_identity='y')\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_BARE_NUMERIC_OUTCOME" in codes


def test_calibration_gate_catches_state_star_import_from(
    tmp_path,
) -> None:
    """Detect ``from arnold.pipelines.megaplan.types import STATE_DONE`` in calibration sources."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "from arnold.pipelines.megaplan.types import STATE_DONE, STATE_FAILED\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_STATE_STAR_IMPORT" in codes


def test_calibration_gate_catches_state_star_bare_usage(
    tmp_path,
) -> None:
    """Detect bare ``STATE_INITIALIZED`` name references in calibration sources."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "def check(state):\n"
        "    return state == STATE_BLOCKED\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_STATE_STAR_USAGE" in codes


def test_calibration_gate_catches_state_star_attribute(
    tmp_path,
) -> None:
    """Detect ``types.STATE_PAUSED`` attribute references in calibration sources."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "import arnold.pipelines.megaplan.types as t\n"
        "def check(state):\n"
        "    return state == t.STATE_PAUSED\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_STATE_STAR_USAGE" in codes


def test_calibration_gate_catches_gaterecommendation_import(
    tmp_path,
) -> None:
    """Detect import of the removed GateRecommendation symbol (AST gate;
    does not require the symbol to be importable)."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "from arnold.pipelines.megaplan._pipeline.types import GateRecommendation\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_GATEREC_IMPORT" in codes


def test_calibration_gate_catches_gaterecommendation_reference(
    tmp_path,
) -> None:
    """Detect bare name reference to the removed GateRecommendation symbol
    (AST gate; does not require the symbol to be importable)."""
    _write(
        tmp_path,
        "megaplan/calibration/bad.py",
        "def route(rec: GateRecommendation) -> str:\n"
        "    return 'ok'\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_CAL_GATEREC_REFERENCE" in codes


def test_calibration_gate_allows_valid_evaluandref_usage(
    tmp_path,
) -> None:
    """Valid EvaluandRef usage must not trip the calibration source gate."""
    _write(
        tmp_path,
        "megaplan/calibration/clean.py",
        "from arnold.pipelines.megaplan.calibration import CapabilityClaim, EvaluandRef\n"
        "ref = EvaluandRef('pv', 'jv', 'rv', 'ish')\n"
        "claim = CapabilityClaim(\n"
        "    outcome=ref,\n"
        "    task_signature='ts',\n"
        "    model_identity='mi',\n"
        ")\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    assert findings == (), (
        "Valid EvaluandRef usage tripped gate: "
        + "; ".join(f"{f.code}:{f.line}" for f in findings)
    )


def test_calibration_gate_allows_normal_calibration_code(
    tmp_path,
) -> None:
    """Normal calibration imports and dataclass usage must be allowed."""
    _write(
        tmp_path,
        "megaplan/calibration/clean.py",
        "from arnold.pipelines.megaplan.calibration import (\n"
        "    CapabilityClaim, EvaluandRef, ModelIdentity,\n"
        "    QueryPolicy, RouteSuggestion,\n"
        "    write_capability_claim, read_capability_claims,\n"
        ")\n"
        "\n"
        "def build_claim():\n"
        "    ref = EvaluandRef('piece-v1', 'judge-v1', 'rubric-v1', 'hash')\n"
        "    claim = CapabilityClaim(\n"
        "        outcome=ref,\n"
        "        task_signature='sig',\n"
        "        model_identity='id',\n"
        "        taint_class='SHARED',\n"
        "    )\n"
        "    return claim\n",
    )
    findings = check_calibration_source_purity(tmp_path)
    assert findings == (), (
        "Normal calibration code tripped gate: "
        + "; ".join(f"{f.code}:{f.line}" for f in findings)
    )


def test_sdk_state_mechanism_gate_passes_current_repo() -> None:
    findings = check_sdk_state_mechanism_purity()
    assert findings == (), (
        "SDK state mechanism violations: "
        + "; ".join(f"{f.code}:{f.path}:{f.line}" for f in findings)
    )


def test_sdk_state_mechanism_gate_rejects_state_imports_in_sdk_module(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/control_interface.py",
        "from arnold.pipelines.megaplan.types import STATE_BLOCKED\n",
    )

    findings = check_sdk_state_mechanism_purity(
        tmp_path,
        paths=["megaplan/control_interface.py"],
    )

    assert {finding.code for finding in findings} == {"M5_CAL_STATE_STAR_IMPORT"}


def test_sdk_state_mechanism_gate_rejects_state_name_usage_in_sdk_module(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/run_outcome.py",
        "def project(state):\n"
        "    return STATE_BLOCKED if state else None\n",
    )

    findings = check_sdk_state_mechanism_purity(
        tmp_path,
        paths=["megaplan/run_outcome.py"],
    )

    assert {finding.code for finding in findings} == {"M5_CAL_STATE_STAR_USAGE"}


def test_sdk_state_mechanism_gate_allows_planning_compatibility_surface(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/planning/control_binding.py",
        "from arnold.pipelines.megaplan.types import STATE_BLOCKED\n"
        "RECOVERY = {'current_state': 'blocked', 'resume_cursor': {'phase': 'execute'}}\n",
    )

    assert (
        check_sdk_state_mechanism_purity(
            tmp_path,
            paths=["megaplan/planning/control_binding.py"],
        )
        == ()
    )


def test_sdk_state_mechanism_gate_rejects_persisted_recovery_resume_map_in_sdk_module(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/control_interface.py",
        "RECOVERY_MAP = {\n"
        "    'current_state': 'blocked',\n"
        "    'resume_cursor': {'phase': 'execute'},\n"
        "}\n",
    )

    findings = check_sdk_state_mechanism_purity(
        tmp_path,
        paths=["megaplan/control_interface.py"],
    )

    assert {finding.code for finding in findings} == {
        "M5_CONTROL_PERSISTED_RECOVERY_MECHANISM"
    }


def test_sdk_state_mechanism_gate_rejects_mechanism_state_delta_in_sdk_module(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/control_interface.py",
        "from arnold.pipelines.megaplan._pipeline.types import StateDelta\n"
        "delta = StateDelta(op='replace', key='resume_cursor', value={'phase': 'execute'})\n",
    )

    findings = check_sdk_state_mechanism_purity(
        tmp_path,
        paths=["megaplan/control_interface.py"],
    )

    assert {finding.code for finding in findings} == {
        "M5_CONTROL_PERSISTED_RECOVERY_MECHANISM"
    }


# ---------------------------------------------------------------------------
# T6 — supervisor source purity gate tests
# ---------------------------------------------------------------------------


def test_supervisor_source_purity_passes_current_repo() -> None:
    """The current repository must pass supervisor source purity
    (no `megaplan/supervisor/` files exist yet)."""
    findings = check_supervisor_source_purity()
    assert findings == (), (
        f"Supervisor source purity violations: "
        + "; ".join(f"{f.code}:{f.path}:{f.line}" for f in findings)
    )


def test_supervisor_purity_missing_directory_is_clean(tmp_path) -> None:
    """Calling `check_supervisor_source_purity` on a root with no
    `megaplan/supervisor/` directory at all must return an empty tuple."""
    findings = check_supervisor_source_purity(tmp_path)
    assert findings == (), (
        f"Expected no findings for missing directory; got: "
        + "; ".join(f"{f.code}:{f.path}" for f in findings)
    )


def test_supervisor_purity_empty_directory_is_clean(tmp_path) -> None:
    """An existing `megaplan/supervisor/` directory containing no `.py`
    files must return an empty tuple."""
    supervisor_dir = tmp_path / "megaplan" / "supervisor"
    supervisor_dir.mkdir(parents=True, exist_ok=True)
    # Create a non-.py file to confirm it isn't scanned
    (supervisor_dir / "README.md").write_text("# supervisor\n", encoding="utf-8")

    findings = check_supervisor_source_purity(tmp_path)
    assert findings == (), (
        f"Expected no findings for directory with no .py files; got: "
        + "; ".join(f"{f.code}:{f.path}" for f in findings)
    )


def test_supervisor_purity_catches_state_star_import_from(tmp_path) -> None:
    """Detect ``from arnold.pipelines.megaplan.types import STATE_DONE`` in supervisor sources."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "from arnold.pipelines.megaplan.types import STATE_DONE, STATE_FAILED\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_STATE_STAR_IMPORT" in codes, (
        f"Expected M5_SUP_STATE_STAR_IMPORT; got: {codes}"
    )


def test_supervisor_purity_catches_state_star_bare_usage(tmp_path) -> None:
    """Detect bare ``STATE_BLOCKED`` name references in supervisor sources."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "def check(state):\n"
        "    return state == STATE_BLOCKED\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_STATE_STAR_USAGE" in codes, (
        f"Expected M5_SUP_STATE_STAR_USAGE; got: {codes}"
    )


def test_supervisor_purity_catches_state_star_attribute(tmp_path) -> None:
    """Detect ``t.STATE_PAUSED`` attribute references in supervisor sources."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "import arnold.pipelines.megaplan.types as t\n"
        "def check(state):\n"
        "    return state == t.STATE_PAUSED\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_STATE_STAR_USAGE" in codes, (
        f"Expected M5_SUP_STATE_STAR_USAGE; got: {codes}"
    )


def test_supervisor_purity_catches_force_proceed_string_literal(
    tmp_path,
) -> None:
    """Detect ``\"force-proceed\"`` string literals in supervisor sources."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        'OVERRIDE = "force-proceed"\n',
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_FORCE_PROCEED" in codes, (
        f"Expected M5_SUP_FORCE_PROCEED; got: {codes}"
    )


def test_supervisor_purity_catches_force_proceed_variant_string(
    tmp_path,
) -> None:
    """Detect ``\"FORCE_PROCEED\"`` (uppercase) string literals."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        'ACTION = "FORCE_PROCEED"\n',
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_FORCE_PROCEED" in codes, (
        f"Expected M5_SUP_FORCE_PROCEED for uppercase variant; got: {codes}"
    )


def test_supervisor_purity_catches_force_proceed_function_def(
    tmp_path,
) -> None:
    """Detect functions named ``force_proceed_override`` in supervisor sources."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "def force_proceed_override(state):\n"
        "    return True\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_FORCE_PROCEED" in codes, (
        f"Expected M5_SUP_FORCE_PROCEED for FunctionDef; got: {codes}"
    )


def test_supervisor_purity_catches_force_proceed_call(tmp_path) -> None:
    """Detect calls to ``force_proceed_pipeline()`` in supervisor sources."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "def runner(state):\n"
        "    return do_force_proceed(state)\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_FORCE_PROCEED" in codes, (
        f"Expected M5_SUP_FORCE_PROCEED for Call; got: {codes}"
    )


def test_supervisor_purity_clean_file_passes(tmp_path) -> None:
    """A clean supervisor source file with no violations must pass."""
    _write(
        tmp_path,
        "megaplan/supervisor/clean.py",
        "from pathlib import Path\n"
        "\n"
        "def run(plan_dir: Path) -> dict:\n"
        "    return {'status': 'ok', 'plan_dir': str(plan_dir)}\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    assert findings == (), (
        f"Expected no findings for clean file; got: "
        + "; ".join(f"{f.code}:{f.line}" for f in findings)
    )


def test_supervisor_purity_catches_chain_routing_violation(tmp_path) -> None:
    """Detect STATE_* imports in chain routing modules
    (``megaplan/chain/runner_supervisor.py``)."""
    _write(
        tmp_path,
        "megaplan/chain/runner_supervisor.py",
        "from arnold.pipelines.megaplan.types import STATE_DONE\n"
        "def route(state):\n"
        "    return state == STATE_DONE\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_STATE_STAR_IMPORT" in codes, (
        f"Expected M5_SUP_STATE_STAR_IMPORT in chain routing; got: {codes}"
    )
    assert "M5_SUP_STATE_STAR_USAGE" in codes, (
        f"Expected M5_SUP_STATE_STAR_USAGE in chain routing; got: {codes}"
    )


def test_supervisor_purity_catches_bakeoff_binding_violation(tmp_path) -> None:
    """Detect force-proceed references in bakeoff binding modules
    (``megaplan/bakeoff/supervisor_binding.py``)."""
    _write(
        tmp_path,
        "megaplan/bakeoff/supervisor_binding.py",
        "BINDING = {\n"
        '    "force-proceed": "allow",\n'
        "}\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_FORCE_PROCEED" in codes, (
        f"Expected M5_SUP_FORCE_PROCEED in bakeoff binding; got: {codes}"
    )


def test_supervisor_purity_neutral_planning_binding_allowed(
    tmp_path,
) -> None:
    """Neutral planning bindings (no STATE_* or force-proceed) must pass
    even when placed in supervisor-scanned paths."""
    _write(
        tmp_path,
        "megaplan/supervisor/planning_adapter.py",
        "from arnold.pipelines.megaplan.planning.control_binding import PlanningControlBinding\n"
        "\n"
        "def bind_controls(state, plan_dir):\n"
        "    binding = PlanningControlBinding(state, plan_dir=plan_dir)\n"
        "    transition = {\n"
        '        "action": "recover-from-stuck",\n'
        '        "plan_dir": plan_dir,\n'
        "    }\n"
        "    return binding.apply_transition(**transition)\n",
    )
    findings = check_supervisor_source_purity(tmp_path)
    assert findings == (), (
        f"Expected no findings for neutral planning binding; got: "
        + "; ".join(f"{f.code}:{f.line}" for f in findings)
    )


def test_supervisor_purity_simultaneous_violations(tmp_path) -> None:
    """A file containing both STATE_* and force-proceed issues must
    report all violations simultaneously."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "from arnold.pipelines.megaplan.types import STATE_BLOCKED\n"
        "\n"
        "def check(state):\n"
        '    return state == STATE_BLOCKED or "force-proceed"\n',
    )
    findings = check_supervisor_source_purity(tmp_path)
    codes = {f.code for f in findings}
    assert "M5_SUP_STATE_STAR_IMPORT" in codes
    assert "M5_SUP_STATE_STAR_USAGE" in codes
    assert "M5_SUP_FORCE_PROCEED" in codes
    assert len(findings) >= 3, (
        f"Expected at least 3 findings; got {len(findings)}: "
        + "; ".join(f"{f.code}:{f.line}" for f in findings)
    )


def test_supervisor_purity_included_in_run_m5_eval_gates(tmp_path) -> None:
    """Verify that `run_m5_eval_gates` includes supervisor source purity
    in its aggregated result, and that a supervisor violation causes
    the overall gate to fail."""
    _write(
        tmp_path,
        "megaplan/supervisor/bad.py",
        "from arnold.pipelines.megaplan.types import STATE_INITIALIZED\n",
    )
    # We also need the other scanned modules to exist cleanly or be absent.
    # Create minimal clean versions of other required files.
    _write(
        tmp_path,
        "megaplan/_pipeline/eval_judge_wrapper.py",
        "def run():\n    return None\n",
    )
    _write(
        tmp_path,
        "megaplan/_pipeline/judge_manifest.py",
        "# empty\n",
    )
    _write(
        tmp_path,
        "megaplan/_pipeline/judge_manifest_discovery.py",
        "# empty\n",
    )
    _write(
        tmp_path,
        "megaplan/observability/evaluand.py",
        "def better(*, plan_dir, judge_version, rubric_version, input_set_hash):\n"
        "    return plan_dir, judge_version, rubric_version, input_set_hash\n",
    )
    _write(
        tmp_path,
        "megaplan/control_interface.py",
        "# empty\n",
    )
    _write(
        tmp_path,
        "megaplan/run_outcome.py",
        "# empty\n",
    )
    # Also create clean SDK stateless targets so the overall gate doesn't
    # fail on missing files.
    _write(
        tmp_path,
        "megaplan/cli/status_view.py",
        "# empty\n",
    )
    _write(
        tmp_path,
        "megaplan/observability/introspect.py",
        "# empty\n",
    )

    result = run_m5_eval_gates(tmp_path)

    assert not result.passed, (
        f"Expected run_m5_eval_gates to fail due to supervisor violation; "
        f"got passed=True"
    )

    codes = {f.code for f in result.findings}
    assert "M5_SUP_STATE_STAR_IMPORT" in codes, (
        f"Expected M5_SUP_STATE_STAR_IMPORT in aggregated gate result; "
        f"got codes: {codes}"
    )


def test_m5_eval_gate_preserved_after_calibration_gate_addition() -> None:
    """Existing M5-eval gates must still pass after calibration gate additions."""
    # Run the pre-existing checks directly (not via run_m5_eval_gates
    # which now includes calibration source purity).
    bare_float_findings = check_no_bare_float_judgments()
    assert bare_float_findings == (), (
        f"Bare-float gate regressed: {bare_float_findings}"
    )

    second_journal_findings = check_no_second_eval_journals()
    assert second_journal_findings == (), (
        f"Second-journal gate regressed: {second_journal_findings}"
    )

    better_pure_findings = check_better_join_is_pure()
    assert better_pure_findings == (), (
        f"Better-join-pure gate regressed: {better_pure_findings}"
    )

    # Full run_m5_eval_gates (includes calibration source purity) must pass.
    result = run_m5_eval_gates()
    assert result.passed, "\n".join(
        f"{f.path}:{f.line}: {f.code}: {f.detail}"
        for f in result.findings
    )
