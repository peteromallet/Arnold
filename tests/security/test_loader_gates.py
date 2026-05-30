"""S4 Step 10 — capability fence on `exec_module` loader call sites.

Covers ``vibecomfy/security/loader_provenance.py::_provenance_for_path`` plus
the gate insertions at ``vibecomfy/scratchpad_loader.py:24`` and
``vibecomfy/registry/ready.py:97``.

Verifies:
  * trusted-dir classification uses ``Path.resolve()`` + ``is_relative_to``
    (NOT prefix-string match), so traversal attempts that resolve outside the
    trusted directory are classified ``untrusted_source``.
  * scratchpads written under the resolved ``out/scratchpads/`` trusted dir
    do NOT prompt and do NOT raise ``CapabilityFenceError`` in headless mode.
  * loading an external attacker-controlled path headless raises
    ``CapabilityFenceError``.
  * built-in ready-template paths are always classified ``agent_authored``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.security import loader_provenance as lp
from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    _gate_context_var,
    set_gate_context,
)


@pytest.fixture(autouse=True)
def _headless_gate_context():
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        try:
            _gate_context_var.reset(token)
        except Exception:
            pass


def _write_trivial_scratchpad(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n"
        "\n"
        "def build():\n"
        "    return VibeWorkflow(id='t', source=WorkflowSource(id='t'))\n"
    )


# ---- _provenance_for_path ----------------------------------------------------


def test_scratchpad_under_trusted_dir_is_agent_authored(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "find_repo_root", lambda: tmp_path)
    sp = tmp_path / "out" / "scratchpads" / "foo.py"
    sp.parent.mkdir(parents=True)
    sp.write_text("# scratchpad\n")
    assert lp._provenance_for_path(sp) == "agent_authored"


def test_external_path_is_untrusted_source(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "find_repo_root", lambda: tmp_path)
    outside = tmp_path.parent / "vibecomfy_attacker_loader_gates_probe.py"
    outside.write_text("# evil\n")
    try:
        assert lp._provenance_for_path(outside) == "untrusted_source"
    finally:
        outside.unlink(missing_ok=True)


def test_traversal_out_of_trusted_dir_is_untrusted(tmp_path, monkeypatch):
    """`out/scratchpads/../../elsewhere/attacker.py` resolves outside the
    trusted dir and must be treated as untrusted — proves we are NOT doing
    prefix-string matching on the unresolved path."""
    monkeypatch.setattr(lp, "find_repo_root", lambda: tmp_path)
    (tmp_path / "out" / "scratchpads").mkdir(parents=True)
    outside_dir = tmp_path.parent / "loader_gates_traversal_target"
    outside_dir.mkdir(exist_ok=True)
    target = outside_dir / "attacker.py"
    target.write_text("# evil\n")
    try:
        traversal = (
            tmp_path / "out" / "scratchpads" / ".." / ".." / ".." / outside_dir.name / "attacker.py"
        )
        # Prefix-string match against str(traversal) would (incorrectly) accept this
        # because it starts with str(tmp_path / "out" / "scratchpads").
        prefix_str = str(tmp_path / "out" / "scratchpads")
        assert str(traversal).startswith(prefix_str)
        # But resolve() + is_relative_to correctly classifies it as untrusted.
        assert lp._provenance_for_path(traversal) == "untrusted_source"
    finally:
        target.unlink(missing_ok=True)
        try:
            outside_dir.rmdir()
        except OSError:
            pass


def test_builtin_ready_template_paths_are_agent_authored():
    """Built-in `ready_templates/` files (resolved under the real repo root)
    are always classified `agent_authored`, regardless of monkeypatching."""
    from vibecomfy.registry.ready import repo_ready_template_paths

    paths = repo_ready_template_paths()
    assert paths, "expected built-in ready templates to be present in the repo"
    assert lp._provenance_for_path(paths[0]) == "agent_authored"


# ---- scratchpad_loader gate --------------------------------------------------


def test_load_scratchpad_under_trusted_dir_does_not_prompt(tmp_path, monkeypatch):
    """Scratchpad under resolved `out/scratchpads/` must NOT raise the gate."""
    from vibecomfy import scratchpad_loader

    monkeypatch.setattr(lp, "find_repo_root", lambda: tmp_path)
    sp = tmp_path / "out" / "scratchpads" / "ok.py"
    _write_trivial_scratchpad(sp)
    # Must not raise CapabilityFenceError — other downstream errors are not the
    # gate's concern; this test asserts the *gate decision*.
    try:
        scratchpad_loader.load_scratchpad(sp)
    except CapabilityFenceError as exc:  # pragma: no cover - defensive
        pytest.fail(f"capability fence wrongly fired on trusted path: {exc.detail}")


def test_load_scratchpad_from_external_path_raises_headless(tmp_path, monkeypatch):
    """An attacker-controlled path outside the trusted dirs must refuse
    headless under the default `non_interactive=True` ctx."""
    from vibecomfy import scratchpad_loader

    monkeypatch.setattr(lp, "find_repo_root", lambda: tmp_path)
    (tmp_path / "out" / "scratchpads").mkdir(parents=True)

    attacker = tmp_path.parent / "vibecomfy_loader_gates_external_attacker.py"
    _write_trivial_scratchpad(attacker)
    try:
        with pytest.raises(CapabilityFenceError) as excinfo:
            scratchpad_loader.load_scratchpad(attacker)
        detail = excinfo.value.detail
        assert detail["operation"] == "scratchpad_exec"
        assert detail["provenance"] == "untrusted_source"
        assert "code_exec" in detail["capabilities"]
    finally:
        attacker.unlink(missing_ok=True)


def test_load_scratchpad_traversal_attempt_raises_headless(tmp_path, monkeypatch):
    """`out/scratchpads/../../elsewhere/attacker.py` must refuse headless —
    proves the gate is keyed off resolved paths, not the literal string."""
    from vibecomfy import scratchpad_loader

    monkeypatch.setattr(lp, "find_repo_root", lambda: tmp_path)
    (tmp_path / "out" / "scratchpads").mkdir(parents=True)

    outside_dir = tmp_path.parent / "loader_gates_traversal_scratchpads"
    outside_dir.mkdir(exist_ok=True)
    target = outside_dir / "attacker.py"
    _write_trivial_scratchpad(target)
    traversal = (
        tmp_path / "out" / "scratchpads" / ".." / ".." / ".." / outside_dir.name / "attacker.py"
    )
    try:
        with pytest.raises(CapabilityFenceError):
            scratchpad_loader.load_scratchpad(traversal)
    finally:
        target.unlink(missing_ok=True)
        try:
            outside_dir.rmdir()
        except OSError:
            pass
