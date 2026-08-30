"""Adversarial and production-shaped gates for Batch 2 iteration 11.

These tests deliberately exercise the producer boundaries rather than merely
checking fields copied into a terminal result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from arnold_pipelines.megaplan.cloud import worker_dispatch as wd
from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    WorkerAdmissionReceipt,
    _default_native_liveness,
    require_production_worker_dispatch_runtime,
)
from arnold_pipelines.megaplan.workers._impl import capture_process_identity

from tests.cloud.dispatch_test_helpers import request


def _receipt(tmp_path: Path, *, logical: str = "logical") -> WorkerAdmissionReceipt:
    result = require_production_worker_dispatch_runtime(
        request(tmp_path, logical_dispatch_id=logical, projection_key=logical)
    )
    assert isinstance(result, WorkerAdmissionReceipt)
    return result


def _process_receipt(receipt: WorkerAdmissionReceipt, identity: dict) -> WorkerAdmissionReceipt:
    return replace(
        receipt,
        production_intent=True,
        route_liveness_evidence={
            "executable": {
                "executable_path": identity["process_executable"],
                "executable_sha256": identity["process_executable_sha256"],
            }
        },
    )


def test_process_attestation_is_producer_bound_before_first_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _receipt(tmp_path)
    other = _receipt(tmp_path, logical="other")
    monkeypatch.setenv(
        "ARNOLD_WORKER_EXECUTION_CONTEXT",
        json.dumps(first.execution_context.to_dict(), sort_keys=True),
    )
    process = subprocess.Popen(["/bin/sleep", "2"])
    try:
        identity = capture_process_identity(process, ("forged", "argv"))
    finally:
        process.terminate()
        process.wait(timeout=5)

    first = _process_receipt(first, identity)
    other = replace(other, production_intent=True, route_liveness_evidence=first.route_liveness_evidence)
    copied = dict(identity)
    copied["process_attestation_scope"] = {
        "admission_receipt_id": other.admission_receipt_id,
        "logical_dispatch_id": other.logical_dispatch_id,
        "semantic_dispatch_fingerprint": other.semantic_dispatch_fingerprint,
    }
    with pytest.raises(ValueError, match="another receipt"):
        wd._validate_worker_identity_for_receipt(copied, other)
    assert wd._validate_worker_identity_for_receipt(dict(identity), first)["pid"] == identity["pid"]
    with pytest.raises(ValueError, match="already consumed"):
        wd._validate_worker_identity_for_receipt(dict(identity), first)


def test_unbound_process_snapshot_cannot_be_adopted_by_production_receipt(
    tmp_path: Path,
) -> None:
    receipt = _receipt(tmp_path)
    process = subprocess.Popen(["/bin/sleep", "2"])
    try:
        identity = capture_process_identity(process, ("/bin/sleep", "2"))
    finally:
        process.terminate()
        process.wait(timeout=5)
    receipt = _process_receipt(receipt, identity)
    with pytest.raises(ValueError, match="another receipt"):
        wd._validate_worker_identity_for_receipt(identity, receipt)


def test_omp_argv_is_exact_and_rejects_eval_or_path_injection(tmp_path: Path) -> None:
    launcher = tmp_path / "bun"
    script = tmp_path / "cli.js"
    launcher.write_text("bun", encoding="utf-8")
    script.write_text("cli", encoding="utf-8")
    allowed = [
        str(launcher), str(script), "--mode", "rpc",
        "--provider", "deepseek", "--model", "deepseek-v4-pro",
        "--no-session", "--no-skills", "--no-rules", "--no-title",
    ]
    wd._validate_canonical_omp_argv(allowed, launcher=str(launcher), script=str(script))
    for forged in (
        allowed + ["-e", "require('evil')"],
        allowed + ["--cwd", "/tmp/evil"],
        [str(launcher), str(script), "--mode", "rpc", "/tmp/evil"],
        ["/usr/bin/env", str(script), "--mode", "rpc"],
    ):
        with pytest.raises(ValueError):
            wd._validate_canonical_omp_argv(forged, launcher=str(launcher), script=str(script))


def test_codex_identity_binds_node_and_trusted_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node = Path(__import__("shutil").which("node") or "")
    script = Path(__import__("shutil").which("codex") or "").resolve(strict=True)
    if not node.is_file() or not script.is_file():
        pytest.skip("Codex Node runtime is not installed")
    receipt = _receipt(tmp_path)
    monkeypatch.setenv(
        "ARNOLD_WORKER_EXECUTION_CONTEXT",
        json.dumps(receipt.execution_context.to_dict(), sort_keys=True),
    )
    process = subprocess.Popen(
        [str(node.resolve()), str(script), "exec", "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        identity = capture_process_identity(process, tuple(process.args))
    finally:
        process.terminate()
        process.wait(timeout=5)
    binding = {
        "executable_path": str(node.resolve()),
        "executable_sha256": hashlib.sha256(node.resolve().read_bytes()).hexdigest(),
        "script_path": str(script),
        "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    }
    receipt = replace(receipt, production_intent=True, route_liveness_evidence={"executable": binding})
    assert wd._validate_worker_identity_for_receipt(identity, receipt)["process_executable"] == binding["executable_path"]


def test_claude_catalog_probe_is_offline_and_local(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []

    def network_probe(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Claude admission must not call an API/catalog probe")

    monkeypatch.setattr("shutil.which", lambda binary: "/bin/echo" if binary == "claude" else network_probe(binary))
    proof = _default_native_liveness("claude", "claude-sonnet-4-6", runner=network_probe)
    assert proof["offline"] is True
    assert proof["probe"] == "offline-local-catalog"
    assert calls == []


def test_claude_worker_returns_the_verified_child_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.workers import _impl
    from arnold_pipelines.megaplan.workers.claude import run_claude_step

    verified = {
        "host": "host",
        "pid": 123,
        "boot_id": "boot",
        "process_start_identity": "birth",
        "verified": True,
        "observed_before_exit": True,
        "process_executable": "/bin/echo",
        "process_executable_sha256": "a" * 64,
        "process_command_sha256": "b" * 64,
        "process_argv": ["/bin/echo", "claude"],
        "process_attestation_token": "token",
    }
    monkeypatch.setattr("shutil.which", lambda binary: "/bin/echo")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.claude._render_prompt",
        lambda *args, **kwargs: "prompt",
    )
    monkeypatch.setattr(
        _impl,
        "run_command",
        lambda *args, **kwargs: _impl.CommandResult(
            command=list(args[0]), cwd=tmp_path, returncode=0,
            stdout='{"ok":true}', stderr="", duration_ms=1,
            worker_identity=verified,
        ),
    )
    result = run_claude_step(
        "plan", {}, tmp_path, root=tmp_path, model="claude-sonnet-4-6"
    )
    assert result.worker_identity == verified
    assert result.worker_identity["verified"] is True


def test_managed_completed_identity_rejects_caller_self_hashed_dead_pid(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path)
    receipt = replace(receipt, production_intent=True)
    manifest_path = tmp_path / receipt.logical_dispatch_id / "manifest.json"
    manifest_path.parent.mkdir()
    manifest = {
        "schema_version": "arnold-managed-agent-run-v2",
        "custodian": "arnold.megaplan.managed_agent",
        "run_id": receipt.logical_dispatch_id,
        "status": "completed",
        "worker_pid": 99999999,
        "worker_host": "test-host",
        "worker_boot_id": "boot-1",
        "worker_start_ticks": "start-1",
        "worker_identity_verified": True,
        "worker_cmdline_sha256": "a" * 64,
    }
    raw = json.dumps(manifest, sort_keys=True).encode()
    manifest_path.write_bytes(raw)
    identity = {
        "host": "test-host", "pid": 99999999, "boot_id": "boot-1",
        "process_start_identity": "start-1", "verified": True,
        "attestation_source": "managed_agent_manifest",
        "manifest_path": str(manifest_path),
        "managed_run_id": receipt.logical_dispatch_id,
        "managed_manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }
    with pytest.raises(ValueError, match="producer attestation"):
        wd._validate_worker_identity_for_receipt(identity, receipt)
