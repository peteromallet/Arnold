from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def _extract_wrapper_function(name: str) -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _run_watchdog_shell(
    script: str,
    *,
    path_prefix: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    for name in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_DM_USER_ID",
        "DISCORD_WEBHOOK_URL",
        "REPORT_WEBHOOK",
        "SLACK_WEBHOOK_URL",
    ):
        env.pop(name, None)
    env["DISCORD_DM_BIN"] = "/bin/false"
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout.strip()


def _write_chain_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _init_repo(root: Path, *, bare: bool = False) -> None:
    args = ["git", "init"]
    if bare:
        args.append("--bare")
    subprocess.run(args, cwd=root, check=True, capture_output=True, text=True)
    if not bare:
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Watchdog Tests"], cwd=root, check=True)


def _seed_origin(origin: Path, tmp_path: Path) -> tuple[Path, str]:
    seed = tmp_path / "seed"
    seed.mkdir()
    _init_repo(seed)
    (seed / "README.md").write_text("base\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "base")
    _git(seed, "branch", "-M", "main")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-u", "origin", "main")
    return seed, _git(seed, "rev-parse", "HEAD")


def _clone(origin: Path, dest: Path) -> None:
    subprocess.run(["git", "clone", str(origin), str(dest)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(dest), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(dest), "config", "user.name", "Watchdog Tests"], check=True)
    _git(dest, "checkout", "-B", "main", "origin/main")


def _setup_merged_pr_workspace(tmp_path: Path) -> tuple[Path, Path, str]:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _init_repo(origin, bare=True)
    _seed_origin(origin, tmp_path)

    workspace = tmp_path / "workspace"
    _clone(origin, workspace)

    author = tmp_path / "author"
    _clone(origin, author)
    _git(author, "checkout", "-b", "feature/pr-42", "origin/main")
    (author / "README.md").write_text("base\nfeature branch change\n", encoding="utf-8")
    _git(author, "add", "README.md")
    _git(author, "commit", "-m", "feature change")
    _git(author, "push", "-u", "origin", "feature/pr-42")
    _git(author, "checkout", "main")
    _git(author, "merge", "--no-ff", "feature/pr-42", "-m", "Merge PR #42")
    merge_sha = _git(author, "rev-parse", "HEAD")
    _git(author, "push", "origin", "main")

    missing = subprocess.run(
        ["git", "cat-file", "-e", f"{merge_sha}^{{commit}}"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert missing.returncode != 0
    return workspace, origin, merge_sha


def test_watchdog_pr_reconciliation_fetches_missing_merge_and_relaunches_auto_chain(
    tmp_path: Path,
) -> None:
    workspace, _origin, merge_sha = _setup_merged_pr_workspace(tmp_path)
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()

    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")

    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "demo-chain.json"
    _write_chain_state(
        chain_path,
        {"last_state": "awaiting_pr_merge", "pr_number": 42, "pr_state": "open"},
    )
    needs_human = repair_dir / "demo-session.needs-human.json"
    needs_human.write_text(json.dumps({"summary": "stale open PR marker"}) + "\n", encoding="utf-8")

    advance_script = tmp_path / "advance_chain.py"
    advance_script.write_text(
        "from __future__ import annotations\n"
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "workspace = Path(sys.argv[1])\n"
        "merge_sha = sys.argv[2]\n"
        "chain_path = Path(sys.argv[3])\n"
        "advanced_flag = Path(sys.argv[4])\n"
        "check = subprocess.run(\n"
        "    ['git', 'cat-file', '-e', f'{merge_sha}^{{commit}}'],\n"
        "    cwd=workspace,\n"
        "    capture_output=True,\n"
        "    text=True,\n"
        "    check=False,\n"
        ")\n"
        "if check.returncode != 0:\n"
        "    raise SystemExit(check.stderr or check.stdout or 'missing merge commit')\n"
        "payload = json.loads(chain_path.read_text(encoding='utf-8'))\n"
        "payload['last_state'] = 'done'\n"
        "payload['pr_state'] = 'merged'\n"
        "payload['advanced_by'] = 'watchdog-test'\n"
        "chain_path.write_text(json.dumps(payload, sort_keys=True) + '\\n', encoding='utf-8')\n"
        "advanced_flag.write_text('advanced\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )

    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2 $3\" == \"pr view 42\" ]]; then\n"
        f"  printf '%s\\n' '{json.dumps({'state': 'MERGED', 'mergeCommit': {'oid': merge_sha}})}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    call_log = tmp_path / "calls.log"
    launch_script = tmp_path / "launch.sh"
    advanced_flag = tmp_path / "advanced.flag"
    script = "\n\n".join(
        [
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("reconcile_awaiting_pr_merge"),
            _extract_wrapper_function("launch_chain_tick"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"CALL_LOG={str(call_log)!r}",
            f"LAUNCH_SCRIPT={str(launch_script)!r}",
            f"ADVANCE_SCRIPT={str(advance_script)!r}",
            f"MERGE_SHA={merge_sha!r}",
            f"CHAIN_PATH={str(chain_path)!r}",
            f"ADVANCED_FLAG={str(advanced_flag)!r}",
            """
log() { printf '%s\n' "$*" >> "$CALL_LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
session_health_status() { echo awaiting_pr_merge; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
plan_terminal_status() { echo none; }
plan_attention_status_env() { :; }
repair_needs_human_path() { printf '%s/%s.needs-human.json\n' "$REPAIR_DATA_DIR" "$1"; }
workspace_has_other_alive_session() { return 1; }
repair_loop_busy_state() { echo none; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { return 1; }
kimi_dispatch_marker_clear() { :; }
kimi_dispatch_marker_set() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() {
  echo "python3 '$ADVANCE_SCRIPT' '$2' '$MERGE_SHA' '$CHAIN_PATH' '$ADVANCED_FLAG'"
}
mktemp() { printf '%s\n' "$LAUNCH_SCRIPT"; }
chmod() { :; }
tmux() {
  printf 'tmux %s\n' "$*" >> "$CALL_LOG"
  case "$1" in
    has-session) return 1 ;;
    kill-session) return 0 ;;
    new-session) bash "$LAUNCH_SCRIPT"; return $? ;;
  esac
  return 0
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert advanced_flag.read_text(encoding="utf-8").strip() == "advanced"
    updated = json.loads(chain_path.read_text(encoding="utf-8"))
    assert updated["last_state"] == "done"
    assert updated["pr_state"] == "merged"
    assert updated["advanced_by"] == "watchdog-test"
    assert not needs_human.exists()
    calls = call_log.read_text(encoding="utf-8")
    assert "session awaiting PR merge reconciled merged; falling through to relaunch" in calls
    assert "tmux new-session -d -s demo-session" in calls
    cat_file = subprocess.run(
        ["git", "cat-file", "-e", f"{merge_sha}^{{commit}}"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert cat_file.returncode == 0
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report


def test_watchdog_pr_reconciliation_open_pr_queues_repair_evidence_without_relaunch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_REPAIR_REQUEST_QUEUE", "1")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()

    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "demo-chain.json"
    _write_chain_state(
        chain_path,
        {"last_state": "awaiting_pr_merge", "pr_number": 43, "pr_state": "open"},
    )

    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2 $3\" == \"pr view 43\" ]]; then\n"
        "  printf '%s\\n' '{\"state\":\"OPEN\"}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    call_log = tmp_path / "calls.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("reconcile_awaiting_pr_merge"),
            _extract_wrapper_function("launch_chain_tick"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"CALL_LOG={str(call_log)!r}",
            """
log() { printf '%s\n' "$*" >> "$CALL_LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
session_health_status() { echo awaiting_pr_merge; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
repair_needs_human_path() { printf '%s/%s.needs-human.json\n' "$REPAIR_DATA_DIR" "$1"; }
tmux() { printf 'tmux %s\n' "$*" >> "$CALL_LOG"; return 0; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8")
    assert "session awaiting PR merge: demo-session detail=PR #43 state=open evidence=queued" in calls
    assert "tmux new-session" not in calls
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tawaiting_pr_merge\tsession waiting on PR merge: PR #43 state=open evidence=queued\t" in report
    queued = list((tmp_path / "repair-queue" / "requests").glob("*.json"))
    assert len(queued) == 1
    payload = json.loads(queued[0].read_text(encoding="utf-8"))
    assert payload["source"] == "watchdog_pr_merge_reconciliation"
    assert payload["target"]["pr_number"] == 43


def test_watchdog_pr_reconciliation_preserves_existing_repair_evidence_when_still_waiting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_REPAIR_REQUEST_QUEUE", "0")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()

    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "demo-chain.json"
    _write_chain_state(
        chain_path,
        {"last_state": "awaiting_pr_merge", "pr_number": 44, "pr_state": "open"},
    )
    needs_human = repair_dir / "demo-session.needs-human.json"
    needs_human.write_text(json.dumps({"summary": "existing blocked repair evidence"}) + "\n", encoding="utf-8")

    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2 $3\" == \"pr view 44\" ]]; then\n"
        "  printf '%s\\n' '{\"state\":\"OPEN\"}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    call_log = tmp_path / "calls.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("reconcile_awaiting_pr_merge"),
            _extract_wrapper_function("launch_chain_tick"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"CALL_LOG={str(call_log)!r}",
            """
log() { printf '%s\n' "$*" >> "$CALL_LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
session_health_status() { echo awaiting_pr_merge; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
repair_needs_human_path() { printf '%s/%s.needs-human.json\n' "$REPAIR_DATA_DIR" "$1"; }
tmux() { printf 'tmux %s\n' "$*" >> "$CALL_LOG"; return 0; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert needs_human.exists()
    assert json.loads(needs_human.read_text(encoding="utf-8"))["summary"] == "existing blocked repair evidence"
    calls = call_log.read_text(encoding="utf-8")
    assert "session awaiting PR merge: demo-session detail=PR #44 state=open evidence=queue_disabled" in calls
    assert "tmux new-session" not in calls
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tawaiting_pr_merge\tsession waiting on PR merge: PR #44 state=open evidence=queue_disabled\t" in report
    assert not list((tmp_path / "repair-queue" / "requests").glob("*.json"))


def test_watchdog_pr_reconciliation_preserves_manual_clean_review_gate(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "manual" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        "merge_policy: auto\n"
        "review_policy:\n"
        "  clean_milestone_pr: manual\n"
        "milestones: []\n",
        encoding="utf-8",
    )
    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "manual.json"
    _write_chain_state(
        chain_path,
        {"last_state": "awaiting_pr_merge", "pr_number": 45, "pr_state": "open"},
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("reconcile_awaiting_pr_merge"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            (
                f"reconcile_awaiting_pr_merge demo-session "
                f"{str(workspace)!r} {str(spec_path)!r}"
            ),
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("review_policy\t")
    assert "clean_milestone_pr=manual" in result.stdout
    assert json.loads(chain_path.read_text(encoding="utf-8"))["pr_state"] == "open"
