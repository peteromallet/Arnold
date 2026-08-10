Working directory: /Users/peteromalley/Documents/Arnold

Task: Adversarial edge review for adding sequential fallback model lists to Megaplan. Find edges outside the obvious profile+worker code: state persistence, receipts, audit query, chain/cloud specs, bakeoff, calibration, policy settings, preflight, cost reporting, active_step/status, resume, and user-facing docs.

Inspect at least:
- arnold_pipelines/megaplan/types.py
- arnold_pipelines/megaplan/receipts/*
- arnold_pipelines/megaplan/cloud/preflight.py
- arnold_pipelines/megaplan/cloud/cli.py
- arnold_pipelines/megaplan/chain/spec.py
- arnold_pipelines/megaplan/calibration/ledger.py
- arnold_pipelines/megaplan/policy_settings.py
- arnold_pipelines/megaplan/observability/*
- relevant tests.

Return:
- hidden breakage risks
- required telemetry/state fields
- migration/backcompat recommendation
- cloud/chain/bakeoff implications
- minimum doc updates

Keep final answer under 1000 words. Take a position.
