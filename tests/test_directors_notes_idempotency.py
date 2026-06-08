from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._core import atomic_write_json, atomic_write_text, read_json
from arnold.pipelines.megaplan.execute.core import _build_aggregate_execution_payload


def _state(project_dir: Path, *, iteration: int) -> dict:
    return {
        "name": "creative-idempotency",
        "idea": "Write a poem about a locked window.",
        "current_state": "finalized",
        "iteration": iteration,
        "created_at": "2026-04-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
            "mode": "creative",
            "form": "poem",
            "output_path": "poems/p.md",
            "primary_criterion": "tightest image",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:test",
                "timestamp": "2026-04-01T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {"notes": []},
    }


def _batch_payload(task_id: str, changed_line: str) -> dict:
    return {
        "output": f"Batch output for {task_id}.",
        "sections_written": ["opening_image"],
        "commands_run": [],
        "deviations": [],
        "task_updates": [
            {
                "task_id": task_id,
                "status": "done",
                "executor_notes": "Wrote a poem section.",
                "sections_written": ["opening_image"],
                "stance": {
                    "challenge_engaged": "I engaged poem-cut-explanation.",
                    "angle_taken": "I chose the image because it accuses the window.",
                    "what_changed": changed_line,
                },
                "stop_signal": {"requested": False, "defense": ""},
            }
        ],
        "sense_check_acknowledgments": [],
    }


def test_directors_notes_keeps_one_entry_per_iteration_across_multi_batch_runs(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    atomic_write_text(
        plan_dir / "plan_v1.md",
        "# Poem Canvas\n"
        "The window is locked because the room wants a witness. "
        "The draft explains the metaphor too directly.\n",
    )

    state = _state(project_dir, iteration=1)
    _build_aggregate_execution_payload(
        [_batch_payload("T1", "I killed the explanatory hinge."), _batch_payload("T2", "I kept the glass cold.")],
        completed_batches=2,
        total_batches=2,
        mode="creative",
        plan_dir=plan_dir,
        state=state,
    )

    notes = read_json(plan_dir / "directors_notes.json")
    assert [entry["iteration"] for entry in notes["passes"]] == [1]
    assert {stance["task_id"] for stance in notes["passes"][0]["stances"]} == {"T1", "T2"}

    state["iteration"] = 2
    _build_aggregate_execution_payload(
        [_batch_payload("T3", "I chose the lock because it indicts the speaker.")],
        completed_batches=1,
        total_batches=1,
        mode="creative",
        plan_dir=plan_dir,
        state=state,
    )

    notes = read_json(plan_dir / "directors_notes.json")
    assert [entry["iteration"] for entry in notes["passes"]] == [1, 2]
    assert [stance["task_id"] for stance in notes["passes"][1]["stances"]] == ["T3"]

    _build_aggregate_execution_payload(
        [_batch_payload("T4", "I refused the neat ending.")],
        completed_batches=1,
        total_batches=1,
        mode="creative",
        plan_dir=plan_dir,
        state=state,
    )

    notes = read_json(plan_dir / "directors_notes.json")
    assert [entry["iteration"] for entry in notes["passes"]] == [1, 2]
    assert [stance["task_id"] for stance in notes["passes"][1]["stances"]] == ["T4"]
    assert notes["passes"][1]["stances"][0]["what_changed"] == "I refused the neat ending."


def test_directors_notes_aggregate_preserves_critique_fired_provocations(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    atomic_write_text(
        plan_dir / "plan_v1.md",
        "# Poem Canvas\n"
        "The speaker explains the window until the image goes slack.\n",
    )
    critique_provocations = [
        {
            "id": "poem-cut-abstraction",
            "vector": "cut",
            "subtype": "exposure",
        },
        {
            "id": "poem-force-close-first",
            "vector": "force",
            "subtype": "reorder",
        },
        {
            "id": "poem-spark-confession",
            "vector": "spark",
            "subtype": "inversion",
        },
    ]
    atomic_write_json(
        plan_dir / "directors_notes.json",
        {
            "form": "poem",
            "primary_criterion": "tightest image",
            "passes": [
                {
                    "iteration": 1,
                    "provocateur_voice": None,
                    "provocations_fired": critique_provocations,
                    "stances": [],
                    "stop_requested": False,
                    "stop_defense": "",
                }
            ],
        },
    )

    _build_aggregate_execution_payload(
        [_batch_payload("T1", "I cut the abstraction because the lock has more nerve.")],
        completed_batches=1,
        total_batches=1,
        mode="creative",
        plan_dir=plan_dir,
        state=_state(project_dir, iteration=1),
    )

    notes = read_json(plan_dir / "directors_notes.json")
    pass_entry = notes["passes"][0]
    assert pass_entry["provocations_fired"] == critique_provocations
    assert [stance["task_id"] for stance in pass_entry["stances"]] == ["T1"]
