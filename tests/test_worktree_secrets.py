from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import megaplan.worktrees.secrets as secrets_module
from megaplan.worktrees import PatchCaptureError, SecretScanError, capture_patch_bundle, run_gitleaks_policy


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")


def test_gitleaks_policy_requires_explicit_mode(tmp_path: Path) -> None:
    with pytest.raises(SecretScanError) as excinfo:
        run_gitleaks_policy(tmp_path, mode="passed")
    assert excinfo.value.code == "invalid_secret_scan_mode"


def test_gitleaks_policy_local_only_explicitly_skips(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _name: None)

    result = run_gitleaks_policy(tmp_path, mode="local_only")

    assert result == {
        "policy": "gitleaks",
        "mode": "local_only",
        "status": "skipped",
        "available": False,
        "exit_class": "skipped",
        "explicit_local_only_opt_in": True,
        "redacted_reason": "local_only mode explicitly skips gitleaks",
        "findings_count": None,
    }


def test_gitleaks_policy_pr_pushed_fails_closed_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _name: None)

    result = run_gitleaks_policy(tmp_path, mode="pr_pushed")

    assert result["status"] == "failed"
    assert result["available"] is False
    assert result["exit_class"] == "missing"
    assert result["explicit_local_only_opt_in"] is False
    assert result["redacted_reason"] == "gitleaks unavailable for pr_pushed scan"


def test_gitleaks_policy_pr_pushed_passes_on_clean_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _name: "/bin/gitleaks")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        report_path = Path(cmd[cmd.index("--report-path") + 1])
        report_path.write_text("[]", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(secrets_module.subprocess, "run", fake_run)

    result = run_gitleaks_policy(tmp_path, mode="pr_pushed")

    assert result["status"] == "passed"
    assert result["available"] is True
    assert result["exit_class"] == "clean"
    assert result["redacted_reason"] is None
    assert result["findings_count"] == 0


def test_gitleaks_policy_pr_pushed_fails_on_findings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _name: "/bin/gitleaks")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        report_path = Path(cmd[cmd.index("--report-path") + 1])
        report_path.write_text('[{"RuleID":"generic-api-key","Secret":"REDACTED"}]', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 1, stdout="raw secret output", stderr="raw secret stderr")

    monkeypatch.setattr(secrets_module.subprocess, "run", fake_run)

    result = run_gitleaks_policy(tmp_path, mode="pr_pushed")

    assert result["status"] == "failed"
    assert result["exit_class"] == "findings"
    assert result["findings_count"] == 1
    assert result["redacted_reason"] == "gitleaks reported potential secrets"
    assert "raw secret" not in json.dumps(result)


def test_gitleaks_policy_pr_pushed_fails_on_scanner_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _name: "/bin/gitleaks")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 2, stdout="raw output", stderr="raw stderr")

    monkeypatch.setattr(secrets_module.subprocess, "run", fake_run)

    result = run_gitleaks_policy(tmp_path, mode="pr_pushed")

    assert result["status"] == "failed"
    assert result["exit_class"] == "error"
    assert result["redacted_reason"] == "gitleaks exited with an error before producing a trusted result"
    assert "raw " not in json.dumps(result)


def test_capture_records_failed_pr_pushed_scan_metadata_before_raising(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(secrets_module.shutil, "which", lambda _name: None)
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "file.txt").write_text("base\nchanged\n", encoding="utf-8")

    with pytest.raises(PatchCaptureError) as excinfo:
        capture_patch_bundle(tmp_path / "coordinator", "run-9", "T9", repo, secret_scan_mode="pr_pushed")

    assert excinfo.value.code == "secret_scan_failed"
    manifest_path = tmp_path / "coordinator" / ".megaplan" / "worktrees" / "patches" / "run-9" / "task-T9" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["secret_scan"]["mode"] == "pr_pushed"
    assert manifest["secret_scan"]["status"] == "failed"
    assert manifest["secret_scan"]["explicit_local_only_opt_in"] is False
    assert manifest["secret_scan"]["available"] is False
    assert manifest["secret_scan"]["exit_class"] == "missing"
    assert manifest["secret_scan"]["redacted_reason"] == "gitleaks unavailable for pr_pushed scan"
