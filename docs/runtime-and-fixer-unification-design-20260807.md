# Arnold runtime + fixer unification — design

**Updated:** 2026-08-07 (UTC)
**Status:** design; revised after an external design review (gpt-5.6-sol via codex, 2026-08-07). The review's core verdict is incorporated: **approve a revised Phase 0 only; do not approve Phases 1–6 as written.** Phase 0 must first produce an evidence-and-restore gate (a process-level map of what is actually running + a clean-room restore drill), and the plan must stop coupling four risky changes — runtime migration, deployment, concurrency control, and model/topology replacement — without first proving what is running and how to roll it back.
**Scope:** (1) per-epic runtime isolation off one promoted base; (2) one unified fixer flow for on-failure and hourly backup, with DeepSeek Flash as a *measured* policy choice, structured as a bounded investigator→executor default with swarm→corps only on ambiguity/L2.

**Builds on:** this design builds directly on the box-local branch **`fixer/critique-epoch-invalidation-20260806`** — the active epic's checked-out working branch (of `arnold-r7-fresh-child-20260805`), HEAD `87a912beb`, currently running the watchdog/repair-loop. It carries **box-only** fixer commits (none on origin), including the `superfixer-debug` skill and execute/finalize ledger fixes, that this plan incorporates as its starting point. The base line is seeded from this branch's line (not a stale `f5a38311`), and these commits are pushed + bundled before any Phase 0–1 cleanup. **Do not treat the fixer as a blank slate — it starts from `fixer/critique-epoch-invalidation-20260806`.**

---

## Reference docs — how to use this pack

This design doc is one of a set. Use them as follows:

0. **Build branch: `fixer/critique-epoch-invalidation-20260806`** — the box-local working branch this design builds off (see header). Box-only commits (HEAD `87a912beb`, incl. `superfixer-debug` skill + execute/finalize fixes) must be pushed + bundled before cleanup.

1. **This doc (`runtime-and-fixer-unification-design-20260807.md`)** — the plan itself: the two proposals, phases 0–6, file changes, open questions. It is the target design the fixer streamlines toward.
2. **`megaplan-fixer-briefing-20260807.md`** — the 52-line briefing loaded into every DeepSeek Flash fixer prompt and passed to the codex planner (the §3 anchor). Read it first when actually running a fixer.
3. **`megaplan-reference-architecture-20260807.md`** — the full intended design (six planes, flow, invariants, divergences, gaps) that the briefing distills. Go here for detail when implementing a phase.
4. **`branch-cleanup-judgment-20260807.md`** + **`branch-cleanup-action-plan-20260807.md`** — the cleanup of the current 114-tree mess, executed before/alongside Phase 0–1. The action plan's `agent-brief-20260807.md` is the Flash executor's operating brief for that cleanup.
5. **`arnold-end-state-20260807.md`** — the target state this whole set serves.

**Ground rules:** anchor every fixer prompt and codex checkpoint against the intended design (the briefing invariants), never the drifted state. If a referenced doc is unreachable in the execution environment, record `DOC-MISSING: <path>` for the operator — do not substitute the drifted checkout as intended design. When a fix would change how runtimes/fixer/deploy are structured, this design doc is the arbiter.

---

## 1. Problem statement

The box (root@159.69.51.216, container `megaplan-cloud-agent-resident-only`) has drifted into a state where **what is running is not recoverable, not singular, and not what a fixer edits.**

- **114 trees** under `/workspace/runtime-candidates/` (host path `/opt/megaplan-cloud/workspace/runtime-candidates/`), all clones/worktrees of `https://github.com/peteromallet/Arnold.git`, left behind forever. No builder, no promotion automation, no GC. ~56G, climbing.
- **Three live trees on three different commits:**
  | tree | HEAD | role |
  |---|---|---|
  | `arnold-4ed98585…-live` | host `44e249df3` / container `4ed98585` | resident superfixer + supervisor runtime |
  | `arnold-r7-fresh-child-20260805` | `f5a38311` | watchdog, repair-loop, resident schedule loop |
  | `/workspace/arnold` | `7d8426ca` | data store root (`main`) |
- **The running code exists only on the box.** `44e249df3`, `f5a38311`, `7d8426ca`, `4ed98585` are NOT on origin and not ancestors of any origin branch. A box failure loses the runtimes.
- **The `-live` tree is shadowed.** The resident container bind-mounts an RO recovery copy (`/var/lib/arnold/…/critique-4ed-pause-live-20260804-1246/runtime`) over `arnold-4ed98585…-live`. Editing the host tree does **not** change what the resident executes.
- **The scheduler timer fails every minute.** `/usr/local/bin/arnold-resident-schedule-run-once-r6` hardcodes `expected_head=234ac3524`, tree is `f5a38311`. Real scheduling is an ad-hoc bash loop.
- **The origin `editible-install` sync is disabled** (`CLOUD_WATCHDOG_SYNC_ENABLED=0`, `MEGAPLAN_AUDIT_RECOVERY_SYNC_ENABLED=0`).
- **Two fixer flows have diverged** (see §3): on-failure = 2-stage investigator→mutator (GLM per quota); hourly = 1-stage autonomous superfixer (`deepseek-v4-flash`). Different models, prompts, topology. Only convergence is both eventually drive the chain via `megaplan auto`/`resume`.
- **Stop-ship gap: we have not mapped what is actually running.** Before choosing a base or changing any pin, we must produce a process-level map of every live PID/container/timer/bash-loop → command line, mount namespace, loaded module `__file__`, content/commit digest, dirty state, schedule store, marker store, and mutable data directory. The plan preselects `f5a38311` as base *without* this census — an unacceptable cutover risk (external review: top risk #1). The actual running HEAD is `87a912beb` on `fixer/critique-epoch-invalidation-20260806` (6 commits past `f5a38311`).

---

## 2. Proposal 1 — per-epic runtimes off one promoted base

Each epic gets a cheap isolated runtime pulled from **one promoted base**, focused on fixing/unblocking that epic. At epic close, durable fixes are promoted back to the base selectively. This is a **build-artifact cache with a retention policy**, not a forest of branches.

### Correct framing
It is not "an editable install per epic" — it is **a cheap isolated runtime per epic, pulled from one promoted base, with selective promotion back.** The editable-install import root is the tail; the expensive part is tree + venv + wiring.

### Design rules (or it recreates today's pileup)
0. **Never mutate an executing runtime — separate source, candidate, and deployed runtime.** This is the review's single biggest addition. The origin branch is **source**, not the live deployment. A deployed runtime is an **immutable release generation** built from an origin-resolvable SHA, verified in a separate namespace, then activated by atomically switching an active-generation pointer. Retain at least the previous healthy generation for rollback. **Only epic/candidate worktrees are editable; the executing runtime is never edited in place.** Mutable state (schedule store, marker store, data) lives *outside* release trees, in a state root named by the manifest. Promotions become deployable and reversible; without this, "continuous promotion" can change code beneath resident processes and create mixed-version behavior (external review: biggest missing thing).
1. **Worktree, not clone.** Full clones don't share objects (~1.9G each — most of the 56G). `git worktree add` from the base shares objects. This is the single biggest cost lever.
2. **Per-epic venv, simplified until measurements require more.** A single venv cannot host two editable installs of the same package — site-packages holds one `__editable__` pointer, last `pip install -e` wins. Each epic worktree gets its **own venv whose only editable is that worktree** (never write an editable pointer into an environment another runtime uses). **Do NOT rely on nested `--system-site-packages` semantics** — it does not portably layer one venv over a parent venv. Start with the simplest isolated venv built from a `deps_lockfile` using a normal package cache/reflinks; add a shared dependency prefix only if measured disk or creation latency justifies it. At the box's real concurrency (probably 2–3 concurrent epics), a few straightforward venvs may be safer and cheaper than a custom dependency-layer system.
3. **One `runtime-manifest.json` per runtime is the ONLY *post-bootstrap* runtime resolver.** It cannot be the literally-only resolver: something outside the manifest must locate the manifest. Define **one stable bootstrap path + one authoritative writer**, and include `runtime_id`, `schema`, `generation`, origin-resolvable SHA/artifact digest, state-root identity, and expected runtime fingerprint. On startup, emit **attestation of the actual module path/digest and mount identity** (not just a declared path). Inventory and disable legacy launchers explicitly (the stale `expected_head`, `Path(__file__).with_name('arnold-repair-loop')`, `.cloud-hot-env` `*_SRC` aliases, systemd units). Schema-versioned, atomic tmp+rename writes under a lock, per-runtime files (not one global file) to avoid write-coherence contention.
4. **Push the epic branch to origin at creation.** Live code must not exist only on the box. `arnold-runtime-create` fails loudly on push failure.
5. **Promote durable fixes via prompt, staged promotion — not continuous auto-promotion.** Create a candidate ref/PR with provenance, permitted-path checks, tests, and explicit adjudication for semantic or conflicting changes. Deploy it as a **canary generation** before advancing base. Use **compare-and-swap on the origin ref**. Treat Git as authoritative; keep a reconcilable promotion journal. Do NOT describe push-plus-manifest-append as a transaction — Git and the manifest cannot be atomically updated together; a failure leaves them disagreeing. Batch-at-close is still a trap; staged-but-prompt beats both.
6. **GC on close.** `arnold-close` (explicit, closed-only) then `arnold-gc-sweep` (only closed + origin-resolvable). **`origin==local` is NOT a deletion predicate** — it does not cover untracked files, stashes, reflog-only objects, extra refs, container writable layers, or operational state. A delete only happens after a clean-room restore of the tree's *runtime* has been proven.
7. **Shadow-proof via content attestation, not just path identity.** `realpath` + `st_dev/st_ino` is NOT inherently shadow-proof — a bind mount can preserve the apparent path and filesystem identity. A fixer pre-flight must assert an **independent content/mount attestation** (a sentinel edit observable from the executing namespace, plus comparing module `__file__` digest from the running process against the tree's content digest). A shadowed/inert path is an error, never an edit target.

### Promotion gate (before a fixer commit reaches base)
1. Fix is engine/runtime infrastructure, not epic-specific data/model.
2. Diff passes an **explicit allowlist + review** (tests, config, docs allowed where appropriate) — "fixer code only" is too narrow; valid fixes need tests/config/docs. Review, not a raw path regex, is the gate.
3. Chain green via `megaplan auto`/`resume` or L2/L3 re-verify.
4. Base regression: resident/repair-loop boots, dry NO-OP run produces no spurious actions.
5. Policy-SHA match.
6. **Canary generation observed healthy before the base pointer advances.**

Mechanics: cherry-pick to a **temp ref** → fresh-interpreter **import smoke test** importing every runtime package → **compare-and-swap push base to origin** → record in the promotion journal → build a **canary generation**, verify it in a separate namespace → observe health → atomically switch the active-generation pointer (retain previous generation for rollback). **A successful push is not a safe cutover.** Base never ahead of origin; never amend base history (revert via a new commit).

---

## 3. Proposal 2 — one unified fixer on DeepSeek Flash

### The problem it solves
Today two different flows run: on-failure (watchdog → `arnold-repair-trigger` → `arnold-repair-loop`, 2-stage investigator→mutator, models default gpt-5.6-sol / deepseek-v4-pro but **overridden to GLM on this box** via `.cloud-hot-env`) and hourly (resident schedule `sched_superfixer_hourly_v2` → `subagent_worker --run-managed` → hermes launcher → `deepseek-v4-flash`, single autonomous agent). They have different models, prompts, topology, and — critically — different marker stores. The COORDINATION GUARD is prompt-level only and can race.

### The target architecture (unified, DeepSeek Flash for everything)

One entry seam — `arnold-repair-loop --mode=reactive|proactive` — shared by both triggers. **The whole flow runs on `deepseek:deepseek-v4-flash`.** The internal topology is a three-stage pipeline regardless of mode:

```
failure or hourly tick
        │
        ▼
┌──────────────────────┐
│ 1. CONTEXT SWARM      │  deploy a swarm of parallel Flash subagents
│    (gather context)   │  to understand the failure
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ 2. PLANNING CORPS     │  feed the gathered context to a corps of
│    (the "codex of     │  planning agents → they produce ONE plan
│    agents" — plan)    │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ 3. FLASH EXECUTOR     │  a Flash subagent receives the plan and
│    (execute the fix)  │  executes it — gets the chain durably moving
└──────────────────────┘
        │
        ▼
   verify durable movement; iterate if not moving
```

**Stage 1 — Context swarm.** A swarm of parallel DeepSeek Flash subagents is deployed to gather context on the failure. Guided to:
- Inspect the current failure/blocker, the chain, the plan state.
- **Look into previous failures** (the `.megaplan/fixer-sessions/index.md` + `summaries/`) — see if there are **patterns between them**.
- Understand the broader context — the general "vibe" of the situation — not just the one error.
- Each swarm agent returns a bounded, structured finding.

> **Anchor the flow in the intended design.** The swarm, the planning corps, and the Flash executor should all be given the **canonical intended-design briefing** — `docs/megaplan-fixer-briefing-20260807.md` (the 52-line briefing: mission, six planes, flow, fixer invariants, divergences, "done"), backed by `docs/megaplan-reference-architecture-20260807.md` for detail. This is surfaced **in the DeepSeek Flash prompt itself** (so the executor reasons against how the system is *designed* to operate, not how it's drifted), and Flash **mentions it to the codex planner** (so the planning corps plans against the intended architecture too). The purpose: keep diagnosis and repair anchored to the design contract — custody flows, guard invariants, evidence discipline — and catch drift-to-symptom where a fixer patches the broken shape of the system instead of restoring the intended shape. See "Reference docs — how to use this pack" above for the full ordering.

**Stage 2 — Planning corps.** The aggregated swarm findings feed a corps of planning agents ("codex of agents") that produces **one plan**. The plan must:
- Get the chain **durably moving** (beyond a frozen baseline — the existing "LAUNCH AND KEEP MOVING" standard).
- **Solve the actual issue at root**, not paper over it.
- **Figure out if there is an underlying structural issue** behind this failure — a fixer-layer bug, a guard gap, a policy divergence — not just the surface blocker.
- **Add that finding to the ticket** (persist the structural issue to the epic/session ticket, as the fixer does today via the synthesis/delivery owner).

**Stage 3 — Flash executor.** A DeepSeek Flash subagent receives the plan back and **executes it**:
- Applies the fix (with the existing guards: NO-OP guard, COORDINATION guard, edit the correct runtime, verify from the executing namespace).
- Re-drives the chain (`megaplan auto`/`resume`) to prove durable milestone movement.
- Reports the durable result to the existing synthesis/delivery owner.
- After trying: verify. If not durably moving, feed back and iterate (bounded — escalate per the existing ladder, never infinite recursion).

### What unification must preserve (do not regress)
- **Unify control-plane contracts first; replace agent internals only after evidence.** Split the work into **Phase 3A** (unify queueing, runtime resolution, markers, telemetry, escalation — preserve the current reactive + proactive implementations behind adapters) and **Phase 3B** (replace internals — the swarm→corps→executor redesign — only after a replay benchmark justifies it). This gets ONE operational seam without betting production on a new reasoning architecture simultaneously (external review: change #3).
- **Do not drop the investigation stage.** The 2-stage investigator→mutator protects against a mutator acting on un-verified root cause. The **context swarm + planning corps are NOT the default path** — they are reserved for ambiguity, repeated failure, or L2. The default remains a bounded investigator→executor flow. The separation of diagnosis from mutation stays.
- **Swarm is a trigger, not the architecture.** A fixed swarm on every repair adds quota pressure, latency, noisy aggregation, and correlated same-model errors. Invoke it only on ambiguity/L2 (external review: oracle #4). This is the "can you make it fan-out" feature — but as a *scaled* response to a hard case, not a per-repair default.
- **L2/L3 escalation ladder stays.** L1 = mode-specific fixer; L2 = deeper investigation on a genuinely stuck fix; L3 = `arnold-meta-repair-loop` (Codex orchestrator) as a distinct top rung. Hourly (proactive) must be able to escalate — today it has no escalation and just re-runs next hour.
- **Coordination = fenced, durable job state machine, not a bare lease.** A heartbeat lease alone permits split-brain: a paused holder can resume after a replacement starts; re-enqueueing cannot make partially completed external effects exactly-once (external review: oracle #5, top risk #3). Use a job state machine: `pending → running → committing → redriving → done`, a **dedupe key** (chain UUID + failure fingerprint), a **monotonically increasing fencing epoch** (a holder with an older epoch cannot act), acknowledge-only-after-redrive, isolated per-attempt edits, and quarantine/reconcile of dirty attempts on crash rather than blind re-run. Test pause-beyond-TTL-and-resume, not just process death.
- **One shared marker store.** Both flows register "active" in the same store (`session_markers.py` exists). If they write different markers today, the COORDINATION GUARD is already a race — unify onto one.
- **One model policy table, but Flash must EARN default.** `fixer_model_policy.py` keyed by mode+rung → `{agent_backend, provider_spec, model, budget}`. Before Flash becomes the default, run a **historical replay/evaluation suite** (`tests/fixer_replay/`): replay representative prior sessions across current models + proposed topologies; measure durable milestone advancement, unsafe-mutation rate, NO-OP false positives, human intervention, latency, cost, rate-limit behavior; require predeclared non-inferiority thresholds; then shadow/canary the new policy; keep a tested fallback across providers (external review: change #4, oracle #3). **Without a measured pass rate, "Flash for everything" is an unsupported availability + correctness gamble.**
  | mode/rung | model (default pending replay) |
  |---|---|
  | reactive_investigator | `deepseek:deepseek-v4-flash` |
  | reactive_mutator | `deepseek:deepseek-v4-flash` |
  | proactive | `deepseek:deepseek-v4-flash` |
  | l2 | `deepseek:deepseek-v4-flash` |
  | l3_orchestrator | codex + `deepseek:deepseek-v4-pro` (keep — orchestrator runs the corps) |
  
  `.cloud-hot-env` is demoted to **provider credentials/keys only** (no `*_MODEL` overrides). Fix the stale `OPENROUTER_API_KEY`→Zhipu-key 429 alias **before** converging, or the unified flow inherits it at both triggers.
- **The planning corps may use a stronger model.** Flash is the fixer/executor policy; the planning stage is the one place a stronger planner (or the existing codex/orchestrator path) is acceptable — a deliberate, documented exception, not a silent fork. (Open question, §7.)

### Mode semantics
- **Reactive** (on-failure): watchdog → trigger → enqueues into the schedule store → `--mode=reactive`. Bounded budget; **bounded investigator→executor as the default path**; fast path for obvious fixes; escalate to swarm/corps/L2 on uncertainty, repeated failure, or ambiguity.
- **Proactive** (hourly): resident schedule tick → `--mode=proactive`. Longer budget; NO-OP guard exits cleanly when nothing is blocked; LAUNCH-AND-KEEP-MOVING.

### The intended-design anchor (addressing oracle #10)
Loading the intended-design briefing into the Flash prompt is **helpful but not a control** — prompt inclusion does not prove behavioral use under context pressure. So the briefing is loaded (as designed), **but critical intended-design rules get executable checks** (the shadow gate, the fencing epoch, the allowlist+review, the NO-OP guard are code, not prompt prose) and the replay/ablation suite measures whether the executor actually reasons against the intended design rather than the drifted one.

---

## 4. Implementation phases

Ordered by dependency and risk — de-risk first, defer the big machinery. Each phase has an explicit exit criterion.

### Phase 0 — Evidence-and-restore gate (recoverability census + scheduler hygiene + shadow gate) — THE APPROVED PHASE
The external review's central instruction: **prove what is running and how to restore it BEFORE changing anything.** Phase 0 is no longer "backstop + pin fix" — it is an evidence gate whose output makes Phases 1–6 defensible.
- **Build the process-level execution map (the census):** enumerate every live PID / container / systemd timer / bash-loop and map it to: command line, mount namespace, loaded module `__file__` (resolve the editable install from inside the process, not the declared path), content/commit digest, dirty state, schedule store, marker store, and mutable data directories. This is the missing basis for picking a base — **do not choose `f5a38311` as base until the census shows which tree actually serves each live function; the running HEAD is `87a912beb` on `fixer/critique-epoch-invalidation-20260806`** (external review: top risk #1).
- **Capture the full recoverability surface, not just reachable git objects:** `git bundle create <off-box>/arnold-live-20260807-<tree>.bundle --all` + `git bundle verify`, PLUS capture unique refs, reflogs, stashes, untracked files, unit definitions (`/etc/systemd/system/arnold*`), container image digests (`docker inspect`), dependency locks, and the RO recovery copy. A git bundle does NOT preserve dirty files, untracked files, runtime state, unit definitions, container layers, credentials, or deps — it is not runtime reconstructability (external review: oracle #9, corrected statement #4). Record checksums; copy genuinely off-box (a host path on the same box does not count).
- **Drill a clean-room restore and measure RTO/RPO:** from the bundles/artifacts alone, rebuild a working runtime in a scratch/off-box namespace and run the fixer seam green. This is the FIRST restore drill — not deferred to Phase 6 (external review: oracle #9).
- Push preserve branches + snapshot tags (`preserve/<tree>-<short>-20260807`, `box-snapshot/<tree>-<short>-20260807`) following the existing `origin/preserve` convention. If `/workspace/arnold` is push-blocked, push from an authorized clone or rely on the bundle.
- Land the scheduler pin fix: install a fresh pinned binary reading `expected_head` from the runtime manifest (interim: one-line pin to the build-branch HEAD `87a912beb`, not the stale `f5a38311`). **Verify the systemd timer runs green for ≥2 hours, not ≥2 minutes** — 2 minutes of a one-minute timer is too weak, especially while an ad-hoc loop may coexist (external review: corrected statement #6).
- Decide the ad-hoc 120s bash loop's fate (convert to a logged systemd unit — preferred — or formally bless it). Reconcile invocation pins + dead containers (archive `.bak`/`.backup`/`pre-*`; remove refs to the Exited `megaplan-cloud-agent` container).
- Prove and record the RO-shadow scope (`findmnt`, `stat -c '%d:%i'` host vs container). Land the shadow gate as **content attestation** (sentinel edit observable from the executing namespace + module `__file__` digest compare), not just path realpath (external review: corrected statement #1).
- Run the four verification probes: (1) do box trees wire `repair_lock.py`? (2) do the two flows register active in the SAME marker store? (3) does the hourly superfixer render policy through `fixer_prompt_policy.py`? (4) enumerate schedule-store non-live refs (`2bd0b2d34`, `6ce6d4eb`, `74b4e6b9`, `bc0c600c`) and confirm they are the only must-not-GC candidates. Add probe (5): how many concurrent epics does the box actually run, and what is the real per-epic env size (drives §2 rule 2 economics).

**Exit:** the census maps every live process → executable tree/commit/mount; a clean-room restore from off-box bundles succeeds with measured RTO/RPO; all 4 live SHAs origin-resolvable AND reconstructable; timer green ≥2h with exactly one live schedule pin; shadow gate uses content attestation and refuses inert-path edits; no dead-container refs; probes recorded (including concurrency + env-size).

### Phase 1 — Execution-source resolution: separate source, candidate, and deployed runtime
Make the origin branch the **source** (never the live deployment), build an **immutable release generation** from an origin-resolvable SHA, and make "the generation you verify" == "the generation the resident executes."
- Resolve the RO bind-mount per the Phase-0 census. Never bind-mount an RO copy over a fixer's edit target.
- **Introduce the generation/rollback contract (design rule 0):** build a release generation from an origin-resolvable SHA, verify it in a separate namespace, atomically switch an active-generation pointer, retain the previous healthy generation for rollback. Mutable state (schedule store, marker store, data) lives in a state root *outside* release trees.
- Seed a durable source branch (default `base/editable-install`; human sign-off) from the **build branch `fixer/critique-epoch-invalidation-20260806`** (HEAD `87a912beb`, not the stale `f5a38311` — the census must confirm it serves the watchdog/schedule control plane). `origin/editible-install` (`8c4b2c956`) stays the deploy-snapshot mirror and is **NOT** the fixer base.
- Point env (`MEGAPLAN_RUNTIME_SRC`, `CLOUD_WATCHDOG_ARNOLD_SRC`) at the canonical base source; push base to origin and make it push-authorized.
- Prove the fix from the executing namespace: run a superfixer tick, assert the **executed tree's content fingerprint (module `__file__` + digest)** == base HEAD — not the declared path.
- Create the base venv from `deps_lockfile` (not nested `--system-site-packages`); confirm data-store writes unaffected by the mount.
- Land the r7 policy delta (`fixer_prompt_policy.py`: trusted-container handling + profile/fast-path rendering) as the only copy; record `policy_sha`.

**Exit:** a release generation built from an origin-resolvable SHA is verified in a separate namespace and activated by switching the active-generation pointer, with the previous generation retained for rollback; the resident executes that generation (content fingerprint verified); base source on origin + push-authorized; policy delta is the only copy; base venv exists; data-store writes confirmed.

### Phase 2 — Runtime manifest + launcher refactor (post-bootstrap resolver)
One per-runtime `runtime-manifest.json` becomes the ONLY **post-bootstrap** runtime resolver, with a stable bootstrap path and one authoritative writer.
- New `runtime_manifest.py`: schema-versioned, atomic tmp+rename under flock, load-by-epic + read-only index, **bootstrap-path resolution + attestation**. Mandatory fields: `runtime_id, schema, generation, epic_id, state, owner, base{ref,commit,editable_install_path,venv_path}, epic{branch,worktree_path,venv_path,runtime_root,expected_head,repair_bin,deps_lockfile}, indirection{host_path,container_path,mount_table,execution_namespace,verified_head,last_verified_at,attestation{module_file,module_digest,mount_id}}, policy{policy_sha,model_policy_sha,sync_policy}, promotions[], timestamps{created,updated,closed}, gc_policy, commands[]`. On startup emit attestation of the actual module path/digest + mount identity.
- Refactor `arnold-repair-trigger` (replace `Path(__file__).with_name('arnold-repair-loop')` at line 537), `arnold-watchdog` (`PRIMARY_REPAIR_BIN`/`META_REPAIR_BIN`), resident schedule runner + systemd unit, `.cloud-hot-env` (`*_SRC` become manifest-validated), schedule store (consumer of the manifest).
- **Inventory and disable legacy launchers explicitly** — a stale systemd unit or copied manifest silently recreates the split-brain (external review: change #6).
- Enforce single post-bootstrap resolution: grep for `with_name`/glob/pin-file resolution; add a conformance test; add a drift check that fails loudly on a manifest/runtime attestation mismatch.

**Exit:** every launcher resolves via the manifest after one stable bootstrap path; `expected_head=234ac3524` and `with_name('arnold-repair-loop')` are dead code; attestation catches drift (module file/digest mismatch fails loudly); shadow gate uses content attestation and refuses inert paths; schedule store manifest-consistent; conformance test green.

### Phase 3 — Unified fixer seam (Proposal 2), split into 3A (control-plane) + 3B (agent redesign)
One entry seam, one fenced job state machine, one escalation ladder, one model policy. The review's instruction: **unify control-plane contracts first; replace agent internals only after evidence.**

**Phase 3A — control-plane unification (safe, do first):**
- `arnold-repair-loop --mode=reactive|proactive` (§3) as a single entry seam, **preserving the current reactive + proactive implementations behind adapters** (no agent-redesign bet yet).
- Port/confirm `repair_lock.py` on the canonical base; extend into the **fenced, durable job state machine** (`pending → running → committing → redriving → done`, dedupe key = chain UUID + failure fingerprint, monotonically increasing fencing epoch, acknowledge-after-redrive, per-attempt isolated edits, quarantine/reconcile on crash). Test pause-beyond-TTL-and-resume.
- Verify both flows register active in the SAME marker store; unify if not. Wire proactive → L2/L3 escalation (today the hourly flow has none).
- Re-point `arnold-repair-trigger` to enqueue into the schedule store (one queue, one lease, one marker store).
- Add dry-run path + smoke tests (mode isolation) so one config/model-routing bug cannot degrade both modes at once.

**Phase 3B — agent redesign, gated on evidence:**
- Build the replay/evaluation suite (`tests/fixer_replay/`) FIRST: replay representative prior sessions across current models + the proposed swarm→corps→executor topology; measure durable milestone advancement, unsafe-mutation rate, NO-OP false positives, human intervention, latency, cost, rate-limit behavior; require predeclared non-inferiority thresholds.
- Only if Flash + the swarm→corps topology beats the current flow on the replay benchmark do we land it as the default path. Otherwise keep the bounded investigator→executor default and invoke the swarm only for ambiguity/repeated-failure/L2.
- **Surface the intended-design briefing (§3 anchor):** load the canonical intended-design briefing (`docs/megaplan-fixer-briefing-20260807.md`) into the Flash prompt and pass it to the codex planner — and add the executable checks + replay/ablation evidence that the anchor actually changes behavior (oracle #10).

**Exit (3A):** on-failure and hourly both dispatch through `arnold-repair-loop --mode=...` from the canonical base; one policy render with a working policy-SHA gate; one fenced job state machine (two concurrent fixers on one chain → exactly one mutator; killed holder's job is quarantined/reconciled, not blindly re-run; a paused holder past TTL cannot resume into the newer epoch); proactive escalates to L2/L3; dry NO-OP in both modes exits 0 with zero mutations; the two-marker race is gone.
**Exit (3B):** replay suite exists with non-inferiority thresholds; the swarm→corps→executor topology is deployed ONLY if it wins the replay; the intended-design anchor has executable checks + replay evidence; Flash default is a measured policy choice, not an assumption.

### Phase 4 — Per-epic runtimes light form + prompt staged promotion + canary deployment
Prove the Proposal-1 lifecycle end-to-end before paying for per-epic venv/runtime machinery.
- `arnold-runtime-create`: `git worktree add <base>/runtime-candidates/<slug> -b fixer/<slug>-<YYYYMMDD>` off base source HEAD (shared objects), `git push origin` at creation (fail loudly), write epic manifest atomically. Run one pilot epic end-to-end.
- `arnold-promote`: **prompt, staged promotion** (gate §2 → candidate ref/PR with provenance + tests → canary generation verified in a separate namespace → compare-and-swap push base to origin → record in the promotion journal → advance the active-generation pointer, retaining the previous generation for rollback). A successful push is NOT a safe cutover.
- Pin each epic to a base revision; epics re-base only on an explicit idle refresh.
- Re-enable sync (`CLOUD_WATCHDOG_SYNC_ENABLED=1`, `MEGAPLAN_AUDIT_RECOVERY_SYNC_ENABLED=1`) — the base→origin PUSH leg is the recoverability guarantee. Gate the pull-side on the durable line.
- **Orphan reclamation is NOT here** — safe deletion begins in Phase 5. Phase 0 may `git worktree prune` for bookkeeping, but no byte-reclaim of orphan trees until Phase 5's closed-only, restore-proven protocol (external review: corrected statement #7).

**Exit:** a pilot epic stands up as worktree+manifest+pushed branch; a durable fix is promoted to base via canary generation + CAS push and lands on origin the same day; a second epic's runtime does not route imports into the first epic's tree; sync re-enabled with no clobber; the previous base generation is retained for rollback; no orphan trees reclaimed in this phase.

### Phase 5 — Safe GC + close protocol (the ONLY deletion phase)
Reclaim ~56G candidates + ~25G venvs safely: closed-only, two-phase, schedule-store-reconciled, restore-proven.
- `arnold-close`: verify all state committed + pushed, push a backstop tag, no open FDs/liveness, atomically set `manifest.state=closed`.
- `arnold-gc-sweep`: removes ONLY closed + origin-resolvable trees **after a clean-room restore of each tree's runtime has been proven** (Phase 0 established the restore protocol). `git worktree remove --force` + delete epic venv + archive manifest. A sweep NEVER infers "stale" — a runner death mid-epic leaves a tree neither-live-neither-closed; reconcile it explicitly.
- **`origin==local` is NOT a deletion predicate.** Deletion is gated on the restore proof, not on commit reachability (external review: oracle #9, corrected statement #3). Bundles don't prove runtime reconstructability; the clean-room restore does.
- Legacy 85 full clones: freeze-then-delete once each HEAD is origin-resolvable AND its runtime restore is proven (backstop tag from Phase 0).
- The 28 orphaned/broken worktrees (~13.5G): `git worktree prune` + rm stale admin dirs — this is where orphan reclaim lives (not Phase 4), after the Phase-0 restore protocol covers them.
- Add a liveness registry (scheduler + schedule runner register heartbeats).

**Exit:** orphan bytes reclaimed and logged; a close→sweep cycle on a scratch epic reclaims its worktree + venv with zero dangling schedule-store refs; no live tree deleted; legacy clones deleted only where their runtime restore is proven (not merely origin==local); reclaimed-disk figures logged.

### Phase 6 — Gated full per-epic machinery + standing invariants + runbook
Full per-epic editable-install runtimes ONLY on evidence of need (dep-fork or engine-code mutation).
- Per-epic venv only when deps fork (own venv, ONLY editable = that worktree, **simplest isolated venv from a lockfile**, `__editable__` pointer verified; shared dependency prefix only if measured disk/latency justifies it).
- Broken-worktree detector + venv GC tied to manifest state.
- Promotion adjudication rule for conflicting durable fixes (revert-via-new-commit, never amend base history); adjudication is explicit for semantic/conflicting changes (external review: change #8).
- Enforce the corrected recoverability rule: **nothing becomes authoritative or receives external side-effect authority unless its exact clean content is origin-resolvable** (external review: corrected statement #2 — "nothing runs unpushed" is impossible during candidate verification).
- Document + drill the runbook: rebuild a runtime from its manifest alone in a scratch dir (the Phase-0 restore drill is the standing practice, not a one-off), run the fixer seam green, spot-check zero box-only commits.

**Exit:** full runtimes exist only on-demand and are manifest-recorded; two epics with divergent deps run without clobbering each other's `__editable__` pointer; closing an epic frees its worktree + venv; a re-run of GC finds nothing to sweep; the restore drill is standing practice; zero authoritative box-only commits.

---

## 5. Ordering rationale

- **Phase 0 FIRST, as an evidence-and-restore gate** — census what is running, capture the full recoverability surface, drill a clean-room restore, then fix the scheduler + shadow. Building machinery on un-mapped, unrecoverable, drifty code is wasted work. This is the only phase the external review approved as written.
- **Phase 1 before any "one base" or "one flow" claim** — the generation/rollback contract makes "what I edit is not what runs" structurally impossible, which is the shared spine of both proposals.
- **Phase 2 before Phase 3** — the seam needs the manifest to name `repair_bin`, `expected_head`, policy SHA, and to attest the running generation.
- **Phase 3A (control-plane unification) before Phase 3B (agent redesign)** — one seam + one fenced job state machine without betting production on a new reasoning architecture; 3B only after the replay suite justifies it.
- **Phase 4 before full venv/runtime machinery** — prove create→promote→close with worktree branches + canary generation first; full runtimes are gated on evidence.
- **Phase 5 only after recoverability (P0), execution-source (P1), manifest (P2) hold** — deletion is only safe once a tree's runtime restore is proven and its state is manifest-authoritative.
- **Phase 6 ongoing/defensive** — lands incrementally from the end of Phase 3.

---

## 6. File changes (target)

| path | change |
|---|---|
| `arnold_pipelines/megaplan/cloud/runtime_manifest.py` | **new** — schema-versioned per-runtime manifest R/W (atomic, flock), load-by-epic, **bootstrap-path resolution + attestation (module file/digest/mount id)**, generation pointer, promotion journal |
| `arnold_pipelines/megaplan/cloud/fixer_prompt_policy.py` | **new on durable line** — port the r7-vs-live 69-line delta (trusted-container + profile/fast-path rendering); expose policy SHA |
| `arnold_pipelines/megaplan/cloud/fixer_model_policy.py` | **new** — mode+rung → `{agent_backend, provider_spec, model, budget}` table; validates `.cloud-hot-env` holds credentials only; **gated on replay-suite non-inferiority** |
| `arnold_pipelines/megaplan/cloud/repair_lock.py` | extend — **fenced durable job state machine** (pending→running→committing→redriving→done, dedupe key, fencing epoch, quarantine/reconcile on crash), not a bare lease |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop` | add `--mode=reactive|proactive`; resolve repair_bin/expected_head from manifest; 3A = adapters over current implementations; 3B = swarm→corps→executor gated on replay |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger` | manifest-based repair_bin (kill line-537 `with_name`); enqueue into schedule store; acquire fencing epoch |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog` | resolve PRIMARY/META_REPAIR_BIN from manifest; dispatch `--mode=reactive`; register heartbeat |
| `arnold_pipelines/megaplan/cloud/current_target.py` | gain **content attestation** (module `__file__` + digest + mount id), not just st_dev/st_ino |
| `arnold_pipelines/megaplan/resident/scheduler.py` | dispatch proactive through the seam; expected_head/pin checks read manifest; job state machine part of lifecycle |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-runtime-create` | **new** — worktree + push-at-creation + manifest write |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-promote` | **new** — prompt staged promotion: candidate ref/PR → canary generation → CAS push → promotion journal → active-generation switch (retain previous) |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-close` | **new** — two-phase close |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep` | **new** — closed-only, schedule-store-reconciled, **restore-proven** GC (`origin==local` is not a predicate) |
| `arnold_pipelines/megaplan/cloud/install_sync.py` | manifest-driven, per-venv editable pointer; simplest venv from lockfile (no nested `--system-site-packages`) |
| `arnold_pipelines/megaplan/cloud/github_sync.py` | add base→origin PUSH leg; re-enable via sync_policy; CAS on origin ref |
| `tests/fixer_replay/` | **new** — replay suite: replay prior sessions across models/topologies; measure milestone advancement, unsafe-mutation, NO-OP false positives, latency, cost, rate-limits; gates Flash + swarm default |
| box: `/usr/local/bin/arnold-resident-schedule-run-once-r7` | replacement binary reading expected_head from manifest |
| box: schedule store | re-point/retire `2bd0b2d34`/`6ce6d4eb`/`74b4e6b9`/`bc0c600c`; assert every source path in a manifest |
| box: `.cloud-hot-env` | credentials only; fix OPENROUTER→Zhipu 429 alias; sync flags re-enable only after base named/pushed |
| `docs/recoverability-20260807.md` | census + bundle paths + checksums, pushed refs, SHA table, **clean-room restore drill + measured RTO/RPO** |
| `docs/megaplan-fixer-briefing-20260807.md` | canonical briefing of how megaplan SHOULD work (from the intended-design swarm + gpt-5.6-sol); loaded into the Flash prompt and passed to the codex planner (§3 anchor) + executable checks |
| `docs/megaplan-reference-architecture-20260807.md` | full consolidated intended-design survey (six planes, flow, invariants, divergences, gaps) that the briefing distills |

---

## 7. Open questions (need human decision)

1. **Planning-corps model.** Does the planning stage stay on Flash too, or use a stronger planner (codex/orchestrator) as a deliberate exception? (Default: keep the L3 orchestrator on codex + deepseek-v4-pro; everything else Flash — **pending the replay-suite results**.)
2. **RO bind-mount scope.** Does the overlay cover only `arnold-4ed98585-live` or `/workspace/runtime-candidates` broadly? (Probe in Phase 0; a broad mount forces the overlay decision early.)
3. **Which tree/snapshot does the resident actually execute today** for the hourly superfixer — host `-live` or the RO recovery copy? (Phase-0 census answers this; it defines the true baseline.)
4. **Base branch naming/semantics.** Distinct `base/editable-install` (recommended) vs promoting onto `origin/editible-install` (rewrites what the deploy snapshot means).
5. **Where exactly is `expected_head=234ac3524` pinned** (r6 script vs resident schedule config)? Sizes the Phase-0 timer fix.
6. **Push authorization.** `/workspace/arnold` is push-blocked today; probe with a throwaway epic branch before Phase 4 relies on push-at-creation. Bundles remain the fallback.
7. **Do the box trees already wire `repair_lock.py`, and do the two flows share a marker store?** Determines verify+extend vs new construction, and whether the COORDINATION GUARD is already a race.
8. **Does the hourly superfixer render policy through `fixer_prompt_policy.py` at all?** The local durable line does NOT contain the file.
9. **Real latency/budget targets** for reactive vs proactive modes — needs numbers from box logs.
10. **Promotion adjudication rule** when two epics promote conflicting durable fixes into the base.
11. **Flash replay threshold (from the review):** what are the non-inferiority thresholds the replay suite must clear before Flash becomes the default? A concrete pass/fail bar must be declared BEFORE running the suite, not after.
12. **Concurrency / env-size measurement (drives §2 rule 2):** how many concurrent epics does the box actually run, and what is real per-epic env size? This decides whether per-epic venvs are a handful of simple venvs or need a shared dependency layer.
13. **Rollback generations:** how many healthy base generations to retain for rollback (memory vs safety tradeoff)?

---

## 8. One-line policy statement

> **Map and restore before you change anything; the origin branch is source, never the live deployment; a deployed runtime is an immutable release generation with a retained rollback; Flash earns the default on a replay benchmark, not by assumption; a bounded investigator→executor fixes by default and a swarm escalates the hard cases; durable fixes promote through canary generation and CAS, never beneath a running process; per-epic runtimes are cheap worktrees with their own venv; nothing authoritative runs un-resolvable; nothing is deleted until its restore is proven.**
> **Authority status: non-authoritative.** This document is historical/design record, not a live-authority operator surface (T44 zero-authority migration).
