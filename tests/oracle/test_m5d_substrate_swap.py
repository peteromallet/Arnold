"""M5d replay-oracle corpus for supervisor boundary vocabulary.

The corpus is intentionally small and stable: it records the five supervisor
boundary classes that later substrate-swap or replay tests must preserve.
Happy-path parity is checked separately from the retirement oracle boundaries.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.control_interface import (
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlTarget,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from arnold_pipelines.megaplan.supervisor.chain_runner import run_chain
from arnold_pipelines.megaplan.supervisor.driver import RunRequest
from arnold_pipelines.megaplan.supervisor.ladder import SupervisorLadderPolicy
from arnold_pipelines.megaplan.supervisor.model import RunNode


FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "characterization" / "supervisor_replay_corpus"
)
CANARY_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "supervisor_canary"
RETIREMENT_ORACLE_BOUNDARIES = ("blocked", "recovery", "escalation", "awaiting-pr")
HAPPY_PATH_PARITY_BOUNDARY = "happy-path"
_NEUTRAL_TARGET_IDS = frozenset(
    {
        CONTROL_TARGET_ABORT,
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_RECOVER_FROM_STUCK,
        CONTROL_TARGET_REROUTE,
    }
)
_PLANNING_LITERALS = frozenset({"force-proceed", "replan", "recover-blocked"})


class OraclePackRunner:
    def __init__(self, *, awaiting_pr: bool = False) -> None:
        self.awaiting_pr = awaiting_pr
        self.nodes: list[str] = []

    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        self.nodes.append(node.node_id)
        attempt = self.nodes.count(node.node_id)
        plan_name = f"canary-{node.node_id}-{attempt}"
        plan_dir = root / ".megaplan" / "plans" / plan_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        state: dict[str, Any] = {
            "name": plan_name,
            "current_state": "initialized",
            "config": {"robustness": "standard"},
        }
        if self.awaiting_pr and node.node_id == "alpha":
            state.update(
                {
                    "current_state": "awaiting_pr_merge",
                    "resume_cursor": {"kind": "awaiting_pr_merge", "pr_number": 42},
                    "pr_number": 42,
                }
            )
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return plan_name


class OracleDriver:
    def __init__(self, statuses: dict[str, list[str]]) -> None:
        self.requests: list[RunRequest] = []
        self._statuses = {plan: list(plan_statuses) for plan, plan_statuses in statuses.items()}

    def drive(self, request: RunRequest) -> DriverOutcome:
        self.requests.append(request)
        status = self._statuses[request.plan].pop(0)
        return DriverOutcome(
            status=status,
            plan=request.plan,
            final_state="done" if status == "done" else status,
            iterations=len(self.requests),
            reason=f"oracle:{status}",
            last_phase="execute",
            events=[],
            blocking_reasons=["quality"] if status == "blocked" else [],
        )


class OracleBinding:
    def __init__(
        self,
        *,
        valid_targets: tuple[str, ...] = (),
        recover_targets: tuple[str, ...] = (),
    ) -> None:
        self._valid_targets = valid_targets
        self._recover_targets = recover_targets
        self.transitions: list[ControlTransitionRequest] = []

    def valid_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        del run_state
        return tuple(ControlTarget(id=target_id) for target_id in self._valid_targets)

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        del run_state
        return tuple(ControlTarget(id=target_id) for target_id in self._recover_targets)

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransitionRequest,
    ) -> ControlTransitionResult:
        del run_state
        self.transitions.append(transition)
        return ControlTransitionResult(
            accepted=True,
            mutated=True,
            reason=f"applied:{transition.target_id}",
        )

    def synthesize_artifacts(
        self,
        run_state: RunStateView,
        transition: ControlTransitionRequest,
    ) -> dict[str, object]:
        del run_state, transition
        return {}


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _materialize_canary(tmp_path: Path, *, beta_maxed: bool = False) -> tuple[Path, Path]:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(CANARY_FIXTURE_DIR, fixture_root)
    alpha = (fixture_root / "alpha.md").resolve()
    beta = (fixture_root / "beta.md").resolve()
    north_star = fixture_root / "NORTHSTAR.md"
    north_star.write_text("# Canary North Star\n\nExercise supervisor chain control flow.\n", encoding="utf-8")
    spec_path = fixture_root / "supervisor-canary.yaml"
    beta_lines = ["  - label: beta", f"    idea: {beta}", "    depends_on: [alpha]"]
    if beta_maxed:
        beta_lines.extend(
            [
                "    profile: apex",
                "    robustness: extreme",
                "    depth: max",
            ]
        )
    spec_path.write_text(
        "\n".join(
            [
                "milestones:",
                "  - label: alpha",
                f"    idea: {alpha}",
                *beta_lines,
                "anchors:",
                "  north_star: NORTHSTAR.md",
                "driver:",
                "  max_iterations: 5",
                "  poll_sleep: 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return fixture_root, spec_path


def _result_target_ids(result: dict[str, Any]) -> list[str]:
    target_ids: list[str] = []
    for event in result["events"]:
        target_id = event.get("target_id")
        if isinstance(target_id, str) and target_id not in target_ids:
            target_ids.append(target_id)
    return target_ids


def _assert_no_planning_literals(payload: dict[str, Any]) -> None:
    trace = payload["boundary_trace"]
    neutral_target_ids = set(trace["neutral_target_ids"])
    assert neutral_target_ids <= _NEUTRAL_TARGET_IDS
    assert not neutral_target_ids & _PLANNING_LITERALS
    assert set(trace["planning_literals"]) == set()


def _run_supervisor_canary(
    *,
    tmp_path: Path,
    statuses: dict[str, list[str]],
    beta_maxed: bool = False,
    binding: OracleBinding | None = None,
    pack_runner: OraclePackRunner | None = None,
    ladder_policy: SupervisorLadderPolicy | None = None,
) -> dict[str, Any]:
    root, spec_path = _materialize_canary(tmp_path, beta_maxed=beta_maxed)
    result = run_chain(
        spec_path,
        root,
        driver=OracleDriver(statuses),
        pack_runner=pack_runner or OraclePackRunner(),
        binding=binding or "planning",
        ladder_policy=ladder_policy or SupervisorLadderPolicy(),
        writer=lambda _msg: None,
    )
    return result


def test_supervisor_persists_successor_lifecycle_before_driving(tmp_path: Path) -> None:
    root, spec_path = _materialize_canary(tmp_path)
    state = chain_spec.load_chain_state(spec_path)
    state.last_state = "done"
    chain_spec.save_chain_state(spec_path, state)

    class InspectingDriver:
        def drive(self, request: RunRequest) -> DriverOutcome:
            saved = chain_spec.load_chain_state(spec_path)
            assert saved.current_milestone_index == 0
            assert saved.current_plan_name == request.plan
            assert saved.last_state == "initialized"
            return DriverOutcome(
                status="blocked",
                plan=request.plan,
                final_state="blocked",
                iterations=1,
                reason="fixture stop after successor-state assertion",
                last_phase="prep",
                events=[],
                blocking_reasons=["fixture"],
            )

    result = run_chain(
        spec_path,
        root,
        driver=InspectingDriver(),
        pack_runner=OraclePackRunner(),
        binding="planning",
        writer=lambda _msg: None,
    )

    assert result["status"] == "stopped"


def test_supervisor_replay_manifest_covers_all_boundary_vocab() -> None:
    manifest = _load("MANIFEST.json")

    assert manifest["oracle"] == "m5d_supervisor_substrate_swap"
    assert manifest["boundary_vocabulary"] == [
        "blocked",
        "recovery",
        "escalation",
        "awaiting-pr",
        "happy-path",
    ]
    fixtures = {entry["boundary_kind"]: entry for entry in manifest["fixtures"]}
    assert set(fixtures) == {
        "blocked",
        "recovery",
        "escalation",
        "awaiting-pr",
        "happy-path",
    }

    for boundary_kind, entry in fixtures.items():
        payload = _load(entry["fixture"])
        assert payload["boundary_kind"] == boundary_kind
        assert payload["recording_kind"] == entry["recording_kind"]
        assert payload["source"]["status"] == entry["status"]
        assert payload["source"]["final_state"] == entry["final_state"]


def test_supervisor_replay_fixtures_keep_neutral_boundary_language() -> None:
    manifest = _load("MANIFEST.json")

    for entry in manifest["fixtures"]:
        payload = _load(entry["fixture"])
        trace = payload["boundary_trace"]

        assert payload["schema_version"] == 1
        assert payload["oracle"] == "m5d_supervisor_substrate_swap"
        assert isinstance(trace["summary"], str) and trace["summary"]
        assert isinstance(trace["states"], list) and trace["states"]
        assert isinstance(trace["events"], list) and trace["events"]
        _assert_no_planning_literals(payload)

    awaiting_pr = _load("awaiting_pr.json")
    assert awaiting_pr["resume_cursor"] == {"kind": "awaiting_pr_merge", "pr_number": 42}
    assert awaiting_pr["pr_state"] == "open"
    assert awaiting_pr["boundary_trace"]["events"][0] == "PR #42 is merge-ready (open)"

    blocked = _load("blocked.json")
    assert blocked["boundary_trace"]["neutral_target_ids"] == [CONTROL_TARGET_RECOVER_FROM_STUCK]

    escalation = _load("escalation.json")
    assert escalation["boundary_trace"]["neutral_target_ids"] == [
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_ABORT,
    ]

    happy_path = _load("happy_path.json")
    assert happy_path["boundary_trace"]["neutral_target_ids"] == []


def test_happy_path_parity_is_labeled_separately_from_retirement_oracle() -> None:
    assert HAPPY_PATH_PARITY_BOUNDARY not in RETIREMENT_ORACLE_BOUNDARIES
    assert set(RETIREMENT_ORACLE_BOUNDARIES) == {
        "blocked",
        "recovery",
        "escalation",
        "awaiting-pr",
    }


@pytest.mark.parametrize(
    ("boundary_kind", "statuses", "beta_maxed", "binding", "ladder_policy", "expected_targets"),
    [
        (
            "blocked",
            {
                "canary-alpha-1": ["done"],
                "canary-beta-1": ["blocked"],
                "canary-beta-2": ["blocked"],
            },
            True,
            OracleBinding(recover_targets=(CONTROL_TARGET_RECOVER_FROM_STUCK,)),
            SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0),
            [CONTROL_TARGET_RECOVER_FROM_STUCK],
        ),
        (
            "recovery",
            {
                "canary-alpha-1": ["done"],
                "canary-beta-1": ["blocked"],
                "canary-beta-2": ["done"],
            },
            False,
            OracleBinding(
                recover_targets=(
                    CONTROL_TARGET_RECOVER_FROM_STUCK,
                    CONTROL_TARGET_REROUTE,
                    CONTROL_TARGET_ABORT,
                )
            ),
            SupervisorLadderPolicy(retry_limit=0),
            [CONTROL_TARGET_RECOVER_FROM_STUCK],
        ),
        (
            "escalation",
            {
                "canary-alpha-1": ["done"],
                "canary-beta-1": ["failed"],
                "canary-beta-2": ["done"],
            },
            True,
            OracleBinding(
                valid_targets=(
                    CONTROL_TARGET_FORCE_ADVANCE,
                    CONTROL_TARGET_REROUTE,
                    CONTROL_TARGET_ABORT,
                )
            ),
            SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0),
            [CONTROL_TARGET_FORCE_ADVANCE],
        ),
    ],
)
def test_retirement_oracle_boundaries_compare_old_and_new_traces_on_canary_corpus(
    tmp_path: Path,
    boundary_kind: str,
    statuses: dict[str, list[str]],
    beta_maxed: bool,
    binding: OracleBinding,
    ladder_policy: SupervisorLadderPolicy,
    expected_targets: list[str],
) -> None:
    payload = _load(f"{boundary_kind.replace('-', '_')}.json")
    _assert_no_planning_literals(payload)

    result = _run_supervisor_canary(
        tmp_path=tmp_path,
        statuses=statuses,
        beta_maxed=beta_maxed,
        binding=binding,
        ladder_policy=ladder_policy,
    )

    target_ids = _result_target_ids(result)
    assert target_ids == expected_targets
    if boundary_kind == "escalation":
        assert payload["boundary_trace"]["neutral_target_ids"][: len(target_ids)] == target_ids
    else:
        assert payload["boundary_trace"]["neutral_target_ids"] == target_ids

    assert not set(target_ids) & _PLANNING_LITERALS
    if boundary_kind == "blocked":
        assert result["status"] == "stopped"
    else:
        assert result["status"] == "done"


def test_retirement_oracle_awaiting_pr_boundary_passes_against_canary_supervisor_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load("awaiting_pr.json")
    _assert_no_planning_literals(payload)

    monkeypatch.setattr("arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._pr_state", lambda *_a, **_k: "open")

    def fake_run_command(
        root: Path,
        argv: list[str],
        *,
        writer,
        timeout: float,
        error_code: str,
    ) -> subprocess.CompletedProcess[str]:
        del root, writer, timeout, error_code
        assert argv == ["gh", "pr", "view", "42", "--json", "state,mergeStateStatus,isDraft"]
        return subprocess.CompletedProcess(
            argv,
            0,
            '{"state":"OPEN","mergeStateStatus":"CLEAN","isDraft":false}',
            "",
        )

    monkeypatch.setattr("arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._run_command", fake_run_command)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._mark_pr_ready",
        lambda root, pr_number, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._enable_auto_merge",
        lambda root, pr_number, *, writer: "open",
    )

    result = _run_supervisor_canary(
        tmp_path=tmp_path,
        statuses={"canary-alpha-1": ["awaiting_human"], "canary-beta-1": ["done"]},
        pack_runner=OraclePackRunner(awaiting_pr=True),
    )

    assert result["status"] == "done"
    assert result["chain_state"]["last_state"] == "done"
    assert _result_target_ids(result) == []
    pr_events = [event for event in result["events"] if event["kind"] == "pr_merge_resolution"]
    assert pr_events == [
        {
            "kind": "pr_merge_resolution",
            "label": "alpha",
            "plan": "canary-alpha-1",
            "advanced": True,
            "pr_number": 42,
            "pr_state": "open",
            "reason": "PR #42 is merge-ready (open)",
        }
    ]
    assert payload["boundary_trace"]["events"][0] == pr_events[0]["reason"]


def test_happy_path_parity_matches_canary_without_claiming_retirement_authority(
    tmp_path: Path,
) -> None:
    payload = _load("happy_path.json")
    _assert_no_planning_literals(payload)

    result = _run_supervisor_canary(
        tmp_path=tmp_path,
        statuses={"canary-alpha-1": ["done"], "canary-beta-1": ["done"]},
    )

    assert result["status"] == "done"
    assert _result_target_ids(result) == payload["boundary_trace"]["neutral_target_ids"] == []
    assert not [event for event in result["events"] if event["kind"] == "pr_merge_resolution"]
    assert HAPPY_PATH_PARITY_BOUNDARY not in RETIREMENT_ORACLE_BOUNDARIES
