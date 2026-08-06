"""Regression coverage for local terminal command fencing."""

from pathlib import Path


def test_local_environment_heredoc_keeps_delimiter_and_fence_status(tmp_path: Path) -> None:
    """A no-final-newline heredoc must not swallow the status/fence trailer.

    The command string is intentionally terminated at the here-doc delimiter,
    matching the way terminal tool payloads arrive.  Appending ``; __hermes_rc``
    directly to that delimiter makes bash treat the trailer as here-doc body;
    the command then loses its closing fence and its real exit status.
    """
    from arnold.agent.tools.environments.local import LocalEnvironment

    environment = LocalEnvironment(cwd=str(tmp_path), timeout=10)
    try:
        result = environment.execute(
            "sh -c 'cat; exit 7' <<'PYEOF'\n"
            "heredoc payload\n"
            "PYEOF"
        )
    finally:
        environment.cleanup()

    assert result == {"output": "heredoc payload\n", "returncode": 7}


def test_local_environment_plain_command_retains_success_fence(tmp_path: Path) -> None:
    """The newline-based trailer remains compatible with ordinary commands."""
    from arnold.agent.tools.environments.local import LocalEnvironment

    environment = LocalEnvironment(cwd=str(tmp_path), timeout=10)
    try:
        result = environment.execute("printf plain")
    finally:
        environment.cleanup()

    assert result == {"output": "plain", "returncode": 0}
