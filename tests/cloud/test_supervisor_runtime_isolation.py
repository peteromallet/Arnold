"""Supervisor runtime isolation contract (seed-gap follow-up).

The supervisor venv is an isolation token: ``runtime_ready``, ``receipt_ready``,
and the receipt writer must never resolve Arnold code from an ambient
``PYTHONPATH`` (a hollow venv could otherwise look ready while importing from a
dead runtime tree, minting a false receipt).  ``PYTHONSAFEPATH`` alone does NOT
ignore ``PYTHONPATH``, so every invocation must also ``env -u PYTHONPATH``.
"""

import re
import subprocess
from pathlib import Path

WRAPPER = (
    Path(__file__).resolve().parents[2]
    / "arnold_pipelines"
    / "megaplan"
    / "cloud"
    / "wrappers"
    / "arnold-supervisor-runtime"
)


def _wrapper_text() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def test_wrapper_runtime_ready_strips_pythonpath() -> None:
    text = _wrapper_text()
    # The three python invocations (runtime_ready, receipt_ready, receipt
    # writer) must isolate PYTHONPATH.  A bare PYTHONSAFEPATH=1 without the
    # env -u is the hollow-receipt bug.
    assert text.count("env -u PYTHONPATH PYTHONSAFEPATH=1") >= 3


def test_wrapper_runtime_ready_uses_dash_p() -> None:
    text = _wrapper_text()
    # -P (isolated mode) must accompany every isolated invocation.
    matches = re.findall(
        r"env -u PYTHONPATH PYTHONSAFEPATH=1 \"[^\"]+\" -P", text
    )
    assert len(matches) >= 3


def test_wrapper_has_no_bare_pythonsafepath_invocations() -> None:
    text = _wrapper_text()
    # No python invocation may rely on PYTHONSAFEPATH without stripping
    # PYTHONPATH: that combination still honors PYTHONPATH.
    bare = re.findall(r"(?<!env -u PYTHONPATH )PYTHONSAFEPATH=1", text)
    assert not bare, f"bare PYTHONSAFEPATH invocations present: {bare}"


def test_wrapper_syntax_is_valid_shell() -> None:
    result = subprocess.run(
        ["bash", "-n", str(WRAPPER)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_wrapper_receipt_writer_isolated() -> None:
    text = _wrapper_text()
    # The receipt-writing heredoc records imports from the venv in isolation;
    # an un-isolated writer could record imports from an ambient PYTHONPATH
    # (the dead-tree hollow-receipt bug).
    writer_block = text.split("env -u PYTHONPATH PYTHONSAFEPATH=1")[-1]
    assert "receipt" in writer_block.lower() or "json.dump" in writer_block
