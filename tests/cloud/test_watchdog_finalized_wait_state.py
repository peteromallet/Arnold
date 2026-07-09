from __future__ import annotations

import json
import stat
from pathlib import Path

from tests.cloud.test_watchdog_wrappers import _extract_wrapper_function, _run_watchdog_shell


def test_watchdog_stopped_tmux_reports_awaiting_pr_merge_for_finalized_open_pr(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: review\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps({"last_state": "finalized", "pr_number": 42}),
        encoding="utf-8",
    )

    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "if [[ \"$1 $2 $3\" == \"pr view 42\" ]]; then",
                "  printf '%s\\n' '{\"state\":\"OPEN\"}'",
                "  exit 0",
                "fi",
                "exit 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            _extract_wrapper_function("session_health_status"),
            """
matching_runner_process_alive() { return 1; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  return 0
}
""".strip(),
            f"session_health_status demo-session {str(workspace)!r} {str(spec_path)!r} chain ''",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "awaiting_pr_merge"
