# Arnold Cloud Rollout Notes

This document records settled deployment decisions for the Arnold cloud repair-system
components (watchdog, progress auditor, repair loop, meta-repair loop, and GitHub sync).
It is a reference for operators, not an automated deployment manifest.

## Editable-install branch propagation

Arnold runs from an **editable install** (`pip install -e .`) in the cloud container.
The editable-install branch is `editible-install` (note the intentional spelling). When
a repair or audit cycle fixes a source bug, it pushes to `origin/editible-install`. The
watchdog's `sync_editable_source_branch` function and the meta-repair loop's
`apply_install_sync` step pull that branch into the container, and the live editable
install immediately reflects the change — no restart, no rebuild, no new deployment
artifact.

This is the **only** propagation path for cloud repair-system fixes. There is no CI
pipeline, no Docker image rebuild, and no orchestrated rollout. The editable install
makes the checked-out source tree the live runtime, so a `git checkout editible-install`
(or a `git pull` from that branch) followed by a successful `pip install -e .` (or the
equivalent `uv pip install -e .`) is the complete propagation sequence.

**Key invariants:**
- The container's `/workspace/arnold` checkout is the live editable-install root.
- `pip install -e` is re-run after any branch switch or pull that changes
  `pyproject.toml` dependencies or entry points.
- The watchdog's `sync_editable_source_branch` does NOT perform `pip install -e`
  itself; it only syncs the git branch. The install step is handled by the
  `apply_install_sync` function in the meta-repair loop.

## Six-hour timer propagation path

The progress-auditor is triggered by a host-side systemd timer:
`megaplan-progress-audit.timer` with `OnUnitActiveSec=6h`.

**Propagation chain:**
1. `megaplan-progress-audit.timer` fires every 6 hours.
2. `megaplan-progress-audit.service` (Type=oneshot) executes
   `/usr/local/bin/arnold-progress-auditor` on the host.
3. The wrapper detects it is outside the container (`/workspace/arnold` not present),
   runs `docker inspect` to confirm the container is available, then
   `docker exec`-s into `megaplan-cloud-agent` and re-invokes itself.
4. Inside the container, the wrapper discovers active workspaces, gathers evidence,
   dispatches Codex audits via DeepSeek subagents, records findings to the incident
   ledger, triggers GitHub sync for persistent problems, and assembles a JSON+Markdown
   report.

**No new systemd unit is required.** The existing `megaplan-progress-audit.service`
and `megaplan-progress-audit.timer` are sufficient. The audit cadence is configurable
via `MEGAPLAN_AUDIT_WINDOW_HOURS` (default 6) and the timer's `OnUnitActiveSec`.

## Runtime freshness evidence: `install_sync.applied`

The `six_hour_auditor` module checks install-sync freshness as part of its per-layer
findings. Evidence of a successful install sync is recorded in the incident ledger
as an `install_sync.applied` event (via the bridge helper). The auditor's
`_install_sync_finding` function inspects the brief's `install_sync` section and
emits either:

- `install_sync_applied` — the install sync ran successfully within the window.
- `install_sync_stale` — the install sync is older than the configured threshold
  (default: 6 hours). The auditor recommends `install_sync.retry`.

The meta-repair loop's `apply_install_sync` step records its result into the
incident ledger via bridge events. The auditor then reads this evidence from the
projection brief rather than re-running git commands — the ledger is the source of
truth for freshness.

Operators can verify install-sync freshness at any time by inspecting the most recent
`install_sync.applied` or `install_sync_failed` event in the incident ledger, or by
checking the meta-repair loop's `INSTALL_SYNC_JSON` output.

## Deferred: `events.jsonl` compaction and rotation

The incident ledger's `events.jsonl` is an append-only JSON-lines file that grows
monotonically. Current behavior:

- All events are appended to a single `events.jsonl` per workspace.
- Projections are rebuilt from the full event stream on each read.

**Deferred tradeoff:**
Compaction (rewriting `events.jsonl` to remove superseded or duplicate events) and
rotation (splitting into time-windowed or size-capped segments) are intentionally
**deferred**. Rationale:

1. **Simplicity wins at this scale.** The event volume per workspace is modest
   (hundreds to low thousands of events per day), and projections are fast enough
   that full rebuilds have not become a bottleneck.
2. **Compaction introduces replay risk.** Rewriting the append-only ledger could
   silently drop events that later projections depend on. The current
   always-append-and-rebuild model guarantees no information loss.
3. **Rotation complicates projection.** Multiple segment files require merge logic
   in the projection layer, adding complexity without a demonstrated need.

**When to revisit:**
- If event volume grows beyond ~10K events per workspace per day.
- If projection rebuild time exceeds ~500ms on the target hardware.
- If disk usage from `events.jsonl` becomes a constraint (current growth rate is
  well under 1MB/day).
- If an operator observes that the majority of events are superseded/duplicate
  (compaction would yield significant space savings).

**Planned approach when implemented:**
- Compaction: periodic (daily or after each audit cycle), write to a new file,
  atomically rename when complete, keep one backup.
- Rotation: daily segments named `events-YYYY-MM-DD.jsonl`, projection reads all
  segments in order.
- Both gated behind a feature flag (`ARNOLD_EVENTS_COMPACTION_ENABLED`) defaulting
  to off.

## GitHub sync invocation

GitHub sync is invoked from the six-hour auditor wrapper path (via
`record_incident_audits` in the `arnold-progress-auditor` wrapper), but the
`github_sync.py` module is also importable as a standalone Python entry point
for manual publication runs:

```bash
python -m arnold_pipelines.megaplan.cloud.github_sync
```

This covers both the automated audit-cycle publication and the operational need
for ad-hoc manual sync runs.

## No new systemd units

All cloud components reuse the existing systemd units:

| Component | Systemd Unit | Timer |
|-----------|-------------|-------|
| Watchdog | (host cron or manual) | N/A |
| Progress Auditor | `megaplan-progress-audit.service` | `megaplan-progress-audit.timer` (6h) |
| Repair Loop | Dispatched by watchdog | N/A |
| Meta-Repair Loop | Dispatched by watchdog | N/A |
| Repair Trigger | `megaplan-repair-trigger.service` | N/A |

No additional systemd units were added for the M3 auditor, GitHub sync, or
hardening work. The existing timer and oneshot service are sufficient.
