#!/usr/bin/env python
"""READ-ONLY reproduction of the finalize critique-custody resolution sweep.

Calls the pure resolver `_resolution_for_finding` exactly as the engine's
`write_critique_clearance` does for every finding in every custody receipt,
under the runtime selected by PYTHONPATH. No plan artifacts are written.
"""
import json
import sys
from pathlib import Path

PLAN_DIR = Path("/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140")

from arnold_pipelines.megaplan.orchestration.critique_custody import (
    _resolution_for_finding,
    CritiqueCustodyError,
)
from arnold_pipelines.megaplan._core.registries import load_flag_registry

state = json.loads((PLAN_DIR / "state.json").read_text())
registry = load_flag_registry(PLAN_DIR)
by_id = {str(f.get("id")): f for f in registry.get("flags", []) if isinstance(f, dict) and f.get("id")}

plan_version_order = {
    str(v.get("file")): int(v.get("version"))
    for v in state.get("plan_versions", [])
    if isinstance(v, dict) and isinstance(v.get("file"), str) and isinstance(v.get("version"), int)
}

robustness = "thorough"
gate_expected = True  # workflow includes gate (gate_signals_v5, step_receipt_gate_v5 exist)

current_plan = PLAN_DIR / "plan_v5.md"
current_plan_sha = "4537c985a9e8f1258af71d97d1d631b8ba6d0bcfc83b9a56fbd29cb327160f46"

receipt_paths = sorted(PLAN_DIR.glob("critique_custody_v*.json"))
latest_occurrences = {}
for path in receipt_paths:
    receipt = json.loads(path.read_text())
    for finding in receipt.get("findings", []):
        flag_id = str(finding.get("flag_id"))
        finding_id = str(finding.get("finding_id"))
        key = f"finding:{finding_id}"
        if flag_id != finding_id:
            key = f"legacy-producer-slot:{flag_id}"
        latest_occurrences[key] = (finding, receipt)

failures = []
resolutions = []
for finding, receipt in latest_occurrences.values():
    finding_id = str(finding.get("finding_id"))
    flag_id = str(finding.get("flag_id"))
    flag = by_id.get(flag_id)
    if flag is None:
        failures.append({"finding_id": finding_id, "flag_id": flag_id, "error": "critique_registry_mapping_missing"})
        continue
    try:
        res = _resolution_for_finding(
            flag,
            finding,
            current_plan_name=current_plan.name,
            current_plan_sha256=current_plan_sha,
            source_plan_name=str(receipt.get("plan_artifact") or ""),
            source_plan_sha256=str(receipt.get("plan_sha256")),
            plan_version_order=plan_version_order,
            gate_expected=gate_expected,
        )
        resolutions.append({"finding_id": finding_id, "disposition": res.get("disposition")})
    except CritiqueCustodyError as exc:
        failures.append({"finding_id": finding_id, "flag_id": flag_id, "error": str(exc), "issues": getattr(exc, "issues", None)})

print(json.dumps({
    "runtime": sys.version,
    "import_root": str(Path(__import__("arnold_pipelines").__file__).resolve().parent.parent),
    "module_file": __import__("arnold_pipelines.megaplan.orchestration.critique_custody", fromlist=["x"]).__file__,
    "findings_processed": len(latest_occurrences),
    "resolved": len(resolutions),
    "failed": len(failures),
    "failures": failures,
    "dispositions": sorted({r["disposition"] for r in resolutions}),
}, indent=2))
