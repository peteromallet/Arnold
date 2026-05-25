# Sprint brief: Foundation hardening — planning-unification prerequisites

**Profile (recorded):** `apex/full/medium` — tier 5 (Claude author/repo-reading + Codex structural
critic), full robustness, medium planner depth / low critic depth.
**Run in a worktree** (`--in-worktree foundation-hardening`); multi-PR foundation work that must not
disturb `main`. **Brief input:** this file + `briefs/planning-unification-FOUNDATION-AUDIT.md`
(the evidence ledger; every claim is verified there with `path:line`).
**Revised 2026-05-24** after a 5-lens sense-check (omissions / over-scope / sequencing / correctness
/ production-risk). Material changes folded in: field-ownership merge model (not "pick one default");
recovery-exempt state transitions; W0 reframed as a drift-detector with per-workstream correctness
tests as the real oracle; a `MEGAPLAN_FOUNDATION_HARDENING` reversibility flag; staged into two
releases; verified line numbers.

---

## 1. Outcome

Harden the substrate the planning-unification epic
(`briefs/pipeline-unification-planning-as-pack.md`) will build on, so that epic starts on verified
ground instead of latent bugs. After this sprint: the pipeline executor can correctly run planning's
topology; `state.json` writes are atomic, versioned, and schema-complete; one documented plan
lifecycle state machine governs all writers (with recovery paths explicitly permitted); observability
emits identically on both dispatch paths; the profile system is pipeline-agnostic; pack discovery
fails loud; and a permanent drift-detection harness guards the legacy-vs-pipeline decision surface.
**Every change is independently valuable as a bug-fix or hardening — none commits us to the epic.**

## 1a. Release staging (blast-radius control)

Ship in **two independently-revertable releases**, each behind the `MEGAPLAN_FOUNDATION_HARDENING`
flag (below). W0 lands first in both as the safety harness.

- **Release A — state & lifecycle core (highest risk):** W0 (drift harness + flag), W1 (atomic
  writes + schema + field-ownership merge), W2 (lifecycle transitions). The changes that touch the
  production write path; smallest, most-scrutinized release.
- **Release B — executor, emission, platform hardening:** W3 (executor), W4 (emission hook), W5
  (pipeline-agnostic profiles), W6 (discovery), W7 (cloud bypass). Builds on A's state model.

Each release must be revertable without a code rollback: the flag is resolved at plan-init and
stamped into `state.json`; flag-off uses the legacy paths; new keys are additive so old code tolerates
them.

## 2. Scope — eight workstreams

**W0 ships first** as the drift-detection harness. **Note (corrected): W0 is a *drift detector*, not
a correctness oracle** — it runs the *same* `handle_*` on both sides via `InProcessHandlerStep`, so a
handler bug identical on both paths passes green. It catches divergence between dispatch paths and is
permanent regression armor; it is NOT sufficient evidence that a W1–W4 change is correct. **Each of
W1–W4 ships its own deterministic correctness tests + at least one real-plan fixture** (below) — those
are the real oracle.

### W0 — Drift-detection harness + reversibility flag (ship first) — epic §7, hazard 8
- Build the legacy-vs-pipeline decision-field diff harness: deep-copy a plan dir; run legacy
  `handle_*` on the original and the corresponding pipeline Step on the copy; diff
  `extract_decision_fields()` (state transitions, gate recommendation, downgrade decisions, next-step
  labels, artifact filenames). Use `MEGAPLAN_MOCK_WORKERS` + `conftest.make_worker_sequence`
  (`conftest.py:268`) `mock_overrides` to exercise the **reprompt / auto-downgrade / tiebreaker**
  branches, not just the happy path. **Fixtures must be extensible** — W3 extends them for
  override/abort/retry/resume branches.
- **Fix the harness's own corruption blind spot:** the parity/state read path
  (`inprocess_step.py:118-127` `_read_state`) swallows `JSONDecodeError → {}`; the harness must read
  state via the W1-fixed loud reader, or a corrupt-state bug shows `{}` on both sides → false green.
- Add a **full byte-level diff mode** (opt-in, not CI-default) comparing raw `phase_result.json` +
  `state.json`, for validating the "legacy unchanged" claim against real-plan snapshots (W4/risk).
- **`MEGAPLAN_FOUNDATION_HARDENING` flag:** env toggle resolved at plan-init, stamped into
  `state.json` (`hardening_enabled`), gating all W1–W3 behavioral changes so legacy and new paths
  coexist and each release is revertable. (~15 LOC; the epic's hazard-8 toggle, pulled forward.)
- **Done:** harness dual-runs the full phase set across happy + reprompt/downgrade/tiebreaker, green
  in CI; uses the loud state reader; byte-diff mode exists; the flag routes dispatch and is stamped at
  init; documented as permanent armor.

### W1 — State write discipline + schema + field-ownership merge — audit F1
- Route **all** `state.json` / `chain_state.json` writes through `atomic_write_json`. Kill the
  **three** non-atomic writers (verified): `chain.py:1646`, `auto.py:845` and `auto.py:945` (both in
  `_recover_execute_callback_failure_state`, fn starts `:802`). *(Note: `auto.py:771` is a param to
  `record_lifecycle_failure`, which is already atomic — do not chase it.)*
- Also make `ResumeCursor.save()` atomic (`resume.py:85` is raw `write_text`) — folded here so W3
  doesn't introduce a new non-atomic writer.
- **Corrupt-state handling:** `read_json` (`_core/io.py:262`) already *raises* `JSONDecodeError`
  (never returned `{}` — the audit's "silent loss" was overstated). Keep it loud; add a
  **quarantine-copy** of the corrupt file before re-raising. Document that raise-on-corrupt is
  intentional and must NOT regress to `{}`. (No legitimate empty-dict fallback exists; missing file is
  a separate `FileNotFoundError` path used by fresh-plan init.)
- Add `schema_version: int` to `state.json` and `chain_state.json`, stamped on **every** write.
- Complete + validate TypedDicts: add `last_gate` to `PlanState` (`types.py:149`); add
  `tiebreaker_count`, `current_invocation_id`, `worktree`, `epic_id` to `PlanMeta` (`types.py:61`).
  Load-time validator **warns** on unknown top-level keys (no hard-reject — forward-compat).
- **Merge model — field-level ownership, NOT a single global default.** The four strategies
  (`save_state_merge_meta` in-memory-wins; `_merge_state_to_disk` disk-wins; `touch_active_step`
  no-merge; `save_state` blind) cannot collapse to one winner without breaking callers. Adopt
  `_merge_state_to_disk`'s model everywhere: **executor-owned keys (from `state_patch`) win for those
  keys; disk wins for the rest; merge-list fields stay merged.** Refactor `save_state_merge_meta`
  callers to **declare owned keys** rather than trust in-memory. This must also fix the
  **StallDetector/CostTracker in-memory staleness** (`runtime.py:38-76`): policy hooks must observe
  fresh disk state (re-read or owned-key model), not the executor's stale dict.
- **Done:** zero raw `state_path.write_text(json.dumps...)` (all 3 + ResumeCursor converted); every
  write stamps `schema_version`; corrupt-state test asserts loud failure + quarantine; TypedDicts
  include all production keys + warn-validator; one documented field-ownership merge function with a
  test proving conflict-resolution AND a test proving StallDetector reads fresh state; a real-plan
  fixture round-trips through the new writers unchanged.

### W2 — Plan lifecycle state machine (recovery-aware) — audit F1/F10
- Extend `WORKFLOW` (`_core/workflow_data.py:43-85`) to cover the currently-undefined states
  (`failed`, `blocked`, `paused`, `cancelled`, `reviewed`, `done`, `awaiting_pr_merge`) and their
  transitions.
- Add one `transition(state, event, *, force=False) -> state` as the **single** authority; route the
  four external writers through it: `chain.py:1646`, `_core/workflow.py:resume_plan` (`:349-353`),
  `store/plan_repository.py:record_lifecycle_failure` (`:392`),
  `auto.py:_recover_execute_callback_failure_state` (`:802-848`).
- **Recovery paths are EXPLICITLY PERMITTED, not rejected (critical correctness/risk fix).** The
  following are load-bearing recovery semantics — encode them as *validated* transitions (or via the
  `force=` recovery path), never as illegal: `blocked→executed` (`_mark_blocked_execute_as_executed`),
  `any→blocked` / `any→failed` (`record_lifecycle_failure`), `failed→executed` / `failed→finalized`
  (`_recover_execute_callback_failure_state`). A strict machine that rejected these would turn today's
  silent recoveries into **permanently-stuck plans** — worse than the status quo.
- **Done:** `WORKFLOW` covers all states; all four writers call `transition()`; recovery transitions
  pass (asserted); genuinely-illegal transitions raise; a **crash-mid-recovery test** asserts the plan
  stays resumable (not stuck); resolved semantics documented.

### W3 — Executor can run planning's topology — audit F2 (BLOCKER) — Release B
- Port override-edge dispatch into `run_pipeline_with_policy`: copy the `find_override_edge` /
  `verdict.override` block from `run_pipeline` (`executor.py:268-273`) into the policy variant after
  `:377`. Verify the surrounding state (in-scope vars, edge-resolution order) matches before copying.
- Add the missing escalate **abort** branch (`:386-392` handles only `force_proceed`) per
  `runtime.py`'s contract (`:86-87`).
- **Disambiguate first-match edge dispatch** (`executor.py:276-291`): when multiple edges share a
  recommendation (planning's gate self-loops), match by `(recommendation, target_stage)`, not first
  hit. A test exercises the gate-loop topology.
- Wire the dead retry hooks `ContextRetry` / `BlockedRetry` (`runtime.py:105-143`) into the post-step
  policy block **with explicit handling of all 7 `ExitKind`s** (`orchestration/phase_result.py:20-33`:
  success / blocked_by_quality / blocked_by_prereq / timeout / context_exhausted / internal_error /
  external_error), matching `auto.py`'s behavior — not just the 2 the hooks cover today. Add a
  **per-stage retry cap** (`max_retries_per_stage`, independent of `max_iterations`) to prevent
  infinite re-dispatch.
- Persist a `ResumeCursor` (atomic, per W1) after each successful stage so a mid-graph crash resumes
  from the last stage. Ensure it does not conflict with the human-gate `awaiting_user.json` pause path.
- **Done:** tests prove `run_pipeline_with_policy` dispatches override + abort, disambiguates gate
  self-loops, handles all 7 ExitKinds with a retry cap, and resumes mid-graph after a simulated crash;
  planning's full gate-loop topology walks correctly under the policy executor (validated against W0).

### W4 — Shared post-step emission hook — audit F4 (BLOCKER) — Release B
- Create a **new lightweight shared module** (e.g. `megaplan/observability.py` or
  `megaplan/_core/emission.py`) housing `_emit_post_step(phase, state, plan_dir, ...)` →
  phase_result + receipt + history + `emit(EventKind.PHASE_END)` + state save. **The placement is a
  real architectural decision, not trivial:** `executor.py` deliberately imports only stdlib + types
  (docstring `:6-9`), and the hook's deps are heavy (`receipts`, `orchestration.phase_result`,
  `_core`). Put the hook where both `_finish_step` and the executor can import it, and **consciously
  relax** the executor's import-purity constraint for this one path (document it). Invoke it
  identically from both. Additive — legacy behavior unchanged (validate via W0 byte-diff).
- Wire the `current_invocation_id` lifecycle: `_emit_phase_result` reads
  `meta.current_invocation_id` (`phase_result.py:627`), set by `set_active_step` (`state.py:510`),
  which the executor never calls — establish it in the hook or emission silently skips. Verify
  `set_active_step` has no other side effects the executor would now trigger.
- Parameterize `upstream_artifact_hashes` (`receipts/schema.py:46-63`) by a pipeline artifact map
  instead of hardcoded planning filenames (else renamed artifacts silently produce empty hashes).
- Deprecate the dormant `_pipeline/receipt.py`; document `megaplan/receipts/` as canonical (it **is**
  load-bearing — the epic brief's "unused" claim is wrong). Add `status_version: 1` to
  `_build_status_payload` (`cli.py:932-1050`); document the fields consumers read.
- **Done:** `megaplan run planning` emits phase_result/receipt/history/PHASE_END at parity with legacy
  (asserted, incl. W0 byte-diff on a real-plan fixture); status JSON carries `status_version`;
  `_pipeline/receipt.py` deprecated with no live callers.

### W5 — Pipeline-agnostic profiles — audit F3 (BLOCKER for the epic's premise) — Release B
- `resolve_agent_mode`: change the bare `DEFAULT_AGENT_ROUTING[step]` (`workers/_impl.py:~2744`) to
  `.get(step)` with a **specific, actionable** failure (don't let `None` crash downstream as
  `AttributeError`): `raise CliError("unknown_step", f"Step {step!r} has no default agent. Pipeline
  stages: {sorted(pipeline_stages)}")`.
- Replace `VALID_PHASE_KEYS` validation (`profiles/__init__.py:24,178-183,271-276`) with per-pipeline
  stage validation (against the target pipeline's actual step names, not planning's 13).
- Wire the already-built, currently-dead slot-agnostic `Profile.model_for()` (`_pipeline/profile.py`,
  imported only by tests) into Step dispatch. **Resolve the dispatch seam explicitly:**
  `InProcessHandlerStep.run()` (`inprocess_step.py:72`) passes `Namespace(agent=None, ...)` and the
  handler calls `resolve_agent_mode` — so either thread the resolved model into the Namespace
  (`agent=resolved_model`) so the handler uses it, or scope W5 to non-InProcessHandlerStep callers.
  Do NOT break the legacy path (which has no `ctx.profile`). **This must not cross into the anti-scope
  HandlerContext/pack-ification work** — if it can't be done without that, stop and flag it.
- **Done:** a non-planning test pack with a Step that **actually calls `resolve_agent_mode`** (not a
  creative/doc stub that never resolves a model) resolves profiles without `CliError`/`KeyError`;
  planning's existing resolution is unchanged (W0 green).

### W6 — Discovery fails loud — audit F7 — Release B
- Convert the three silent `except → return None` paths in `_load_module_from_path`
  (`registry.py:313-314, 321-322, 337-339`) to `logging.warning` (module path + exception); record a
  `discovery_errors` map the registry surfaces.
- Strengthen the §8 discovery-integrity guard: `get_pipeline("planning")` (forcing `build_pipeline()`
  to compile) **and** resolve one canonical planning prompt key (prompt registration is a separate
  import that can fail independently) — not just a name-in-list check.
- **Done:** a deliberately-broken pack logs a warning + `discovery_errors` entry (no silent vanish);
  the guard fails if `planning` doesn't compile OR a known prompt key doesn't resolve; tested.

### W7 — Cloud consumer-bypass versioning + inventory — audit F5 — Release B
- Replace the cloud `sync-refresh` raw remote import (`cloud/supervise.py:54`,
  `python3 -c "from megaplan.chain import ..."`) with a versioned CLI subcommand
  (`megaplan cloud sync-refresh --spec <path>`) that stamps/checks `chain_state.json`'s `schema_version`.
- Add a CI smoke test diffing the in-process status payload vs real-subprocess `megaplan status`.
- **Inventory (handoff artifact, not a fix this sprint):** document the other consumer bypasses the
  epic's DAG-runner will break — `chain.py` glob reads of `execution_batch_*.json` (`:1588`) /
  `finalize.json` (`:1617`), and `bakeoff` importing `_core.state.load_plan`.
- **Done:** no `python3 -c "from megaplan..."` in `cloud/`; sync-refresh goes through the versioned
  subcommand; status-parity smoke test green; bypass inventory documented.

## 3. Locked decisions
- **No new pipeline types or registry features.**
- **Legacy path stays default and behavior-unchanged** behind `MEGAPLAN_FOUNDATION_HARDENING=off`;
  every change is additive or gated. Validated by W0's byte-diff against real-plan fixtures.
- **Merge model = field-level ownership** (executor-owned keys win; disk wins for rest; merge fields
  merged) — *not* a single global in-memory/disk default.
- **Recovery transitions are permitted, not rejected** (W2).
- The canonical receipt system is `megaplan/receipts/`; `_pipeline/receipt.py` is deprecated.
- `read_json` stays loud on corrupt input (quarantine + raise), never `{}`.
- The state schema + field-ownership merge, the lifecycle transition function, and the emission-hook
  contract + versioned status JSON are the **handoff artifacts** the epic cites.

## 4. Open questions (planner must resolve, not invent)
- Exact `owned-keys` declaration mechanism for each `save_state_merge_meta` caller.
- The exact `WORKFLOW` transition table entries + which events carry `force=` recovery semantics.
- Final home of the emission hook module given the import graph (and the precise scope of the
  executor import-purity relaxation).
- The W5 dispatch seam: thread model into `Namespace` vs scope to non-InProcessHandlerStep callers.

## 5. Constraints
- **Reversibility:** all W1–W3 behavioral changes gated by `MEGAPLAN_FOUNDATION_HARDENING`, resolved
  at plan-init and stamped into `state.json`. Two-release rollout (§1a); each independently revertable.
- **Backward-compatible:** in-flight plans with no `schema_version` load fine (absent = v1, stamp on
  next write); no forced migration that breaks running plans. New TypedDict keys are additive.
- **Cloud version-skew window:** during rollout, new-local + old-remote (or vice-versa) shelling
  `megaplan status` / W7 sync-refresh must not hard-fail; the pinned status-JSON + `schema_version`
  are the guard.
- **Atomic + crash-safe:** all writes via `atomic_write_json`; recovery paths exempt from strict
  transition rejection so a crash mid-recovery never strands a plan.
- **No regression on the legacy production path** — W0 byte-diff on real-plan fixtures is the gate.
- **Public API:** the two `handle_*` `__all__` exports keep their signatures (HandlerContext is epic).

## 6. Done criteria (sprint-level)
- **Release A** shippable: W0 harness green (happy + branches) in CI; W1 atomic/versioned/field-merge
  with StallDetector-freshness test + real-plan round-trip; W2 recovery-aware transitions with
  crash-mid-recovery test; all gated by the flag; legacy byte-identical (flag off).
- **Release B** shippable: W3–W7 per-workstream Done met; pipeline path emits + resumes + dispatches
  overrides + all-7-ExitKind retries correctly; profiles pipeline-agnostic; discovery loud; cloud
  bypass versioned.
- Handoff artifacts documented for the epic: (1) state schema + field-ownership merge, (2) lifecycle
  transition function (incl. recovery semantics), (3) emission-hook contract + versioned status JSON,
  (4) ambient-handler-input inventory (§ below), (5) consumer-bypass inventory (W7).

## 6a. Handoff inventories (documentation, not builds — for the epic's Body 1b/Body 3)
- **Ambient handler inputs (audit F6):** enumerate every input a future `HandlerContext` must capture
  — `args` mutated in-place by `apply_profile_expansion` (sentinel flags), the ~14 `MEGAPLAN_*` env
  vars, `resolve_agent_mode` reading `~/.megaplan/config.json`, handler subprocess/event/PATH side
  effects — with `path:line`. Body 1b will silently break without this.
- **Consumer bypasses (W7):** the chain glob reads + bakeoff internal imports above.

## 7. Touchpoints
`megaplan/_pipeline/executor.py`, `runtime.py`, `resume.py` (`:85` atomic), `registry.py`,
`_pipeline/profile.py`, `_pipeline/receipt.py`, `_pipeline/stages/inprocess_step.py` (`:118-127`,
`:72`) · `megaplan/_core/io.py` (`:262`), `state.py` (`:210,400,510,514`), `workflow.py` (`:349`),
`workflow_data.py` (`:43-85`) · `megaplan/store/plan_repository.py` (`:174,392`) ·
`megaplan/types.py` (`:61,149`) · `megaplan/handlers/shared.py` (`:355`),
`megaplan/orchestration/phase_result.py` (`:627`) · `megaplan/profiles/__init__.py`
(`:24,178-183,271-276`) · `megaplan/workers/_impl.py` (`resolve_agent_mode`) · `megaplan/chain.py`
(`:1646,1588,1617`) · `megaplan/auto.py` (`:802-848` incl. `:845,:945`) · `megaplan/cli.py`
(`_build_status_payload`) · `megaplan/cloud/supervise.py` (`:54`) · `megaplan/receipts/schema.py`
(`:46-63`) · new emission module · `tests/test_pipeline_parity.py`, `tests/conftest.py` (`:268`),
+ new tests per workstream + real-plan fixtures.

## 8. Anti-scope (do NOT do — these are the EPIC, not this sprint)
- **Do NOT** pack-ify planning / move it to `pipelines/planning/` / drop it from `_BUILTIN_NAMES`.
- **Do NOT** build `HandlerContext` or change `handle_*` signatures (Body 1b). W5 must stop short of
  this; if profile thread-through requires it, flag and halt.
- **Do NOT** rewire the CLI off `COMMAND_HANDLERS` or rewrite `auto.py` in-process (Body 2).
- **Do NOT** extract realizers / DAG-runner or refactor `execute/`'s `is_prose_mode` seam (Body 3).
- **Do NOT** touch or merge PR #43 (`worktree-execute-redesign`) — it re-homes into Body 3 later.
- **Do NOT** demote the gate verdict vocabulary or promote `FaultRegistry`/`DeadlockResolver` (Body 3).
- Keep this sprint to **fixing the foundation**, not building on it.
