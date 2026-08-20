from __future__ import annotations

import json
import secrets
from pathlib import Path

from scripts import run_maintenance_consolidation_agent as launcher


class FakeProcess:
    pid = 424242
    returncode = 0

    def communicate(self, timeout=None):
        assert timeout == 30
        return b"resolved_model: openai-codex/gpt-5.6-luna\n", b""

class StderrResolvedProcess(FakeProcess):
    def communicate(self, timeout=None):
        assert timeout == 30
        return b"launcher started\n", b"model=codex:gpt-5.6-luna \u2192 resolved=openai-codex/gpt-5.6-luna\n"

class FailedProcess(FakeProcess):
    returncode = 7

    def communicate(self, timeout=None):
        return b"resolved_model: openai-codex/gpt-5.6-luna\n", b"child failed"


class MalformedProcess(FakeProcess):
    def communicate(self, timeout=None):
        return b"launcher emitted no identity\n", b""
    def kill(self):
        raise AssertionError("fake process should not be killed")


def _args(root: Path, *, role: str = "[HARD]", route: str = "gpt-5.6-luna") -> list[str]:
    project = root / "project"
    project.mkdir(parents=True, exist_ok=True)
    query = root / "brief.md"
    query.write_text("brief", encoding="utf-8")
    allowance = root / "allowance.json"
    allowance.write_text(json.dumps({"allowance_id": "new", "production_files": ["src/new.py"], "tests": ["tests/new.py"]}), encoding="utf-8")
    return [
        f"--task-id=T1", f"--role={role}", "--label=focused", f"--model-route={route}",
        f"--query-file={query}", f"--project-dir={project}", f"--allowance-file={allowance}",
        f"--evidence-dir={root / 'evidence'}", "--timeout=30",
    ]


def test_invocation_id_generation_and_atomic_receipt_lifecycle(tmp_path, monkeypatch):
    root = tmp_path / f"mrc-wrapper-{secrets.token_hex(6)}"
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    assert launcher.main(_args(root)) == 0
    receipt_files = list((root / "evidence/receipts").glob("mrc-*.json"))
    assert len(receipt_files) == 1
    receipt = json.loads(receipt_files[0].read_text(encoding="utf-8"))
    assert receipt["invocation_id"].startswith("mrc-")
    assert receipt["status"] == "completed"
    assert receipt["exit_status"] == 0
    assert receipt["child_process_identity"]["pid"] == 424242
    assert Path(receipt["stdout_path"]).is_file()
    assert Path(receipt["stderr_path"]).is_file()
    assert Path(receipt["result_path"]).is_file()
    assert (root / "evidence").resolve() not in (root / "project").resolve().parents
def test_stderr_only_resolved_model_closes_completed_receipt(tmp_path, monkeypatch):
    root = tmp_path / f"mrc-wrapper-stderr-{secrets.token_hex(6)}"
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: StderrResolvedProcess())

    assert launcher.main(_args(root)) == 0
    receipt = next((root / "evidence/receipts").glob("mrc-*.json"))
    closed = json.loads(receipt.read_text(encoding="utf-8"))

    assert closed["status"] == "completed"
    assert closed["exit_status"] == 0
    assert closed["resolved_model"] == "openai-codex/gpt-5.6-luna"


def test_routing_table_rejects_wrong_and_unclassified_routes(tmp_path):
    assert launcher.main(_args(tmp_path, role="[XHARD]", route="gpt-5.6-luna")) == 2
    assert launcher.main(_args(tmp_path, role="[MYSTERY]", route="gpt-5.6-luna")) == 2


def test_allowance_overlap_rejected_before_start_receipt(tmp_path):
    root = tmp_path / f"mrc-wrapper-overlap-{secrets.token_hex(6)}"
    args = _args(root)
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "manifest.json").write_text(json.dumps({"allowances": [{"allowance_id": "existing", "active": True, "production_files": ["src"], "tests": [], "fixtures": [], "exports": [], "helpers": [], "generated_surfaces": []}]}), encoding="utf-8")
    allowance = root / "allowance.json"
    allowance.write_text(json.dumps({"allowance_id": "new", "production_files": ["src/file.py"]}), encoding="utf-8")
    assert launcher.main(args) == 2
    assert not list((evidence / "receipts").glob("*.json"))

def test_failed_or_malformed_launcher_closes_failed_receipt(tmp_path, monkeypatch):
    root = tmp_path / f"mrc-wrapper-failure-{secrets.token_hex(6)}"
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: FailedProcess())
    assert launcher.main(_args(root)) == 1
    receipt = next((root / "evidence/receipts").glob("mrc-*.json"))
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "failed"

    malformed_root = tmp_path / f"mrc-wrapper-malformed-{secrets.token_hex(6)}"
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: MalformedProcess())
    assert launcher.main(_args(malformed_root)) == 1
    malformed_receipt = next((malformed_root / "evidence/receipts").glob("mrc-*.json"))
    closed = json.loads(malformed_receipt.read_text(encoding="utf-8"))
    assert closed["status"] == "failed"
    assert closed["exit_status"] == 78


def test_caller_supplied_invocation_id_and_abbreviation_rejected(tmp_path):
    args = _args(tmp_path)
    assert launcher.main(args + ["--invocation-id=caller-id"]) == 2
    assert launcher.main(args + ["--invocation=caller-id"]) == 2


def test_state_writing_root_is_disposable(tmp_path, monkeypatch):
    root = tmp_path / f"mrc-wrapper-disposable-{secrets.token_hex(6)}"
    candidate = root / "candidate"
    live = root / "live-runtime"
    monkeypatch.setenv("MRC_CANDIDATE_ROOT", str(candidate))
    monkeypatch.setenv("MRC_LIVE_RUNTIME_ROOT", str(live))
    assert (root / "evidence").resolve() != (root / "project").resolve()
    assert (root / "evidence").resolve() != candidate.resolve()
    assert (root / "evidence").resolve() != live.resolve()
