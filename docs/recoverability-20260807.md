# Arnold box recoverability — Phase-0 evidence gate (2026-08-07)

**Status:** evidence captured, restore drill green, artifacts off-box.
**Box:** `arnold-agentbox-01` = root@159.69.51.216 (Ubuntu 6.8.0-136, docker + containerd).
**Owner of record:** fixer-unification project (implementation agent), worktree branch `fixer/fixer-unification-20260807`.
**Generated:** 2026-08-07 (UTC), from a read-only process-level census of the live box plus off-box bundle capture.

This document is the Phase-0 output of `docs/runtime-and-fixer-unification-design-20260807.md` — the evidence-and-restore gate that the external design review approved. It exists so Phases 1–6 can be built on a proven map of what is actually running and a proven way to restore it.

---

## 1. Execution map (the census) — what is actually running

Method: read-only probes over SSH (`ps`, `/proc/<pid>`, `findmnt`, `stat`, `docker ps/inspect`, `git -C` read-only, `systemctl list-timers/status`). No mutations. Two probes ~5 min apart; one live commit landed mid-census (`87a912beb` → `49af598c0`), which is itself evidence that the box runs a live repair loop.

### Host
- `Linux arnold-agentbox-01 6.8.0-136-generic x86_64`; one 601G root fs, 51% used (301G), climbing during census (304G second sample).
- Runtime-candidate trees: exactly one root, `/opt/megaplan-cloud/workspace/runtime-candidates` = container `/workspace/runtime-candidates`. **114 tree dirs, 57G.**

### Containers (13 total, 2 running)
| container | image (sha256) | status | notes |
|---|---|---|---|
| `megaplan-cloud-agent-resident-only` | `78474208a513…` | Up 3 days | resident Discord listener + schedule; **RO-binds the recovery runtime over the `-live` tree** (see §4) |
| `megaplan-cloud-agent-critique-ledger-v3` | `2b6b18caeaf9…` | Up 2 days | isolated chain-runner HTTP server (8080) |
| `megaplan-cloud-agent` | `de249469ec93…` | **Exited (1) 4 days ago** | dead container — must-not-revive; references to it should be retired |
| 9× `megaplan-cloud-agent-finite-canary[-2..-16]` | local | Exited 137/143 | spent canaries |

### Live process map (host view)
| PID | role | command line / resolution |
|---|---|---|
| 69508→69556 | resident listener | `python3.11 -P -m arnold_pipelines.megaplan resident discord --listener-only --recovery-seed /run/…/launch-seed.json --mode production --store-root /workspace/arnold/.megaplan/resident`; cwd `/workspace/arnold`; fds → `delivery-effects.sqlite3` |
| 1231693 | **ad-hoc scheduler loop** | `while true; do cd <r7 tree> && python3 -P -m arnold_pipelines.megaplan resident schedule run-once; sleep 120; done` — this is the REAL scheduling; systemd timer fails (below) |
| 1437464→1437466→1437482→1437483 | watchdog chain | launcher `source .cloud-hot-env; ARNOLD_SRC=<r7 tree>` → `arnold-watchdog` snapshot re-point (`MEGAPLAN_AUDIT_ARNOLD_SRC`/`MEGAPLAN_RUNTIME_SRC` → **`-live` tree**, `ARNOLD_WATCHDOG_SNAPSHOT_ACTIVE=1`) → lock-holder python (`/workspace/.megaplan/watchdog.lock`) |
| 80183→80184 | repair-trigger (respawn during census) | `…-live/…/wrappers/arnold-repair-trigger --marker-dir /workspace/.megaplan/cloud-sessions --repair-data-dir …/cloud-sessions/repair-data` (99% CPU at capture) |
| 1259022→1259092 | chain-runner health server | `MEGAPLAN_ISOLATED_CHAIN_RUNNER=1` http.server in critique-ledger-v3 container |

Loaded module resolution: `nsenter` import probes failed (`python3` not on ns PATH); editable pointer evidence instead — the `-live` supervisor venv site-packages contains real `arnold`/`arnold_pipelines` dirs (non-editable copy) while the `-live` top venv and container image hold `_editable_impl_arnold.pth`. `PYTHONPATH` of the repair-trigger includes the **`-live` tree path** — i.e. the shadowed tree. [INFERENCE, marked]

### The three live code lines (census-verified)
| tree | HEAD | branch | dirty | design-doc claim | verdict |
|---|---|---|---|---|---|
| `arnold-4ed98585…-live` (host) | `44e249df3` | detached | 0 | host 44e249df3 | **CONFIRMED** |
| RO recovery copy (container view of `-live`) | `4ed98585f` | — | — | container 4ed98585 | **CONFIRMED** |
| `arnold-r7-fresh-child-20260805` | `87a912beb` → `49af598c0` | `fixer/critique-epoch-invalidation-20260806` | 7 (untracked .bak files) | table said f5a38311; §1 said 87a912beb | **table CONTRADICTED / narrative CONFIRMED + moved during census** |
| `/workspace/arnold` (data root) | `3299a4f0` | `main` | 1 | table said 7d8426ca | **CONTRADICTED** |

`87a912beb` exists in exactly **one** box tree (`arnold-r7-fresh-child-20260805`), and the build branch `fixer/critique-epoch-invalidation-20260806` exists only there.

### Scheduler / timers
- `megaplan-resident-schedule-runner.timer` (systemd, **enabled, active**) fires every 60s → service **fails every minute**: `ExecStart=/usr/local/bin/arnold-resident-schedule-run-once-r6` (via drop-in `10-r6-runtime.conf`), which pins `expected_head=234ac3524da29…` ≠ actual HEAD → exit 1. **The stale pin is the failure cause.**
- Real scheduling = the ad-hoc 120s bash loop (PID 1231693). No crontab entries.
- Masked units (symlink→/dev/null, Aug 3): `megaplan-repair-trigger.{path,service}`, `megaplan-resident-ensure.{service,timer}`, `megaplan-watchdog-ensure.{service,timer}`, `megaplan-progress-audit.{service,timer}`.
- `CLOUD_WATCHDOG_META_REPAIR_BIN=/usr/local/bin/arnold-meta-repair-loop` — **referenced but the file does not exist on the box** (meta-repair exec would fail if triggered). Surfaced as a structural finding.

### Fixer flows — two stores, one store is prompt-level coordination
- Reactive (on-failure): watchdog → repair-trigger → repair-loop; markers in `/workspace/.megaplan/cloud-sessions` (+ `repair-data/`); models overridden to **`hermes:zhipu:glm-5.2`** via `.cloud-hot-env` (`MEGAPLAN_META_MODEL`, `CLOUD_WATCHDOG_REPAIR_{INVESTIGATOR,BROKERED_INVESTIGATOR,OWNER}_MODEL`).
- Proactive (hourly): schedule store `/workspace/arnold/.megaplan/resident` (store-root) + `/workspace/.megaplan/ops/schedules` + `schedule-inputs`; superfixer `sched_superfixer_hourly_v2` definition, `deepseek-v4-flash`, launched as managed subagent.
- **The two flows register in different stores** (probe-2). Coordination is prompt-level; can race — design-doc claim CONFIRMED.
- `.megaplan/fixer-sessions/` does **not** exist on the box (design-doc swarm stage expects it).
- `OPENROUTER_API_KEY` alias: present only as a **commented-out** line in `.cloud-hot-env` — the stale 429 alias is neutralized, not active.

### Sync flags
- `CLOUD_WATCHDOG_SYNC_ENABLED=0`, `MEGAPLAN_AUDIT_RECOVERY_SYNC_ENABLED=0` — both in `.cloud-hot-env` AND in live watchdog-chain process env. `CLOUD_WATCHDOG_SYNC_BRANCH=editible-install`.

### Shadow mount (proven by content/mount identity)
- Bind: `/var/lib/arnold/megaplan-resident-recovery/277d2e6dbc…/critique-4ed-pause-live-20260804-1246/runtime` → `/workspace/runtime-candidates/arnold-4ed98585…-live` **rw=false** (docker inspect).
- dev/ino: host tree `dev=2049 ino=20349117` vs container view via `/proc/69508/root` `dev=2049 ino=18668571` = the recovery copy's inode. **The resident executes the RO recovery copy, not the host tree. Editing the host tree does not change what runs — shadow PROVEN, exactly as the design doc claims.**
- Recovery root holds 10+ `*/runtime` snapshots under `/var/lib/arnold/megaplan-resident-recovery/277d2e6dbc…/`.

### Concurrency + env size (probe-5)
- 2 running containers; 2 distinct live runtime trees (`r7-fresh-child` + `-live`) plus `/workspace/arnold` data root → matches design's "2–3 concurrent epics".
- Per-runtime env ≈ **2.2G** (tree ≈ 975–998M + venv ≈ 1.2G at `/workspace/runtime-venvs/`); largest tree 1.9G; 114 trees = 57G. Container writable layers: resident 12.1G, v3 2.12G.

---

## 2. Recoverability surface (captured off-box)

Bundles + dirty-state artifacts + checksums. **All artifacts copied off-box to the operator's machine; checksums verified on-box and off-box (identical).** "Off-box" here = the operator Mac; a second off-site copy is recommended (the design's clean-room restore drill now makes one more bundle copy cheap).

### Git bundles (`git bundle create --all`, `git bundle verify` = "complete history", sha1)
| artifact | size | sha256 (off-box re-verify) | captures |
|---|---|---|---|
| `arnold-live-20260807-r7-fresh-child.bundle` | 840M | `32555d4a88a525e033b005b4ee8b9c19806e7bf6d94d45cb4239a3b7fa0aab38` | r7 tree full history incl. build branch `fixer/critique-epoch-invalidation-20260806` @ `49af598c0`, `87a912beb`, superfixer-debug skill, ledger fixes |
| `arnold-live-20260807-4ed-live.bundle` | 841M | `d3d800accb150a920e33f87e1e895c6414738cceff48c08618631ee2a1e18d01` | `-live` tree full history @ `44e249df3` (incl. ancestor `4ed98585f` = RO recovery copy HEAD) |
| `arnold-live-20260807-workspace-arnold.bundle` | 831M | `b0cda2d9a5d16a0b5fa49fabad0af460cb31b158d3d81c92d67d328f4f94a134` | data-root tree @ `3299a4f0` + 188 box refs (resident/schedule/custody branch history) |

### Dirty-state / runtime artifacts (bundles do NOT include these)
| artifact | sha256 | contents |
|---|---|---|
| `r7.status.txt` | `826d6be91fca885103f9a8094f7b0b24cbab7a3afb0cdd93a7de6bcb9d7a32a5` | 7 untracked `.bak*` files in r7 tree |
| `r7-untracked.tar` | `7b2aa8470d0e752456c3e99cb50ab699d9ff9d8b0eb4c8d20e43a8d29eb65d5e` | the untracked files themselves (1.7M) |
| `r7.patch` | empty (e3b0c442…) | no tracked modifications |
| `4ed.status.txt` | empty | `-live` tree clean |
| `wa.status.txt` | `d6c3b857f9aa1e122070781b6fe336cfeffa1214d080f47d75ae06563a0f88d8` | 1 untracked file in `/workspace/arnold` |
| `wa-untracked.tar` | `80233590fdf10eedef17bc2c2d50df2f989321b87e7d98dce571d78d63d5f2f0` | the untracked file (70K) |
| `arnold-systemd-units.tar` | `a696f173033edfb231616c00d7c44efa1efa45a62c64ca6b19cd7e68412be30f` | schedule-runner unit + timer + drop-in |
| `cloud-hot-env-names.txt` | `24db6729c2b1810d77404995fa1bcf9d502ab0d0f0fefa64b03d101ba8994b99` | 70 env var **names** (values masked; the live env file never leaves the box) |
| `container-images.txt` | `d270d49bacefabcaf32cf9fe9ba03361618c70f71e326021743ceeaf34e1515c` | container image digests |

Not captured as artifacts (deliberately): secret VALUES (keys/tokens stay on the box), container writable-layer contents (12G resident layer — the immutable image + bundles reconstruct the code; writable state is schedule/marker/data, captured in the next section).

### Mutable state inventory (paths, not contents)
- Schedule store: `/workspace/arnold/.megaplan/resident` (+ `scheduled_jobs`), `/workspace/.megaplan/ops/schedules`, `/workspace/.megaplan/schedule-inputs`.
- Marker store: `/workspace/.megaplan/cloud-sessions` (+ `repair-data`, `repair-queue`).
- Delivery effects: `/workspace/arnold/.megaplan/resident/delivery_effects/delivery-effects.sqlite3`.
- Data store root: `/workspace/arnold` (git tree @ `3299a4f0`, `main`).
- Resident recovery snapshots: `/var/lib/arnold/megaplan-resident-recovery/277d2e6dbc…/` (10+ RO runtime copies).
- Secrets: `/opt/megaplan-cloud/workspace/.cloud-hot-env` (mode 600; 17 backups), `/root/.hermes/.env`, `/workspace/.codex/auth.json` + `/workspace/.creds/`.

### Origin-resolvability of the four live SHAs (post-push)
| SHA | origin-resolvable via |
|---|---|
| `44e249df3` (-live host) | tag `box-snapshot/4ed-live-20260807` |
| `4ed98585f` (RO recovery copy) | ancestor of `44e249df3` (tag above) + build-branch ancestry |
| `49af598c0` (r7, new HEAD) | branch `fixer/critique-epoch-invalidation-20260806` (fast-forward pushed this session) |
| `3299a4f0` (/workspace/arnold) | tag `box-snapshot/workspace-arnold-20260807` |

All four SHAs also reconstruct locally from the bundles (verified: `git cat-file -t` OK for each; bundle `list-heads` shows the refs).

---

## 3. Clean-room restore drill (measured RTO)

**Drill:** from the r7 bundle alone, on a different machine (operator Mac), rebuild a working runtime and import the fixer seam.

| step | wall time |
|---|---|
| `git clone` from bundle → tree at `49af598c0`, branch `fixer/critique-epoch-invalidation-20260806`, dirty=0 | 15s |
| `python3 -m venv` + `pip install -e .` (full deps, no cache) | 38s |
| import smoke: `repair_lock`, `current_target`, `runtime_attestation`, `fixer_prompt_policy`, `session_markers` all import; `arnold_pipelines.__file__` resolves **inside the restored tree** | <1s |
| **RTO (bundle → working editable runtime)** | **≈ 53s** |

RPO: committed state is fully reconstructable (bundle = complete history); dirty/untracked state captured separately (7 `.bak` files + 1 data-root file), so RPO ≈ 0 for code, with the caveat that the 12G container writable layer and secrets are not in the bundle — those are restored from image + `.cloud-hot-env`/creds (paths listed §2). A full runtime restore (tree + venv + image + secrets) is the standing drill target for Phases 1–6; this session proved the code half end-to-end.

---

## 4. Verification probes (structured, machine-checkable)

The five probes are recorded as code in `arnold_pipelines/megaplan/cloud/probe_records.py` with a CLI (`python -m arnold_pipelines.megaplan.cloud.probe_records`) and tests (`tests/cloud/test_probe_records.py`). Summary:

| id | question | answer |
|---|---|---|
| probe-1 | Do the box trees wire `repair_lock.py`? | **YES** — present in both box runtime trees, used by watchdog/repair-trigger |
| probe-2 | Do both fixer flows register active in the SAME marker store? | **NO** — reactive = `/workspace/.megaplan/cloud-sessions`; proactive = `/workspace/arnold/.megaplan/resident` + ops/schedules; different roots, not proven shared |
| probe-3 | Does the hourly superfixer render policy through `fixer_prompt_policy.py`? | **NO** — reactive-only (meta_repair.py:42-45; repair-loop:7329/7339/7349); zero hits in resident/subagent/worker |
| probe-4 | Schedule-store non-live refs are the only must-not-GC candidates? | **YES** — exactly four (`arnold-2bd0b2d3450` dirty=12, `arnold-6ce6d4eb487` dirty=2, `arnold-74b4e6b992` dirty=2, `arnold-bc0c600c41` dirty=23) |
| probe-5 | Live concurrency + per-epic env size? | 2 containers / 2 live runtime trees + data root; per-runtime ≈ 2.2G; 114 trees = 57G |

Full evidence per probe: see `probe_records.py` (canonical) or the render in this doc's sibling artifact.

---

## 5. Structural findings surfaced (not fixed box-side — candidates landed in-worktree)

1. **`CLOUD_WATCHDOG_META_REPAIR_BIN=/usr/local/bin/arnold-meta-repair-loop` → file missing on box.** If meta-repair is triggered, it fails. Candidate: restore the binary from the r7 bundle (it lives in-tree at `arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop`).
2. **Test drift on the build branch:** `tests/cloud/test_repair_lock_namespace_fencing.py::test_wrappers_fail_closed_on_unknown_and_do_not_reap_pidfile_projection` fails on the pristine build branch (asserts `result.status == "stale"` in `arnold-watchdog`; wrapper lacks it). Pre-existing — verified identical with all session changes stashed. The box watchdog has drifted from the test's contract; surfaced for Phase 3A when the seam is promoted.
3. **The systemd timer + the ad-hoc 120s loop both exist; the timer fails.** Interim fix landed as candidate `arnold_pipelines/megaplan/cloud/systemd/arnold-resident-schedule-run-once-r7` (operator-controlled `expected_head` pin — env → pin file, exit 2 if unpinned; never a baked SHA; Phase-2 target: read from `runtime_manifest.json`, now implemented in-worktree). **Deployment to the box is NOT done** — operator direction for this session: no box-side deployment. The box remains byte-identical to its pre-session state (drop-in reverted to r6, r7 binary + pin file removed, bundle scratch removed — all verified).
4. **`/workspace/arnold/.megaplan/fixer-sessions/` does not exist** although the design's swarm stage expects it — the summary store must be created when the unified seam is promoted.
5. **Design-doc corrections from census:** r7-fresh-child is at `87a912beb`/`49af598c0` (not `f5a38311`); `/workspace/arnold` at `3299a4f0` (not `7d8426ca`); `fixer_prompt_policy.py` IS present in the box trees (design open-Q8 premise false for the box); `OPENROUTER` alias is commented out (not active).

---

## 6. What happened this session (push record)

- Worktree `fixer/fixer-unification-20260807` created off build branch; design-doc pack committed + pushed (`f2acac65d`).
- Build branch `fixer/critique-epoch-invalidation-20260806` fast-forward pushed to origin: `5299c299c…` → `49af598c0b…` (box-only commits `87a912beb` + `49af598c0` now on origin; no force push).
- Snapshot tags pushed: `box-snapshot/r7-fresh-child-20260807`, `box-snapshot/4ed-live-20260807`, `box-snapshot/workspace-arnold-20260807`.
- Bundles + dirty artifacts copied off-box, checksums verified both sides.
- Phase-0 code landed in worktree (`fd9e6015e5`), tests green, restore drill green (RTO ≈ 53s).
- **Phases 1–6 implemented in-worktree (`2965975c4e`)** per the design doc §6 file-changes table — see §8. 108 new tests + 329 adjacent pass; the only failures are 12 pre-existing host-environment ones (`.profile`→missing `.cargo/env`, `/proc`-less heartbeat probe, watchdog-wrapper extraction) verified identical on pristine HEAD.
- **Base branch seeded:** `base/editable-install` @ `49af598c0b` created off the build branch and pushed to origin (Phase 1 — the durable source line; `origin/editible-install` stays the deploy-snapshot mirror, NOT the fixer base).
- **Box NOT mutated this session** (operator direction: no box-side deployment; live repair loop active). Box verified byte-identical to pre-session state after an interim deployment was reverted (drop-in → r6, r7 binary + pin file + bundle scratch removed, unit failing exactly as before).

---

## 7. Phase-0 code delivered in this worktree (this session)

| path | purpose |
|---|---|
| `arnold_pipelines/megaplan/cloud/runtime_census.py` | repeatable read-only process/tree/mount census + markdown render + CLI (`python -m …runtime_census`) |
| `arnold_pipelines/megaplan/cloud/shadow_attestation.py` | content-attestation shadow gate: tree digest (bounded python surface), module `__file__` + digest, mount identity; `refuse_shadowed_target` raises on shadowed/inert targets (design rule 7) |
| `arnold_pipelines/megaplan/cloud/probe_records.py` | the five verification probes as structured records + render + CLI |
| `arnold_pipelines/megaplan/cloud/systemd/arnold-resident-schedule-run-once-r7` | corrected schedule runner: operator-controlled `expected_head` (env → pin file, exit 2 if unpinned), same load-bearing guards as r6, never a baked stale SHA |
| `tests/cloud/test_runtime_census.py`, `test_shadow_attestation.py`, `test_probe_records.py`, `test_schedule_runner_pin.py` | 34 tests, all passing |

## 8. Phases 1–6 code delivered in this worktree (commit `2965975c4e`)

| design §6 path | change | verification |
|---|---|---|
| `cloud/runtime_manifest.py` (new) | schema-v1 manifest: atomic flock R/W, load-by-epic + index, bootstrap-path resolution, content attestation, generation advance with rollback records, promotion journal | `test_runtime_manifest.py` 24 passed |
| `cloud/wrappers/arnold-repair-trigger` | manifest-first repair_bin/meta_bin resolution (`bootstrap_manifest` → env → with_name + deprecation); dispatch untouched | `test_launcher_manifest_conformance.py` 5 passed + py_compile |
| `cloud/wrappers/arnold-watchdog` | PRIMARY/META/TRIGGER bins resolve manifest-first (bash `runtime_manifest_field`), fallbacks preserved; heartbeat already present (not duplicated) | conformance + bash -n |
| `cloud/systemd/megaplan-repair-trigger.service` | pins `ARNOLD_RUNTIME_MANIFEST` bootstrap path | conformance |
| `cloud/repair_lock.py` | fenced durable job state machine added: `pending→running→committing→redriving→done`, dedupe key = chain UUID + failure fingerprint, monotonic fencing epoch, quarantine/reconcile on crash, acknowledge-after-redrive; existing lock API untouched | `test_repair_lock_state_machine.py` 18 passed + `test_repair_lock.py` 34 passed |
| `cloud/wrappers/arnold-repair-loop` | `--mode=reactive\|proactive` seam (reactive byte-identical), `--dry-run` pure-read, proactive = Flash + 3× budget + NO-OP guard | `test_repair_loop_mode_seam.py` 9 passed |
| `cloud/fixer_model_policy.py` (new) | mode+rung→{backend, provider, model, budget} table; Flash rows `gated` (PolicyError without replay approval); hot-env credentials-only validation; `model_policy_sha()` | `test_fixer_model_policy.py` 13 passed |
| `cloud/fixer_prompt_policy.py` | additive: `policy_sha()` + `render_policy_briefing()`; existing fragments byte-identical | `test_fixer_prompt_policy_sha.py` 8 passed |
| `tests/fixer_replay/` (new) | replay harness + 5 canned traces + predeclared non-inferiority thresholds; baseline fixture FAILS the bar (Flash stays gated); live replay opt-in via `FIXER_REPLAY_LIVE=1` | 19 passed + 1 opt-in skip |
| `cloud/wrappers/arnold-runtime-create` (new) | worktree add + push-at-creation (fail loud) + atomic manifest write; slug-exists guard | `test_runtime_lifecycle.py` 12 passed |
| `cloud/wrappers/arnold-promote` (new) | staged CAS promotion (plain push, exit 3 on reject), promotion journal, canary-verification warning ('push is NOT a safe cutover') | lifecycle |
| `cloud/wrappers/arnold-close` (new) | two-phase: verify clean+pushed+no-locks → state=closed | lifecycle |
| `cloud/wrappers/arnold-gc-sweep` (new) | closed-only + origin-resolvable + restore-proven gate; never infers stale; needs-reconcile surfaced; `--dry-run` | lifecycle |
| `base/editable-install` branch | seeded @ `49af598c0b` from build branch, pushed to origin | pushed |

**Not landed (by operator direction, no box deployment):** the r7 runner, the lifecycle wrappers, and the manifest resolver are verified candidates in the worktree only. The box continues to run its drifted pre-session state (timer failing on stale pin, ad-hoc 120s loop, two fixer flows). Promotion = the operator's generation switch, gated on the box's live repair loop standing down.
> **Authority status: non-authoritative.** This document is historical/design record, not a live-authority operator surface (T44 zero-authority migration).
