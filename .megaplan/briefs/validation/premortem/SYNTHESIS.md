# Pre-mortem synthesis — Pipeline Unification epic

12 lenses (8 Claude judgment + 4 DeepSeek surface sweeps), each assuming the epic already failed.
Full per-lens findings: `p1`–`p8` + the DeepSeek sweeps (folded in below). All code claims spot-verified.

## Convergent killer findings (multiple independent lenses agreed)

### A. The auto.py in-process port (m3) is the risk crux — and nothing needs it
Flagged independently by **six** lenses:
- **p1:** in-process auto blinds observability — `doctor._check_orphan_subprocesses` / `introspect._process_tree` scan for `megaplan <plan>` child PIDs; liveness/timeout compute against per-phase subprocess lifecycle. One long-lived PID breaks all of it.
- **p2:** the per-phase subprocess is a *container safety property* — OOM/crash kills the phase, parent retries. In-process, an OOM kills the whole runner; recovery falls back to from-scratch restart. Even if you want in-process *policy*, keep *worker dispatch* out-of-process.
- **p3:** porting auto in-process removes the last version-isolation seam and creates the self-reference deadlock (below).
- **p4:** the subprocess→in-process boundary is exactly the regression surface the mock parity gate is blind to by construction.
- **p5:** biggest over-build; zero pack/product value; "two engines coexisting" is fine.
- **p7:** over-bundled (4 sub-projects in one apex milestone) and freezes the chain behind the riskiest item.

**And m4/m5 do NOT depend on it** (p5, p7): they need m1's *executor merge* (one override-complete path), not in-process auto. The dependency is false and severable.
→ **Revision: drop/defer the auto.py in-process port; keep two engines; sever m4/m5's dependency on m3.** Keep only the test_auto_drive oracle + the status/contract pin from m3's scope.

### B. Pack-ification may be aimed at the wrong target — Arnold already exists, and it's not a pipeline (p6, VERIFIED)
In-tree right now: `schemas/arnold.py` (437 L), `store/base.py` (1,354 L — a `Store` Protocol with `Transaction`, `RevisionConflict`, `LockConflict`, `LeaseConflict`, `ExecutionLease`, `ResidentConversation`), a full `store/` package (db/file/blob/snapshot/multi/identity/legacy_migration), and `loop/engine.py` (743 L `MegaLoop`). Arnold is a **long-running, transactional, lease-based, event-sourced, resident-conversation service** — the opposite shape of a finite-DAG pipeline pack (`Pipeline` = static `Edge`s + a `while`-loop to `halt`; state = one last-writer-wins `state.json`; `ParallelStage` forbidden from shared state).
The epic spends its apex milestones (m3/m5/m6) generalizing planning **along the axis it already varies on** (more DAG phases) — none adds an await-event edge, transactional state, or a resident loop. The tell: the only two non-planning packs (creative/doc) never dispatch a model — genericity is asserted, not demonstrated.
→ **Cheap de-risk BEFORE apex effort:** (1) a half-day paper spike expressing Arnold's resident loop in the current `Pipeline/Stage/Edge/StepResult` vocabulary against the real schemas — enumerate every primitive with no home; (2) ship m2's pack-agnostic dispatch as a **standalone service** Arnold can call *without being a pipeline*. If a resident tool can dispatch + share state without being a pack, the thin-shared-services thesis wins and m3/m5/m6 defer.

## Guardrail findings (do these regardless of scope)

### C. schema_version must be legacy-tolerant, never fail-closed (p2, p3, p8, pm-persistence)
Absent version → treat as v0 → run existing migration → stamp. **Migration must run BEFORE validation** (`load_plan_from_dir` is called on every plan load incl. `megaplan status`/`list`; a strict validator deadlocks every pre-epic plan and every live cloud chain). `chain_state.json` needs the same + a write lock. Round-trip gap: `Plan.to_plan_state()` / `schemas/sprint1.py` silently drops stamped fields (`schema_version`, `dispatch_path`) — not in any touchpoint list.

### D. The parity gate is necessary but is NOT "drift provably zero" (p4)
Mock-only, happy-path-only, excludes state/phase_result/receipts; agent-invariant (can't see routing/cost/timeouts); both arms run in-process so it's blind to the m3 boundary. Re-label the claim to "control-flow + artifact parity on the happy path." Add: `extract_decision_fields` + `make_worker_sequence`-forced branch diffs; structural comparison of phase_result/receipts/faults (incl. a test that dropping `set_active_step` FAILS the gate); routing/profile resolution without the mock bypass.

## Missing surface area the epic did NOT capture (the explicit ask)
- **Two more subprocess drivers** beyond auto.py: `_core/workflow.py::resume_plan` (subprocess + hardcoded planning-phase dict) and `loop/engine.py::MegaLoop` (independent `subprocess.Popen` driver). m3 unifies one, leaves two.
- **A THIRD next-step encoding:** `_core/workflow.py::workflow_next` (feeds override's 9 actions, status `next_step`, doctor, introspect). m4 collapses only the `inprocess_step` encoding → `workflow_next` left as an unreconciled third source.
- **Second cloud→auto coupling:** `cloud/cli.py:225` imports `auto.py::_phase_command` (distinct from the supervise SSH coupling) — breaks when auto is ported.
- **Observability rides the execution model:** doctor/introspect read `state.json` raw (bypass the store) AND scan subprocess PIDs — break under both schema_version and m3.
- **Raw state readers that break on schema_version:** `list`, `feedback search`, `introspect` use bare key access bypassing `load_plan`.
- **63 raw `state["config"]` reads outside handlers** — m5's typed surface authoritative in only half the codebase.
- **InProcessHandlerStep is THE chokepoint** hardcoding `handler(root, args)` — the m5 signature change breaks ALL pipeline flows, not just planning.
- **Many auto importers:** chain (constants), control.py, handlers/init.py (`auto.drive`), cli/parser.py.
- **Skipped tests in blast radius:** tmux worker path, docker cloud lifecycle — uncovered in CI.
- **DB mirror:** the supabase `plans` table mirrors plan-state shape; schema_version/dispatch_path need a coordinated path through `Plan.to/from_plan_state`.

### E. Don't dogfood the epic on itself off an editable install (p3)
`megaplan chain` binds `auto.drive` in-memory at startup while phase subprocesses re-import from disk, and `_refresh_base_branch` does `git checkout main && git pull` on the engine's own tree between milestones → split-version driver. Recommendation: drive from a **pinned external engine** (own venv/tag or pinned cloud image) with the epic tree as the *target* repo; keep the schema validator **report-only until the final milestone**; run the driver on the subprocess path throughout (`MEGAPLAN_UNIFIED_DISPATCH` default-OFF); `--no-git-refresh` off a frozen branch.

## Recommended revised epic shape
**Phase −1 (cheap, days):** Arnold paper-spike + ship m2 pack-agnostic dispatch as a standalone callable service. **Gate the whole epic on the spike's result.**
**m1-lean:** parity gate (with real teeth, relabelled claim) + legacy-tolerant schema_version + status/chain-name contract pins + the two write fixes + assertion-grade discovery guard + executor merge. (Skip the unified-dispatch toggle unless the auto port stays in.)
**m2 (parallel, off m1 base):** profile pack-agnosticism + the live model-dispatching reference pack. Independent — delivers Arnold value early, off the critical path.
**m4 re-pointed onto m1** (not m3): planning pack-ification + collapse ALL THREE next-step encodings.
**m5 thin slice:** `RunConfig` + `services` as an added kwarg (no signature break, no "pure handlers"); drop 81-field typing.
**m6 half-day:** mode-keyed in-place fork consolidation (skip `capabilities` tuple + the symmetric Realizer Protocol).
**auto.py in-process port:** spun out, optional, gated on a real second tenant that needs it.
**Land m1 pieces as standalone PRs to main** as they pass (not one long-lived epic branch); reserve the chain for the true serial spine.
