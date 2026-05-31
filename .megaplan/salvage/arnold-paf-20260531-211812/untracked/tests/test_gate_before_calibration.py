"""M5-eval T11: ratchet gate — calibration vocabulary stays out of megaplan/.

Asserts that the forbidden tokens (Calibration / CapabilityClaim /
calibration_ledger) do not appear under ``megaplan/**/*.py``. Excludes
``tests/``, ``briefs/``, ``docs/``, ``*.md``, and this gate file itself.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MEGAPLAN_ROOT = _REPO_ROOT / "megaplan"
_PATTERN = re.compile(r"Calibration|CapabilityClaim|calibration_ledger")
_SELF = Path(__file__).resolve()


def test_no_calibration_vocabulary_in_megaplan_package() -> None:
    offenders: list[tuple[str, int, str]] = []
    for path in _MEGAPLAN_ROOT.rglob("*.py"):
        rp = path.resolve()
        if rp == _SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PATTERN.search(line):
                offenders.append((str(path.relative_to(_REPO_ROOT)), lineno, line.strip()))

    assert offenders == [], (
        "Forbidden calibration vocabulary found:\n"
        + "\n".join(f"  {p}:{ln}: {txt}" for p, ln, txt in offenders)
    )
