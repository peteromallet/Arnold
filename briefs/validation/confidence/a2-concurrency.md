# a2 — Concurrency safety of the shared substrate under multiple tenants

**Question:** Is the shared substrate safe under MULTIPLE concurrent megaplan *processes* /
tenants (a planning chain + an Arnold resident loop) sharing workers, API keys, and rate
limits?

**Verdict:** Multi-tenant concurrency is a **REAL risk. Severity: HIGH for API-key/rate-limit
coordination; MEDIUM-LOW for filesystem/state (already mostly defended for the *single-plan*
case, but undefended for cross-tenant *resource* contention).** Every coordination primitive
that matters for shared workers/keys/quotas is **in-process only**. Two megaplan processes do
NOT coordinate on anything except per-plan filesystem locks.

Grounded against current `main`, 2026-05-28.

---

## 1. What enforces safe concurrency for workers/keys today? Is the key pool in-process only?

**The key pool is in-process only. Confirmed.**

- `megaplan/runtime/key_pool.py:69` — `self._lock = threading.Lock()`. A `threading.Lock`
  serializes *threads inside one interpreter*; it provides **zero** cross-process exclusion.
- The pool is a **module-global singleton**: `_pool = KeyPool()` (`key_pool.py:197`). Its
  entire state — `_entries`, per-key `last_used`, `cooldown_until`, `failed` — lives in
  process memory only. Nothing is written to disk or any shared file. There is no shared
  ledger, lock file, or IPC.
- Cooldown timestamps use `time.monotonic()` (`key_pool.py:160,175,187`) — a *per-process*
  clock that is **not comparable across processes** even if state were shared. So a
  cross-process broker could not even reuse this state as-is.
- `acquire()` (`key_pool.py:158`) picks the least-recently-used eligible key. Two processes
  each run their own LRU over their own view of the *same physical keys* (loaded from the same
  `~/.hermes/.env` / `auto_improve/api_keys.json`, `key_pool.py:73-128`). They will happily
  hand the **same key** to concurrent calls and each believes it is balancing load.

**Net:** within ONE megaplan process, worker/key concurrency is correctly serialized by the
threading lock (e.g. the in-process Hermes `ThreadPoolExecutor` fan-out,
`_core/hermes_fanout.py:221`, and `ProcessPoolExecutor` at `:299` — note the child processes
of a fanout each build their *own* KeyPool too). Across SEPARATE megaplan processes there is
**no coordination whatsoever**.

## 2. API rate limits / quotas: any cross-process / cross-tenant rate limiting?

**None. This is the highest-severity finding.**

- The only rate-limit machinery is `report_429()` (`key_pool.py:171`) → bumps an in-memory
  `cooldown_until` on the offending key, and the MiniMax/Zhipu fallback in
  `_core/hermes_fanout.py:70-93` which reports the 429 and retries via OpenRouter. All of this
  is **per-process in-memory state.** A 429 learned by the planning chain is invisible to the
  Arnold loop and vice-versa.
- `orchestration/phase_result_classify.py:80` detects 429 and extracts `retry-after`, but this
  is post-hoc *classification* of a worker failure, not a *limiter*. There is no token-bucket,
  no semaphore, no shared quota accounting anywhere in `megaplan/runtime/`, `_core/`, or
  `orchestration/`.
- Codex/Shannon paths fare worse: they hit the operator's Codex/Claude-Code subscription
  quotas directly with no megaplan-side limiter at all; concurrent tenants simply race the
  provider.

**Consequence:** concurrent tenants **race the same provider quotas**. They will mutually
trigger 429s, each independently cool down (often the *same* key), and there is no global
backoff — under load this degrades into thundering-herd retries against an already
rate-limited provider. For a shared-key, shared-quota deployment this is a correctness and
cost hazard, not a theoretical one.

## 3. Worktree / filesystem isolation

**Mixed. Plan-dir collisions are defended; cross-tenant worktree/resource contention is not.**

- Worktree creation (`bakeoff/worktree.py`) shells out to `git worktree add` and relies on
  git's own refusal to double-register a path. Bakeoff profiles get distinct paths
  (`.megaplan-worktrees/<plan>/<profile>/`), so two *named* tenants with distinct plan/profile
  names do not collide on the working tree itself.
- BUT `git worktree add`/`remove`/`prune` mutate **one shared `.git` worktree registry** in the
  common repo. Concurrent `worktree add`/`remove` from two processes is **not serialized by
  megaplan** — git's own index/ref locking is the only guard, and `worktree prune` from one
  tenant can race another tenant mid-add. `ensure_no_inprogress_op` (`worktree.py:48`) checks
  rebase/merge markers but not concurrent worktree mutation.
- Plan state files are reasonably defended *per plan*: `plan_lock` (`_core/state.py:177`, an
  `fcntl.flock` on `.plan.lock`, **cross-process**) and `plan_state_lock`
  (`_core/state.py:234`, blocking `fcntl.flock` on a per-plan `.state-locks/<name>.lock`) DO
  coordinate across processes — but only for the *same plan directory*. Two tenants on
  *different* plan dirs never contend here, which is correct for isolation but means these
  locks do nothing for the shared-resource problem.

**Net:** two tenants on distinct plan dirs / worktrees won't corrupt each other's *files*, but
they share one git registry (un-serialized by megaplan) and, more importantly, share the
unguarded key/quota substrate from (1)/(2).

## 4. State writes: is concurrent multi-tenant state access safe?

**For per-plan `state.json`: YES (cross-process `fcntl.flock`).** `write_plan_state`
(`_core/state.py:329`) does the whole read-modify-validate-write under `plan_state_lock`
(`fcntl.flock(LOCK_EX)`), and append-only operator meta fields are union-merged
(`save_state_merge_meta`, `:626`) to survive the override-vs-phase race. This is genuinely
multi-process-safe **for a single plan**.

**For chain state: NO — `chain_state.json` is LOCK-FREE.** `save_chain_state`
(`chain/__init__.py:553`) does an atomic *rename* (`tmp.replace(state_path)`) but takes **no
lock** — `grep -c flock chain/__init__.py == 0`. Atomic-rename prevents a *torn* file but does
**not** prevent lost updates: two writers each read, mutate in memory, and the last `replace`
wins, silently dropping the other's update. The task's premise of "the m1 lock added to
chain_state" is **not present in current `main`** — there is no flock on the chain-state path.
A planning chain and any other chain/tenant sharing a spec would lose updates. (Within a single
chain driver this is moot — one process owns it — but it is a lock-free path the moment a second
writer touches the same chain spec, e.g. an operator override or a supervisor.)

## 5. Does "dispatch as a shared service" make concurrent multi-tenant dispatch MORE likely?

**Yes — directly and by design.** This is the crux.

- m2 (`briefs/epic-pipeline-unification/m2-dispatch-service.md`) *explicitly* formalizes
  dispatch into a standalone entry callable **without a Pipeline**, and its load-bearing
  acceptance test is a **resident-style, store-backed caller (the Arnold shape)** dispatching a
  real worker (m2 Outcome 2 & 4, Scope 4, Done-criteria 4–5). The entire point of m2 is to make
  a non-planning resident loop dispatch through the shared path.
- That is the *exact* configuration this investigation flags: a planning chain + an Arnold
  resident loop, both pulling on the same `acquire_key`/`run_step_with_worker` substrate. m2
  lowers the barrier to running them **concurrently in separate processes** while the
  coordination underneath (1)/(2) stays single-process.
- m2 even commits to running on a "parallel branch" and to a resident loop that dispatches with
  "no `state.json`" (m2 Scope 6) — i.e. it deliberately steps *outside* the per-plan
  `fcntl.flock` that is the only working cross-process guard. So the one defended path (4,
  per-plan state lock) does not cover the new tenant.

**Conclusion:** the epic increases the probability and blast radius of concurrent multi-tenant
dispatch precisely while leaving the key/quota substrate single-process. The abstraction and the
safety mechanism are moving in opposite directions.

---

## Severity & residual exposure

- **API keys / rate limits (Q1, Q2): HIGH.** No cross-process coordination of keys or quotas;
  shared-key deployments will race quotas, double-cool the same key, and thundering-herd retry.
- **Chain state (Q4): MEDIUM.** Lock-free `save_chain_state`; lost-update under any second
  writer. Low today (one driver per chain) but a latent footgun the moment a supervisor/override
  writes concurrently, and the task's assumed "m1 lock" does not exist.
- **Git worktree registry (Q3): LOW-MEDIUM.** Un-serialized `git worktree` mutation across
  tenants; relies on git's own locking, with a real add-vs-prune race.
- **Per-plan state.json (Q4): SAFE.** Cross-process `fcntl.flock` already correct.

## CONCRETE plan change

1. **m4 owns the fix — build a cross-process key + rate broker, injected via the `services`
   bag.** m4 already introduces `RunConfig` + a `services` bag (`{worker_runner,
   progress_emitter, event_sink, evidence_strategy}`, m4 Scope 3). **Add `key_broker` /
   `rate_broker` to `services`.** Back it with a **file-locked, on-disk** key/cooldown ledger
   (e.g. `fcntl.flock` over `~/.megaplan/keypool.lock` guarding a JSON ledger of per-key
   `cooldown_until` as *wall-clock* `time.time()`, not `monotonic()`), so any megaplan process
   reads/writes the same cooldowns and a single global token/quota budget. Replace the
   `threading.Lock` singleton in `key_pool.py` with a broker that falls back to the in-process
   pool only when no shared ledger is configured (preserving today's single-process behaviour
   and parity). This is the "cross-process key/rate broker" called for; m4's `services`
   injection is its natural seam.

2. **Add an explicit acceptance gate to m2.** m2's resident-style acceptance consumer (Done
   criteria 4–5) MUST run **concurrently with a second dispatching tenant against a shared key
   set** and assert no double-issue of a cooled key and a shared backoff is observed — turning
   the multi-tenant race into a tested invariant at the moment the shared service is introduced,
   rather than discovering it in production.

3. **Add an `fcntl.flock` to `save_chain_state`/`load_chain_state`** (mirror the per-plan
   `plan_state_lock` pattern at `_core/state.py:234`) so chain state is read-modify-write safe
   under any second writer. Cheap, isolated; land in m1 or m2 alongside the store-integrity work.

## Residual uncertainty

- The task asserted an "m1 lock added to chain_state"; I could not find it on current `main`
  (`save_chain_state` is lock-free). Either it is planned-but-unlanded, or lives on a branch not
  checked out here. If it exists elsewhere, recommendation (3) may be partially satisfied —
  verify the branch.
- Codex/Shannon subscription-quota racing is outside the key-pool entirely (those workers do not
  go through `acquire_key`); a key/rate broker for the Hermes/OpenRouter path will NOT cover
  them. A separate concurrency cap (a shared semaphore on subscription-backed workers) may be
  needed and is not scoped by any current milestone.
- Whether the intended multi-tenant deployment actually shares one key set (HIGH severity) vs.
  gives each tenant distinct keys (severity drops to the chain-state/worktree issues only) is a
  deployment decision I could not confirm from code; the broker is the safe default regardless.
