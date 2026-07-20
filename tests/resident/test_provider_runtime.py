from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.provider_runtime import (
    claude_tools_for,
    collect_provider_evidence,
    normalize_toolsets,
    provider_execution_contract,
    valid_session_id,
)


ROOT = Path(__file__).resolve().parents[2]
LAUNCHERS = ROOT / "arnold_pipelines/megaplan/skills/subagent-launcher"


def _load_launcher(name: str):
    path = LAUNCHERS / name
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_provider_capability_matrix_is_truthful_and_complete() -> None:
    contracts = {
        backend: provider_execution_contract(
            backend=backend,
            toolsets="file,web,terminal",
            max_tokens=4096,
            timeout_s=90,
            timeout_source="trusted_cli",
        )
        for backend in ("codex", "hermes", "claude")
    }

    for backend, contract in contracts.items():
        capabilities = contract["capabilities"]
        assert capabilities["persistent_session"] is True
        assert capabilities["exact_session_resume"] is True
        assert capabilities["raw_stream"]
        assert contract["controls"]["max_tokens"] == 4096
        assert contract["controls"]["timeout_s"] == 90.0
        assert contract["backend"] == backend
    assert contracts["hermes"]["capabilities"]["max_output_tokens"] == "native_request_cap"
    assert contracts["claude"]["capabilities"]["max_output_tokens"] == (
        "claude_code_environment_cap"
    )
    assert contracts["codex"]["capabilities"]["max_output_tokens"] == (
        "upstream_model_managed"
    )


def test_unbounded_provider_contract_is_explicit_and_provenanced() -> None:
    contract = provider_execution_contract(
        backend="codex",
        toolsets="file,web,terminal",
        max_tokens=4096,
        timeout_s=None,
    )
    assert contract["controls"]["timeout_s"] is None
    assert contract["controls"]["timeout_enforcement"] == "not_configured"
    assert contract["controls"]["timeout_policy"] == {
        "mode": "unbounded",
        "source": "default",
        "timeout_s": None,
    }


def test_generic_tool_policy_maps_exactly_or_fails_truthfully() -> None:
    assert normalize_toolsets("terminal,file,file") == ("file", "terminal")
    assert claude_tools_for(("file", "web", "terminal")) == (
        "Read,Edit,Write,Glob,Grep,WebFetch,WebSearch,Bash"
    )
    with pytest.raises(ValueError, match="unsupported managed-agent toolsets"):
        normalize_toolsets("file,secrets")
    with pytest.raises(ValueError, match="cannot enforce a narrowed generic toolset"):
        provider_execution_contract(
            backend="codex", toolsets="file", max_tokens=100, timeout_s=30, timeout_source="trusted_cli"
        )


@pytest.mark.parametrize(
    ("backend", "session_id", "valid"),
    [
        ("codex", "019f5d2e-d5da-75f3-a617-4712a1c57cc4", True),
        ("claude", "019f5d2e-d5da-75f3-a617-4712a1c57cc4", True),
        ("hermes", "resident_0123456789abcdef", True),
        ("hermes", "contains spaces", False),
        ("claude", "not-a-uuid", False),
    ],
)
def test_provider_specific_session_identity_validation(
    backend: str, session_id: str, valid: bool
) -> None:
    assert valid_session_id(backend, session_id) is valid


def test_claude_stream_normalizes_session_tools_usage_and_result(tmp_path: Path) -> None:
    session_id = "019f5d2e-d5da-75f3-a617-4712a1c57cc4"
    raw = tmp_path / "provider.raw"
    raw.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": session_id,
                    "model": "opus",
                    "tools": ["Read", "Bash"],
                },
                {
                    "type": "assistant",
                    "session_id": session_id,
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "tool-1", "name": "Read"}
                        ]
                    },
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "session_id": session_id,
                    "is_error": False,
                    "result": "DONE",
                    "usage": {"output_tokens": 7},
                },
            )
        )
        + "\n"
    )

    evidence = collect_provider_evidence(
        backend="claude",
        raw_output_path=raw,
        metadata_path=tmp_path / "metadata.json",
        expected_session_id=session_id,
        returncode=0,
    )

    assert evidence.session_id == session_id
    assert evidence.final_text == "DONE"
    assert evidence.usage == {"output_tokens": 7}
    assert evidence.failure_category is None
    assert {event["kind"] for event in evidence.events} >= {
        "session.started",
        "tool.requested",
        "turn.completed",
        "provider.process.completed",
    }


def test_claude_auth_failure_is_classified_from_durable_diagnostics(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "provider.raw"
    raw.touch()
    diagnostics = tmp_path / "run.log"
    diagnostics.write_text("Not logged in · Please run /login\n")

    evidence = collect_provider_evidence(
        backend="claude",
        raw_output_path=raw,
        metadata_path=tmp_path / "metadata.json",
        expected_session_id="019f5d2e-d5da-75f3-a617-4712a1c57cc4",
        returncode=1,
        diagnostics_path=diagnostics,
    )

    assert evidence.failure_category == "authentication_failed"
    assert "authenticated session" in evidence.failure_message


def test_claude_launcher_persists_new_sessions_and_resumes_exact_id() -> None:
    launcher = _load_launcher("launch_claude_agent.py")
    session_id = "019f5d2e-d5da-75f3-a617-4712a1c57cc4"

    new = launcher.build_claude_command(
        claude_bin="claude", model="opus", session_id=session_id
    )
    resumed = launcher.build_claude_command(
        claude_bin="claude", model="opus", resume=session_id
    )

    assert ["--session-id", session_id] == new[-2:]
    assert "--no-session-persistence" not in new
    assert ["--resume", session_id] == resumed[-2:]
    with pytest.raises(ValueError, match="mutually exclusive"):
        launcher.build_claude_command(
            claude_bin="claude",
            model="opus",
            session_id=session_id,
            resume=session_id,
        )


def test_hermes_launcher_hydrates_persisted_history_on_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    launcher = _load_launcher("launch_hermes_agent.py")
    session_id = "resident_0123456789abcdef"
    captured: dict[str, object] = {}

    class _DB:
        def get_session(self, requested):
            return {"id": requested}

        def get_messages_as_conversation(self, requested):
            assert requested == session_id
            return [{"role": "user", "content": "prior turn"}]

    class _Agent:
        def __init__(self, **kwargs):
            self.session_id = kwargs["session_id"]
            self.context_compressor = type(
                "Compressor",
                (),
                {"threshold_tokens": 1000, "context_length": 2000, "threshold_percent": 0.5},
            )()
            self._print_fn = None

        def run_conversation(self, **kwargs):
            captured.update(kwargs)
            return {
                "final_response": "RESUMED",
                "messages": [],
                "output_tokens": 2,
            }

    def load_hermes_env_with_stale_deadline():
        monkeypatch.setenv("HERMES_API_TIMEOUT", "300")
        monkeypatch.setenv("HERMES_DEEPSEEK_API_TIMEOUT", "1200")

    monkeypatch.setenv("ARNOLD_RESIDENT_UNBOUNDED_REQUEST", "1")
    monkeypatch.setattr(launcher, "_load_hermes_env", load_hermes_env_with_stale_deadline)
    monkeypatch.setattr(launcher, "_prefer_legacy_megaplan_distribution", lambda: None)
    monkeypatch.setattr(launcher, "_add_fallback_megaplan_paths", lambda: None)
    monkeypatch.setattr(
        launcher,
        "_import_runtime",
        lambda: (_Agent, _DB, lambda model: (model, {"api_key": "present"})),
    )

    metadata = tmp_path / "metadata.json"
    launcher.run(
        model="zhipu:glm-5.2",
        query="new turn",
        session_id=session_id,
        resume_session=True,
        metadata_file=str(metadata),
        project_dir=str(tmp_path),
    )

    assert captured["conversation_history"] == [
        {"role": "user", "content": "prior turn"}
    ]
    assert json.loads(metadata.read_text())["session_id"] == session_id
    assert "RESUMED" in capsys.readouterr().out
    assert os.environ["HERMES_API_TIMEOUT"] == "inf"
    assert os.environ["HERMES_DEEPSEEK_API_TIMEOUT"] == "inf"
