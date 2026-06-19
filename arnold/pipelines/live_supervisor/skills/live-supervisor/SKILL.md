---
name: live-supervisor
description: "live-supervisor"
---

# live-supervisor

Input: a Snapshot dict passed as `initial_state={"snapshot": <dict>}`. The
snapshot contains a `scan_ts_utc` ISO timestamp and a list of `incidents`, each
with a `plan_entry` and a pre-computed `signal_bundle`.

Output: four JSON artifact files written under the supplied
`RuntimeEnvelope.artifact_root`:

- `classify/classifications.json` — per-incident health category
- `diagnose/diagnoses.json` — per-incident diagnosis and normalized findings
- `repair_decision/repair_decisions.json` — recommended action + allowlist verdict
- `recheck_emit/recheck_emit.json` — `recheck_after` timestamp and resumable flag

The pipeline never sleeps, shells out, or makes network requests. Repair-agent
credentials may be absent; in that case the repair decision degrades to
`no_repair_available` rather than failing.
