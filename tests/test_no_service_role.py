from __future__ import annotations

from pathlib import Path


def test_no_service_role_in_python_source() -> None:
    pkg_dir = Path(__file__).parent.parent / "megaplan"
    offenders = [
        str(path.relative_to(pkg_dir.parent))
        for path in sorted(pkg_dir.rglob("*.py"))
        if "SERVICE_ROLE" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        "SERVICE_ROLE must not appear in megaplan Python source "
        "(it belongs only in migration SQL):\n" + "\n".join(offenders)
    )
