from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from megaplan._core import atomic_write_json, atomic_write_text, read_json, schemas_root
from megaplan._core.hermes_fanout import GenericScatterResult
from megaplan.audits.robustness import checks_for_robustness
from megaplan.workers.hermes import parse_agent_output
from megaplan.orchestration.parallel_critique import _run_check, run_parallel_critique
from megaplan.prompts.critique import write_single_check_template
from megaplan.types import AgentMode, PlanState
from megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult


REPO_ROOT = Path(__file__).resolve().parents[1]


def _state(project_dir: Path, *, iteration: int = 1) -> PlanState:
    return {
        "name": "test-plan",
        "idea": "parallelize critique",
        "current_state": "planned",
        "iteration": iteration,
        "created_at": "2026-04-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": iteration,
                "file": f"plan_v{iteration}.md",
                "hash": "sha256:test",
                "timestamp": "2026-04-01T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }


def _scaffold(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    state = _state(project_dir, iteration=iteration)
    atomic_write_text(plan_dir / f"plan_v{iteration}.md", "# Plan\nDo it.\n")
    atomic_write_json(
        plan_dir / f"plan_v{iteration}.meta.json",
        {
            "version": iteration,
            "timestamp": "2026-04-01T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(plan_dir / "faults.json", {"flags": []})
    return plan_dir, project_dir, state


def _critique_schema() -> dict:
    return read_json(schemas_root(REPO_ROOT) / STEP_SCHEMA_FILENAMES["critique"])


def _finding(detail: str, *, flagged: bool) -> dict[str, object]:
    return {"detail": detail, "flagged": flagged}


def _check_payload(check: dict[str, str], detail: str, *, flagged: bool = False) -> dict[str, object]:
    return {
        "id": check["id"],
        "question": check["question"],
        "findings": [_finding(detail, flagged=flagged)],
    }


def _resolved_mode(
    agent: str = "hermes",
    mode: str = "creative",
    model: str | None = "test-model",
) -> AgentMode:
    return AgentMode(agent=agent, mode=mode, refreshed=False, model=model)


def _enrich_checks(checks: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Enrich each check with ``_resolved_agent_mode`` metadata per SD1."""
    enriched: list[dict[str, Any]] = []
    for check in checks:
        c = dict(check)
        c["_resolved_agent_mode"] = _resolved_mode()
        enriched.append(c)
    return enriched


# ---------------------------------------------------------------------------
# Existing fan-out tests — adapted from _run_check monkeypatching to
# scatter_worker_units monkeypatching (T17 refactor).
# ---------------------------------------------------------------------------


def test_run_parallel_critique_merges_in_original_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Results must be returned in input order, not completion order."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks)

    # Build synthetic ordered_results in the shape _parse_result returns:
    # (check_payload, verified_ids, disputed_ids)
    def _fake_scatter(**kwargs: Any) -> GenericScatterResult:
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for i, chk in enumerate(enriched):
            items.append((
                _check_payload(chk, f"Checked {chk['id']} in detail for ordered merge coverage.", flagged=False),
                [f"FLAG-{i + 1:03d}"],
                [],
            ))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.25 * len(enriched),
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    result = run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    assert [check["id"] for check in result.payload["checks"]] == [chk["id"] for chk in enriched]
    assert result.payload["flags"] == []
    assert result.payload["verified_flag_ids"] == [f"FLAG-{i:03d}" for i in range(1, len(enriched) + 1)]
    assert result.payload["disputed_flag_ids"] == []
    # No session mutation
    assert result.session_id is None


def test_run_parallel_critique_accepts_multi_check_payload_when_one_matches_unit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks[:1])

    def _fake_scatter(**kwargs: Any) -> GenericScatterResult:
        unit = kwargs["units"][0]
        parsed = kwargs["parse_result"](
            0,
            {
                "checks": [
                    _check_payload({"id": "other", "question": "Other"}, "not this check", flagged=False),
                    _check_payload(enriched[0], "matched the assigned unit", flagged=False),
                ],
                "verified_flag_ids": ["FLAG-MATCH"],
                "disputed_flag_ids": [],
            },
            unit,
        )
        return GenericScatterResult(
            ordered_results=[parsed],
            total_cost=0.25,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    result = run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    assert [check["id"] for check in result.payload["checks"]] == [enriched[0]["id"]]
    assert result.payload["verified_flag_ids"] == ["FLAG-MATCH"]


def test_run_parallel_critique_disputed_flags_override_verified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Disputed flags must override verified flags in the merged result."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks[:2])

    def _fake_scatter(**kwargs: Any) -> GenericScatterResult:
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for i, chk in enumerate(enriched):
            verified = ["FLAG-001"] if i == 0 else []
            disputed = ["FLAG-001"] if i == 1 else []
            items.append((
                _check_payload(chk, f"Checked {chk['id']} with explicit flag merge coverage.", flagged=(i == 1)),
                verified,
                disputed,
            ))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.2,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    result = run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    assert result.payload["disputed_flag_ids"] == ["FLAG-001"]
    assert "FLAG-001" not in result.payload["verified_flag_ids"]


def test_write_single_check_template_filters_prior_findings_to_target_check(tmp_path: Path) -> None:
    plan_dir, _project_dir, state = _scaffold(tmp_path, iteration=2)
    target_check = checks_for_robustness("standard")[1]
    other_check = checks_for_robustness("standard")[2]
    atomic_write_json(
        plan_dir / "critique_v1.json",
        {
            "checks": [
                {
                    "id": target_check["id"],
                    "question": target_check["question"],
                    "findings": [
                        _finding(
                            "Checked the target check thoroughly and found a significant issue still worth tracking.",
                            flagged=True,
                        ),
                        _finding(
                            "Checked a second branch of the target check and found it behaved as expected.",
                            flagged=False,
                        ),
                    ],
                },
                {
                    "id": other_check["id"],
                    "question": other_check["question"],
                    "findings": [
                        _finding(
                            "This finding belongs to another check and must not appear in the single-check template.",
                            flagged=True,
                        )
                    ],
                },
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
    )
    atomic_write_json(plan_dir / "faults.json", {"flags": [{"id": target_check["id"], "status": "addressed"}]})

    output_path = write_single_check_template(plan_dir, state, target_check, "critique_check_target.json")
    payload = read_json(output_path)

    assert [check["id"] for check in payload["checks"]] == [target_check["id"]]
    assert payload["checks"][0]["prior_findings"] == [
        {
            "detail": "Checked the target check thoroughly and found a significant issue still worth tracking.",
            "flagged": True,
            "status": "addressed",
        },
        {
            "detail": "Checked a second branch of the target check and found it behaved as expected.",
            "flagged": False,
            "status": "n/a",
        },
    ]


def test_write_single_check_template_uses_unique_output_paths(tmp_path: Path) -> None:
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    check_a, check_b = checks_for_robustness("standard")[:2]

    path_a = write_single_check_template(plan_dir, state, check_a, "critique_check_issue_hints.json")
    path_b = write_single_check_template(plan_dir, state, check_b, "critique_check_correctness.json")

    assert path_a != path_b
    assert path_a.exists()
    assert path_b.exists()
    assert read_json(path_a)["checks"][0]["id"] == check_a["id"]
    assert read_json(path_b)["checks"][0]["id"] == check_b["id"]


def test_run_parallel_critique_reraises_subagent_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Errors from scatter_worker_units propagate to the caller."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks)

    def _fake_scatter(**kwargs: Any) -> GenericScatterResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    with pytest.raises(RuntimeError, match="boom"):
        run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))


def test_run_parallel_critique_does_not_mutate_session_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Parallel critique must not mutate the outer plan session state."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    state["sessions"] = {
        "hermes_critic": {
            "id": "persisted-session",
            "mode": "persistent",
            "created_at": "2026-04-01T00:00:00Z",
            "last_used_at": "2026-04-01T00:00:00Z",
            "refreshed": False,
        }
    }
    original_sessions = copy.deepcopy(state["sessions"])
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks)

    def _fake_scatter(**kwargs: Any) -> GenericScatterResult:
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for chk in enriched:
            items.append((
                _check_payload(chk, f"Checked {chk['id']} while preserving the outer session state.", flagged=False),
                [],
                [],
            ))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    assert state["sessions"] == original_sessions


# ---------------------------------------------------------------------------
# New T18 tests — per-lens resolved models, unique output paths, read-only
# dispatch, and WorkerUnit construction.
# ---------------------------------------------------------------------------


def test_run_parallel_critique_builds_read_only_worker_units(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every WorkerUnit built by run_parallel_critique must have read_only=True."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks)

    captured_units: list[Any] = []

    def _fake_scatter(*, units: Any, **kwargs: Any) -> GenericScatterResult:
        captured_units.extend(units)
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for chk in enriched:
            items.append((_check_payload(chk, "read-only verify", flagged=False), [], []))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    assert len(captured_units) == len(enriched)
    for unit in captured_units:
        assert unit.read_only is True, f"WorkerUnit for {unit.step} should be read_only=True"


def test_run_parallel_critique_uses_per_lens_resolved_agent_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Each check's _resolved_agent_mode must be passed to its WorkerUnit."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")[:3]
    enriched = _enrich_checks(raw_checks)

    # Give each check a distinct resolved mode
    modes = [
        _resolved_mode(agent="hermes", model="model-A"),
        _resolved_mode(agent="claude", mode="prose", model="model-B"),
        _resolved_mode(agent="codex", model="model-C"),
    ]
    for i, chk in enumerate(enriched):
        chk["_resolved_agent_mode"] = modes[i]

    captured_units: list[Any] = []

    def _fake_scatter(*, units: Any, **kwargs: Any) -> GenericScatterResult:
        captured_units.extend(units)
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for chk in enriched:
            items.append((_check_payload(chk, "per-lens verify", flagged=False), [], []))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    assert len(captured_units) == len(enriched)
    for i, unit in enumerate(captured_units):
        assert unit.resolved == modes[i], (
            f"WorkerUnit[{i}] resolved={unit.resolved}, expected={modes[i]}"
        )


def test_run_parallel_critique_unique_output_paths_per_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Each check receives a distinct, deterministic output path."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks)

    captured_units: list[Any] = []

    def _fake_scatter(*, units: Any, **kwargs: Any) -> GenericScatterResult:
        captured_units.extend(units)
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for chk in enriched:
            items.append((_check_payload(chk, "unique paths verify", flagged=False), [], []))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    output_paths = [unit.output_path for unit in captured_units]
    # All paths must be unique
    assert len(output_paths) == len(set(output_paths)), (
        f"Expected {len(output_paths)} unique output paths, got {len(set(output_paths))}"
    )
    # All paths must be inside plan_dir
    for p in output_paths:
        assert p.parent == plan_dir or plan_dir in p.parents, (
            f"Output path {p} is not under plan_dir {plan_dir}"
        )
    # Each path must include the check id for determinism
    for i, chk in enumerate(enriched):
        assert chk["id"] in str(output_paths[i]), (
            f"Output path for check '{chk['id']}' must include the check id"
        )


def test_run_parallel_critique_missing_resolved_agent_mode_raises_invariant_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing _resolved_agent_mode metadata must raise CliError before dispatch."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    # Do NOT enrich — leave checks without _resolved_agent_mode
    bare_checks = [dict(chk) for chk in raw_checks]

    from megaplan.types import CliError

    with pytest.raises(CliError, match="No _resolved_agent_mode metadata"):
        run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(bare_checks))


def test_run_parallel_critique_empty_checks_returns_clean_result(tmp_path: Path) -> None:
    """Empty checks tuple returns a zero WorkerResult without error."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    result = run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=())

    assert result.payload["checks"] == []
    assert result.payload["verified_flag_ids"] == []
    assert result.payload["disputed_flag_ids"] == []
    assert result.cost_usd == 0.0
    assert result.session_id is None


def test_run_parallel_critique_worker_units_have_unique_step_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """WorkerUnit step and output_path must be unique per check — no reuse of
    paths across different checks."""
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    raw_checks = checks_for_robustness("standard")
    enriched = _enrich_checks(raw_checks)

    captured_units: list[Any] = []

    def _fake_scatter(*, units: Any, **kwargs: Any) -> GenericScatterResult:
        captured_units.extend(units)
        items: list[tuple[dict[str, Any], list[str], list[str]]] = []
        for chk in enriched:
            items.append((_check_payload(chk, "unique step/path verify", flagged=False), [], []))
        return GenericScatterResult(
            ordered_results=items,
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "megaplan.orchestration.parallel_critique.scatter_worker_units",
        _fake_scatter,
    )

    run_parallel_critique(state, plan_dir, root=REPO_ROOT, model="mock-model", checks=tuple(enriched))

    # Verify no two units share an output_path
    seen_paths: set[Path] = set()
    for unit in captured_units:
        assert unit.output_path not in seen_paths, (
            f"Duplicate output_path {unit.output_path} across WorkerUnits"
        )
        seen_paths.add(unit.output_path)
        # Verify each unit carries the check id in extra
        assert "check_id" in unit.extra


def test_parse_agent_output_template_prompt_fallback(tmp_path: Path) -> None:
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    output_path = write_single_check_template(plan_dir, state, check, "critique_check_issue_hints.json")
    payload = {
        "checks": [
            {
                "id": check["id"],
                "question": check["question"],
                "guidance": check["guidance"],
                "prior_findings": [],
                "findings": [
                    _finding(
                        "Checked the repository against the user notes and confirmed the resulting path is covered.",
                        flagged=False,
                    )
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": ["FLAG-001"],
        "disputed_flag_ids": [],
    }

    class FakeAgent:
        def __init__(self, followup: dict[str, object]) -> None:
            self.followup = followup
            self.calls: list[tuple[str, object]] = []

        def run_conversation(self, *, user_message: str, conversation_history: object = None) -> dict[str, object]:
            self.calls.append((user_message, conversation_history))
            return self.followup

    initial_result = {
        "final_response": "",
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [{"function": {"name": "read_file", "arguments": "{}"}}],
            }
        ],
    }
    followup = {"final_response": json.dumps(payload), "messages": [{"role": "assistant", "content": json.dumps(payload)}]}
    agent = FakeAgent(followup)

    parsed, raw_output = parse_agent_output(
        agent,
        initial_result,
        output_path=output_path,
        schema=_critique_schema(),
        step="critique",
        project_dir=project_dir,
        plan_dir=plan_dir,
    )

    assert parsed == payload
    assert raw_output == json.dumps(payload)
    assert len(agent.calls) == 1
    assert "fill in this JSON template" in agent.calls[0][0]


def test_run_check_uses_same_parse_fallback_chain_as_hermes_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    schema = _critique_schema()
    payload = {
        "checks": [
            {
                "id": check["id"],
                "question": check["question"],
                "guidance": check["guidance"],
                "prior_findings": [],
                "findings": [
                    _finding(
                        "Checked the single-check path and confirmed the summary-prompt fallback can recover JSON.",
                        flagged=False,
                    )
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    class FakeSessionDB:
        def __init__(self, db_path=None):
            pass

    class FakeAIAgent:
        instances: list["FakeAIAgent"] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.calls: list[tuple[str, object]] = []
            self._print_fn = None
            self.__class__.instances.append(self)

        def run_conversation(self, *, user_message: str, conversation_history: object = None) -> dict[str, object]:
            self.calls.append((user_message, conversation_history))
            if len(self.calls) == 1:
                return {
                    "final_response": "",
                    "messages": [
                        {
                            "role": "assistant",
                            "tool_calls": [{"function": {"name": "read_file", "arguments": "{}"}}],
                        }
                    ],
                    "estimated_cost_usd": 0.42,
                }
            return {
                "final_response": json.dumps(payload),
                "messages": [{"role": "assistant", "content": json.dumps(payload)}],
                "estimated_cost_usd": 0.0,
            }

    monkeypatch.setitem(sys.modules, "run_agent", ModuleType("run_agent"))
    monkeypatch.setitem(sys.modules, "hermes_state", ModuleType("hermes_state"))
    sys.modules["run_agent"].AIAgent = FakeAIAgent
    sys.modules["hermes_state"].SessionDB = FakeSessionDB

    index, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt = _run_check(
        0,
        check,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        model="minimax:test-model",
        schema=schema,
        project_dir=project_dir,
    )

    assert index == 0
    assert check_payload == {
        "id": check["id"],
        "question": check["question"],
        "findings": [
            {
                "detail": "Checked the single-check path and confirmed the summary-prompt fallback can recover JSON.",
                "flagged": False,
            }
        ],
    }
    assert verified_ids == []
    assert disputed_ids == []
    assert cost_usd == pytest.approx(0.42)
    assert len(FakeAIAgent.instances) == 1
    assert len(FakeAIAgent.instances[0].calls) == 2
    assert "fill in this JSON template" in FakeAIAgent.instances[0].calls[1][0]
