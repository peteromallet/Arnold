from __future__ import annotations

from pathlib import Path
import queue
import threading
from typing import Any
from unittest.mock import patch

import pytest

from megaplan.orchestration import prep_research
from megaplan.types import CliError, PlanState
from megaplan.workers import WorkerResult


def _slow_research_child(payload: dict[str, Any], out_queue: Any) -> None:
    del payload, out_queue
    import time

    time.sleep(5)


def _state(project_dir: Path) -> PlanState:
    return {
        "name": "prep-test",
        "idea": "research the safe prep path",
        "current_state": "initialized",
        "iteration": 0,
        "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "standard"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
        "last_gate": {},
    }


@pytest.mark.parametrize(
    ("stage", "spec"),
    [
        ("triage", "claude:low"),
        ("triage", "shannon:claude-opus-4-7"),
        ("distill", "claude:low"),
        ("distill", "shannon:claude-opus-4-7"),
        ("fanout", "claude:low"),
        ("fanout", "shannon:claude-opus-4-7"),
    ],
)
def test_explicit_write_capable_prep_models_are_rejected(
    tmp_path: Path, stage: str, spec: str
) -> None:
    state = _state(tmp_path)
    state["config"]["prep_models"] = {stage: spec}

    with pytest.raises(CliError) as exc_info:
        prep_research.resolve_prep_stage_model(state, stage)

    assert exc_info.value.code == "invalid_prep_model"


def test_codex_fanout_prep_model_is_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["config"]["prep_models"] = {"fanout": "codex:gpt-5.4"}

    with pytest.raises(CliError) as exc_info:
        prep_research.resolve_prep_stage_model(state, "fanout")

    assert exc_info.value.code == "invalid_prep_model"
    assert "fanout" in exc_info.value.message


def test_fanout_research_failures_return_ordered_zero_cost_sentinels(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    areas = [
        {"id": "a", "area": "A", "brief": "first", "suggested_files": []},
        {"id": "b", "area": "B", "brief": "second", "suggested_files": []},
        {"id": "c", "area": "C", "brief": "third", "suggested_files": []},
    ]

    def fake_unit(**kwargs: Any):
        index = kwargs["index"]
        if index == 1:
            raise RuntimeError("unit failed")
        finding = {
            "area": areas[index]["id"],
            "brief": areas[index]["brief"],
            "status": "complete",
            "findings": [f"finding-{index}"],
            "files": [f"src/{areas[index]['id']}.py"],
            "code_refs": [f"pkg.{areas[index]['id']}"],
            "confidence": "high",
            "error": "",
        }
        return index, prep_research._research_unit_payload(finding, elapsed_time_ms=11), 0.25, 3, 4, 7

    with patch.object(prep_research, "run_hermes_research_unit_process", side_effect=fake_unit):
        result = prep_research.run_research_fanout(
            state,
            plan_dir,
            root=tmp_path,
            areas=areas,
            timeout_seconds=1.0,
            max_concurrent=3,
        )

    assert [item["area"] for item in result.ordered_results] == ["a", "b", "c"]
    assert result.ordered_results[1]["status"] == "error"
    assert result.ordered_results[1]["error"] == "unit failed"
    assert result.total_cost == 0.5
    assert result.total_prompt_tokens == 6
    assert result.total_completion_tokens == 8
    assert result.total_tokens == 14
    assert result.side_results[0]["files"] == ["src/a.py"]
    assert result.side_results[1]["status"] == "error"
    assert result.side_results[2]["code_refs"] == ["pkg.c"]


def test_run_prep_orchestration_caps_fanout_writes_dossier_and_returns_worker(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state["config"]["robustness"] = "full"
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (tmp_path / "megaplan").mkdir()
    (tmp_path / "megaplan" / "a.py").write_text("def a():\n    pass\n", encoding="utf-8")
    (tmp_path / "megaplan" / "b.py").write_text("def b():\n    pass\n", encoding="utf-8")
    (tmp_path / "megaplan" / "orchestration").mkdir()
    (tmp_path / "megaplan" / "orchestration" / "prep_research.py").write_text(
        "def run():\n    pass\n",
        encoding="utf-8",
    )
    areas = [
        {"id": f"a{index}", "area": f"Area {index}", "brief": f"brief {index}"}
        for index in range(6)
    ]
    triage_worker = WorkerResult(
        payload={"triage_framing": "Investigate bounded areas.", "areas": areas},
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
    )
    fanout_result = prep_research.GenericScatterResult(
        ordered_results=[
            {
                "area": "a0",
                "brief": "b0",
                "status": "complete",
                "findings": ["f0"],
                "files": ["megaplan/a.py"],
                "code_refs": ["pkg.a0"],
                "confidence": "high",
                "error": "",
            },
            {
                "area": "a1",
                "brief": "b1",
                "status": "partial",
                "findings": ["f1"],
                "files": ["megaplan/a.py", "megaplan/b.py"],
                "code_refs": ["pkg.a1"],
                "confidence": "medium",
                "error": "",
            },
            {
                "area": "a2",
                "brief": "b2",
                "status": "timed_out",
                "findings": [],
                "files": [],
                "code_refs": [],
                "confidence": "low",
                "error": "slow",
            },
            {
                "area": "a3",
                "brief": "b3",
                "status": "error",
                "findings": [],
                "files": [],
                "code_refs": [],
                "confidence": "low",
                "error": "bad",
            },
        ],
        total_cost=0.2,
        total_prompt_tokens=3,
        total_completion_tokens=4,
        total_tokens=7,
        side_results=[
            {"area": "a0", "status": "complete", "elapsed_time_ms": 30, "files": ["megaplan/a.py"], "code_refs": ["pkg.a0"]},
            {"area": "a1", "status": "partial", "elapsed_time_ms": 40, "files": ["megaplan/a.py", "megaplan/b.py"], "code_refs": ["pkg.a1"]},
            {"area": "a2", "status": "timed_out", "elapsed_time_ms": 50, "files": [], "code_refs": []},
            {"area": "a3", "status": "error", "elapsed_time_ms": 60, "files": [], "code_refs": []},
        ],
    )
    distill_worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [{"point": "evidence", "source": "research", "relevance": "high"}],
            "relevant_code": [
                {
                    "file_path": "megaplan/orchestration/prep_research.py",
                    "why": "final assembly",
                    "functions": ["run_prep_orchestration"],
                }
            ],
            "test_expectations": [
                {
                    "test_id": "tests/test_prep_research.py",
                    "what_it_checks": "prep orchestration sidecars",
                    "status": "pass_to_pass",
                }
            ],
            "constraints": [],
            "suggested_approach": "approach",
        },
        raw_output="distill",
        duration_ms=20,
        cost_usd=0.3,
        session_id="distill-session",
        prompt_tokens=5,
        completion_tokens=6,
        total_tokens=11,
    )

    with (
        patch.object(prep_research, "run_prep_triage", return_value=triage_worker),
        patch.object(prep_research, "run_research_fanout", return_value=fanout_result) as fanout,
        patch.object(prep_research, "distill_prep", return_value=distill_worker),
    ):
        result = prep_research.run_prep_orchestration(state, plan_dir, root=tmp_path)

    fanout.assert_called_once()
    assert [area["id"] for area in fanout.call_args.kwargs["areas"]] == ["a0", "a1", "a2", "a3"]
    assert result.worker.payload["task_summary"] == "summary"
    assert result.worker.cost_usd == pytest.approx(0.6)
    assert result.worker.prompt_tokens == 9
    assert result.worker.completion_tokens == 12
    assert result.worker.total_tokens == 21
    assert result.artifacts == [
        "prep.json",
        "prep_dossier.md",
        "prep_metrics.json",
        "prep_triage.json",
        "research.json",
    ]
    metrics = prep_research.json.loads((plan_dir / "prep_metrics.json").read_text(encoding="utf-8"))
    assert metrics["area_count"] == 6
    assert metrics["fanout_count"] == 4
    assert metrics["completed_count"] == 1
    assert metrics["partial_count"] == 1
    assert metrics["timed_out_count"] == 1
    assert metrics["error_count"] == 1
    assert metrics["missed_units"] == ["a2", "a3"]
    assert metrics["total_cost_usd"] == pytest.approx(0.6)
    assert metrics["prompt_tokens"] == 9
    assert metrics["completion_tokens"] == 12
    assert metrics["total_tokens"] == 21
    assert metrics["elapsed_time_ms"] == 210
    assert metrics["files"] == ["megaplan/a.py", "megaplan/b.py"]
    assert metrics["code_refs"] == ["pkg.a0", "pkg.a1"]
    assert [item["status"] for item in metrics["per_unit"]] == ["complete", "partial", "timed_out", "error"]
    assert metrics["gap_notes"] == [
        "a1: research returned partial coverage.",
        "a2: research timed out before the area could be closed.",
        "a3: research failed with bad.",
    ]
    assert metrics["contradiction_notes"] == [
        "file megaplan/a.py appears in multiple areas with differing evidence/status: a0=complete, a1=partial"
    ]
    assert metrics["overlap_groups"] == [
        {"kind": "file", "value": "megaplan/a.py", "areas": ["a0", "a1"]}
    ]
    assert metrics["cross_reference"] == {
        "performed": True,
        "checked_files": [
            "megaplan/a.py",
            "megaplan/b.py",
            "megaplan/orchestration/prep_research.py",
        ],
        "existing_files": [
            "megaplan/a.py",
            "megaplan/b.py",
            "megaplan/orchestration/prep_research.py",
        ],
        "missing_files": [],
        "shared_files": [],
        "to_be_built_files": [],
    }
    assert metrics["stage_metrics"]["triage"]["total_tokens"] == 3
    assert metrics["stage_metrics"]["fanout"]["total_tokens"] == 7
    assert metrics["stage_metrics"]["distill"]["total_tokens"] == 11
    dossier = (plan_dir / "prep_dossier.md").read_text(encoding="utf-8")
    assert "Investigate bounded areas." in dossier
    assert "a2 (timed_out)" in dossier
    assert "## Adjudication" in dossier
    assert "a2: research timed out before the area could be closed." in dossier
    assert "file megaplan/a.py appears in multiple areas with differing evidence/status" in dossier
    assert (plan_dir / "prep.json").exists()
    assert (plan_dir / "research.json").exists()


def test_research_unit_process_timeout_returns_sentinel_without_sibling_state(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    area = {"id": "slow", "area": "Slow", "brief": "times out", "suggested_files": []}

    index, unit_payload, cost, pt, ct, tt = prep_research.run_hermes_research_unit_process(
        index=0,
        area=area,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        model="deepseek:deepseek-v4-flash",
        timeout_seconds=0.05,
        hard_kill_grace_seconds=0.05,
        child_target=_slow_research_child,
    )

    assert index == 0
    assert unit_payload["finding"]["status"] == "timed_out"
    assert unit_payload["finding"]["error"] == "research timeout"
    assert unit_payload["metrics"]["status"] == "timed_out"
    assert (cost, pt, ct, tt) == (0.0, 0, 0, 0)


def test_research_child_watchdog_calls_child_local_interrupt(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()
    interrupted: list[str] = []
    agents: list["FakeAgent"] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs
            agents.append(self)

        def interrupt(self, message: str) -> None:
            interrupted.append(message)

        def run_conversation(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            import time

            time.sleep(0.08)
            return {
                "final_response": '{"area":"a","brief":"b","status":"complete","findings":[],"files":[],"code_refs":[],"confidence":"high","error":""}',
                "estimated_cost_usd": 0.1,
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "total_tokens": 3,
            }

    payload = {
        "index": 0,
        "area": {"id": "a", "area": "A", "brief": "b", "suggested_files": []},
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "model": "deepseek:deepseek-v4-flash",
        "timeout_seconds": 0.01,
        "max_iterations": 7,
    }

    with patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)):
        prep_research._run_research_child(payload, out)

    result = out.get_nowait()
    assert result["ok"] is True
    assert interrupted == ["research timeout"]
    assert agents[0].kwargs["enabled_toolsets"] == ["file-readonly", "web"]
    assert agents[0].kwargs["max_iterations"] == 7
    assert agents[0].kwargs["session_id"]
    assert isinstance(agents[0].kwargs["session_db"], FakeSessionDB)


def test_research_child_timeout_interrupt_is_isolated_from_concurrent_sibling(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()
    released = threading.Event()
    interrupted: dict[int, list[str]] = {0: [], 1: []}

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.index = int(str(kwargs["session_id"]).split("-")[-1])

        def interrupt(self, message: str) -> None:
            interrupted[self.index].append(message)
            released.set()

        def run_conversation(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            del user_message
            released.wait(timeout=1.0)
            return {
                "final_response": (
                    '{"area":"a","brief":"b","status":"complete",'
                    '"findings":[],"files":[],"code_refs":[],"confidence":"high","error":""}'
                ),
                "estimated_cost_usd": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

    payloads = [
        {
            "index": 0,
            "area": {"id": "slow", "area": "Slow", "brief": "times out", "suggested_files": []},
            "state": state,
            "plan_dir": str(plan_dir),
            "root": str(tmp_path),
            "model": "deepseek:deepseek-v4-flash",
            "timeout_seconds": 0.01,
            "max_iterations": 7,
        },
        {
            "index": 1,
            "area": {"id": "sibling", "area": "Sibling", "brief": "continues", "suggested_files": []},
            "state": state,
            "plan_dir": str(plan_dir),
            "root": str(tmp_path),
            "model": "deepseek:deepseek-v4-flash",
            "timeout_seconds": 1.0,
            "max_iterations": 7,
        },
    ]

    session_ids = iter(["session-0", "session-1"])

    with (
        patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)),
        patch.object(prep_research.uuid, "uuid4", side_effect=lambda: next(session_ids)),
    ):
        threads = [
            threading.Thread(target=prep_research._run_research_child, args=(payload, out))
            for payload in payloads
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

    assert all(not thread.is_alive() for thread in threads)
    results = sorted((out.get_nowait() for _ in threads), key=lambda item: item["index"])
    assert [item["ok"] for item in results] == [True, True]
    assert interrupted[0] == ["research timeout"]
    assert interrupted[1] == []


def test_research_child_parse_failure_becomes_error_sentinel(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

        def interrupt(self, message: str) -> None:
            del message

        def run_conversation(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            del user_message
            return {
                "final_response": "not json",
                "messages": [{"role": "assistant", "content": "not json"}],
                "estimated_cost_usd": 0.0,
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            }

    payload = {
        "index": 0,
        "area": {"id": "a", "area": "A", "brief": "b", "suggested_files": []},
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "model": "deepseek:deepseek-v4-flash",
        "timeout_seconds": 0.5,
        "max_iterations": 7,
    }

    with patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)):
        prep_research._run_research_child(payload, out)

    result = out.get_nowait()
    assert result["ok"] is False
    assert result["payload"]["finding"]["status"] == "error"
    assert "invalid json" in result["payload"]["finding"]["error"].lower()
    assert result["cost_usd"] == 0.0


def test_research_child_uses_parse_fallback_chain_and_keeps_metrics(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs
            self.calls: list[tuple[str, object]] = []

        def interrupt(self, message: str) -> None:
            del message

        def run_conversation(self, *, user_message: str, conversation_history: object = None, **kwargs: Any) -> dict[str, Any]:
            del kwargs
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
                    "prompt_tokens": 5,
                    "completion_tokens": 6,
                    "total_tokens": 11,
                }
            return {
                "final_response": (
                    '{"area":"a","brief":"b","status":"complete","findings":["f"],'
                    '"files":["megaplan/orchestration/prep_research.py"],'
                    '"code_refs":["prep_research.run_research_fanout"],'
                    '"confidence":"high","error":""}'
                ),
                "messages": [{"role": "assistant", "content": "{}"}],
                "estimated_cost_usd": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

    payload = {
        "index": 0,
        "area": {"id": "a", "area": "A", "brief": "b", "suggested_files": []},
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "model": "deepseek:deepseek-v4-flash",
        "timeout_seconds": 0.5,
        "max_iterations": 7,
    }

    with patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)):
        prep_research._run_research_child(payload, out)

    result = out.get_nowait()
    assert result["ok"] is True
    assert result["payload"]["finding"]["status"] == "complete"
    assert result["payload"]["metrics"]["files"] == ["megaplan/orchestration/prep_research.py"]
    assert result["payload"]["metrics"]["code_refs"] == ["prep_research.run_research_fanout"]
    assert result["cost_usd"] == pytest.approx(0.42)
    assert result["prompt_tokens"] == 5
    assert result["completion_tokens"] == 6
    assert result["total_tokens"] == 11


# ---------------------------------------------------------------------------
# T12(g): _compatible_prep_payload preserves open_questions
# ---------------------------------------------------------------------------


def test_compatible_prep_payload_preserves_open_questions() -> None:
    """open_questions must survive the _compatible_prep_payload filter."""
    payload = {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
        "open_questions": [
            {"severity": "blocking", "question": "Which auth library?"},
            {"severity": "assume_and_proceed", "question": "Which cache?", "assumption": "Redis."},
        ],
        # Extra key not in PREP_COMPATIBLE_KEYS
        "extra_field": "should be stripped",
    }
    result = prep_research._compatible_prep_payload(payload)
    assert "open_questions" in result
    assert result["open_questions"] == payload["open_questions"]
    assert "extra_field" not in result
    # Verify other keys are preserved
    assert result["skip"] is False
    assert result["task_summary"] == "summary"


def test_compatible_prep_payload_handles_absent_open_questions() -> None:
    """Payload without open_questions should pass through unchanged (minus extra keys)."""
    payload = {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
    }
    result = prep_research._compatible_prep_payload(payload)
    assert "open_questions" not in result
    assert result["skip"] is False


# ---------------------------------------------------------------------------
# T5: forced upstream-summary prep research areas
# ---------------------------------------------------------------------------


def test_forced_upstream_areas_returns_empty_when_no_chain_policy() -> None:
    """No forced areas when state lacks chain_policy."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
        "last_gate": {},
    }
    assert prep_research._forced_upstream_areas(state) == []


def test_forced_upstream_areas_returns_empty_when_not_plan_only() -> None:
    """No forced areas when contract_context has plan_only=False."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": False,
                    "dependency_labels": ["m1"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "m1",
                            "provides": [{
                                "name": "P",
                                "interfaces": [{"symbol": "P.run", "path": "megaplan/p.py", "signature": "P.run()"}],
                            }],
                        }
                    ],
                },
            },
        },
        "last_gate": {},
    }
    assert prep_research._forced_upstream_areas(state) == []


def test_forced_upstream_areas_derives_one_area_per_dependency_label() -> None:
    """Each dependency_label becomes one forced area with upstream path context."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": True,
                    "dependency_labels": ["m1", "m2"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "m1",
                            "provides": [{
                                "name": "Planner surface",
                                "interfaces": [
                                    {"symbol": "Planner.run", "path": "megaplan/planner.py", "signature": "Planner.run()"},
                                ],
                            }],
                        },
                        {
                            "milestone_label": "m2",
                            "provides": [{
                                "name": "Executor surface",
                                "interfaces": [
                                    {"symbol": "Executor.run", "path": "megaplan/executor.py", "signature": "Executor.run()"},
                                ],
                            }],
                        },
                    ],
                },
            },
        },
        "last_gate": {},
    }
    forced = prep_research._forced_upstream_areas(state)
    assert len(forced) == 2
    assert forced[0]["id"] == "upstream-m1"
    assert "megaplan/planner.py" in forced[0]["suggested_files"]
    assert forced[1]["id"] == "upstream-m2"
    assert "megaplan/executor.py" in forced[1]["suggested_files"]
    # Deduplication within forced areas
    state["meta"]["chain_policy"]["contract_context"]["dependency_labels"] = ["m1", "m1", "m2"]
    deduped = prep_research._forced_upstream_areas(state)
    assert len(deduped) == 2
    assert [a["id"] for a in deduped] == ["upstream-m1", "upstream-m2"]


def test_deduplicate_areas_keeps_forced_first_and_drops_duplicate_ids() -> None:
    """Forced areas appear first; triage areas with same id are dropped."""
    forced = [{"id": "f1", "area": "forced-1"}, {"id": "f2", "area": "forced-2"}]
    triage = [{"id": "t1", "area": "triage-1"}, {"id": "f1", "area": "triage-f1-dup"}, {"id": "t2", "area": "triage-2"}]
    merged = prep_research._deduplicate_areas(forced, triage)
    ids = [a.get("id") for a in merged]
    assert ids == ["f1", "f2", "t1", "t2"]


def test_cap_research_areas_retains_forced_when_forced_count_exceeds_cap(tmp_path: Path) -> None:
    """When forced_count >= cap, all slots go to forced areas; triage is culled."""
    state = _state(tmp_path)
    state["config"]["robustness"] = "light"  # cap = 2
    areas = [
        {"id": "forced-a", "area": "FA"},
        {"id": "forced-b", "area": "FB"},
        {"id": "forced-c", "area": "FC"},  # 3 forced
        {"id": "triage-a", "area": "TA"},
    ]
    capped, cap = prep_research._cap_research_areas(state, areas, forced_count=3)
    assert cap == 2
    assert len(capped) == 3  # all forced areas retained, triage dropped
    assert [a["id"] for a in capped] == ["forced-a", "forced-b", "forced-c"]


def test_cap_research_areas_normal_cap_when_forced_fewer_than_cap(tmp_path: Path) -> None:
    """When forced_count < cap, normal slicing applies to merged areas."""
    state = _state(tmp_path)
    state["config"]["robustness"] = "full"  # cap = 4
    areas = [
        {"id": "forced-a", "area": "FA"},
        {"id": "triage-a", "area": "TA"},
        {"id": "triage-b", "area": "TB"},
        {"id": "triage-c", "area": "TC"},
        {"id": "triage-d", "area": "TD"},
    ]
    capped, cap = prep_research._cap_research_areas(state, areas, forced_count=1)
    assert cap == 4
    assert len(capped) == 4
    assert capped[0]["id"] == "forced-a"


def test_prep_metrics_includes_forced_count() -> None:
    """_prep_metrics records forced_count in the returned dict."""
    fanout = prep_research.GenericScatterResult(
        ordered_results=[],
        total_cost=0.0,
        total_prompt_tokens=0,
        total_completion_tokens=0,
        total_tokens=0,
        side_results=[],
    )
    triage = WorkerResult(
        payload={}, raw_output="", duration_ms=0, cost_usd=0.0,
        session_id="s", prompt_tokens=0, completion_tokens=0, total_tokens=0,
    )
    distill = WorkerResult(
        payload={}, raw_output="", duration_ms=0, cost_usd=0.0,
        session_id="s", prompt_tokens=0, completion_tokens=0, total_tokens=0,
    )
    metrics = prep_research._prep_metrics(
        original_area_count=5,
        capped_area_count=3,
        forced_count=2,
        findings=[],
        fanout=fanout,
        triage_worker=triage,
        distill_worker=distill,
    )
    assert metrics["forced_count"] == 2
    assert metrics["area_count"] == 5
    assert metrics["fanout_count"] == 3


def test_minimal_prep_metrics_has_forced_count() -> None:
    """minimal_prep_metrics includes forced_count=0."""
    metrics = prep_research.minimal_prep_metrics()
    assert "forced_count" in metrics
    assert metrics["forced_count"] == 0


# ---------------------------------------------------------------------------
# T6: upstream-provided path cross-reference classification
# ---------------------------------------------------------------------------


def test_collect_upstream_provided_paths_returns_path_map() -> None:
    """_collect_upstream_provided_paths maps interface paths to milestone labels."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": True,
                    "dependency_labels": ["m1"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "m1",
                            "provides": [{
                                "name": "Planner surface",
                                "interfaces": [
                                    {"symbol": "Planner.run", "path": "megaplan/planner.py", "signature": "Planner.run()"},
                                    {"symbol": "Planner.init", "path": "megaplan/init.py", "signature": "Planner.init()"},
                                ],
                            }],
                        },
                    ],
                },
            },
        },
        "last_gate": {},
    }
    paths = prep_research._collect_upstream_provided_paths(state)
    assert paths == {"megaplan/planner.py": "m1", "megaplan/init.py": "m1"}


def test_collect_upstream_provided_paths_returns_empty_without_policy() -> None:
    """_collect_upstream_provided_paths returns empty dict when plan_only is not True."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
        "last_gate": {},
    }
    assert prep_research._collect_upstream_provided_paths(state) == {}


def test_cross_reference_classifies_upstream_paths_as_to_be_built(tmp_path: Path) -> None:
    """Upstream-provided paths appear in to_be_built_files and are excluded from missing_files."""
    # Create a file that exists locally
    (tmp_path / "megaplan").mkdir(parents=True)
    (tmp_path / "megaplan" / "existing.py").write_text("# exists")

    findings = [
        {
            "area": "a", "brief": "b", "status": "complete",
            "findings": ["f"], "files": ["megaplan/upstream.py", "megaplan/existing.py"],
            "code_refs": [], "confidence": "high", "error": "",
        }
    ]
    prep_payload: dict[str, Any] = {
        "relevant_code": [{"file_path": "megaplan/missing.py"}],
    }
    upstream_paths = {"megaplan/upstream.py": "m1"}

    cr = prep_research._cross_reference_prep_output(
        root=tmp_path,
        findings=findings,
        prep_payload=prep_payload,
        upstream_provided_paths=upstream_paths,
    )
    assert cr["performed"] is True
    assert "megaplan/upstream.py" in cr["checked_files"]
    # upstream.py should be to-be-built, NOT missing
    assert "megaplan/upstream.py" not in cr["missing_files"]
    to_be_built = {(item["path"], item["upstream_milestone"]) for item in cr["to_be_built_files"]}
    assert ("megaplan/upstream.py", "m1") in to_be_built
    # existing.py exists locally → in existing_files
    assert "megaplan/existing.py" in cr["existing_files"]
    # missing.py doesn't exist and isn't upstream → missing
    assert "megaplan/missing.py" in cr["missing_files"]


def test_cross_reference_only_uses_declared_dependency_contract_paths(tmp_path: Path) -> None:
    """Sibling-only paths stay missing; only declared dependency paths become to-be-built."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": True,
                    "milestone_label": "M-b",
                    "dependency_labels": ["M-a"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "M-a",
                            "provides": [{
                                "name": "Planner surface",
                                "interfaces": [
                                    {"symbol": "Planner.run", "path": "planner.py", "signature": "run()"},
                                ],
                            }],
                        },
                    ],
                },
            },
        },
        "last_gate": {},
    }
    findings = [
        {
            "area": "a", "brief": "b", "status": "complete",
            "findings": ["f"], "files": ["planner.py", "builder.py"],
            "code_refs": [], "confidence": "high", "error": "",
        }
    ]
    upstream_paths = prep_research._collect_upstream_provided_paths(state)

    cr = prep_research._cross_reference_prep_output(
        root=tmp_path,
        findings=findings,
        prep_payload={},
        upstream_provided_paths=upstream_paths,
    )

    assert {(item["path"], item["upstream_milestone"]) for item in cr["to_be_built_files"]} == {
        ("planner.py", "M-a")
    }
    assert "planner.py" not in cr["missing_files"]
    assert "builder.py" in cr["missing_files"]


def test_cross_reference_without_upstream_paths_keeps_old_behavior(tmp_path: Path) -> None:
    """Without upstream_provided_paths, to_be_built_files is empty and all missing paths stay missing."""
    findings = [
        {
            "area": "a", "brief": "b", "status": "complete",
            "findings": ["f"], "files": ["megaplan/nonexistent.py"],
            "code_refs": [], "confidence": "high", "error": "",
        }
    ]
    prep_payload: dict[str, Any] = {}

    cr = prep_research._cross_reference_prep_output(
        root=tmp_path,
        findings=findings,
        prep_payload=prep_payload,
    )
    assert cr["to_be_built_files"] == []
    assert "megaplan/nonexistent.py" in cr["missing_files"]


def test_gap_notes_mentions_to_be_built_files() -> None:
    """_gap_notes includes a note for to_be_built_files."""
    findings: list[dict[str, Any]] = []
    prep_payload: dict[str, Any] = {"key_evidence": ["e"], "relevant_code": [], "test_expectations": []}
    cross_reference = {
        "performed": True,
        "checked_files": [],
        "existing_files": [],
        "missing_files": [],
        "shared_files": [],
        "to_be_built_files": [
            {"path": "megaplan/planner.py", "upstream_milestone": "m1"},
            {"path": "megaplan/executor.py", "upstream_milestone": "m2"},
        ],
    }
    notes = prep_research._gap_notes(findings, prep_payload, cross_reference)
    to_be_built_note = [n for n in notes if "not yet built locally" in n]
    assert len(to_be_built_note) == 1
    assert "m1" in to_be_built_note[0]
    assert "m2" in to_be_built_note[0]
    assert "megaplan/planner.py" in to_be_built_note[0]
    assert "megaplan/executor.py" in to_be_built_note[0]
