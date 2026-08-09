# Luna explorer 6 — observer, snapshot, and notification bounds

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Return under 1200 words.

Read `sol-p2-framing-result-20260804.md`, `sol-final-plan-20260804.md`, and
`luna-synthesis-20260804.md`. Known symptoms: `/whats-cooking` returned stale
or duplicate running/attention messages; live queries could hang; watchdog
snapshots were stale/corrupt; an unmatched old LLM call survived a blocked
transition; `latest_failure` was absent from the human-facing status.

Audit `cloud/status_snapshot.py`, `cli/status_view.py`, hot-context/resident
status loaders, heartbeat/write-error sidecars, watchdog snapshot writers,
notification formatting/deduplication, and live fallback calls.

Specify a snapshot-first, deadline-bounded projection contract: authoritative
cursor/attempt ID, generation, freshness, heartbeat age, corruption/write
error, live-process proof, and explicit stale/unavailable labels. Recommend
how to collapse repeated notifications by incident occurrence/fingerprint and
how terminal/block transitions quarantine telemetry. Provide tests for hung
backend, valid cached snapshot, stale snapshot, corruption, write error,
dead-PID, unmatched LLM call, and repeated identical notification.
