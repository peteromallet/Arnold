"""Tests for revise-phase blast-radius carry-forward safety."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from arnold.pipelines.megaplan.handlers import critique


def test_revise_merge_failure_falls_back_to_prior_floor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    plan_path = plan_dir / "plan_v1.md"
    meta_path = plan_dir / "plan_v1.meta.json"
    plan_path.write_text("Step 1: Existing\n", encoding="utf-8")
    meta_path.write_text("{}", encoding="utf-8")

    floor_radius = {
        "strategy": "scoped",
        "confidence": "high",
        "selectors": [{"kind": "path", "value": "tests/test_floor.py"}],
        "changed_surfaces": ["pkg/floor.py"],
        "always_run": [],
        "full_suite_fallback": True,
        "rationale": "deterministic floor",
    }
    candidate_radius = {
        "strategy": "none",
        "confidence": "high",
        "selectors": [],
        "changed_surfaces": [],
        "always_run": [],
        "full_suite_fallback": True,
        "rationale": "unsafe narrowing",
    }
    state: dict[str, Any] = {
        "iteration": 1,
        "current_state": "critiqued",
        "config": {"project_dir": str(tmp_path)},
        "meta": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:old",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
    }
    captured_meta_fields: dict[str, Any] = {}

    @contextmanager
    def fake_load_plan_locked(*args: Any, **kwargs: Any) -> Iterator[tuple[Path, dict]]:
        yield plan_dir, state

    class FakeWorker:
        cost_usd = 0.0
        duration_ms = 1
        session_id = "session"
        prompt_tokens = 0
        completion_tokens = 0
        receipt_metrics: dict[str, Any] = {}
        payload = {
            "plan": "Step 1: Revised\n",
            "changes_summary": "Changed.",
            "flags_addressed": [],
            "questions": [],
            "success_criteria": [],
            "assumptions": [],
            "test_blast_radius": candidate_radius,
        }

    def fake_write_plan_version(**kwargs: Any) -> tuple[str, str, dict[str, str]]:
        captured_meta_fields.update(kwargs["meta_fields"])
        return "plan_v2.md", "plan_v2.meta.json", {
            "hash": "sha256:new",
            "timestamp": "2026-01-01T00:01:00Z",
        }

    monkeypatch.setattr(critique, "load_plan_locked", fake_load_plan_locked)
    monkeypatch.setattr(critique, "require_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(critique, "apply_profile_expansion", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        critique,
        "_resolve_revise_transition",
        lambda *args, **kwargs: (False, SimpleNamespace(next_state="critiqued")),
    )
    monkeypatch.setattr(critique, "latest_plan_path", lambda *args, **kwargs: plan_path)
    monkeypatch.setattr(critique, "latest_plan_meta_path", lambda *args, **kwargs: meta_path)
    monkeypatch.setattr(critique, "read_json", lambda *args, **kwargs: {"test_blast_radius": floor_radius})
    monkeypatch.setattr(
        critique._pkg,
        "_run_worker",
        lambda *args, **kwargs: (FakeWorker(), "agent", "mode", False),
    )
    monkeypatch.setattr(critique, "audit_step_payload", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        critique,
        "_merge_imported_decision_criteria",
        lambda _state, criteria: criteria,
    )
    monkeypatch.setattr(critique, "compute_plan_delta_percent", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(critique, "_write_plan_version", fake_write_plan_version)
    monkeypatch.setattr(critique, "update_flags_after_revise", lambda *args, **kwargs: None)
    monkeypatch.setattr(critique, "_next_progress_step", lambda *args, **kwargs: "finalize")
    monkeypatch.setattr(critique, "_remaining_significant_flags", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        critique,
        "_finish_step",
        lambda *args, **kwargs: {"summary": kwargs.get("summary", "")},
    )

    from arnold.pipelines.megaplan.orchestration import test_selection

    def raise_merge(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("merge failed")

    monkeypatch.setattr(test_selection, "merge_blast_radius_floor", raise_merge)

    critique.handle_revise(tmp_path, SimpleNamespace(plan="demo"))

    assert captured_meta_fields["test_blast_radius"] == floor_radius
