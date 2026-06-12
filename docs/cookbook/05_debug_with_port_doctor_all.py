"""
05_debug_with_port_doctor_all.py — Debug a failing template with port doctor-all
=================================================================================

Use ``vibecomfy port doctor-all`` to diagnose problems in a workflow: missing
schemas, broken custom-node pins, model URL reachability, and compile errors.

The actual CLI invocation is behind ``if __name__ == '__main__'`` — the
module body only defines helper functions with no side effects.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. What ``port doctor-all`` does
# ---------------------------------------------------------------------------
# It runs five diagnostic sections on a workflow:
#
#   Section                  What it checks
#   ───────────────────────  ────────────────────────────────────────────
#   port check               JSON validity, custom nodes, widget aliases
#   nodes install-plan       Whether custom nodes can be installed
#   validate                 Schema validation of every node call
#   doctor                   Deep inspection: compile, models, contracts
#   runtime doctor           Runtime health (if a server is reachable)
#
# Together they give you a machine-readable JSON report with a ``next_action``
# field telling you what to fix next.


def explain_doctor_all() -> None:
    """Print the doctor-all concept (no side effects)."""
    print("port doctor-all runs five diagnostic sections:")
    for section, desc in [
        ("port check", "JSON validity, custom nodes, widget aliases"),
        ("nodes install-plan", "Custom node install feasibility"),
        ("validate", "Schema validation of every node call"),
        ("doctor", "Deep inspection: compile, models, contracts"),
        ("runtime doctor", "Runtime health (requires server URL)"),
    ]:
        print(f"  {section:25s} {desc}")


# ---------------------------------------------------------------------------
# 2. Run doctor-all on a file (guarded — may require indexes)
# ---------------------------------------------------------------------------

def run_doctor_all(workflow_path: str) -> dict | None:
    """Invoke ``vibecomfy port doctor-all`` and return the parsed JSON result.

    Returns None if the CLI is unavailable or the workflow doesn't exist.
    """
    path = Path(workflow_path)
    if not path.exists():
        print(f"Workflow not found: {workflow_path}", file=sys.stderr)
        return None

    try:
        result = subprocess.run(
            [sys.executable, "-m", "vibecomfy.cli", "port", "doctor-all", str(path), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0 and not result.stdout.strip():
            print(f"doctor-all stderr: {result.stderr[:500]}", file=sys.stderr)
            return None
        return json.loads(result.stdout) if result.stdout.strip() else None
    except FileNotFoundError:
        print("vibecomfy CLI not found — install the package first", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("doctor-all timed out (may need indexes built)", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# 3. Interpret a doctor-all report
# ---------------------------------------------------------------------------

def interpret_report(report: dict) -> str:
    """Return a human-readable summary of a doctor-all JSON report."""
    summary = report.get("summary", {})
    status = report.get("status", "unknown")
    next_action = report.get("next_action", "none")

    lines = [
        f"Status: {status}",
        f"Sections: {summary.get('ok_sections', 0)} ok / "
        f"{summary.get('warning_sections', 0)} warn / "
        f"{summary.get('error_sections', 0)} err "
        f"(of {summary.get('section_count', 0)} total)",
        f"Findings: {summary.get('finding_count', 0)}",
        f"Next action: {next_action}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    explain_doctor_all()

    # Try to doctor the wan_i2v corpus workflow if available
    corpus = Path(__file__).resolve().parents[2] / "ready_templates/sources" / "official" / "video" / "wan_i2v.json"
    if corpus.exists():
        print(f"\nRunning doctor-all on: {corpus}")
        report = run_doctor_all(str(corpus))
        if report:
            print(interpret_report(report))
        else:
            print("(doctor-all unavailable — build indexes with `vibecomfy sources sync`)")
    else:
        print("\n(No corpus workflow available for demo — clone the full repo)")
