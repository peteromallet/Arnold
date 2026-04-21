from __future__ import annotations

import subprocess

import pytest

from megaplan.cloud.cli import _relay_output
from megaplan.cloud.redact import REDACTION, redact


@pytest.mark.parametrize(
    ("text", "secret_names", "env", "expected"),
    [
        ("token=supersecretvalue", ["API_TOKEN"], {"API_TOKEN": "supersecretvalue"}, f"token={REDACTION}"),
        (
            "OPENAI_API_KEY=supersecretvalue",
            ["OPENAI_API_KEY"],
            {"OPENAI_API_KEY": "supersecretvalue"},
            f"OPENAI_API_KEY={REDACTION}",
        ),
        (
            "OPENAI_API_KEY: supersecretvalue",
            ["OPENAI_API_KEY"],
            {"OPENAI_API_KEY": "supersecretvalue"},
            f"OPENAI_API_KEY: {REDACTION}",
        ),
        ("bearer sk-abc123456789", [], {}, f"bearer {REDACTION}"),
        ("github ghp_abc123456789", [], {}, f"github {REDACTION}"),
        ("slack xoxb-123456-abcdef", [], {}, f"slack {REDACTION}"),
    ],
)
def test_redact_handles_literals_assignments_and_known_token_patterns(
    text: str,
    secret_names: list[str],
    env: dict[str, str],
    expected: str,
) -> None:
    assert redact(text, secret_names, env=env) == expected


def test_relay_output_redacts_stdout_and_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    result = subprocess.CompletedProcess(
        args=["ssh"],
        returncode=0,
        stdout="OPENAI_API_KEY=supersecretvalue\n",
        stderr="github ghp_abc123456789\n",
    )

    _relay_output(
        result,
        secret_names=["OPENAI_API_KEY"],
        env={"OPENAI_API_KEY": "supersecretvalue"},
    )

    captured = capsys.readouterr()
    assert REDACTION in captured.out
    assert "supersecretvalue" not in captured.out
    assert REDACTION in captured.err
    assert "ghp_abc123456789" not in captured.err
