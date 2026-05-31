# Confidence synthesis — Pipeline Unification epic

11 investigations (7 Claude deep + 4 DeepSeek sweeps) aimed at FULL confidence. Each blind spot is now
resolved to a verdict + concrete fix. Findings: `k-arnold-reconciliation`, `a2`–`a7`, `d1`–`d4`.

## The keystone result (verified firsthand) — the premise was largely wrong
**Arnold is not hypothetical and not "schemas only." It is a built-out service: `megaplan/resident/`,
4,201 LOC, 13 modules** (`runtime`, `agent_loop`, `scheduler`, `auth`, `discord`, its own
`ResidentConfig` + `OpenAICompatibleAgentRunner`). Verified by grep:
- Uses of `resolve_agent_mode`, `run_step_with_worker`, `tier_models`, `VALID_PHASE_KEYS`,
  `apply_profile_expansion` inside `resident/`: **0, 0, 0**. Not even the shared `key_pool`.
- It uses the **`Store`** (5 modules) and the **control/cloud handoff plane**. Nothing else.

So, by the guiding principle ("share what others use; don't generalize planning-only machinery"), the
answer is now **known, not inferred**: the only thing the real second tool reuses is the `Store`
(+ control plane) — and that is **already shared**. The epic's planned "shared" pieces (m2 pack-agnostic
dispatch, m4 evidence strategy / RunConfig) are **planning-only**; Arnold does not touch them.

Corollary: several scary blind spots are **downstream of building a shared dispatch service** that
Arnold doesn't use — so if we don't build it, they don't arise.

## Blind spots — resolved, with the keystone applied
| # | Risk | Verdict | Fix / note |
|---|------|---------|-----------|
| A2 | Multi-tenant concurrency (keys/rate/chain_state) | REAL, but narrower — Arnold has its own runner+keys, so the shared-key race is between **planning** processes (chains/bakeoffs), not Arnold. Lock-free `save_chain_state` confirmed; the "m1 chain_state lock" is NOT on main. | fcntl-locked key/rate broker + lock `chain_state`. Only urgent if shared dispatch ships. |
| A3 | Human-recovery surface vs m3 routing collapse | HIGH coupling, CONTAINED | m3 safe **iff** `workflow_next` survives as a thin projection over edges (keep signature, re-implement body). Concrete. |
| A4 | Stall protection in shared dispatch | REAL/HIGH for the **planning loop** path (hermes loses all stall protection; `loop/engine.py` already has this bug — no `set_active_step`). Arnold unaffected (own runner). | If shared dispatch ships, it must carry `active_step.run_id` + a liveness sink. |
| A5 | Sandbox/trust under shared dispatch | LOW, no new hole | two foot-guns: make `install_sandbox` fail-closed; per-call `project_dir`. |
| A6 | Prompt-assembly boundary | HONEST seam (not a half-measure) | no change; optionally validate `shim_state`. |
| A7 | Executor merge (m1) | LOW-MED, ~1 day — **as a superset** (`run_pipeline(policy=None)`), not a swap | trap: never route prod through the policy variant (drops override edges). Fixes a real lossy bug. Worth doing. |
| D1 | Cost attribution for non-plan dispatch | HIGH gap — cost is plan-dir-scoped; non-plan dispatch vanishes | only matters if shared dispatch ships (Arnold tracks its own). |
| D2 | schema_version migration + rollback | Migration testable; **rollback NOT safe** (`StorageModel` `extra="forbid"` → revert strands plans); no fixture corpus | one-line fix: `extra="ignore"` on `Plan` + `schema_version` field + build a fixture corpus. Must ship in m1 if we touch state shape. |
| D3 | Event schema unpinned + duplicate systems | MEDIUM — two parallel event systems (`events.ndjson` vs Store `EpicEvent`), unpinned, naming collisions | pin the envelope; reconcile the two or document the split. |
| D4 | CI can't enforce the gate | HIGH — CI runs **4 of 50 files** (named list); 92% unenforced. Parity gate IS hermetic. | switch CI to `pytest -m "not slow"`. Cheap, high-value, do first regardless. |

## What "full confidence" actually concludes
1. **The high-risk item was the premise, and it doesn't hold.** Generalizing planning for Arnold is
   unjustified — Arnold shares only the (already-shared) `Store`.
2. **The genuinely valuable work is small and mostly unconditional** — and is hygiene/safety, not a
   platform epic:
   - **CI fix** (marker-based discovery) — 92% of tests are unenforced today. Highest ROI, do first.
   - **Executor merge as a superset** — fixes the real lossy `run_pipeline_with_policy` bug. ~1 day.
   - **Backward-compatible state hygiene** (`extra="ignore"`, optional `schema_version`, fixture corpus).
   - **Two foot-gun fixes** (sandbox fail-closed; stall-sink on the loop path).
3. **Planning-internal quality refactors** (routing collapse, RunConfig, evidence seam, pack-ification)
   are worth doing **as planning hygiene** if desired — but framed honestly, not as "shared for Arnold."
4. **The real platform move, if wanted, is the inverse of the plan:** recognize/document the
   `Store` + control-plane as the shared substrate and make planning consume it as cleanly as `resident/`
   already does — most of which already exists.

## Recommended shape — two tracks
- **Track 1 (do now, standalone PRs, no epic):** CI marker-switch · executor-merge superset ·
  state back-compat (`extra="ignore"` + fixture corpus) · sandbox/stall foot-guns. Cheap, safe, high-value.
- **Track 2 (HOLD):** the generalization (pack-agnostic dispatch, evidence strategy, pack-ification).
  Gate on a **confirmed second DAG-shaped tenant** that needs it — Arnold isn't it. Until then it's
  speculative generality the principle says to avoid.

## The one thing only Peter can resolve
Is the generalization justified by something not in the code today — a future DAG-shaped tool, or an
intent to migrate Arnold onto planning's dispatch later? If yes, Track 2 is justified prospectively (and
we'd want that tool's shape to design it right). If no, the confident plan is Track 1 + treat Store/control
as the already-existing shared layer.
