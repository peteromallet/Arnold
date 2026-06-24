# live-supervisor

Runtime: `live-supervisor` is a native-default converted pipeline. Fresh runs
through `megaplan run live-supervisor ...` or
`arnold pipelines run live-supervisor ...` persist runtime ownership in
`state.json.runtime_envelope.runtime` and `state.json.meta.executor`. During
the M7 deprecation window, the derived graph remains available as a
compatibility fallback: pass `--runtime graph` (or the deprecated
`--executor graph`) for a fresh run that must use the graph executor. Existing
graph-born plan directories keep resuming on graph. Native-born runs resume on
native, and corrupt native cursors fail closed rather than silently falling
back to graph.

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
