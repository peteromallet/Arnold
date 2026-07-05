You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate signals about the 6-hour auditor itself: discovery quality, gather coverage, green checks, report-only safety, model dispatch, dedupe/grouping, prompt breadth, report schema, cost/latency, and whether the model saw enough evidence.

Inspect:
- arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- tests/cloud/test_progress_auditor.py
- latest /workspace/audit-reports/*-audit.json on cloud
- arnold_pipelines/megaplan/data/progress_auditor_fix_decision_20260704.md

Return:
- recommended pure gather/report schema
- model-dispatch input schema
- signals that should be computed before any model runs
- data quality/coverage fields
- test fixture ideas

Pay special attention to how the report can nudge model breadth without making the prompt vague.
