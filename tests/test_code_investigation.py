from __future__ import annotations

from agent_kit.prompts import build_system_prompt
from tests.helpers import create_store, insert_epic


def test_hot_context_includes_codebases_and_artifact_summaries_without_content(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    codebase = store.create_codebase(
        owner="Owner",
        name="Repo",
        default_branch="main",
        group_name="backend",
        notes="Core service",
    )
    store.create_code_artifact(
        kind="excerpt",
        source="codebase",
        content="very large source text",
        codebase_id=codebase["id"],
        epic_id="epic_1",
        file_path="src/app.py",
        content_summary="Important API shape",
    )

    hot_context = store.load_hot_context("epic_1")
    assert hot_context["codebases"][0]["group_name"] == "backend"
    assert hot_context["recent_code_artifacts"][0]["content_summary"] == "Important API shape"
    assert "content" not in hot_context["recent_code_artifacts"][0]

    prompt = build_system_prompt(hot_context)
    assert "# Available Codebases" in prompt
    assert "owner/repo" in prompt
    assert "Important API shape" in prompt
    assert "very large source text" not in prompt
