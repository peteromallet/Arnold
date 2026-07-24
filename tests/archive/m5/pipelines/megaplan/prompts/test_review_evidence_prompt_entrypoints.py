from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan.prompts import create_prompt
from arnold.pipelines.megaplan.prompts import __dict__ as prompts_module
from arnold.pipelines.megaplan.prompts import review as review_prompts


def _state(tmp_path: Path) -> dict:
    return {"config": {"project_dir": str(tmp_path), "plan": "p"}, "current_state": "executed", "iteration": 1}


def test_create_prompt_review_branch_refreshes_review_evidence(monkeypatch, tmp_path: Path) -> None:
    calls = []
    review_evidence_path = tmp_path / "review_evidence.json"

    def fake_ensure(state, plan_dir, root=None):
        calls.append((state, plan_dir, root))
        review_evidence_path.write_text(json.dumps({"evidence": [{"kind": "fresh"}]}), encoding="utf-8")
        return {"evidence": []}

    def fake_builder(state, plan_dir):
        assert review_evidence_path.exists()
        return "review body"

    monkeypatch.setitem(prompts_module["_AGENT_REGISTRY"], "test-agent", ({"review": fake_builder}, "Test"))
    monkeypatch.setattr("arnold.pipelines.megaplan.prompts.ensure_review_evidence_for_prompt", fake_ensure)

    prompt = create_prompt("test-agent", "review", _state(tmp_path), tmp_path, root=tmp_path)

    assert "review body" in prompt
    assert review_evidence_path.exists()
    assert calls == [(_state(tmp_path), tmp_path, tmp_path)]


def test_direct_review_prompt_entrypoints_refresh_review_evidence(monkeypatch, tmp_path: Path) -> None:
    calls = []
    state = _state(tmp_path)
    plan_dir = tmp_path
    review_evidence_path = tmp_path / "review_evidence.json"

    def fake_ensure(state_arg, plan_dir_arg, root=None):
        review_evidence_path.write_text(
            json.dumps({"evidence": [{"kind": "fresh", "status": "satisfied"}]}),
            encoding="utf-8",
        )
        calls.append(
            {
                "root": root,
                "exists_after_ensure": review_evidence_path.exists(),
            }
        )
        return {"evidence": [{"kind": "fresh", "status": "satisfied"}]}

    context = {
        "project_dir": tmp_path,
        "intent_block": "intent",
        "approved_plan": "plan",
        "git_diff": "diff",
        "large_diff": False,
        "diff_summary": "",
        "changed_files": [],
        "prior_unmet_block": "",
        "finalize_data": {},
        "execution_data": {},
        "execution_audit_data": None,
        "settled_decisions": [],
        "prior_flags": [],
    }

    monkeypatch.setattr(review_prompts, "ensure_review_evidence_for_prompt", fake_ensure)
    monkeypatch.setattr(review_prompts, "_parallel_review_context", lambda state, plan_dir: context)
    monkeypatch.setattr(review_prompts, "_projected_review_blocks", lambda *args, **kwargs: ({}, {}))
    monkeypatch.setattr(review_prompts, "latest_plan_path", lambda plan_dir, state: tmp_path / "plan.md")
    monkeypatch.setattr(review_prompts, "read_json", lambda path: {})
    monkeypatch.setattr(review_prompts, "collect_git_diff_patch", lambda *args, **kwargs: "")
    monkeypatch.setattr(review_prompts, "collect_git_diff_summary", lambda *args, **kwargs: "")
    monkeypatch.setattr(review_prompts, "_gate_summary_or_skipped", lambda plan_dir: {"settled_decisions": []})
    (tmp_path / "plan.md").write_text("plan", encoding="utf-8")

    review_prompts.compact_review_prompt(state, plan_dir, tmp_path)
    review_prompts.single_check_review_prompt(
        state,
        plan_dir,
        tmp_path,
        check={"id": "c", "question": "q", "guidance": ""},
        output_path=tmp_path / "single.json",
        pre_check_flags=[],
    )
    review_prompts.parallel_criteria_review_prompt(state, plan_dir, tmp_path, tmp_path / "criteria.json")

    assert calls == [
        {"root": tmp_path, "exists_after_ensure": True},
        {"root": tmp_path, "exists_after_ensure": True},
        {"root": tmp_path, "exists_after_ensure": True},
    ]


def test_review_prompt_entrypoints_render_fresh_evidence_separately_from_historical_audit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path
    review_evidence = {"evidence": [{"kind": "fresh", "status": "satisfied", "summary": "new"}]}
    audit_data = {"tasks": [{"id": "T1", "status": "done"}]}
    context = {
        "project_dir": tmp_path,
        "intent_block": "intent",
        "approved_plan": "plan",
        "git_diff": "diff --git a/app.py b/app.py",
        "large_diff": False,
        "diff_summary": "",
        "changed_files": ["app.py"],
        "prior_unmet_block": "",
        "finalize_data": {"tasks": [{"id": "T1"}]},
        "execution_data": {"summary": "ok"},
        "execution_audit_data": audit_data,
        "settled_decisions": [],
        "prior_flags": [],
    }

    def fake_ensure(state_arg, plan_dir_arg, root=None):
        (plan_dir_arg / "review_evidence.json").write_text(json.dumps(review_evidence), encoding="utf-8")
        return review_evidence

    monkeypatch.setattr(review_prompts, "ensure_review_evidence_for_prompt", fake_ensure)
    monkeypatch.setattr(review_prompts, "_parallel_review_context", lambda state, plan_dir: context)
    monkeypatch.setattr(review_prompts, "_projected_review_blocks", lambda *args, **kwargs: ({"tasks": []}, audit_data))
    monkeypatch.setattr(review_prompts, "latest_plan_path", lambda plan_dir, state: tmp_path / "plan.md")
    monkeypatch.setattr(
        review_prompts,
        "read_json",
        lambda path: review_evidence if Path(path).name == "review_evidence.json" else {"tasks": []},
    )
    monkeypatch.setattr(review_prompts, "collect_git_diff_patch", lambda *args, **kwargs: "diff --git a/app.py b/app.py")
    monkeypatch.setattr(review_prompts, "collect_git_diff_summary", lambda *args, **kwargs: "")
    monkeypatch.setattr(review_prompts, "_gate_summary_or_skipped", lambda plan_dir: {"settled_decisions": []})
    (tmp_path / "plan.md").write_text("plan", encoding="utf-8")
    (tmp_path / "execution_audit.json").write_text(json.dumps(audit_data), encoding="utf-8")

    compact_prompt = review_prompts.compact_review_prompt(state, plan_dir, tmp_path)
    single_prompt = review_prompts.single_check_review_prompt(
        state,
        plan_dir,
        tmp_path,
        check={"id": "c", "question": "q", "guidance": ""},
        output_path=tmp_path / "single.json",
        pre_check_flags=[],
    )
    parallel_prompt = review_prompts.parallel_criteria_review_prompt(
        state, plan_dir, tmp_path, tmp_path / "criteria.json"
    )

    for prompt in (compact_prompt, single_prompt, parallel_prompt):
        assert "Fresh review-time evidence (`review_evidence.json`):" in prompt
        assert "Historical execution audit context (`execution_audit.json`, prompt projection only):" in prompt
        assert prompt.index("Fresh review-time evidence (`review_evidence.json`):") > prompt.index(
            "Historical execution audit context (`execution_audit.json`, prompt projection only):"
        )
        assert '"kind": "fresh"' in prompt


def test_pure_review_projection_helpers_do_not_refresh_review_evidence(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("pure helper collected review evidence")

    monkeypatch.setattr(review_prompts, "ensure_review_evidence_for_prompt", fail)

    review_prompts._projected_review_blocks({}, {}, None)
    assert "Historical execution audit context" in review_prompts._execution_audit_block(None)
