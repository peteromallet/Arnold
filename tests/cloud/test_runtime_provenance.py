from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import arnold_pipelines.megaplan.cloud.runtime_provenance as provenance_module
from arnold_pipelines.megaplan.cloud.runtime_provenance import (
    m11_bound_runtime_identity,
    runtime_provenance,
)


def test_runtime_provenance_rejects_wrong_expected_root(tmp_path: Path) -> None:
    payload = runtime_provenance(expected_root=tmp_path)
    assert payload["ok"] is False
    assert "import_root_mismatch" in payload["errors"]


def test_runtime_provenance_rejects_wrong_expected_revision() -> None:
    source = Path(__file__).parents[2].resolve()
    payload = runtime_provenance(
        expected_root=source,
        expected_revision="0" * 40,
    )
    assert payload["ok"] is False
    assert "source_revision_mismatch" in payload["errors"]


def test_runtime_source_has_valid_git_metadata() -> None:
    source = Path(__file__).parents[2].resolve()
    assert (source / ".git").is_file() or (source / ".git").is_dir()
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--git-dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_editable_subprocess_uses_pinned_source_despite_cwd_shadow(tmp_path: Path) -> None:
    source = Path(__file__).parents[2].resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True
    )
    python = venv / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "-e", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    target = tmp_path / "target"
    (target / "arnold_pipelines").mkdir(parents=True)
    (target / "arnold_pipelines" / "__init__.py").write_text(
        "raise RuntimeError('cwd shadow imported')\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source)
    result = subprocess.run(
        [
            str(python),
            "-P",
            "-m",
            "arnold_pipelines.megaplan.cloud.runtime_provenance",
            "--expected-root",
            str(source),
            "--expected-revision",
            revision,
        ],
        cwd=target,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["import_root"] == str(source)
    assert payload["editable_root"] == str(source)
    assert payload["source_revision"] == revision
    assert payload["runtime_revision"] == revision
    assert payload["pth"]
    assert {
        entry
        for record in payload["pth"]
        for entry in record["entries"]
    } == {str(source)}


def test_runtime_provenance_rejects_stale_editable_pth(
    monkeypatch,
) -> None:
    source = Path(__file__).parents[2].resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    monkeypatch.setattr(
        provenance_module,
        "_direct_url_identity",
        lambda: (source, {"dir_info": {"editable": True}, "url": source.as_uri()}),
    )
    monkeypatch.setattr(
        provenance_module,
        "_pth_identity",
        lambda: [
            {
                "path": "/venv/site-packages/_editable_impl_arnold.pth",
                "entries": [str(source), "/workspace/stale-arnold"],
                "readable": True,
            }
        ],
    )

    payload = runtime_provenance(
        expected_root=source,
        expected_revision=revision,
    )

    assert payload["ok"] is False
    assert "editable_pth_mismatch" in payload["errors"]


# ── M11 bound runtime identity (Step 3) ──────────────────────────────────


def _resolve_runtime_root() -> Path:
    """Return the actual editable runtime root where Python imports resolve.

    This prefers the actual import location over editable metadata, because
    the latter may point to a symlinked or copied tree that differs from
    what Python actually loads at runtime.
    """
    import arnold_pipelines

    import_root = Path(arnold_pipelines.__file__).resolve().parents[1]
    if import_root.is_dir():
        return import_root
    # Fallback: use editable metadata
    from arnold_pipelines.megaplan.cloud.runtime_provenance import _direct_url_identity

    root, _payload = _direct_url_identity()
    if root is not None:
        return root
    # Last resort: use the source tree
    return Path(__file__).parents[2].resolve()


def _resolve_runtime_revision(root: Path) -> str:
    """Return the HEAD revision for the runtime root."""
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def test_m11_bound_runtime_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Step 3: m11_bound_runtime_identity validates all eight components
    and emits a content-addressed identity receipt.

    When called without the optional supervisor/wrapper/target args,
    those components report invalid while interpreter, editable checkout,
    .pth, imports, and source lineage validate against the current
    runtime.  The overall identity is invalid because the optional
    components are not configured.
    """
    # This is the aggregate identity-schema test, not the editable-install
    # integration test (covered above in a dedicated venv).  Pin discovery to
    # this checkout so a developer's globally installed Arnold distribution
    # cannot make the result depend on whichever worktree pip last saw.
    root = Path(__file__).parents[2].resolve()
    revision = _resolve_runtime_revision(root)
    monkeypatch.setattr(
        provenance_module,
        "_direct_url_identity",
        lambda: (
            root,
            {"dir_info": {"editable": True}, "url": root.as_uri()},
        ),
    )
    monkeypatch.setattr(
        provenance_module,
        "_pth_identity",
        lambda: [
            {
                "path": str(root / ".test-editable-arnold.pth"),
                "entries": [str(root)],
                "readable": True,
            }
        ],
    )

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision=revision,
    )

    # Schema is present
    assert identity["schema"] == "arnold.megaplan.m11_bound_runtime_identity.v1"
    assert "content_sha256" in identity

    # All eight components must be present
    assert set(identity["component_names"]) == {
        "interpreter",
        "editable_checkout",
        "pth_files",
        "imports",
        "source_lineage",
        "wrappers",
        "supervisor_command",
        "target_marker",
    }

    components = identity["components"]

    # Interpreter must be valid
    assert components["interpreter"]["ok"] is True
    assert components["interpreter"]["executable"]
    assert components["interpreter"]["sha256"]

    # Editable checkout must be valid (pip install -e)
    assert components["editable_checkout"]["ok"] is True, (
        f"editable checkout errors: {components['editable_checkout']['errors']}"
    )
    assert components["editable_checkout"]["root"]

    # .pth files must be valid
    assert components["pth_files"]["ok"] is True, (
        f"pth errors: {components['pth_files']['errors']}"
    )
    assert components["pth_files"]["records"]

    # Imports must be valid
    assert components["imports"]["ok"] is True, (
        f"import errors: {components['imports']['errors']}"
    )
    assert "arnold" in components["imports"]["paths"]
    assert "arnold_pipelines" in components["imports"]["paths"]

    # Source lineage must be valid
    assert components["source_lineage"]["ok"] is True
    assert components["source_lineage"]["revision"] == revision

    # Optional components are invalid when not configured
    assert components["wrappers"]["ok"] is False
    assert components["supervisor_command"]["ok"] is False
    assert components["target_marker"]["ok"] is False

    # Overall identity is invalid because optional components fail
    assert identity["valid"] is False
    assert "wrappers_invalid" in identity["errors"]
    assert "supervisor_command_invalid" in identity["errors"]
    assert "target_marker_invalid" in identity["errors"]


def test_m11_bound_runtime_identity_deterministic() -> None:
    """Step 3: identity is deterministic — same inputs produce same content_sha256."""
    root = _resolve_runtime_root()
    revision = _resolve_runtime_revision(root)

    a = m11_bound_runtime_identity(expected_root=root, expected_revision=revision)
    b = m11_bound_runtime_identity(expected_root=root, expected_revision=revision)

    assert a["content_sha256"] == b["content_sha256"]
    assert a["valid"] == b["valid"]
    assert a["errors"] == b["errors"]


def test_m11_bound_runtime_identity_rejects_wrong_root(tmp_path: Path) -> None:
    """Step 3: identity rejects a wrong expected root."""
    identity = m11_bound_runtime_identity(expected_root=tmp_path)

    # Editable checkout and imports should fail because tmp_path != real root
    assert identity["components"]["editable_checkout"]["ok"] is False
    assert identity["components"]["imports"]["ok"] is False
    assert identity["valid"] is False


def test_m11_bound_runtime_identity_rejects_wrong_revision() -> None:
    """Step 3: identity rejects a wrong expected revision."""
    root = _resolve_runtime_root()

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision="0" * 40,
    )

    assert identity["components"]["source_lineage"]["ok"] is False
    assert "revision_mismatch" in identity["components"]["source_lineage"]["errors"]


def test_m11_bound_runtime_identity_with_wrapper_dir(tmp_path: Path) -> None:
    """Step 3: wrappers validate when a wrapper dir with arnold-* files exists."""
    root = _resolve_runtime_root()
    revision = _resolve_runtime_revision(root)

    wrapper_dir = tmp_path / "wrappers"
    wrapper_dir.mkdir()
    (wrapper_dir / "arnold-repair").write_text("#!/bin/bash\necho repair\n")
    (wrapper_dir / "arnold-watchdog").write_text("#!/bin/bash\necho watchdog\n")

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision=revision,
        wrapper_dir=wrapper_dir,
    )

    assert identity["components"]["wrappers"]["ok"] is True
    wrapper_names = {e["name"] for e in identity["components"]["wrappers"]["entries"]}
    assert "arnold-repair" in wrapper_names
    assert "arnold-watchdog" in wrapper_names
    for entry in identity["components"]["wrappers"]["entries"]:
        assert entry["sha256"]


def test_m11_bound_runtime_identity_with_supervisor_python() -> None:
    """Step 3: supervisor validates when the python binary exists."""
    root = _resolve_runtime_root()
    revision = _resolve_runtime_revision(root)

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision=revision,
        supervisor_python=Path(sys.executable),
    )

    assert identity["components"]["supervisor_command"]["ok"] is True
    assert identity["components"]["supervisor_command"]["exists"] is True
    assert identity["components"]["supervisor_command"]["sha256"]


def test_m11_bound_runtime_identity_with_target_marker(tmp_path: Path) -> None:
    """Step 3: target marker validates when the marker file exists."""
    root = _resolve_runtime_root()
    revision = _resolve_runtime_revision(root)

    marker = tmp_path / "target.marker"
    marker.write_text('{"session_id": "custody-control-plane"}\n')

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision=revision,
        target_marker_path=marker,
    )

    assert identity["components"]["target_marker"]["ok"] is True
    assert identity["components"]["target_marker"]["exists"] is True
    assert (
        identity["components"]["target_marker"]["fields"]["session_id"]
        == "custody-control-plane"
    )


def test_m11_strict_identity_requires_complete_exact_tuple(
    tmp_path: Path, monkeypatch
) -> None:
    root = _resolve_runtime_root()
    revision = _resolve_runtime_revision(root)
    import arnold
    import arnold_pipelines

    pth = tmp_path / "_editable_impl_arnold.pth"
    pth.write_text(str(root) + "\n", encoding="utf-8")
    wrapper_dir = tmp_path / "wrappers"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "arnold-progress-auditor"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    marker = tmp_path / "target.json"
    marker.write_text(
        '{"session_id":"custody-control-plane-20260714","status":"executing"}\n',
        encoding="utf-8",
    )
    import_paths = {
        "arnold": str(Path(arnold.__file__).resolve()),
        "arnold_pipelines": str(Path(arnold_pipelines.__file__).resolve()),
        "megaplan": str(
            (
                root / "arnold_pipelines" / "megaplan" / "__init__.py"
            ).resolve()
        ),
    }
    monkeypatch.setattr(
        provenance_module,
        "_direct_url_identity",
        lambda: (root, {"dir_info": {"editable": True}, "url": root.as_uri()}),
    )
    monkeypatch.setattr(
        provenance_module,
        "_pth_identity",
        lambda: [
            {
                "path": str(pth.resolve()),
                "sha256": provenance_module._sha256_file(pth),
                "entries": [str(root)],
                "readable": True,
            }
        ],
    )
    monkeypatch.setattr(provenance_module, "_git_is_clean", lambda _root: True)
    monkeypatch.setattr(provenance_module, "_safe_path_enabled", lambda: True)
    executable = Path(sys.executable).resolve()
    argv = [str(executable), "-P", "-m", "arnold_pipelines.megaplan.cloud.runner"]

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision=revision,
        expected_interpreter=executable,
        expected_interpreter_sha256=provenance_module._sha256_file(executable),
        expected_pth_hashes={
            str(pth.resolve()): provenance_module._sha256_file(pth)
        },
        expected_import_paths=import_paths,
        supervisor_python=executable,
        supervisor_argv=argv,
        expected_supervisor_argv=argv,
        wrapper_dir=wrapper_dir,
        expected_wrapper_hashes={
            str(wrapper.resolve()): provenance_module._sha256_file(wrapper)
        },
        target_marker_path=marker,
        expected_target_marker_sha256=provenance_module._sha256_file(marker),
        expected_target_fields={
            "session_id": "custody-control-plane-20260714",
            "status": "executing",
        },
        strict=True,
    )

    assert identity["valid"] is True, identity


def test_m11_strict_identity_rejects_each_mutable_binding(
    tmp_path: Path, monkeypatch
) -> None:
    root = _resolve_runtime_root()
    revision = _resolve_runtime_revision(root)
    monkeypatch.setattr(provenance_module, "_safe_path_enabled", lambda: False)

    identity = m11_bound_runtime_identity(
        expected_root=root,
        expected_revision=revision,
        expected_interpreter=Path(sys.executable),
        expected_interpreter_sha256="0" * 64,
        expected_pth_hashes={"/wrong/editable.pth": "1" * 64},
        expected_import_paths={"arnold": "/wrong/arnold/__init__.py"},
        supervisor_python=Path(sys.executable),
        supervisor_argv=[str(sys.executable), "-m", "wrong"],
        expected_supervisor_argv=[str(sys.executable), "-P", "-m", "expected"],
        wrapper_dir=tmp_path,
        expected_wrapper_hashes={"/wrong/arnold-progress-auditor": "2" * 64},
        target_marker_path=tmp_path / "missing.json",
        expected_target_marker_sha256="3" * 64,
        expected_target_fields={"session_id": "custody-control-plane-20260714"},
        strict=True,
    )

    assert identity["valid"] is False
    assert "interpreter_sha256_mismatch" in identity["components"]["interpreter"]["errors"]
    assert "python_safe_path_disabled" in identity["components"]["interpreter"]["errors"]
    assert "pth_set_or_hash_mismatch" in identity["components"]["pth_files"]["errors"]
    assert "import_path_map_mismatch" in identity["components"]["imports"]["errors"]
    assert "wrapper_set_or_hash_mismatch" in identity["components"]["wrappers"]["errors"]
    assert "supervisor_argv_mismatch" in identity["components"]["supervisor_command"]["errors"]
    assert "target_marker_missing" in identity["components"]["target_marker"]["errors"]
