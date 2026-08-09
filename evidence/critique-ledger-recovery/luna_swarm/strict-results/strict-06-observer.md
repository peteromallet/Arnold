The bounded fix is to make the resident read model strictly snapshot-first:

- Load the canonical snapshot and derive `plan_activity_summary` immediately.
- Run `live_cloud_chain` only as an optional, deadline-bounded degraded fallback; it must never delay or replace the snapshot response.
- Surface `stale_banner`, `cloud-status.write-error.json`, and watchdog heartbeat age in notifications as explicit `stale/unavailable` states.
- Preserve last-known state, but never present stale `summary`, progress, or session data as current.

Remaining gap: the watchdog has bounded sync/install timeouts, atomic snapshot writes, heartbeat, and write-failure sidecars, but `load_cloud_status_snapshot()` checks only `generated_at`. It does not incorporate heartbeat or write-error sidecars, and `load_hot_context()` awaits live cloud status before completing. Consequently, a hung SSH/status backend can still make observer responses time out, while repeated snapshot-write failures may remain merely “fresh” for up to the two-hour resident freshness window.

Acceptance tests:

1. A hanging `cloud_status_chain` backend still returns the cached snapshot within the observer deadline, labeled degraded only if fallback is unavailable.

2. A snapshot older than the freshness limit returns the verbatim stale banner, empty authoritative sessions/summary, and no progress numbers in resident notifications.

3. Three consecutive watchdog snapshot-write failures cause observer status to report `stale/unavailable` immediately from the write-error sidecar, even when `generated_at` is otherwise recent.

4. A fresh snapshot plus an older or corrupted live-chain response produces the snapshot-derived notification and records the live fallback as bounded, degraded evidence rather than replacing the read model.
