# Watchdog snapshot staleness — bug + finalized fix plan

**Status:** sense-checked by Codex (GPT-5.5, high reasoning). Diagnosis confirmed;
five corrections folded in below. This document is the single source of truth for
implementation.
**Scope:** eliminate the class of bug where the Discord resident answers broad
status ("is it improving?", "still cookin?") from a **frozen** cloud-status
snapshot that contradicts the live per-chain introspect.

## Symptom (2026-07-09)
Resident reported `Snapshot 2026-07-09T16:11:40Z: 0% overall, 0/2 sprints done,
… initialized` on messages at **18:28 and 18:41** — identical, 2.5h-stale
timestamp — while the "check in detail" path showed the chain actively advancing
(prep 16:20 → plan 16:23 → critique 16:23:36).

---

## 1. The two data paths

Broad-status answers and the detailed introspect read **different sources**.

- **Snapshot path** — `resident/profile.py:592` `_load_cloud_status_snapshot()`
  forks on `status_snapshot.is_trusted_container()` (`status_snapshot.py:71`):
  - trusted → `build_cloud_status_snapshot()` fresh every message, `generated_at
    = now` (`status_snapshot.py:163`); also rewrites the shared cache
    (`profile.py:617`).
  - not trusted → `load_cloud_status_snapshot(path, max_age_s=…)` reads the
    cached `/workspace/.megaplan/status/cloud-status.json` (`config.py:119`).
- **Deep-look path** — `local_epic_chain_state` (`profile.py:536`) +
  `live_cloud_chain` (`profile.py:556`) read the runner's live files.

Hot context is **not memoized** — each burst calls `load_hot_context()` →
`_load_cloud_status_snapshot()` directly (`runtime.py:223`). So freshness *is*
attempted per message; the freeze is purely the cache-read path.

## 2. The airtight tell + what stalled
A fresh build always stamps `generated_at = now`; the resident served `16:11:40Z`
on two messages 30 min apart. So the resident is on the **cache-read path**
(`is_trusted_container()` False) and **no successful shared-file refresh by the
watchdog *or* a trusted resident has occurred since 16:11.** (Correction: the
shared file is written by both the watchdog sweep *and* trusted resident turns,
not watchdog-only.)

Why the writes stopped — **not yet disambiguated, needs the box** (path mismatch
ruled out: both sides resolve to `/workspace/.megaplan/status/cloud-status.json`):
1. Watchdog tmux loop dead/hung.
2. `build_and_write_snapshot` throws every sweep and is swallowed.
3. `scan_once` hung in `repair_trigger_scan` / git sync / pip refresh **before
   the first snapshot write**. (Correction: repairs themselves are *not* in-band
   — `arnold-repair-loop` is backgrounded `setsid … &` at `:4011`, asserted by
   `tests/cloud/test_watchdog_wrappers.py:3886`.)

**Confidence:** ~100% on the mechanism; ~50/50 dead-loop vs write-failing.
Disambiguation (box): `tmux has-session -t watchdog`; `ls -l
/workspace/.megaplan/status/cloud-status.json`; `tail /workspace/watchdog.log`.

## 3. Why a stall is even possible (structural holes)
1. **Watchdog only auto-starts at container boot** (`entrypoint.sh.tmpl:188`); the
   loop is otherwise unsupervised inside the container. **`ensure-megaplan-watchdog`
   can restart it but has no committed `.service`/`.timer`** — so when the tmux
   session dies, nothing brings it back. ← this is the key "stays dead" gap.
2. **No snapshot write at sweep *start*** — `scan_once` writes in the
   missing-marker branch (`:7101`) and at completion (`:7156`), but all the
   heavy/stall-prone work (`repair_trigger_scan`, git sync, pip refresh) runs
   *before* the completion write.
3. **Write failures swallowed silently** (`|| log "… write failed"`), every sweep.
4. **No consumer-facing freshness alarm** — a stale snapshot yields only a
   *degraded string* (`_SNAPSHOT_MAX_AGE_S = 2h`, `profile.py:66`) the prompt
   merely *suggests* surfacing; the LLM under-surfaced it and presented stale
   numbers as authoritative.
5. Brittleness: per-message freshness gates on `MEGAPLAN_TRUSTED_CONTAINER=1`
   (`entrypoint.sh.tmpl:21`); a resident restart that drops it silently degrades.

---

## 4. Finalized solution (P0–P3) — implement verbatim

### P0 — live-per-message independent of the env var
- `status_snapshot.py`: add `has_local_markers(marker_dir=None) -> bool` =
  canonical marker dir exists. Keep `is_trusted_container()` unchanged (write/trust
  semantics). Gate on the **absolute** `/workspace/.megaplan/cloud-sessions` so a
  laptop can't falsely build fresh.
- `profile.py:607`: build fresh `if status_snapshot.has_local_markers()`; gate the
  best-effort shared-file write on `is_trusted_container()`.
- Visibility: add `trusted_container`, `has_local_markers`, `status_snapshot_path`
  to `resident_runtime` (`profile.py:476`) and to the tmux resident start echo
  (`entrypoint.sh.tmpl:200`).

### P1 — impossible to serve stale numbers silently
- `profile.py:623`: when the cache read returns a stale reason, return a
  **sanitized** snapshot — `sessions=[]`, zeroed `summary`, original
  `generated_at`, plus top-level `stale_banner`:
  `WATCHDOG STALE — last snapshot Ns old; numbers withheld; use
  live_cloud_chain/local_epic_chain_state as degraded fallback.`
  Do **not** keep stale numbers behind the banner.
- `profile.py:436` prompt block: require the verbatim `stale_banner` first when
  present.

### P2 — watchdog writes early, bounds its hangs, escalates write failures
- Add `write_watchdog_heartbeat()` (→ `/workspace/.megaplan/status/watchdog.heartbeat`)
  near `:1498`.
- In `scan_once`, immediately after `log "scan start"` (`:7088`), call
  `write_watchdog_heartbeat` **and** `write_status_snapshot` *before*
  `repair_trigger_scan`/sync.
- Bound git fetch/pull/push and pip refresh with `timeout` under new envs
  `CLOUD_WATCHDOG_SYNC_TIMEOUT_SECS` / `CLOUD_WATCHDOG_INSTALL_REFRESH_TIMEOUT_SECS`
  (do **not** reuse `CODEX_TIMEOUT`=7200).
- Replace the swallowed `|| log "… write failed"` with counted escalation: a
  `STATUS_DIR/snapshot-failures.json` counter; after 3 consecutive failures write
  `cloud-status.write-error.json` + alert; reset on success.

### P3 — actually supervise the watchdog
- Add `cloud/systemd/megaplan-watchdog-ensure.service` + `.timer` (1-min cadence)
  beside `ensure-megaplan-watchdog`. Keep external supervision; do not wrap the
  infinite loop in another loop yet.
- **Heartbeat-aware restart (Codex sense-check #2 refinement).** Make
  `ensure-megaplan-watchdog` revive a *hung* watchdog, not just a missing one:
  even when `tmux has-session -t watchdog` succeeds, if
  `/workspace/.megaplan/status/watchdog.heartbeat` (written by P2 at each sweep
  start) is older than `MEGAPLAN_WATCHDOG_STALE_HEARTBEAT_MIN` (default 130m ≈
  2× the 60m interval + grace), `tmux kill-session` it and restart. This is the
  actual failure mode — a loop alive in tmux but not sweeping.
- Also bound the first-checkout `git clone` with `timeout "$SYNC_TIMEOUT_SECS"`
  (fetch/pull/push/pip were already wrapped; the initial clone was missed).

### Deferred / out of scope
- Do not redesign the cloud status CLI (it has its own 5-min stale fallback,
  `cli.py:5035`).
- Discord admin paging deferred until P1 sanitization is proven.

---

## 5. Tests
- `tests/cloud/test_status_snapshot.py`: `has_local_markers` is env-independent;
  `is_trusted_container` unchanged.
- `tests/resident/test_megaplan_initiatives.py`: marker-dir-without-env builds
  fresh but does not write the cache; stale cache strips sessions/summary and
  emits the banner.
- `tests/cloud/test_watchdog_wrappers.py`: scan-start writes heartbeat + early
  snapshot; write failures create/reset the counter sidecar; git/pip are
  timeout-wrapped; ensure timer/service files exist.
- Run: `pytest tests/cloud/test_status_snapshot.py
  tests/resident/test_megaplan_initiatives.py
  tests/cloud/test_watchdog_wrappers.py`.

## 6. Operator follow-up (out of code scope)
On the box: disambiguate §2 candidates and restart whatever is stalled; deploy
this change; confirm the new ensure-timer is enabled (`systemctl enable --now
megaplan-watchdog-ensure.timer`).

**Deploy note (Codex sense-check #2).** The cloud `systemd/` files
(`megaplan-watchdog-ensure.{service,timer}`, `ensure-megaplan-watchdog`) are
host-side artifacts — like the existing `megaplan-resident-ensure` /
`megaplan-progress-audit` units, they are intentionally NOT in the Python wheel
(`pyproject.toml` packages only `agentbox/systemd/*`). They must be installed by
the host provisioner: the `.service`/`.timer` to `/etc/systemd/system/`, the
`ensure-megaplan-watchdog` script to `/usr/local/bin`, then
`systemctl enable --now megaplan-watchdog-ensure.timer`. Whatever already deploys
the resident-ensure pair deploys these too (same directory).

## 7. Sense-check log
- **#1 (plan), Codex high-reasoning:** diagnosis confirmed; 5 corrections folded
  into §2/§3/§4 (shared file also written by trusted resident; repair is
  backgrounded not in-band; `ensure-*` had no committed timer; hot context not
  memoized; P0 safe via absolute marker path).
- **#2 (execution), Codex high-reasoning:** P0/P1 faithful; flagged 3 SHOULD-FIX
  + 1 NIT. Addressed: heartbeat-aware supervision (P3), `git clone` timeout,
  `has_local_markers` → `is_dir()`; packaging documented as pre-existing host
  deploy model (not a regression). New tests added for each.
