"""P4 config cleanup: the editable-install machinery is deleted.

The cloud launch path is manifest-bound: ``_refresh_then_chain_start_command``
activates the per-epic runtime from its manifest (no editable-install refresh,
no env-selector fallback), and an unbound launch runs the plain chain start
with the launch pin + fixed /workspace/arnold engine fallback.  The legacy
refresh / source-sync helpers these tests used to cover no longer exist.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.cloud.cli import (
    _refresh_then_chain_start_command,
    _chain_start_command,
)
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
)


def _cloud_spec(**megaplan_overrides) -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/project.git"),
        agents={},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(**megaplan_overrides),
        resources=ResourcesSpec(),
        secrets=[],
    )


def _runtime_binding(**overrides) -> dict:
    binding = {
        "manifest_path": "/workspace/.megaplan/demo-abc123.json",
        "runtime_src": "/workspace/runtime-candidates/demo-abc123",
        "runtime_revision": "a" * 40,
        "runtime_id": "demo-abc123-20260810",
        "slug": "demo-abc123",
        "created": True,
        "policy_path": None,
    }
    binding.update(overrides)
    return binding


def test_chain_start_uses_manifest_activate_when_bound() -> None:
    command = _refresh_then_chain_start_command(
        "/workspace/project/.megaplan/initiatives/example/chain.yaml",
        spec=_cloud_spec(),
        project_dir="/workspace/project",
        log_relative=".megaplan/cloud-chain.log",
        runtime_binding=_runtime_binding(),
    )

    # Manifest-bound runtime: the runtime IS the code.  The launch env is
    # bound to the created runtime via ARNOLD_RUNTIME_MANIFEST only — no
    # editable-install refresh, no SRC selector transport (G4).
    assert "activating manifest-bound runtime" in command
    assert 'export ARNOLD_RUNTIME_MANIFEST="$MANIFEST"' in command
    assert "MEGAPLAN_LAUNCH_RUNTIME_SRC" not in command
    assert "MEGAPLAN_RUNTIME_SRC" not in command
    assert "megaplan-refresh" not in command
    assert "pip install -e" not in command
    assert "git fetch" not in command
    assert "git pull" not in command
    assert "python -P -m arnold_pipelines.megaplan chain start" in command


def test_chain_start_without_binding_never_refreshes_remote_git() -> None:
    command = _refresh_then_chain_start_command(
        "/workspace/project/.megaplan/initiatives/example/chain.yaml",
        spec=_cloud_spec(),
        project_dir="/workspace/project",
        log_relative=".megaplan/cloud-chain.log",
    )

    # Unbound (pre-binding marker write / legacy marker) launch: the
    # editable-install refresh is gone; the manifest pin + fixed engine
    # fallback carry the runtime identity.
    assert "megaplan-refresh" not in command
    assert "pip install -e" not in command
    assert "git push" not in command
    assert "git fetch" not in command
    assert "git pull" not in command
    assert 'PINNED_RUNTIME_MANIFEST="${ARNOLD_RUNTIME_MANIFEST:-}"' in command
    assert (
        'ENGINE_DIR="$(env -u PYTHONHOME PYTHONSAFEPATH=1 python -P -c '
        '\'import json,sys; print(json.load(open(sys.argv[1])).get("epic",{}).get("runtime_root",""))\' '
        '"$PINNED_RUNTIME_MANIFEST" 2>/dev/null || true)"'
    ) in command
    assert 'if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR=/workspace/arnold; fi;' in command
    assert 'PYTHONPATH="$ENGINE_DIR"' in command
    assert "MEGAPLAN_LAUNCH_RUNTIME_SRC" not in command
    assert "MEGAPLAN_RUNTIME_SRC" not in command
    assert "python -P -m arnold_pipelines.megaplan chain start" in command


def test_chain_start_command_keeps_launch_pin_before_hot_env() -> None:
    command = _chain_start_command(
        "/workspace/project/.megaplan/initiatives/example/chain.yaml",
        project_dir="/workspace/project",
        engine_dir="/workspace/arnold",
    )

    pin_at = command.index(
        'PINNED_RUNTIME_MANIFEST="${ARNOLD_RUNTIME_MANIFEST:-}"'
    )
    hot_env_at = command.index(
        "if [ -f /workspace/.cloud-hot-env ]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;"
    )
    # The launch transport pin (the manifest path) is snapshotted BEFORE the
    # credentials-only hot env load; hot env can never override the runtime
    # identity.
    assert pin_at < hot_env_at
    assert (
        'if [ -n "$PINNED_RUNTIME_MANIFEST" ]; then '
        'export ARNOLD_RUNTIME_MANIFEST="$PINNED_RUNTIME_MANIFEST"; fi;'
    ) in command
