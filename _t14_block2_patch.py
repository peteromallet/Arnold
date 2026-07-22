#!/usr/bin/env python3
"""Apply T14 change 6 to batch.py - the blocked_by_prereq evidence."""
from pathlib import Path

path = Path("arnold_pipelines/megaplan/execute/batch.py")
content = path.read_text(encoding="utf-8")

old_block2 = """                "_phase_outcome": "blocked_by_prereq",
                # Attach the typed retry decision so the handler can
                # emit targeted anchor evidence without re-deriving it.
                "_blocked_retry_decision": {
                    "outcome": _retry_decision.outcome.value,
                    "reason": _retry_decision.reason,
                },
            }
            if baseline_deviations:
                response["deviations"] = _deviation_dicts(baseline_deviations)"""

new_block2 = """                "_phase_outcome": "blocked_by_prereq",
                # Attach the typed retry decision so the handler can
                # emit targeted anchor evidence without re-deriving it.
                # M8A T14 -- preserve `failed: <detail>` command/artifact
                # evidence for prerequisite-block traceability.
                "_blocked_retry_decision": {
                    "outcome": _retry_decision.outcome.value,
                    "reason": _retry_decision.reason,
                    "failed": "blocked_by_prereq: prerequisite-blocked tasks prevent dependent execution; review blocked task evidence",
                    "evidence": {
                        "blocked_task_ids": sorted(prereq_blocked_ids or blocked_task_ids),
                    },
                },
            }
            if baseline_deviations:
                response["deviations"] = _deviation_dicts(baseline_deviations)"""

assert old_block2 in content, "Block2 not found"
content = content.replace(old_block2, new_block2)
path.write_text(content, encoding="utf-8")
print("Block2 updated successfully.")
