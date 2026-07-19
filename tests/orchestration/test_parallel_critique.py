from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.hermes_fanout import GenericScatterResult
from arnold_pipelines.megaplan.orchestration import parallel_critique
from arnold_pipelines.megaplan.types import AgentMode, CliError


def test_parallel_critique_persists_raw_output_on_worker_error(
    tmp_path: Path, monkeypatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    def fake_prompt(*_args: Any, **_kwargs: Any) -> str:
        return "critique prompt"

    def fake_scatter_worker_units(*, units, on_unit_error, **_kwargs):
        payload, cost, pt, ct, tt = on_unit_error(
            0,
            CliError(
                "worker_parse_error",
                "model emitted unsupported tool-call markup; critique template unchanged",
                extra={"raw_output": '<read_file path="critique_check_scope.json"/>'},
            ),
        )
        return GenericScatterResult(
            ordered_results=[payload],
            total_cost=cost,
            total_prompt_tokens=pt,
            total_completion_tokens=ct,
            total_tokens=tt,
            side_results=[],
        )

    monkeypatch.setattr(parallel_critique, "single_check_critique_prompt", fake_prompt)
    monkeypatch.setattr(parallel_critique, "scatter_worker_units", fake_scatter_worker_units)

    state = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "iteration": 1,
    }
    check = {
        "id": "scope",
        "question": "Does the plan cover scope?",
        "complexity": 4,
        "_resolved_agent_mode": AgentMode(
            agent="hermes",
            mode="fresh",
            refreshed=False,
            model="deepseek:deepseek-v4-pro",
            resolved_model="deepseek:deepseek-v4-pro",
        ),
    }

    worker = parallel_critique.run_parallel_critique(
        state,
        plan_dir,
        root=tmp_path,
        model="deepseek:deepseek-v4-pro",
        checks=(check,),
    )

    raw_path = plan_dir / "critique_check_scope_raw.txt"
    assert raw_path.read_text(encoding="utf-8") == '<read_file path="critique_check_scope.json"/>'
    assert worker.payload["checks"][0]["id"] == "scope"
    assert worker.payload["checks"][0]["status"] == "unverifiable"


def test_parallel_critique_flags_only_verifiability_payload_becomes_unverifiable_check(
    tmp_path: Path, monkeypatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    def fake_prompt(*_args: Any, **_kwargs: Any) -> str:
        return "critique prompt"

    def fake_scatter_worker_units(**_kwargs):
        return GenericScatterResult(
            ordered_results=[
                {
                    "checks": [],
                    "flags": [
                        {
                            "id": "cannot-access-local-path",
                            "category": "verifiability",
                            "concern": "shell/file access is blocked in this environment",
                            "evidence": (
                                "Attempts to inspect /workspace/tmp via local commands "
                                "failed with a sandbox namespace error."
                            ),
                        }
                    ],
                    "verified_flag_ids": ["cannot-access-local-path"],
                    "disputed_flag_ids": [],
                }
            ],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(parallel_critique, "single_check_critique_prompt", fake_prompt)
    monkeypatch.setattr(parallel_critique, "scatter_worker_units", fake_scatter_worker_units)

    state = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "iteration": 1,
    }
    check = {
        "id": "correctness",
        "question": "Is the plan technically correct?",
        "complexity": 4,
        "_resolved_agent_mode": AgentMode(
            agent="codex",
            mode="fresh",
            refreshed=False,
            model="gpt-5.4",
            resolved_model="gpt-5.4",
        ),
    }

    worker = parallel_critique.run_parallel_critique(
        state,
        plan_dir,
        root=tmp_path,
        model="gpt-5.4",
        checks=(check,),
    )

    payload = worker.payload["checks"][0]
    assert payload["id"] == "correctness"
    assert payload["status"] == "unverifiable"
    assert payload["unverifiable_cause"] == "sandbox_namespace"
    assert payload["unverifiable_error_kind"] == "sandbox_namespace"


def test_parallel_critique_flags_only_scope_payload_preserves_blocking_findings(
    tmp_path: Path, monkeypatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    monkeypatch.setattr(
        parallel_critique,
        "single_check_critique_prompt",
        lambda *_args, **_kwargs: "critique prompt",
    )
    monkeypatch.setattr(
        parallel_critique,
        "scatter_worker_units",
        lambda **_kwargs: GenericScatterResult(
            ordered_results=[
                {
                    "checks": [],
                    "flags": [
                        {
                            "id": "god-task",
                            "category": "scope",
                            "concern": "Step 2 combines independent objectives.",
                            "evidence": "The step spans protocol, migration, and broad tests.",
                        }
                    ],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                }
            ],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        ),
    )
    state = {"config": {"mode": "code", "project_dir": str(tmp_path)}, "iteration": 1}
    check = {
        "id": "scope",
        "question": "Are steps bounded?",
        "complexity": 5,
        "_resolved_agent_mode": AgentMode(
            agent="codex",
            mode="fresh",
            refreshed=False,
            model="gpt-5.5",
            resolved_model="gpt-5.5",
        ),
    }

    worker = parallel_critique.run_parallel_critique(
        state, plan_dir, root=tmp_path, model="gpt-5.5", checks=(check,)
    )

    payload = worker.payload["checks"][0]
    assert payload["status"] == "complete"
    assert payload["findings"] == [
        {"detail": "The step spans protocol, migration, and broad tests.", "flagged": True}
    ]
    assert worker.payload["flags"] == [
        {
            "id": worker.payload["flags"][0]["id"],
            "category": "completeness",
            "producer_category": "scope",
            "concern": "Step 2 combines independent objectives.",
            "evidence": "The step spans protocol, migration, and broad tests.",
            "severity_hint": "uncertain",
            "source_check_id": "scope",
            "producer_flag_id": "god-task",
        }
    ]
    assert worker.payload["flags"][0]["id"].startswith("CF-")


def test_parallel_worker_local_flag_ids_are_globally_stable_and_evidence_complete(
    tmp_path: Path, monkeypatch
) -> None:
    """Reproduce the three-worker shape that blocked custody M6 on 2026-07-16."""
    producer_payloads = [
        {
            "checks": [],
            "flags": [
                {
                    "id": "FLAG-001",
                    "category": "correctness",
                    "concern": "The declared-contract scanner cannot parse constructor calls.",
                    "evidence": "The existing extractor accepts literals, not BoundaryContract calls.",
                },
                {
                    "id": "FLAG-002",
                    "category": "correctness",
                    "concern": "The producer matrix is stale.",
                    "evidence": "The matrix has 35 rows while the registry has 49 entries.",
                },
            ],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        {
            "checks": [],
            "flags": [
                {
                    "id": "FLAG-001",
                    "category": "scope",
                    "concern": "The inventory task is too large for one worker turn.",
                    "evidence": "It combines multiple discovery channels and a full re-audit.",
                },
                {
                    "id": "FLAG-002",
                    "category": "scope",
                    "concern": "The registry tasks over-bundle source families.",
                    "evidence": "The readers span execute, cloud, repair, process, and session surfaces.",
                },
            ],
            "verified_flag_ids": ["FLAG-001"],
            "disputed_flag_ids": ["FLAG-002"],
        },
        {
            "checks": [],
            "flags": [
                {
                    "id": "FLAG-001",
                    "category": "verification",
                    "concern": "Generated evidence is not compared with checked-in artifacts.",
                    "evidence": "   ",
                }
            ],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
    ]

    monkeypatch.setattr(
        parallel_critique,
        "single_check_critique_prompt",
        lambda *_args, **_kwargs: "critique prompt",
    )
    monkeypatch.setattr(
        parallel_critique,
        "scatter_worker_units",
        lambda **_kwargs: GenericScatterResult(
            ordered_results=producer_payloads,
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        ),
    )
    state = {"config": {"mode": "code", "project_dir": str(tmp_path)}, "iteration": 1}
    checks = tuple(
        {
            "id": check_id,
            "question": f"Check {check_id}",
            "complexity": 5,
            "_resolved_agent_mode": AgentMode(
                agent="codex",
                mode="fresh",
                refreshed=False,
                model="gpt-5.5",
                resolved_model="gpt-5.5",
            ),
        }
        for check_id in ("correctness", "scope", "verification")
    )

    results = []
    for replay in range(2):
        plan_dir = tmp_path / f"plan-{replay}"
        plan_dir.mkdir()
        results.append(
            parallel_critique.run_parallel_critique(
                state, plan_dir, root=tmp_path, model="gpt-5.5", checks=checks
            ).payload
        )

    flag_ids = [flag["id"] for flag in results[0]["flags"]]
    assert len(flag_ids) == len(set(flag_ids)) == 5
    assert all(flag_id.startswith("CF-") for flag_id in flag_ids)
    assert all(flag["evidence"].strip() for flag in results[0]["flags"])
    assert results[0] == results[1]
    assert results[0]["verified_flag_ids"] == [results[0]["flags"][2]["id"]]
    assert results[0]["disputed_flag_ids"] == [results[0]["flags"][3]["id"]]


def test_parallel_flag_identity_conformance_for_arbitrary_repeated_local_ids() -> None:
    flags = []
    for worker_index in range(40):
        flags.extend(
            parallel_critique._source_flags(
                {
                    "flags": [
                        {
                            "id": f"FLAG-{local_index:03d}",
                            "category": "correctness",
                            "concern": f"Concern {worker_index}-{local_index}",
                            "evidence": f"Evidence {worker_index}-{local_index}",
                        }
                        for local_index in range(3)
                    ]
                },
                f"worker-{worker_index}",
            )
        )

    flag_ids = [flag["id"] for flag in flags]
    assert len(flag_ids) == len(set(flag_ids)) == 120
    assert all(flag["evidence"].strip() for flag in flags)


def test_blank_concern_and_evidence_retry_locally_with_worker_attribution(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    attempts = 0

    monkeypatch.setattr(
        parallel_critique,
        "single_check_critique_prompt",
        lambda *_args, **_kwargs: "critique prompt",
    )

    def fake_scatter_worker_units(**_kwargs):
        nonlocal attempts
        attempts += 1
        return GenericScatterResult(
            ordered_results=[
                {
                    "checks": [],
                    "flags": [
                        {
                            "id": "FLAG-001",
                            "category": "correctness",
                            "concern": " ",
                            "evidence": " ",
                        }
                    ],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                }
            ],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        parallel_critique, "scatter_worker_units", fake_scatter_worker_units
    )
    state = {"config": {"mode": "code", "project_dir": str(tmp_path)}, "iteration": 1}
    check = {
        "id": "correctness",
        "question": "Is it correct?",
        "complexity": 5,
        "_resolved_agent_mode": AgentMode(
            agent="codex",
            mode="fresh",
            refreshed=False,
            model="gpt-5.5",
            resolved_model="gpt-5.5",
        ),
    }
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    result = parallel_critique.run_parallel_critique(
        state, plan_dir, root=tmp_path, model="gpt-5.5", checks=(check,)
    )

    assert attempts == 3
    assert result.payload["flags"] == []
    assert result.payload["checks"][0]["status"] == "unverifiable"
    stderr = capsys.readouterr().err
    assert "worker 'correctness' contract invalid" in stderr
    assert "flags[0].concern and evidence are blank" in stderr
