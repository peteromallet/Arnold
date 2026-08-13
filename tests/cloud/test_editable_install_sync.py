"""P4 config cleanup: the editable-install machinery is deleted.

The cloud launch path is manifest-bound: ``_refresh_then_chain_start_command``
activates the per-epic runtime from its manifest (no editable-install refresh,
no env-selector fallback), and an unbound launch runs the plain chain start
with the manifest pin mandatory and no fixed-path engine fallback (T-0011).
The auto/bootstrap entrypoints follow the same contract (T-0021): the engine
dir derives ONLY from the per-session runtime manifest pin and missing or
invalid pins fail closed (exit 24) before any marker write, state load, or
subprocess.  The legacy refresh / source-sync helpers these tests used to
cover no longer exist.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.cli import (
    _refresh_then_chain_start_command,
    _chain_start_command,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import COMPATIBILITY_ONLY_KEY
from arnold_pipelines.megaplan.cloud.spec import (
    AutoSpec,
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
    # T-0301: the launch runs under the generation interpreter
    # (manifest-bound, worktree-first PYTHONPATH) — never ambient python.
    assert '"$GEN_INTERPRETER" -P -m arnold_pipelines.megaplan chain start' in command
    assert "python -P -m arnold_pipelines.megaplan chain start" not in command


def test_chain_start_without_binding_never_refreshes_remote_git() -> None:
    command = _refresh_then_chain_start_command(
        "/workspace/project/.megaplan/initiatives/example/chain.yaml",
        spec=_cloud_spec(),
        project_dir="/workspace/project",
        log_relative=".megaplan/cloud-chain.log",
    )

    # Unbound (pre-binding marker write / legacy marker) launch: the
    # editable-install refresh is gone; the manifest pin is mandatory and
    # fails closed — there is no fixed-path engine fallback (T-0011).
    assert "megaplan-refresh" not in command
    assert "pip install -e" not in command
    assert "git push" not in command
    assert "git fetch" not in command
    assert "git pull" not in command
    assert 'PINNED_RUNTIME_MANIFEST="${ARNOLD_RUNTIME_MANIFEST:-}"' in command
    # G6 round-2 finding 2: the ENGINE_DIR read is CANONICAL-schema gated —
    # the emitted reader requires schema "1" plus the manifest's required key
    # sets, so a present-but-schema-invalid manifest fails closed.
    assert (
        'ENGINE_DIR="$(env -u PYTHONHOME PYTHONSAFEPATH=1 python -P -c '
        "'import json,sys; d=json.load(open(sys.argv[1]));"
    ) in command
    assert 'd.get("schema")=="1"' in command
    assert "all(k in d for k in R)" in command
    assert "all(k in e for k in E)" in command
    assert 'if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR=' not in command
    assert "isolated_chain_runtime_binding_drift: missing runtime manifest pin" in command
    assert "isolated_chain_runtime_binding_drift: manifest lacks runtime_root" in command
    assert "isolated_chain_runtime_binding_drift: manifest lacks runtime identity" in command
    # T-0301: the generation-interpreter gate (proof completeness +
    # executable check) runs before the provenance check, and the launch
    # executes under the generation interpreter — no ambient python, no
    # editable-install fallback.
    assert "manifest lacks dependency generation interpreter" in command
    assert "dependency generation interpreter not executable" in command
    assert 'PYTHONPATH="$ENGINE_DIR"' in command
    assert "MEGAPLAN_LAUNCH_RUNTIME_SRC" not in command
    assert "MEGAPLAN_RUNTIME_SRC" not in command
    assert '"$GEN_INTERPRETER" -P -m arnold_pipelines.megaplan chain start' in command
    assert "python -P -m arnold_pipelines.megaplan chain start" not in command


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


# ── T-0021: auto/bootstrap entrypoints are manifest-bound ────────────────────


def _auto_cloud_spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(
            url="https://github.com/example/project.git", workspace="/workspace/app"
        ),
        agents={},
        codex=CodexSpec(),
        mode="auto",
        megaplan=MegaplanSpec(src_path="/workspace/arnold"),
        resources=ResourcesSpec(),
        secrets=[],
        auto=AutoSpec(plan_name="demo-plan", idea_file="/workspace/app/idea.txt"),
    )


def _runtime_shim(tmp_path: Path, *, provenance_exit: int = 0) -> Path:
    shim = tmp_path / "bin" / "python"
    shim.parent.mkdir(parents=True)
    shim.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *arnold_pipelines.megaplan.cloud.runtime_provenance*)\n"
        f"    exit {provenance_exit} ;;\n"
        "esac\n"
        "exec \"$REAL_PYTHON\" \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def _canonical_manifest_payload(
    runtime_root: str,
    *,
    expected_head: str,
    interpreter_path: str = "/opt/arnold/runtime-venvs/generation/bin/python",
) -> dict[str, object]:
    """Canonical schema-"1" runtime-manifest payload (G6 round-9 finding 1).

    Must satisfy the shell pin-gate's canonical required key sets
    (``TOP_LEVEL_REQUIRED`` / ``EPIC_REQUIRED``), which the schema-gated
    pinned-manifest reads now enforce.  A schema-less ``{"epic": {...}}``
    shape is canonically INVALID and must never be used as a trusted fixture.

    T-0301: carries a complete ``dependency_generation`` proof whose
    ``interpreter_path`` the launch gate requires (every production launch
    runs under the generation interpreter; a manifest without the proof
    fails closed with exit 24).
    """
    return {
        "runtime_id": "auto-pin-runtime-1",
        "schema": "1",
        "generation": 1,
        "epic_id": "auto-pin-epic",
        "state": "active",
        "owner": "test",
        "base": {
            "ref": "refs/heads/main",
            "commit": expected_head or "0" * 40,
            "editable_install_path": f"{runtime_root}/base",
            "venv_path": f"{runtime_root}/base/venv",
        },
        "epic": {
            "branch": "main",
            "worktree_path": runtime_root,
            "venv_path": f"{runtime_root}/venv",
            "runtime_root": runtime_root,
            "expected_head": expected_head,
            "repair_bin": f"{runtime_root}/venv/bin/arnold-repair-loop",
            "deps_lockfile": f"{runtime_root}/uv.lock",
            "dependency_generation": {
                "id": "a" * 64,
                "frozen_spec_sha256": "a" * 64,
                "interpreter_path": interpreter_path,
                "venv_digest": "b" * 64,
                "created": "2026-08-12T00:00:00Z",
            },
        },
        "indirection": {
            "host_path": runtime_root,
            "container_path": "/workspace/auto-pin",
            "mount_table": [],
            "execution_namespace": "auto-pin-ns",
            "verified_head": expected_head or "0" * 40,
            "last_verified_at": "2026-08-12T00:00:00Z",
            "attestation": {
                "module_file": f"{runtime_root}/arnold_pipelines/__init__.py",
                "module_digest": "0" * 64,
                "mount_id": "0:0",
            },
        },
        "policy": {
            "policy_sha": "0" * 64,
            "model_policy_sha": "0" * 64,
            "sync_policy": "disabled",
        },
        "promotions": [],
        "timestamps": {
            "created": "2026-08-12T00:00:00Z",
            "updated": "2026-08-12T00:00:00Z",
            "closed": "",
        },
        "gc_policy": "closed-only",
        "commands": [],
    }


def test_auto_entrypoint_manifest_pin_precedes_marker_and_launch() -> None:
    from arnold_pipelines.megaplan.cloud.template import _auto_command, render_entrypoint

    quoted = _auto_command(_auto_cloud_spec())
    script = shlex.split(quoted)[0]

    # T-0021: the exit-24 manifest pin is enforced BEFORE the session marker
    # write (prelude) and before any init/auto state load; the manifest root
    # is the ONLY directory that reaches PYTHONPATH and the spec's declared
    # megaplan.src_path is never consulted (no /workspace/arnold fallback).
    assert (
        script.index("isolated_chain_runtime_binding_drift")
        < script.index("MEGAPLAN_MANAGED_RUN_MARKER")
    )
    assert "PYTHONPATH=\"$ENGINE_DIR\"" in script
    assert "PYTHONPATH=\"/workspace/arnold" not in script
    assert "MEGAPLAN_SRC_PATH" not in script
    parsed = subprocess.run(
        ["bash", "-n"], input=script, text=True, capture_output=True, check=False
    )
    assert parsed.returncode == 0, parsed.stderr

    entrypoint = render_entrypoint(_auto_cloud_spec())
    assert "MEGAPLAN_SRC_PATH" not in entrypoint


@pytest.mark.parametrize(
    ("case", "kind", "provenance_rc", "expect"),
    [
        (
            "missing-file",
            "missing-file",
            0,
            "runtime manifest unreadable",
        ),
        (
            "schema-invalid-with-root",  # G6 round-9 finding 1
            "schema-invalid-with-root",
            0,
            "manifest lacks runtime_root",
        ),
        (
            "compatibility-only",  # G6 round-9 finding 1
            "compatibility-only",
            0,
            "manifest lacks runtime_root",
        ),
        (
            "empty-epic",
            "empty-epic",
            0,
            "manifest lacks runtime_root",
        ),
        (
            "no-expected-head",
            "no-expected-head",
            0,
            "manifest lacks runtime identity",
        ),
        (
            "no-generation",  # T-0301: proof missing -> launch blocked
            "valid-no-generation",
            0,
            "manifest lacks dependency generation interpreter",
        ),
        (
            "provenance-mismatch",
            "valid",
            23,
            "active imports disagree with manifest-bound runtime",
        ),
    ],
)
def test_auto_entrypoint_fails_closed_before_marker_write(
    tmp_path: Path,
    case: str,
    kind: str,
    provenance_rc: int,
    expect: str,
) -> None:
    from arnold_pipelines.megaplan.cloud.template import _auto_command

    script = shlex.split(_auto_command(_auto_cloud_spec()))[0]
    script_path = tmp_path / "auto-entrypoint.sh"
    script_path.write_text(script + "\n", encoding="utf-8")

    shim = _runtime_shim(tmp_path, provenance_exit=provenance_rc)
    env = {
        **os.environ,
        "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
        "REAL_PYTHON": sys.executable,
    }
    manifest_path = tmp_path / "runtime-manifest.json"
    runtime_root = str(tmp_path / "accepted-runtime")
    if kind == "missing-file":
        env["ARNOLD_RUNTIME_MANIFEST"] = str(
            tmp_path / "does-not-exist-runtime-manifest.json"
        )
    else:
        if kind == "schema-invalid-with-root":
            # Parseable but schema-invalid (schema-less) with epic.runtime_root:
            # the raw reader derived ENGINE_DIR from it; the canonical
            # schema-gated read must yield EMPTY so the pin fails closed.
            manifest: dict[str, object] = {
                "epic": {
                    "runtime_root": runtime_root,
                    "expected_head": "a" * 40,
                }
            }
        elif kind == "compatibility-only":
            # Schema-valid full manifest demoted to a NON-AUTHORITATIVE
            # pointer: must never select a runtime.
            manifest = {
                **_canonical_manifest_payload(
                    runtime_root, expected_head="a" * 40
                ),
                COMPATIBILITY_ONLY_KEY: True,
            }
        elif kind == "empty-epic":
            manifest = {"epic": {}}
        elif kind == "no-expected-head":
            # Canonically schema-valid (gate passes) but expected_head empty:
            # ENGINE_DIR reads, then the runtime-identity check fails.
            manifest = _canonical_manifest_payload(runtime_root, expected_head="")
        elif kind == "valid-no-generation":
            # T-0301: canonically schema-valid but carrying NO
            # dependency_generation proof — the launch gate fails closed
            # (a runtime without a verifiable immutable generation is never
            # launched, and there is no editable-install fallback).
            manifest = _canonical_manifest_payload(
                runtime_root, expected_head="a" * 40, interpreter_path=str(shim)
            )
            del manifest["epic"]["dependency_generation"]  # type: ignore[typeddict-item]
        else:  # kind == "valid"
            # The generation proof points at the shim so the gate's
            # interpreter-existence check passes and the failure lands in the
            # provenance check (provenance_rc).
            manifest = _canonical_manifest_payload(
                runtime_root, expected_head="a" * 40, interpreter_path=str(shim)
            )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        env["ARNOLD_RUNTIME_MANIFEST"] = str(manifest_path)

    result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 24, (case, result.stdout, result.stderr)
    assert "isolated_chain_runtime_binding_drift" in result.stderr, case
    assert expect in result.stderr, case
    # The pin is enforced before the marker prelude: the marker was never
    # materialized and no launch boundary ran.
    assert "MEGAPLAN_MANAGED_RUN_MARKER" not in result.stdout, case


def test_auto_entrypoint_schema_valid_manifest_binds_engine_dir_to_root(
    tmp_path: Path,
) -> None:
    """G6 round-9 finding 1: a schema-valid, non-compatibility_only manifest
    yields ENGINE_DIR from ``epic.runtime_root``.

    Runs only the manifest-pin fragment of the auto entrypoint (everything
    before the managed-run prelude) with a canonically schema-valid manifest
    and a provenance shim that records the PYTHONPATH it was invoked with.
    The pin must pass and the recorded provenance PYTHONPATH must be exactly
    the manifest's ``epic.runtime_root`` — the same value the launch would
    bind as ENGINE_DIR.
    """
    from arnold_pipelines.megaplan.cloud.template import _auto_command

    script = shlex.split(_auto_command(_auto_cloud_spec()))[0]
    pin_fragment = script.split("unset ARNOLD_LIVENESS_OWNER_PID")[0]
    assert "MEGAPLAN_MANAGED_RUN_MARKER" not in pin_fragment
    pin_path = tmp_path / "auto-pin-fragment.sh"
    pin_path.write_text(pin_fragment + "\n", encoding="utf-8")

    runtime_root = tmp_path / "accepted-runtime"
    runtime_root.mkdir(parents=True)
    provenance_pythonpath = tmp_path / "provenance-pythonpath"
    shim = tmp_path / "bin" / "python"
    shim.parent.mkdir(parents=True)
    shim.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *arnold_pipelines.megaplan.cloud.runtime_provenance*)\n"
        f"    printf '%s' \"$PYTHONPATH\" > {shlex.quote(str(provenance_pythonpath))}\n"
        "    exit 0 ;;\n"
        "esac\n"
        "exec \"$REAL_PYTHON\" \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
        "REAL_PYTHON": sys.executable,
    }
    manifest_path = tmp_path / "runtime-manifest.json"
    # T-0301: the generation proof's interpreter IS the shim — the gate's
    # interpreter-existence check passes and the provenance check runs via
    # the shim (which records the PYTHONPATH it was invoked with).
    manifest_path.write_text(
        json.dumps(
            _canonical_manifest_payload(
                str(runtime_root),
                expected_head="a" * 40,
                interpreter_path=str(shim),
            )
        ),
        encoding="utf-8",
    )
    env["ARNOLD_RUNTIME_MANIFEST"] = str(manifest_path)

    result = subprocess.run(
        ["bash", str(pin_path)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "isolated_chain_runtime_binding_drift" not in result.stderr
    # The provenance check ran with PYTHONPATH == manifest epic.runtime_root:
    # ENGINE_DIR was derived from the schema-valid manifest root.
    assert provenance_pythonpath.read_text(encoding="utf-8") == str(runtime_root)
