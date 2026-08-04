# Sprint brief: ship safe Execute fan-out and conflict custody

## Outcome

Make the Execute phase genuinely useful for independent tasks while preserving
the custody guarantees that the critique recovery work depends on. A ready
frontier may run concurrently only when its task contracts prove that it is
safe. Results are returned as immutable task artifacts (commit/patch, base
revision, write/effect sets, hashes, and evidence), and a single deterministic
reducer admits them to the plan. Any overlap, stale base, malformed result,
failed merge, or missing receipt becomes a typed conflict/blocked state; it is
never finalized, silently overwritten, or presented as successful acceptance.

The sprint ends with a cloud canary on an isolated runtime and a documented
rollback path. It must not mutate or restart the currently live critique run.

## Scope

### In scope

- Extend the finalized task contract with explicit `depends_on`, base revision,
  write set, effect set, concurrency class, and retry/idempotency identity.
- Compute ready frontiers and partition them into safe sibling waves with a
  bounded concurrency limit and a sequential fallback for unknown or unsafe
  tasks.
- Give every parallel task an isolated worktree/branch (or equivalent patch
  custody), WBC/lease ownership, and a stable attempt identity.
- Return a machine-readable worker envelope containing task id, plan/run id,
  base SHA, result commit/patch, changed-path and effect manifests, content
  hashes, tests/evidence, and lifecycle status.
- Add a single-writer reducer that validates envelopes, rejects stale writers,
  detects declared and actual overlap, merges disjoint results in deterministic
  order, and emits a durable merge receipt.
- Define conflict classes and resolution: retry a transient infrastructure
  failure once; serialize or rebase a safe overlap; dispatch a bounded resolver
  for a typed semantic conflict; otherwise stop at `blocked`/`review_required`.
  A resolver may propose a patch, but the reducer still validates it against
  the same base/effect/acceptance gates.
- Make Finalize and acceptance fail closed when a merge receipt is absent,
  stale, conflicted, or only narrative. Finalize must not invent a resolution.
- Make retries/restarts idempotent: preserve accepted siblings, avoid duplicate
  effects, and resume from the durable frontier rather than rerunning a whole
  plan.
- Add status/notification fields for `ready`, `running n/m`, `merge_pending`,
  `conflict`, `resolved`, `blocked`, and `accepted`, with one coalesced alert
  per incident transition.
- Add deterministic unit, integration, crash/retry, and cloud-canary tests.

### Out of scope for this sprint

- Redesigning the Critique phase or changing the live critique session.
- A whole-pipeline parallel rewrite, a new database/event bus, or a new model
  routing policy unrelated to Execute custody.
- Merging whole worktrees or allowing an LLM to choose an unchecked overwrite.
- Treating plan bookkeeping/progress as acceptance evidence.
- Automatic acceptance of unresolved conflicts or indefinite retry loops.

## Locked decisions

1. No shared mutable worktree for parallel workers.
2. The reducer is the sole authority that changes accepted plan state.
3. Git/path overlap is a hard conflict unless an explicit, testable resolver
   contract says otherwise; effect overlap is always treated conservatively.
4. Deterministic merge order is part of the contract, not an implementation
   accident.
5. Missing custody, version, evidence, or merge receipt fails closed.
6. The default concurrency cap is small (2–4; never above the configured
   resource budget), and the sequential path remains a first-class fallback.
7. Unresolved conflict cannot enter Finalize, release, or success notification.

## Questions the planner must settle

- Whether the first implementation should use temporary branches, patch bundles,
  or both at the existing Execute seam.
- How to represent semantic overlap (imports, schemas, generated files, and
  external effects) beyond changed paths without making the scheduler opaque.
- Where the reducer and merge receipt belong in the existing WBC/effect-ledger
  contracts, and how cloud restart reconstructs its frontier.
- Whether to reuse the existing threaded batch helper or introduce a task-scoped
  worker pool with explicit cancellation and resource accounting.
- Exact isolated-canary and rollback procedure for the Hetzner runtime.

## Touchpoints

- `arnold_pipelines/megaplan/execute/batch.py`
- `arnold_pipelines/megaplan/execute/merge.py` and related custody/effect code
- `arnold_pipelines/megaplan/_core/io.py`
- Finalize schema/prompt/handler and plan-state admission gates
- `arnold_pipelines/megaplan/runtime/batch.py`
- Native runtime parallel-map lowering and its tests
- Worktree/WBC/lease, lifecycle, notification, and cloud status code

## Done criteria

- Two independent tasks overlap in wall-clock time in a controlled test and
  prove separate roots, leases/WBCs, attempts, and artifact ownership.
- Disjoint siblings merge deterministically, produce one receipt, and pass the
  combined acceptance suite.
- Same-file/effect overlap produces a durable conflict receipt; no Finalize or
  acceptance transition occurs until an explicit resolver/serialization path
  clears it.
- A worker crash and duplicate retry produce at most one accepted task/effect;
  accepted siblings are preserved.
- A stale base or changed write set is rejected and recoverable without a silent
  overwrite.
- Finalize cannot synthesize conflicts and status/notifications show one clear
  incident rather than repeated identical messages.
- Unsafe/unknown frontiers use the sequential fallback and remain correct.
- Targeted tests, lint/type checks, and an isolated cloud canary pass; the
  current live critique run is unchanged.
- Any deferred broad rollout or semantic resolver work is recorded in the
  follow-up epic before handoff.

## Anti-scope / safety guard

Do not “prove” parallelism by running two workers against the same checkout,
and do not call a run healthy merely because bookkeeping advanced. A run is
shippable only when worker custody, reducer receipt, merge result, and
acceptance evidence all agree.
