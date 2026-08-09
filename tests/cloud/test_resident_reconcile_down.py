from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from subprocess import CompletedProcess

import pytest

from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.cli import _register_cloud_subcommands
from arnold_pipelines.megaplan.cloud.providers.resident_recovery import (
    RECONCILE_ADOPTION_SCHEMA,
    RECONCILE_DOWN_SCHEMA,
    RESIDENT_ONLY_COMMAND,
    parse_resident_reconcile_adoption_receipt,
    parse_resident_reconcile_down_receipt,
    resident_down_command,
    resident_receipt_sha256,
    resident_reconcile_adoption_command,
)
from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.types import CliError


SOURCE = "megaplan-cloud-agent"
SOURCE_ID = "a" * 64
SOURCE_IMAGE = "sha256:" + "b" * 64
RESIDENT_ID = "c" * 64
RESIDENT_IMAGE = "sha256:" + "d" * 64
WORKSPACE = "/opt/megaplan-cloud/workspace"
EPOCH = "unreceipted-listener-20260804"
RUNTIME_PATH = "/workspace/runtime-candidates/arnold-b384"
RUNTIME_COMMIT = "1" * 40
RUNTIME_TREE = "2" * 40
RUNTIME_CONTENT = "3" * 64
RUNTIME_PYTHON = "/root/.pyenv/versions/3.11.11/bin/python3.11"
RUNTIME_PYTHON_SHA = "4" * 64
ENV_SHA = "5" * 64
SEED_SHA = "6" * 64
COMMAND = [
    "/run/megaplan-resident-recovery/launch-seed.json"
    if item == "__RECOVERY_SEED_PATH__"
    else item
    for item in RESIDENT_ONLY_COMMAND
]
COMMAND_SHA = hashlib.sha256(
    json.dumps(COMMAND, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost", container=SOURCE, workspace_dir=WORKSPACE),
    )


def _adoption() -> dict[str, object]:
    return {
        "schema": RECONCILE_ADOPTION_SCHEMA,
        "status": "adopted",
        "outage_epoch": EPOCH,
        "source_container": SOURCE,
        "source_container_id": SOURCE_ID,
        "source_image_id": SOURCE_IMAGE,
        "resident_container": SOURCE + "-resident-only",
        "resident_container_id": RESIDENT_ID,
        "resident_image_id": RESIDENT_IMAGE,
        "resident_command_sha256": COMMAND_SHA,
        "resident_env_sha256": ENV_SHA,
        "recovery_seed_host_dir": (
            f"/var/lib/arnold/megaplan-resident-recovery/{SOURCE_ID}/{EPOCH}/seed"
        ),
        "recovery_seed_sha256": SEED_SHA,
        "runtime_path": RUNTIME_PATH,
        "runtime_commit": RUNTIME_COMMIT,
        "runtime_tree": RUNTIME_TREE,
        "runtime_content_sha256": RUNTIME_CONTENT,
        "runtime_python_path": RUNTIME_PYTHON,
        "runtime_python_sha256": RUNTIME_PYTHON_SHA,
        "workspace": WORKSPACE,
        "workspace_identity": {"st_dev": 10, "st_ino": 20},
        "reconcile_intent_sha256": "7" * 64,
        "started_at": "2026-08-04T00:00:00Z",
        "source_fence_rollback": {"status": "not_applicable"},
    }


def _builder_kwargs() -> dict[str, object]:
    return {
        "source_container": SOURCE,
        "expected_source_container_id": SOURCE_ID,
        "expected_source_image_id": SOURCE_IMAGE,
        "expected_resident_image_id": RESIDENT_IMAGE,
        "expected_resident_container_id": RESIDENT_ID,
        "expected_resident_command_sha256": COMMAND_SHA,
        "expected_resident_env_sha256": ENV_SHA,
        "expected_recovery_seed_host_dir": (
            f"/var/lib/arnold/megaplan-resident-recovery/{SOURCE_ID}/{EPOCH}/seed"
        ),
        "expected_recovery_seed_sha256": SEED_SHA,
        "expected_runtime_path": RUNTIME_PATH,
        "expected_runtime_commit": RUNTIME_COMMIT,
        "expected_runtime_tree": RUNTIME_TREE,
        "expected_runtime_content_sha256": RUNTIME_CONTENT,
        "expected_runtime_python_path": RUNTIME_PYTHON,
        "expected_runtime_python_sha256": RUNTIME_PYTHON_SHA,
        "expected_workspace_device": 10,
        "expected_workspace_inode": 20,
        "workspace": WORKSPACE,
        "outage_epoch": EPOCH,
    }


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _relocate(command: str, custody_root: Path) -> str:
    argv = shlex.split(command)
    cfg = json.loads(base64.b64decode(argv[2], validate=True))
    cfg["custody_host_root"] = str(custody_root)
    argv[2] = base64.b64encode(
        json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    return shlex.join(argv)


def _local_script(script: str) -> str:
    return script.replace(
        'if os.geteuid() != 0:\n    raise RuntimeError("resident_down_requires_root_custody")',
        'if False:\n    raise RuntimeError("resident_down_requires_root_custody")',
    ).replace(".st_uid != 0", ".st_uid != os.geteuid()")


def _prepare_custody(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = tmp_path / "custody" / SOURCE_ID
    epoch_root = root / EPOCH
    epoch_root.mkdir(parents=True)
    root.chmod(0o700)
    epoch_root.chmod(0o700)
    prefix = epoch_root / "transaction"
    intent = {"schema": "arnold.cloud.resident_only_reconcile_intent.v1"}
    adoption = _adoption()
    adoption["reconcile_intent_sha256"] = resident_receipt_sha256(intent)
    _write_receipt(Path(str(prefix) + ".reconcile.intent.json"), intent)
    _write_receipt(Path(str(prefix) + ".reconcile.adopted.json"), adoption)
    return root, adoption


def _fake_docker(tmp_path: Path, *, image: str = RESIDENT_IMAGE) -> tuple[dict[str, str], Path]:
    state_path = tmp_path / "docker.json"
    state_path.write_text(
        json.dumps({"running": True, "present": True, "image": image, "ops": []}),
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        f"""#!{sys.executable}
import json, os, sys
p=os.environ["FAKE_DOCKER_STATE"]
with open(p, encoding="utf-8") as h: s=json.load(h)
a=sys.argv[1:]; s["ops"].append(a)
def save():
    with open(p, "w", encoding="utf-8") as h: json.dump(s,h)
def item():
    return {{"Id":"{RESIDENT_ID}","Image":s["image"],"Name":"/{SOURCE}-resident-only",
      "State":{{"Running":s["running"]}},
      "Mounts":[{{"Type":"bind","Source":"{WORKSPACE}","Destination":"/workspace","RW":True}}]}}
if a[0]=="inspect":
    ident=a[-1]
    if not s["present"] or ident not in ("{RESIDENT_ID}","{SOURCE}-resident-only"):
        save(); print("Error: No such container: "+ident,file=sys.stderr); raise SystemExit(1)
    save(); print(json.dumps([item()])); raise SystemExit(0)
if a[0]=="stop":
    assert a[-1]=="{RESIDENT_ID}"; s["running"]=False; save(); print(a[-1]); raise SystemExit(0)
if a[0]=="rm":
    assert a[-1]=="{RESIDENT_ID}"; s["present"]=False; save(); print(a[-1]); raise SystemExit(0)
save(); raise SystemExit(2)
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
        "FAKE_DOCKER_STATE": str(state_path),
    }
    return env, state_path


def _run_down(tmp_path: Path, root: Path, adoption: dict[str, object], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command, script = resident_down_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=SOURCE_IMAGE,
        expected_resident_image_id=RESIDENT_IMAGE,
        expected_resident_container_id=RESIDENT_ID,
        workspace=WORKSPACE,
        outage_epoch=EPOCH,
        expected_reconcile_adoption_sha256=resident_receipt_sha256(adoption),
    )
    command = _relocate(command, root)
    return subprocess.run(
        [sys.executable, "-", shlex.split(command)[2]],
        input=_local_script(script),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_reconcile_builder_pins_fixed_command_and_seed_custody() -> None:
    command, script = resident_reconcile_adoption_command(**_builder_kwargs())
    cfg = json.loads(base64.b64decode(shlex.split(command)[2], validate=True))
    assert cfg["expected_resident_command"] == COMMAND
    assert cfg["expected_resident_command_sha256"] == COMMAND_SHA
    assert cfg["expected_recovery_seed_host_dir"].endswith(f"/{EPOCH}/seed")
    assert "docker\", \"stop" not in script
    assert "docker\", \"rm" not in script
    assert "resident_listener_singleton_mismatch" in script
    assert "resident_live_probe_mismatch" in script


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_resident_command_sha256", "f" * 64),
        ("expected_recovery_seed_host_dir", "/tmp/untrusted-seed"),
        ("expected_workspace_inode", -1),
    ],
)
def test_reconcile_builder_rejects_changed_operator_pins(
    field: str, value: object
) -> None:
    kwargs = _builder_kwargs()
    kwargs[field] = value
    with pytest.raises(CliError):
        resident_reconcile_adoption_command(**kwargs)


def test_reconcile_receipt_parsers_are_strict() -> None:
    adoption = _adoption()
    assert (
        parse_resident_reconcile_adoption_receipt(json.dumps(adoption))
        == adoption
    )
    down = {
        "schema": RECONCILE_DOWN_SCHEMA,
        "status": "down",
        "outage_epoch": EPOCH,
        "resident_container": SOURCE + "-resident-only",
        "resident_container_id": RESIDENT_ID,
        "removed": True,
        "reconcile_adoption_sha256": resident_receipt_sha256(adoption),
        "source_fence_rollback": {
            "status": "not_applicable",
            "source_container_id": SOURCE_ID,
        },
    }
    assert parse_resident_reconcile_down_receipt(json.dumps(down)) == down
    adoption["unexpected"] = True
    with pytest.raises(CliError):
        parse_resident_reconcile_adoption_receipt(json.dumps(adoption))


def test_reconcile_down_is_idempotent_and_never_restores_source_policy(
    tmp_path: Path,
) -> None:
    root, adoption = _prepare_custody(tmp_path)
    env, state_path = _fake_docker(tmp_path)
    first = _run_down(tmp_path, root, adoption, env)
    assert first.returncode == 0, first.stderr
    receipt = parse_resident_reconcile_down_receipt(first.stdout)
    assert receipt["source_fence_rollback"]["status"] == "not_applicable"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [op[0] for op in state["ops"]].count("stop") == 1
    assert [op[0] for op in state["ops"]].count("rm") == 1
    assert all(op[0] != "update" for op in state["ops"])
    second = _run_down(tmp_path, root, adoption, env)
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [op[0] for op in state["ops"]].count("stop") == 1
    assert [op[0] for op in state["ops"]].count("rm") == 1


def test_reconcile_down_wrong_image_fails_before_stop_or_remove(tmp_path: Path) -> None:
    root, adoption = _prepare_custody(tmp_path)
    env, state_path = _fake_docker(tmp_path, image="sha256:" + "e" * 64)
    result = _run_down(tmp_path, root, adoption, env)
    assert result.returncode != 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert all(op[0] not in {"stop", "rm"} for op in state["ops"])


def test_reconcile_down_completes_stopped_intermediate_without_second_stop(
    tmp_path: Path,
) -> None:
    root, adoption = _prepare_custody(tmp_path)
    env, state_path = _fake_docker(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["running"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = _run_down(tmp_path, root, adoption, env)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [op[0] for op in state["ops"]].count("stop") == 0
    assert [op[0] for op in state["ops"]].count("rm") == 1


def test_reconcile_down_resumes_after_remove_before_terminal_receipt(
    tmp_path: Path,
) -> None:
    root, adoption = _prepare_custody(tmp_path)
    env, state_path = _fake_docker(tmp_path)
    prefix = root / EPOCH / "transaction"
    down_intent = {
        "schema": "arnold.cloud.resident_only_reconcile_down_intent.v1",
        "outage_epoch": EPOCH,
        "resident_container": SOURCE + "-resident-only",
        "resident_container_id": RESIDENT_ID,
        "reconcile_adoption_sha256": resident_receipt_sha256(adoption),
    }
    _write_receipt(Path(str(prefix) + ".reconcile.down.intent.json"), down_intent)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["present"] = False
    state["running"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = _run_down(tmp_path, root, adoption, env)
    assert result.returncode == 0, result.stderr
    parse_resident_reconcile_down_receipt(result.stdout)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert all(op[0] not in {"stop", "rm"} for op in state["ops"])


def test_concurrent_reconcile_down_callers_converge_to_one_mutation(
    tmp_path: Path,
) -> None:
    root, adoption = _prepare_custody(tmp_path)
    env, state_path = _fake_docker(tmp_path)
    command, script = resident_down_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=SOURCE_IMAGE,
        expected_resident_image_id=RESIDENT_IMAGE,
        expected_resident_container_id=RESIDENT_ID,
        workspace=WORKSPACE,
        outage_epoch=EPOCH,
        expected_reconcile_adoption_sha256=resident_receipt_sha256(adoption),
    )
    command = _relocate(command, root)
    argv = [sys.executable, "-", shlex.split(command)[2]]
    first = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    second = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    local = _local_script(script)
    first_out, first_err = first.communicate(local, timeout=10)
    second_out, second_err = second.communicate(local, timeout=10)
    assert first.returncode == 0, first_err
    assert second.returncode == 0, second_err
    assert first_out == second_out
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [op[0] for op in state["ops"]].count("stop") == 1
    assert [op[0] for op in state["ops"]].count("rm") == 1


def test_provider_runs_adoption_then_canonical_down() -> None:
    adoption = _adoption()
    down = {
        "schema": RECONCILE_DOWN_SCHEMA,
        "status": "down",
        "outage_epoch": EPOCH,
        "resident_container": SOURCE + "-resident-only",
        "resident_container_id": RESIDENT_ID,
        "removed": True,
        "reconcile_adoption_sha256": resident_receipt_sha256(adoption),
        "source_fence_rollback": {
            "status": "not_applicable",
            "source_container_id": SOURCE_ID,
        },
    }

    class Provider(SshProvider):
        def __init__(self) -> None:
            super().__init__(_spec())
            self.effects: list[dict[str, object]] = []
            self.payloads = [adoption, down]

        def observe_container(self):
            return {
                "schema": "arnold.cloud.ssh_container_observation.v1",
                "status": "available",
                "lifecycle": "stopped",
                "container_id": SOURCE_ID,
                "image_id": SOURCE_IMAGE,
                "workspace_bind": {
                    "status": "present",
                    "type": "bind",
                    "source": WORKSPACE,
                    "destination": "/workspace",
                    "rw": True,
                },
            }

        def _remote_run(
            self, command, *, capture_output=True, input=None, surface="remote"
        ):
            self.effects.append(
                {"command": command, "input": input, "surface": surface}
            )
            return CompletedProcess(
                [], 0, json.dumps(self.payloads.pop(0)), ""
            )

    provider = Provider()
    payload = provider.resident_reconcile_down(
        **{
            key: value
            for key, value in _builder_kwargs().items()
            if key not in {"source_container", "workspace"}
        }
    )
    assert payload["status"] == "down"
    assert [effect["surface"] for effect in provider.effects] == [
        "resident_only_reconcile_adopt",
        "resident_only_reconcile_down",
    ]
    second_cfg = json.loads(
        base64.b64decode(
            shlex.split(str(provider.effects[1]["command"]))[2],
            validate=True,
        )
    )
    assert second_cfg["expected_reconcile_adoption_sha256"] == resident_receipt_sha256(
        adoption
    )


def test_cli_dispatches_full_reconcile_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = argparse.ArgumentParser()
    _register_cloud_subcommands(parser)
    args = parser.parse_args(
        [
            "resident-reconcile-down",
            "--outage-epoch", EPOCH,
            "--expected-source-container-id", SOURCE_ID,
            "--expected-source-image-id", SOURCE_IMAGE,
            "--expected-resident-image-id", RESIDENT_IMAGE,
            "--expected-resident-container-id", RESIDENT_ID,
            "--expected-resident-command-sha256", COMMAND_SHA,
            "--expected-resident-env-sha256", ENV_SHA,
            "--expected-recovery-seed-host-dir", f"/var/lib/arnold/megaplan-resident-recovery/{SOURCE_ID}/{EPOCH}/seed",
            "--expected-recovery-seed-sha256", SEED_SHA,
            "--expected-runtime-path", RUNTIME_PATH,
            "--expected-runtime-commit", RUNTIME_COMMIT,
            "--expected-runtime-tree", RUNTIME_TREE,
            "--expected-runtime-content-sha256", RUNTIME_CONTENT,
            "--expected-runtime-python-path", RUNTIME_PYTHON,
            "--expected-runtime-python-sha256", RUNTIME_PYTHON_SHA,
            "--expected-workspace-device", "10",
            "--expected-workspace-inode", "20",
        ]
    )

    class Provider:
        def resident_reconcile_down(self, **kwargs):
            assert kwargs["expected_resident_container_id"] == RESIDENT_ID
            assert kwargs["expected_workspace_inode"] == 20
            return {
                "schema": "arnold.cloud.resident_only_reconcile_transaction.v1",
                "status": "down",
            }

    monkeypatch.setattr(cloud_cli, "_load_cloud_spec", lambda root, args: _spec())
    monkeypatch.setattr(
        cloud_cli, "_provider_for_action", lambda spec, args: Provider()
    )
    assert cloud_cli.run_cloud_cli(tmp_path, args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "down"
