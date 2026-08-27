"""Behavioral regressions for the chain wrapper's local OOM redrive."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-chain"


@pytest.fixture
def wrapper_runtime(tmp_path: Path) -> dict[str, Path | dict[str, str]]:
    engine = tmp_path / "engine"
    project = tmp_path / "project"
    cgroup = tmp_path / "cgroup"
    package = engine / "arnold_pipelines/megaplan"
    cloud = package / "cloud"
    for directory in (cloud, project / ".megaplan", cgroup):
        directory.mkdir(parents=True, exist_ok=True)
    for init_file in (
        engine / "arnold_pipelines/__init__.py",
        package / "__init__.py",
        cloud / "__init__.py",
    ):
        init_file.write_text("", encoding="utf-8")

    (cloud / "runtime_provenance.py").write_text(
        "raise SystemExit(0)\n", encoding="utf-8"
    )
    (cloud / "wrapper_acceptance_gate.py").write_text(
        """
class AcceptanceGateDecisionError(Exception):
    code = "fixture_error"

def check_wrapper_acceptance_gate(*args, **kwargs):
    return {"gate_open": True}

def validate_wrapper_acceptance_decision(*args, **kwargs):
    return None
""".lstrip(),
        encoding="utf-8",
    )
    (package / "__main__.py").write_text(
        """
import json
import os
import subprocess
import sys
import time
from pathlib import Path

attempts = Path(os.environ["STUB_ATTEMPTS"])
with attempts.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"one": "--one" in sys.argv}) + "\\n")
attempt = len(attempts.read_text(encoding="utf-8").splitlines())
mode = os.environ.get("STUB_MODE", "success")
if mode == "wait":
    Path(os.environ["STUB_READY"]).write_text("ready", encoding="utf-8")
    while not Path(os.environ["STUB_RELEASE"]).exists():
        time.sleep(0.02)
elif mode == "oom_once" and attempt == 1:
    events = Path(os.environ["ARNOLD_CHAIN_CGROUP_ROOT"]) / "memory.events"
    before = int(events.read_text(encoding="utf-8").split()[1])
    events.write_text(f"oom_kill {before + 1}\\n", encoding="utf-8")
    os._exit(137)
elif mode == "oom_always":
    events = Path(os.environ["ARNOLD_CHAIN_CGROUP_ROOT"]) / "memory.events"
    before = int(events.read_text(encoding="utf-8").split()[1])
    events.write_text(f"oom_kill {before + 1}\\n", encoding="utf-8")
    os._exit(137)
elif mode == "signal_without_oom":
    os._exit(137)
elif mode == "oom_terminated":
    events = Path(os.environ["ARNOLD_CHAIN_CGROUP_ROOT"]) / "memory.events"
    before = int(events.read_text(encoding="utf-8").split()[1])
    events.write_text(f"oom_kill {before + 1}\\n", encoding="utf-8")
    os._exit(143)
elif mode == "oom_once_headroom_drop" and attempt == 1:
    cgroup_dir = Path(os.environ["ARNOLD_CHAIN_CGROUP_ROOT"])
    events = cgroup_dir / "memory.events"
    before = int(events.read_text(encoding="utf-8").split()[1])
    events.write_text(f"oom_kill {before + 1}\\n", encoding="utf-8")
    subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; import time; time.sleep(0.4); open(sys.argv[1], 'w').write(str(int(3.9 * 1024**3)))",
            str(cgroup_dir / "memory.current"),
        ]
    )
    os._exit(137)
""".lstrip(),
        encoding="utf-8",
    )

    spec = project / "chain.yaml"
    spec.write_text("milestones: []\n", encoding="utf-8")
    manifest = tmp_path / "runtime-manifest.json"
    expected_head = "1" * 40
    manifest.write_text(
        json.dumps(
            {
                "runtime_id": "fixture",
                "schema": "1",
                "generation": 1,
                "epic_id": "fixture",
                "state": "active",
                "owner": {},
                "base": {},
                "epic": {
                    "branch": "fixture",
                    "worktree_path": str(engine),
                    "venv_path": str(Path(sys.executable).parent.parent),
                    "runtime_root": str(engine),
                    "expected_head": expected_head,
                    "repair_bin": "",
                    "deps_lockfile": "",
                    "dependency_generation": {
                        "id": "fixture",
                        "frozen_spec_sha256": "2" * 64,
                        "interpreter_path": sys.executable,
                        "venv_digest": "3" * 64,
                        "created": "2026-08-27T00:00:00Z",
                    },
                },
                "indirection": {},
                "policy": {},
                "promotions": [],
                "timestamps": {},
                "gc_policy": {},
                "commands": {},
            }
        ),
        encoding="utf-8",
    )
    (cgroup / "memory.events").write_text("oom_kill 10\n", encoding="utf-8")
    (cgroup / "memory.current").write_text(str(1024**3), encoding="utf-8")
    (cgroup / "memory.max").write_text(str(4 * 1024**3), encoding="utf-8")
    attempts = tmp_path / "attempts.ndjson"
    env = {
        **os.environ,
        "ARNOLD_RUNTIME_MANIFEST": str(manifest),
        "MEGAPLAN_PROJECT_DIR": str(project),
        "ARNOLD_CHAIN_CGROUP_ROOT": str(cgroup),
        "ARNOLD_CHAIN_REDRIVE_BACKOFF_SECONDS": "0",
        "STUB_ATTEMPTS": str(attempts),
    }
    return {
        "project": project,
        "cgroup": cgroup,
        "spec": spec,
        "attempts": attempts,
        "env": env,
    }


def _run(runtime: dict[str, Path | dict[str, str]], *extra: str) -> subprocess.CompletedProcess[str]:
    env = runtime["env"]
    assert isinstance(env, dict)
    return subprocess.run(
        ["bash", str(WRAPPER), str(runtime["spec"]), *extra],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def test_wrapper_redrives_typed_oom(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "oom_once"

    result = _run(wrapper_runtime)

    assert result.returncode == 0, result.stderr
    attempts = Path(wrapper_runtime["attempts"]).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in attempts] == [{"one": False}, {"one": False}]
    assert "cgroup OOM confirmed; waiting" in result.stderr
    assert "cgroup OOM confirmed; redriving (retry 1/2)" in result.stderr


def test_wrapper_one_mode_does_not_redrive_typed_oom(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "oom_once"

    result = _run(wrapper_runtime, "--one")

    assert result.returncode == 137, result.stderr
    attempts = Path(wrapper_runtime["attempts"]).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in attempts] == [{"one": True}]
    assert "cgroup OOM confirmed; redriving" not in result.stderr


def test_wrapper_does_not_redrive_signal_without_oom_or_low_headroom(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "signal_without_oom"
    result = _run(wrapper_runtime)
    assert result.returncode == 137
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 1
    assert "without a new cgroup OOM" in result.stderr

    Path(wrapper_runtime["attempts"]).unlink()
    env["STUB_MODE"] = "oom_always"
    cgroup = Path(wrapper_runtime["cgroup"])
    (cgroup / "memory.current").write_text(str(3.5 * 1024**3), encoding="utf-8")
    result = _run(wrapper_runtime)
    assert result.returncode == 137
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 1
    assert "post-backoff headroom is below 1 GiB" in result.stderr


def test_wrapper_bounds_repeated_oom_to_two_retries(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "oom_always"

    result = _run(wrapper_runtime)

    assert result.returncode == 137
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 3
    assert result.stderr.count("cgroup OOM confirmed; redriving") == 2


def test_wrapper_does_not_redrive_sigterm_even_with_oom_advance(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "oom_terminated"

    result = _run(wrapper_runtime)

    assert result.returncode == 143, result.stderr
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 1
    assert "redriving" not in result.stderr


def test_wrapper_headroom_lost_during_backoff_prevents_retry(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "oom_once_headroom_drop"
    env["ARNOLD_CHAIN_REDRIVE_BACKOFF_SECONDS"] = "1"

    result = _run(wrapper_runtime)

    assert result.returncode == 137, result.stderr
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 1
    assert "post-backoff headroom is below 1 GiB" in result.stderr


def test_wrapper_competing_launch_during_backoff_exits_zero_at_lease(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    env["STUB_MODE"] = "oom_once"
    env["ARNOLD_CHAIN_REDRIVE_BACKOFF_SECONDS"] = "2"

    first = subprocess.Popen(
        ["bash", str(WRAPPER), str(wrapper_runtime["spec"])],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def _attempts_count() -> int:
        path = Path(wrapper_runtime["attempts"])
        return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0

    deadline = time.monotonic() + 5
    while _attempts_count() < 1 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert _attempts_count() == 1

    second = _run(wrapper_runtime)
    assert second.returncode == 0
    assert "another drive owns the chain" in second.stdout
    assert _attempts_count() == 1

    first_stdout, first_stderr = first.communicate(timeout=10)
    assert first.returncode == 0, (first_stdout, first_stderr)
    assert _attempts_count() == 2


def test_wrapper_lease_prevents_overlap_and_stale_pid_does_not_wedge(
    wrapper_runtime: dict[str, Path | dict[str, str]],
) -> None:
    env = wrapper_runtime["env"]
    assert isinstance(env, dict)
    ready = Path(wrapper_runtime["project"]) / "ready"
    release = Path(wrapper_runtime["project"]) / "release"
    env.update({"STUB_MODE": "wait", "STUB_READY": str(ready), "STUB_RELEASE": str(release)})
    first = subprocess.Popen(
        ["bash", str(WRAPPER), str(wrapper_runtime["spec"])],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 5
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ready.exists()

    second = _run(wrapper_runtime)
    assert second.returncode == 0
    assert "another drive owns the chain" in second.stdout
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 1

    release.write_text("release", encoding="utf-8")
    first_stdout, first_stderr = first.communicate(timeout=5)
    assert first.returncode == 0, (first_stdout, first_stderr)

    # The completed wrapper leaves diagnostic PID text, but no kernel lock.
    # A successor must acquire and overwrite it rather than wedging.
    env["STUB_MODE"] = "success"
    third = _run(wrapper_runtime)
    assert third.returncode == 0, third.stderr
    assert len(Path(wrapper_runtime["attempts"]).read_text().splitlines()) == 2
