You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate signals around meta-repair. Include meta trigger correctness, launch success, response verdict parsing, persistence, recursion guard, commit/install sync, ordinary-repair retrigger, and stale/false triggers while target is alive.

Inspect:
- arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop
- arnold_pipelines/megaplan/cloud/meta_repair.py
- arnold_pipelines/megaplan/cloud/meta_repair_policy.py
- arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- /workspace/.megaplan/meta-runs and repair-data/meta on cloud read-only

Return signals and coverage matrix entries. Include what a "good" meta-repair run must prove before the auditor calls it success.
