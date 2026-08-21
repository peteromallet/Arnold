from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path

from scripts import run_maintenance_consolidation_agent as launcher


class FakeProcess:
    pid = 424242
    returncode = 0

    def communicate(self, timeout=None):
        assert timeout == 30
        return b"resolved_model: openai-codex/gpt-5.6-luna\n", b""

class SolProcess(FakeProcess):
    def communicate(self, timeout=None):
        assert timeout == 30
        return b"resolved_model: openai-codex/gpt-5.6-sol\n", b""


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


def _args(root: Path, *, role: str = "[HARD]", route: str = "ox-alpha") -> list[str]:
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
def _close_args(project: Path, allowance_id: str, evidence: Path | None = None) -> list[str]:
    args = [f"--deactivate-allowance={allowance_id}", f"--project-dir={project}"]
    if evidence is not None:
        args.append(f"--evidence-dir={evidence}")
    return args


def _write_manifest(path: Path, value: dict) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return raw


def test_close_active_allowance_preserves_manifest_content(tmp_path, capsys):
    project = tmp_path / "project"
    evidence = tmp_path / "evidence"
    registry_path = evidence / "manifest.json"
    target = {
        "allowance_id": "active",
        "task_id": "T0.3",
        "production_files": ["scripts/wrapper.py"],
        "tests": ["tests/test_wrapper.py"],
        "generated_surfaces": ["docs/evidence.json"],
        "allowance_digest": "a" * 64,
        "lifecycle_state": "active",
        "active": True,
    }
    other = {"allowance_id": "other", "active": True, "production_files": ["other.py"]}
    manifest = {"schema": "keep-me", "metadata": {"owner": "mrc"}, "allowances": [target, other], "tail": ["unchanged"]}
    _write_manifest(registry_path, manifest)

    assert launcher.main(_close_args(project, "active", evidence)) == 0
    output = json.loads(capsys.readouterr().out)
    updated = json.loads(registry_path.read_text(encoding="utf-8"))
    closed = updated["allowances"][0]
    preclose_digest = launcher.canonical_allowance(target)[1]
    _, closed_digest = launcher.canonical_allowance(closed)
    assert closed["allowance_digest"] == closed_digest
    assert closed["allowance_digest"] != preclose_digest

    assert output == {"allowance_id": "active", "manifest": str(registry_path.resolve()), "status": "closed"}
    assert closed["active"] is False
    assert closed["lifecycle_state"] == "closed"
    assert closed["closed_at_utc"].endswith("Z")
    assert datetime.fromisoformat(closed["closed_at_utc"].replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert {key: closed[key] for key in target if key not in {"active", "lifecycle_state", "allowance_digest"}} == {
        key: target[key] for key in target if key not in {"active", "lifecycle_state", "allowance_digest"}
    }
    assert updated["allowances"][1] == other
    assert {key: updated[key] for key in manifest if key != "allowances"} == {
        key: manifest[key] for key in manifest if key != "allowances"
    }




def test_close_active_allowance_preserves_noncanonical_manifest_bytes(tmp_path, capsys):
    project = tmp_path / "project"
    evidence = tmp_path / "evidence"
    registry_path = evidence / "manifest.json"
    before = (
        b'{\r\n'
        b'  "schema"  :  "keep\\u00e9",\n'
        b'  "allowances"\t:\r\n'
        b'[\n'
        b'\t {\r\n'
        b'\t\t"allowance_id" : "target",\r\n'
        b'\t\t"production_files" : ["src/target.py"],\r\n'
        b'\t\t"tests" : ["tests/test_target.py"],\r\n'
        b'\t\t"fixtures" : [],\r\n'
        b'\t\t"exports" : [],\r\n'
        b'\t\t"helpers" : [],\r\n'
        b'\t\t"generated_surfaces" : ["docs/target.json"],\r\n'
        b'\t\t"allowance_digest" : "' + b"a" * 64 + b'",\r\n'
        b'\t\t"active" : true,\n'
        b'\t\t"lifecycle_state" : "active",\r\n'
        b'\t\t"closed_at_utc" : "old",\r\n'
        b'\t\t"note" : "target"\r\n'
        b'\t },\r\n'
        b'\t{\r\n'
        b'\t\t"allowance_id" : "other",\r\n'
        b'\t\t"active" : false,\r\n'
        b'\t\t"note" : "\\u00e9",\r\n'
        b'\t\t"note" : "duplicate"\r\n'
        b'\t}\n'
        b']\r\n'
        b'}\r\n \t\r\n'
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_bytes(before)

    assert launcher.main(_close_args(project, "target", evidence)) == 0
    json.loads(capsys.readouterr().out)
    after = registry_path.read_bytes()
    closed_at_utc = json.loads(after.decode("utf-8"))["allowances"][0]["closed_at_utc"]
    assert datetime.fromisoformat(closed_at_utc.replace("Z", "+00:00")).utcoffset().total_seconds() == 0

    expected = before
    closed = json.loads(after.decode("utf-8"))["allowances"][0]
    _, expected_digest = launcher.canonical_allowance(closed)
    preclose_digest = launcher.canonical_allowance(json.loads(before.decode("utf-8"))["allowances"][0])[1]
    assert closed["allowance_digest"] == expected_digest
    assert closed["allowance_digest"] != preclose_digest
    for old, new in (
        (b'\t\t"active" : true', b'\t\t"active" : false'),
        (b'\t\t"lifecycle_state" : "active"', b'\t\t"lifecycle_state" : "closed"'),
        (
            b'\t\t"closed_at_utc" : "old"',
            f'\t\t"closed_at_utc" : "{closed_at_utc}"'.encode("utf-8"),
        ),
        (
            b'\t\t"allowance_digest" : "' + b"a" * 64 + b'"',
            f'\t\t"allowance_digest" : "{closed["allowance_digest"]}"'.encode("utf-8"),
        ),
    ):
        assert expected.count(old) == 1
        expected = expected.replace(old, new, 1)
    assert after == expected
    assert b'"schema"  :  "keep\\u00e9"' in after
    assert after.count(b'\t\t"note" : "\\u00e9"') == 1
    assert after.count(b'\t\t"note" : "duplicate"') == 1
    assert b'  "schema"  :  "keep\\u00e9",\n' in after
    assert b"\r\n" in after
    assert after.endswith(b']\r\n}\r\n \t\r\n')
def test_close_registry_uses_evidence_first_then_project_fallback(tmp_path):
    project = tmp_path / "project"
    fallback = project / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"
    evidence = tmp_path / "evidence"
    evidence_registry = evidence / "manifest.json"
    _write_manifest(fallback, {"allowances": [{"allowance_id": "target", "active": True}]})
    _write_manifest(evidence_registry, {"allowances": [{"allowance_id": "target", "active": True}]})

    assert launcher.main(_close_args(project, "target", evidence)) == 0
    assert json.loads(evidence_registry.read_text(encoding="utf-8"))["allowances"][0]["active"] is False
    assert json.loads(fallback.read_text(encoding="utf-8"))["allowances"][0]["active"] is True

    evidence_registry.unlink()
    assert launcher.main(_close_args(project, "target", evidence)) == 0
    assert json.loads(fallback.read_text(encoding="utf-8"))["allowances"][0]["active"] is False


def test_close_absent_allowance_leaves_manifest_byte_identical(tmp_path, capsys):
    project = tmp_path / "project"
    registry_path = project / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"
    before = _write_manifest(registry_path, {"allowances": [{"allowance_id": "other", "active": True}], "extra": 7})

    assert launcher.main(_close_args(project, "missing")) == 2
    assert "ALLOWANCE_NOT_FOUND:missing" in capsys.readouterr().err
    assert registry_path.read_bytes() == before


def test_close_already_closed_is_deterministic_and_preserves_timestamp(tmp_path, capsys):
    project = tmp_path / "project"
    registry_path = project / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"
    _write_manifest(registry_path, {"allowances": [{"allowance_id": "target", "active": True}]})

    assert launcher.main(_close_args(project, "target")) == 0
    first = registry_path.read_bytes()
    timestamp = json.loads(first.decode())["allowances"][0]["closed_at_utc"]
    assert launcher.main(_close_args(project, "target")) == 2
    assert "ALLOWANCE_ALREADY_CLOSED:target" in capsys.readouterr().err
    assert registry_path.read_bytes() == first
    assert json.loads(first.decode())["allowances"][0]["closed_at_utc"] == timestamp


def test_close_malformed_selected_manifest_does_not_fall_back_or_replace(tmp_path, capsys):
    project = tmp_path / "project"
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    selected = evidence / "manifest.json"
    fallback = project / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"
    selected.write_text("{not-json", encoding="utf-8")
    fallback_before = _write_manifest(fallback, {"allowances": [{"allowance_id": "target", "active": True}]})

    assert launcher.main(_close_args(project, "target", evidence)) == 2
    assert "MALFORMED_ALLOWANCE_REGISTRY" in capsys.readouterr().err
    assert selected.read_text(encoding="utf-8") == "{not-json"
    assert fallback.read_bytes() == fallback_before


def test_inactive_overlap_allows_dispatch(tmp_path, monkeypatch):
    root = tmp_path / f"mrc-wrapper-inactive-{secrets.token_hex(6)}"
    args = _args(root)
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "manifest.json").write_text(
        json.dumps({"allowances": [{"allowance_id": "closed", "active": False, "production_files": ["src"], "tests": []}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    assert launcher.main(args) == 0
    assert list((evidence / "receipts").glob("*.json"))


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

def test_sol_review_dispatch_builds_sol_command_and_rejects_wrong_route(tmp_path, monkeypatch, capsys):
    commands = []

    def fake_popen(command, **kwargs):
        commands.append(command)
        return SolProcess()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    root = tmp_path / "sol-review"
    assert launcher.main(_args(root, role="[SOL-REVIEW]", route="ox-alpha")) == 0

    command = commands[0]
    assert command[1] == str(
        launcher.INTEGRATION_WORKTREE
        / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py"
    )
    assert "--model=openrouter/stealth/ox-alpha" in command

    capsys.readouterr()
    wrong_root = tmp_path / "sol-review-wrong-route"
    assert launcher.main(_args(wrong_root, role="[SOL-REVIEW]", route="gpt-5.6-sol")) == 2
    assert "WRONG_MODEL_ROUTE" in capsys.readouterr().err
    assert len(commands) == 1


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
