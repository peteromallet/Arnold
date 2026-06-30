from __future__ import annotations

import asyncio
import os
from pathlib import Path

from arnold_pipelines.megaplan.resident.agent_loop import AgentRequest, CodexCliAgentRunner
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistry


def test_codex_cli_runner_uses_output_last_message_and_medium_effort(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    codex = bin_dir / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_CALLS\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output-last-message\" ]]; then\n"
        "    shift\n"
        "    printf 'codex resident reply\\n' > \"$1\"\n"
        "  fi\n"
        "  shift || true\n"
        "done\n"
        "cat >/dev/null\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("CODEX_CALLS", str(calls))
    config = ResidentConfig(model_provider="codex", model_name="gpt-5.5", codex_reasoning_effort="medium")
    runner = CodexCliAgentRunner(config, cwd=tmp_path)

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "hello"},),
                system_prompt="system prompt",
            ),
            ToolRegistry(),
        )
    )

    assert response.final_text == "codex resident reply"
    assert response.metadata["runner"] == "codex_cli"
    call_text = calls.read_text(encoding="utf-8")
    assert "--model\ngpt-5.5" in call_text
    assert 'model_reasoning_effort="medium"' in call_text
    assert "--sandbox\nworkspace-write" in call_text
