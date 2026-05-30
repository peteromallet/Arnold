"""W6 — characterize sandbox install fail-closed + hermes per-call installation.

Pins the existing behavior. NO new fail-closed path is introduced; the
``if toolsets:`` skip on the hermes path is BY DESIGN (non-tool phases need
no sandbox) and is asserted here as the intended invariant.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from megaplan.runtime.sandbox import install_sandbox
from megaplan.workers import hermes as hermes_module


def test_install_sandbox_raises_on_missing_project_dir(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert not missing.exists()
    with pytest.raises(ValueError, match="does not exist"):
        with install_sandbox(missing):
            pass


def test_hermes_run_step_installs_sandbox_when_toolsets_present() -> None:
    """When toolsets is truthy on the hermes worker path, install_sandbox is
    entered for the per-call project_dir. We pin the source-level invariant
    rather than driving a full hermes run."""
    src = inspect.getsource(hermes_module)
    # The if-toolsets gate immediately precedes the install_sandbox enter.
    assert "if toolsets:" in src
    assert "install_sandbox(project_dir)" in src
    # The install_sandbox call must be inside the if-toolsets block (no
    # unconditional installation introduced).
    after = src.split("if toolsets:", 1)[1]
    install_idx = after.find("install_sandbox(project_dir)")
    assert install_idx >= 0
    # Same line is not preceded by a de-indented block before it (the
    # snippet between `if toolsets:` and the call stays within the block).
    block = after[:install_idx]
    for line in block.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        # Any non-blank line in this region must remain indented at least
        # as much as the body of the if (4+ spaces).
        assert line.startswith("    "), f"unexpected dedent before install_sandbox: {line!r}"


def test_hermes_skips_sandbox_when_toolsets_falsy_is_by_design() -> None:
    """A toolsets-falsy phase intentionally does NOT install the sandbox —
    pin the documented by-design skip as an invariant."""
    src = inspect.getsource(hermes_module)
    # The comment block explaining the by-design skip is present near the
    # if-toolsets gate.
    assert "Phases without tools (no toolsets)" in src or "don't need it" in src
    # There is no unconditional install_sandbox(... ) call that bypasses
    # the if-toolsets gate (a single guarded call site exists).
    assert src.count("install_sandbox(project_dir)") == 1
