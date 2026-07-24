from __future__ import annotations

from pathlib import Path


def test_run_agent_main_reads_query_file(tmp_path: Path, monkeypatch) -> None:
    from arnold.agent import run_agent

    prompt = tmp_path / "prompt.md"
    prompt.write_text("repair this from a file\n", encoding="utf-8")
    captured: dict[str, str] = {}

    class FakeAgent:
        def __init__(self, **_kwargs):
            pass

        def run_conversation(self, user_query: str):
            captured["query"] = user_query
            return {"completed": True, "api_calls": 0, "messages": [], "final_response": ""}

    monkeypatch.setattr(run_agent, "AIAgent", FakeAgent)

    run_agent.main(query_file=str(prompt), model="fake-model", api_key="fake-key")

    assert captured["query"] == "repair this from a file\n"

