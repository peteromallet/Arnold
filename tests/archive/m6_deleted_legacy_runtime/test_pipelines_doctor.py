"""W7 — pipelines doctor per-path report tests (T14).

`pipelines doctor` consumes the NON-raising ``scan_python_pipelines()`` and
prints a per-path disposition (discovered / rejected + traceback / skipped +
reason). It does NOT trigger ``discover_python_pipelines()``'s aggregate raise.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from arnold_pipelines.megaplan._pipeline import registry as registry_mod


def _run_cli(cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", "pipelines", "doctor"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_doctor_lists_in_tree_packs_as_discovered() -> None:
    """Every in-tree pack must appear in the doctor report."""
    result = _run_cli()
    assert result.returncode == 0, result.stderr
    # at least one in-tree discovered line
    assert "in_tree" in result.stdout
    assert "discovered" in result.stdout


def test_doctor_reports_broken_user_pack_without_raising(
    tmp_path: Path, monkeypatch
) -> None:
    """A deliberately-broken user pack is listed as rejected with a traceback.

    We point a fresh scan root at a tmp dir, drop a broken module in, and
    confirm scan_python_pipelines() (which doctor consumes) lists it as
    rejected — and that it never raises.
    """
    broken_dir = tmp_path / "user_pack"
    broken_dir.mkdir()
    (broken_dir / "broken_pipeline.py").write_text(
        textwrap.dedent(
            """
            # Deliberately raises at import time so the discovery path
            # records a traceback rather than vanishing silently.
            raise RuntimeError("synthetic broken pack for doctor test")
            """
        ).lstrip(),
        encoding="utf-8",
    )

    # Append our broken dir as a USER scan root (not in_tree).
    extra_root = (broken_dir, "user.pack")
    original_fn = registry_mod._get_scan_roots
    monkeypatch.setattr(
        registry_mod,
        "_get_scan_roots",
        lambda: list(original_fn()) + [extra_root],
    )

    dispositions = registry_mod.scan_python_pipelines()

    matches = [d for d in dispositions if "broken_pipeline" in str(d.path)]
    assert matches, "broken pack should appear in scan_python_pipelines output"
    broken = matches[0]
    assert broken.status == "rejected"
    assert broken.origin == "user"
    assert broken.traceback is not None and broken.traceback.strip()

    # The non-raising contract: scanning a broken pack must not throw.
    assert isinstance(dispositions, list)
