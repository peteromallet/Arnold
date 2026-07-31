"""Generate evidence/m10-git-mutation-sinks.json from the AST scanner.

Run:  python3 tests/m10/generate_git_mutation_inventory.py
"""
from __future__ import annotations

import json
import os

import sys
sys.path.insert(0, os.path.dirname(__file__))
from git_sink_scanner import scan_all, MODULES  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO_ROOT, "evidence", "m10-git-mutation-sinks.json")

# bakeoff + CLI rows are explicitly action_off for M10 (Step 13E9).
ACTION_OFF_MODULES = {
    "arnold_pipelines/megaplan/bakeoff/worktree.py",
    "arnold_pipelines/megaplan/bakeoff/merge.py",
    "arnold_pipelines/megaplan/cli/__init__.py",
}

FAMILY = {
    "commit": "local_commit", "commit-tree": "local_commit", "add": "stage",
    "push": "remote_ref", "fetch": "remote_fetch", "reset": "working_tree",
    "clean": "working_tree", "checkout": "working_tree", "switch": "working_tree",
    "stash": "working_tree", "revert": "working_tree", "rebase": "working_tree",
    "cherry-pick": "working_tree", "restore": "working_tree",
    "update-ref": "ref_update", "worktree": "worktree_lifecycle",
    "apply": "patch_apply", "branch": "ref_update",
}

DESTRUCTIVE = {
    "push": "high", "reset": "high", "clean": "high", "rebase": "high",
    "worktree": "high", "revert": "medium", "checkout": "medium", "switch": "medium",
    "commit": "medium", "commit-tree": "medium", "add": "low", "fetch": "low",
    "stash": "medium", "apply": "medium", "update-ref": "high", "branch": "medium",
}


def _short(module: str) -> str:
    return module.split("/")[-1].replace(".py", "").replace("__init__", "pkg")


def build_rows() -> list[dict]:
    sinks = scan_all()
    rows: list[dict] = []
    for s in sinks:
        primary = s.subcommands[0]
        module_short = _short(s.module)
        is_action_off = s.module in ACTION_OFF_MODULES
        disposition = "action_off" if is_action_off else "action_off"
        sink_id = s.sink_id  # == f"{module}::{function}" — matches the scanner
        row = {
            "sink_id": sink_id,
            "module": s.module,
            "enclosing_function": s.function,
            "def_line": s.def_line,
            "call_line": s.call_line,
            "subcommands": list(s.subcommands),
            "effect_family": FAMILY.get(primary, "git_mutation"),
            "destructive_level": DESTRUCTIVE.get(primary, "medium"),
            "disposition": disposition,
            "global_effect_key_recipe": f"git:{primary}:{s.module}:{s.function}",
            "source_anchor": s.source_anchor,
            "owner": "m10-inventory",
            "reason": (
                "Bake-off worktree / patch-apply / CLI worktree-reset operations "
                "are lower-urgency than core chain/loop paths; controlled WBC "
                "enablement deferred to M11 (Step 13E9)."
                if is_action_off
                else "Production Git mutation sink; routing through the WBC/action "
                "adapter is performed by a later numbered shard (Steps 13E2-13E8). "
                "Remains action-off throughout M10 (SD3)."
            ),
            "expiry": "M11",
            "bypass_test_id": f"m10_git_bypass::{module_short}::{s.function}",
            "overflow_shard": "13E9" if is_action_off else "13E1",
        }
        rows.append(row)
    return rows


def main() -> None:
    rows = build_rows()
    # Build per-module sink-id index for the overflow gate; every inventoried
    # module is present even when it contributes zero sinks.
    by_module: dict[str, list[str]] = {relpath: [] for relpath in MODULES.values()}
    for r in rows:
        by_module.setdefault(r["module"], []).append(r["sink_id"])

    doc = {
        "schema": "m10.git-mutation-sinks.v1",
        "generated_by": "tests/m10/generate_git_mutation_inventory.py",
        "scanner": "tests/m10/git_sink_scanner.py",
        "milestone": "M10",
        "notes": [
            "Every mutating git call site across the 9 listed modules is inventoried.",
            "A static AST scanner (git_sink_scanner.py) is the source of truth; the",
            "gate test re-scans and asserts this file is complete and not stale.",
            "All rows are disposition=action_off for M10 (SD3). Bake-off/CLI rows",
            "are the Step 13E9 action-off set; core chain/loop/auto rows await a",
            "numbered routing shard (Steps 13E2-13E8).",
        ],
        "modules_inventoried": sorted(MODULES.values()),
        "module_sink_index": by_module,
        "sinks": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=False)
        fh.write("\n")
    print(f"wrote {OUT} with {len(rows)} sinks across {len(by_module)} modules")


if __name__ == "__main__":
    main()
