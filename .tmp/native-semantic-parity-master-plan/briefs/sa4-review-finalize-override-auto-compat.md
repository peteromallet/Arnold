Working directory: /Users/peteromalley/Documents/Arnold

You are SA4: Review/finalize/override/auto/compat audit.

Read source files directly. Do not modify files.

Scope:
- Review outcome state machine, rework caps, parallel review, no-review terminal, force-proceed.
- Finalize baseline fallback and failure routes.
- `_OVERRIDE_ACTIONS` or equivalent dispatch, override matrix, CLI/control routing.
- `auto.py` next-step derivation and retry/escalation policies.
- Everything `arnold_pipelines/megaplan/_compatibility.py` still load-bears at runtime.

Return:
- File:line-cited findings only.
- Name which S5/S6/S7 gate should enforce each finding.
- Commands you ran, if any.
- Keep it under 1100 words.
