You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate signals around ordinary repair loop custody and effectiveness. Include repair-data sidecars, attempts, iteration history, current_attempt_id, attempt logs, repair-progress markers, needs-human records, run dirs, repeated same diagnosis, repair without relaunch, repair_running ghosts, and repair index reconciliation.

Inspect:
- arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop
- arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- arnold_pipelines/megaplan/cloud/repair_contract.py
- tests/cloud/test_repair_contract.py
- cloud repair data under /workspace/.megaplan/cloud-sessions/repair-data read-only

Return candidate signals with evidence paths and false-positive guards. Include both low-level repair-loop signals and high-level "is the repairer helping or wasting cycles?" signals.
