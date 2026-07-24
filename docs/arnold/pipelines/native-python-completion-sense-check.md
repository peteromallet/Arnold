# Native Python Completion — Epic Reshape Sense-Check

**Status:** Claude's load-bearing questions + believed answers (Phase 1 of a 3-model check).
**Subject:** the 3-epic reshape of `migration-completion-plan-v4.md` (regrouping V4 milestones M1–M7 into 3 strictly-sequential epics).
**Companion outputs:** `native-python-completion-sense-check-deepseek.md` (independent answers), `native-python-completion-sense-check-codex.md` (divergence verdict).

---

## Plan under review (the reshape)

The V4 plan's 8 milestones regrouped into 3 strictly-sequential epics keyed off the dependency graph:

- **Epic 1 — Platform contract + layout foundation (M1→M2).** Add `Pipeline.native_program`; make executor/registry/validator/discovery/CLI native-first; keep `resource_bundles` + env flags as transitional shims. Normalize `writing_panel_strict` (single `.py` → package) and `select-tournament` → `select_tournament`. **Handoff:** `native_program` + stable package paths.
- **Epic 2 — Package + runtime migrations (M3→M3.5→M4).** Migrate 9 shared packages (M3), canonical Megaplan (M3.5), and `evidence_pack` (M4). **Handoff:** shared native runtime/resume contract.
- **Epic 3 — Test/doc rewrite + purge (M5→M6→M7).** Native-truth tests + golden traces (M5), native-first docs/scaffolds (M6), inventory-driven final purge (M7).

Each epic ships: narrowed North Star, milestone table, partnered-5 rubric, base-branch strategy, handoff. **Readiness prep:** create `native-python-working-tree` from `editible-install`, reconcile `native-python-pipelines` donor work, commit split-epic specs, review gates on. Plus a launch-ready Epic-1 `chain.yaml`.

## Master load-bearing question (cuts across all 3 epics)

**How much of this plan is already executed, and is the reshape forward-planning or retrospective organization of donor work?**

Verified in the current tree (`editible-install`):
- `Pipeline.native_program: NativeProgram | None` **already exists** (`arnold/pipeline/types.py:316`).
- Executor **already prefers** `native_program` and falls back to `resource_bundles` (`executor.py:138–141,269–294`); builder + validator accept/check it (`builder.py:137,165`; `validator.py:619–629`).
- The full native subsystem **already exists**: `arnold/pipeline/native/{compiler,graph_projection,runtime,routing,flags,ir,trace,hooks,context,decorators,checkpoint}.py`.
- **No** stage-order / `_LEGACY_STAGE_ORDER` strings in `routing.py` or megaplan top-level (the thing M3.5 was to remove is already gone).
- `arnold/pipelines/megaplan/_pipeline/` **does not exist** (the M7 purge target is already absent).
- Git history **already contains** V4 M1–M7 commits: `Complete native pipeline platform contract`, `M2: delete legacy arnold/pipelines/megaplan…`, `M3: migrate shared pipeline packages…`, `M3-5: canonical Megaplan native migration`, `M4: evidence-pack native migration`, `M6 WIP purge progress`, `M7: megaplan relocation, final import inventory, purge`.
- `native-python-working-tree` branch **already exists** (local + remote).

Not-yet / ambiguous:
- `arnold.pipeline.legacy` does **not** exist (still a to-do or N/A).
- Env flags still present (`flags.py`, `executor.py`, `folder_audit/native.py`).
- Only `folder_audit` + `deliberation` literally reference `native_program`; `creative/jokes/doc/writing_panel_strict/select_tournament/epic_blitz/live_supervisor/evidence_pack` show no literal reference — **likely decorator-based (`@pipeline(...)`) migration, but unconfirmed** (could also mean not-yet-migrated in this tree).

**My belief:** the V4 migration has been *substantially executed* already (donor work on `native-python-working-tree`, inherited into `editible-install`). The reshape is therefore less "plan new work" and more "organize/verify/finish already-done work into clean, reviewable, sequential epics + close the real gaps (WIP M6, env-flag purge, `arnold.pipeline.legacy`, M7 inventory)." If true, **the reshape's risk calibration is too high** (it reads like greenfield) and its value is reviewability/gate-ability, not de-risking unknown implementation.

This single question dominates everything below. Each epic's questions are written assuming the work is *partially landed* and the reshape's job is to define acceptance/gaps on top of existing code.

---

## Epic 1 — Platform contract + layout foundation (M1→M2)

**Q1. Is `Pipeline.native_program` actually plumbed through the executor's hot path, or could it be populated-but-ignored dead metadata?**
*A1.* Already plumbed — verified: `_find_native_program` is called on the executor's primary and selection paths (`executor.py:138–141,269–294`), builder attaches it, validator checks it. So the V4 M1 "dead field" risk is already mitigated. Remaining load-bearing risk: the *ordering* must be a hard preference (native wins, bundles only when `native_program is None`), not a tiebreak; confirm there's no path where a populated `native_program` is bypassed for a migrated package.

**Q2. Does adding `native_program` destabilize topology hashing / serialization?**
*A2.* `compute_topology_hash` lives in `arnold/pipeline/topology.py:130` and "projects a stable subset." The M1 brief explicitly adds `test_topology_hash.py` to prove the field doesn't destabilize hashing — which implies the design intends `native_program` to be *excluded* from the hash input (it's an execution artifact, not a topology-declaring field). Belief: correct by design, but load-bearing — if hashing silently shifted for any already-migrated package, resume state and M5 goldens both break. Verify `native_program` is not in the hashed projection.

**Q3. Is the "prefer native, fall back to bundles" fallback keyed on a single source of truth (`native_program is None`), or also on legacy env flags (split-brain)?**
*A3.* Belief: should be single-keyed on `native_program is None`. Load-bearing risk: if executor also consults `ARNOLD_NATIVE_RUNTIME` to decide native-vs-bundle, you get a flag-and-field split-brain where a package has `native_program` but a flag forces bundles. The plan converts flags to no-ops in M1 — verify the fallback decision reads *only* the field.

**Q4. Is `arnold.pipeline.legacy` ready to be the re-export home for graph-era symbols in M1 without breaking current importers?**
*A4.* It does **not** exist yet. Belief: M1 should *create* it as a thin re-export namespace and keep graph symbols importable, deleting nothing. Load-bearing: need an importer census (who imports graph-era symbols from `arnold.pipeline` today) before deciding what `legacy` must re-export. If the `_pipeline/` deletion (per git history) already moved those callers, `legacy` may be near-empty or unnecessary.

**Q5. Is manifest-first discovery actually safe as the *default* in M1 (i.e., does every discoverable package have a manifest)?**
*A5.* The M1 brief converts `MEGAPLAN_M6_MANIFEST_DISCOVERY` to a no-op alias and keeps Python-discovery compatibility. Belief: safe *if* every package that must be discoverable ships a manifest; load-bearing risk is packages reachable only via Python discovery silently disappearing from `arnold pipelines describe`. Verify manifest coverage == registered-package coverage.

**Q6. [reshape-level] Is bundling M1 + M2 into one epic sound, or should M2 (pure layout renames) be split out so it isn't blocked behind M1?**
*A6.* Belief: bundling is defensible — M2 is low-risk mechanical layout work that depends on M1 and unblocks M3, and the handoff ("native_program + stable paths") is coherent as one unit. Risk: if M1 surfaces late surprises (e.g., a hashing regression), M2's cheap win stalls behind it. Strict-sequence epics serialize them; M2 *could* run parallel to M1's tail. Net: keep bundled, but allow M2 to start once M1's contract type lands, not after all of M1.

**Q7. Will the `writing_panel_strict` and `select_tournament` renames leave stale imports/registrations that M3 inherits as confusing failures?**
*A7.* Belief: the named M2 tests cover the renames, but stale references most likely hide in docs, generated metadata, registration dicts, or non-named tests. M3 *assumes* stable paths, so a stale reference surfaces as an M3 failure mis-attributed to behavioral migration. Load-bearing: M2 needs a repo-wide grep gate (`select-tournament`, `writing_panel_strict.py` import paths) as an explicit completion criterion, not just the named tests.

**Q8. Does the human-gate (continue/stop) semantics of `writing_panel_strict` survive the M2 layout move unchanged?**
*A8.* M2 is explicitly layout-only; behavioral parity is only asserted in M3. That creates a window where M2 could ship a latent behavioral break caught only in M3. Belief: acceptable *if* M2 carries at least one behavioral smoke (run the panel, assert continue/stop fires) — verify such a smoke exists in M2, not deferred to M3.

**Q9. [readiness prep] Is creating `native-python-working-tree` from `editible-install` the right foundation, given the branch already exists and `editible-install` carries in-flight changes?**
*A9.* The branch already exists (local + remote); current `editible-install` has staged skill-file changes (per session git status). Belief: the real prep is not "create" but "refresh `native-python-working-tree` onto current `editible-install`, reconcile the `native-python-pipelines` donor payload, and start from a clean tree." Load-bearing: if donor work isn't reconciled first, Epic 1 builds on a stale/dirty base and the "already done" findings above won't match the branch the epic actually runs on.

**Q10. Will the M1 validator change (require `driver`/`default_profile`/`supported_modes`, fail on placeholder strings) red-line unmigrated packages on day 1?**
*A10.* The validator must permit transitional `resource_bundles` as deprecated-but-valid so unmigrated packages still pass. Belief: intended; load-bearing risk is the validator being too strict and failing every not-yet-migrated package, blocking the whole tree. Verify the validator's "migrated vs not" path doesn't penalize absent `native_program` with a hard error (should be a deprecation/soft path until that package's milestone).

---

## Epic 2 — Package + runtime migrations (M3→M3.5→M4)

**Q1. Is M3→M3.5→M4 strictly sequential inside Epic 2 the right order (canonical Megaplan before evidence_pack)?**
*A1.* Yes — V4 deps put M4 after M3.5 because `evidence_pack` needs the *shared* native resume contract that canonical Megaplan establishes at M3.5. If M4 went first it would invent its own resume and M3.5 couldn't converge. The order is load-bearing-correct; the risk is enforcing convergence (see Q5).

**Q2. Can the "structurally valid but behaviorally wrong" failure mode actually be caught *during* Epic 2 (before M5's native-truth rewrite)?**
*A2.* This is the core risk of the whole epic. During Epic 2 the only behavioral signal is each package's per-milestone `native_parity` suite. Belief: catchable *only if* those suites are converted to genuine behavioral assertions in-milestone (not loosened). Load-bearing danger: a suite converted too loosely ships a behaviorally-wrong migration undiscovered until M5 — or worse, after M5 deletes the graph oracle. Mitigation: keep the graph oracle alive as a *cross-check* through Epic 2 even as native becomes default.

**Q3. For M3.5, can canonical Megaplan's stage-order routing heuristics actually be removed — or do they encode ordering knowledge the native program can't express?**
*A3.* The heuristics **already appear gone** (no stage-order strings in `routing.py`/megaplan top-level), and git shows an `M3-5: canonical Megaplan native migration` commit. Belief: either already done, or the native declaration already carries enough routing info. Load-bearing: confirm the native DSL expresses whatever `_LEGACY_STAGE_ORDER` encoded (phase ordering, escalation routing); if it can't, M3.5 forces a DSL extension. This is the highest-value thing to verify on the actual branch.

**Q4. Does removing the canonical-megaplan graph-bridge executor path produce characterization-golden diffs that get rubber-stamped instead of verified?**
*A4.* The M3.5 brief explicitly warns of large characterization diffs. Belief: high risk. Load-bearing rule the reshape should state: golden re-baselining requires "diff is *explained* AND new behavior is *independently verified correct*," not just "regenerate and bless." Without that rule, large diffs hide semantic regressions.

**Q5. Is the shared native resume contract actually *shared* — one contract M3.5 establishes and M4 + the human-gated M3 packages (writing_panel_strict, deliberation) converge on?**
*A5.* The MILESTONE_5B handoff says human-gate suspend/resume parity is already implemented for `writing-panel-strict` (graph-default, native opt-in at that time). Belief: the mechanism exists; the load-bearing risk is *convergence discipline* — that M3.5/M4 reuse it rather than each shipping a package-local resume. If N resume contracts survive, M5/M7 can't clean up. The reshape should make "single shared resume" an explicit Epic-2 exit gate.

**Q6. Does `folder_audit`'s explicit native-runtime guard logic mask transition bugs?**
*A6.* The M3 brief flags `folder_audit/native.py` still has native-runtime guard logic; env flags still live there. Belief: yes, it can mask bugs — the guards must be removed in M3, not left as a tolerated special case. Verify `folder_audit` actually runs the shared contract after M3, not a guarded branch. (It's one of only two packages that literally reference `native_program`, so it may be further along — confirm it's *converged*, not just *touched*.)

**Q7. Can `live_supervisor`'s multi-module sprawl (pipelines/steps/model/repair_agent/rules) be migrated without leaving split-brain builder logic?**
*A7.* The brief explicitly warns of this. `live_supervisor` is the most sprawling package; belief: high risk of two coexisting builders unless M3 deliberately designates one authoritative `build_pipeline` and reduces the rest to helpers. Load-bearing: needs an explicit "single builder" assertion in M3 acceptance.

**Q8. For M4 evidence_pack, does routing resume through *shared* native semantics preserve the suspend-for-human-review → resume-on-attestation lifecycle?**
*A8.* This is the crux of M4. Git shows an `M4: evidence-pack native migration (shared runtime suspension, cursor safety, tests)` commit — so it may be substantially done. Belief: feasible because the human-gate resume mechanism (Q5) already exists for `writing_panel_strict`. Load-bearing: verify the shared resume expresses the *attestation* gate specifically, not just generic suspend/resume; else evidence_pack either regresses or forks the contract.

**Q9. Does `_deliberation_example` keep stale graph-era imports alive past Epic 2 if not updated in-lockstep with M4?**
*A9.* The M4 brief updates it in-milestone. Belief: yes, risk is real — a stale example import keeps a graph-era surface alive and sabotages M7's "inventory clean" gate. Load-bearing: M4 must treat the example as a first-class migration target, not a doc afterthought.

**Q10. [reshape-level] Is Epic 2 too heavy as a single epic (9 packages + flagship runtime + evidence_pack, two of them extreme/max)?**
*A10.* Belief: this is the highest-risk epic by far and the best candidate to re-split. M3 (9 packages) is wide; M3.5 (flagship) and M4 (evidence_pack) are deep. Strict sequencing inside the epic means no parallelism benefit from keeping them together — only shared handoff coherence. Recommendation to weigh: split Epic 2 into "Epic 2a: shared packages (M3)" and "Epic 2b: runtime convergence (M3.5+M4)" so a wide-but-shallow epic doesn't block behind a deep one. If much of it is already landed (master question), the split is cheap and improves reviewability.

---

## Epic 3 — Test/doc rewrite + purge (M5→M6→M7)

**Q1. Does M5 run too late — leaving Epic 2 with no behavioral safety net if the old parity suites are loosened per-milestone?**
*A1.* Sequencing M5 after M3/M3.5/M4 is correct (native truth must stabilize first). But it creates a cross-epic tension: M3/M4 convert per-package parity suites to native-truth *in-milestone*, while M5 is the full rewrite. Belief: the old graph-parity suites must be **kept intact through Epic 2 as the cross-check oracle** and only deleted in M5. Load-bearing risk: incremental in-milestone loosening erodes the oracle before M5 can use it as the migration's proof. The reshape should forbid parity-suite deletion before M5.

**Q2. When M5 regenerates "native canonical goldens," how do we know they're correct vs. "whatever native happens to emit" — given the graph oracle is being removed in the same milestone?**
*A2.* The brief says "keep scenario coverage constant." Belief: necessary but not sufficient. Load-bearing: there's a window in M5 with no oracle (graph suites deleted, native goldens not yet trusted). Mitigation the reshape should mandate: capture graph-baseline goldens *before* deletion and diff native-vs-graph per scenario; bless native only where the diff is explained. Otherwise goldens bless whatever native does, including regressions.

**Q3. Is keeping exactly one legacy baseline suite (through M5/M6, deleted in M7) enough signal to catch M7 purge regressions?**
*A3.* Belief: one suite is thin. Load-bearing risk: its narrow scope passes while a real caller category breaks at M7. The richer signal is the M7 import inventory + `tests/characterization/test_import_surface.py` (the hard gate), not the single baseline suite. The reshape should not over-rely on the one-suite canary; treat it as a tripwire, not proof.

**Q4. Does M6's "subtractive only, no new positive authoring story" posture leave a documentation gap for composing native pipelines?**
*A4.* M6 deliberately defers composition guidance to "the native composition follow-up epic." Belief: defensible but load-bearing *on that follow-up epic existing and being near-term* — otherwise users get "what not to do" with no "how to compose." The reshape should name the follow-up epic and a rough ETA so the gap is bounded, not open-ended.

**Q5. Does M6's "no shims for new work" rule conflict with M7 possibly discovering a retained compatibility surface that must stay?**
*A5.* The M6 brief anticipates this. Belief: the M6↔M7 boundary is the trickiest — M6 writes docs *before* M7's inventory is final, so M6 bets on an outcome M7 then reverses. Load-bearing: either sequence M7's inventory *before* M6's doc claims (reorder), or scope M6 to avoid asserting retention/deletion outcomes that M7 owns. The current M5→M6→M7 order puts docs before the inventory that validates them.

**Q6. Is the M7 import inventory genuinely exhaustive across BOTH `arnold.pipelines.megaplan.*` AND `arnold_pipelines.megaplan.*` (the installed-package alias)?**
*A6.* The M7 brief requires both. Belief: this is the classic purge failure mode — the `arnold_pipelines.megaplan` (underscore, installed) import path is separate from `arnold.pipelines.megaplan` (dot). Git shows an `M7: …final import inventory, and compatibility purge` commit, so an inventory may exist. Load-bearing: verify the inventory file exists, is current, and covers both surfaces; if `_pipeline/` is already gone (it is, per verification), confirm nothing dynamic still imports through it.

**Q7. Is the M7 "don't delete-first-investigate-later" rule actually enforceable under time pressure?**
*A7.* The rule is explicit; `chain.yaml` has review gates + `require_clean_base`. Belief: enforceable *via the characterization import-surface test as a hard gate*. Load-bearing risk: a shim deleted because "grep looked clean" but a dynamic/import-time reference existed. The reshape should make the import-surface test a merge blocker, not advisory.

**Q8. Does relocating live Megaplan runtime helpers out of `_pipeline/` (M7) risk breaking the `arnold_pipelines.megaplan` public surface external tooling imports?**
*A8.* `_pipeline/` already does not exist — so relocation may already be done. Belief: if so, M7 collapses to "inventory + verify no regression," not a move. Load-bearing: `tests/characterization/test_import_surface.py` must pin the exact public paths (`store`, `workers`, `cli`, `chain`, `execute`, agent runtime, cloud modules). Verify that test exists and is green before claiming M7 done.

**Q9. Is `_pipeline/resume.py` deletion gated correctly against persisted resume files from prior runs?**
*A9.* The M7 brief calls this out. Since `_pipeline/` is already absent, this may be moot — but the *principle* is load-bearing: persisted resume state on disk from prior runs must still load after code moves. Verify old resume files either migrate cleanly through `arnold.pipeline.resume` or fail with a diagnostic, not a silent break.

**Q10. [verification] Does the final 10-item checklist actually close the loop with an end-to-end "run the flagship megaplan on native, resume it, verify" gate — or is verification all unit/contract-level?**
*A10.* The checklist is contract/test/inventory-focused. Belief: **no single end-to-end acceptance run is named** — the ultimate proof ("the whole flagship workflow actually runs on native, end to end, including resume") is implied but not an explicit gate. This is the most important *addition* the reshape should make: a named e2e acceptance run per epic (especially Epic 2 exit and Epic 3 final) as a hard gate, so "green on tests, broken in reality" can't ship.

---

## Notes on confidence and what the deepseek/codex loop should resolve

- Highest-confidence belief: the V4 M1 platform contract is **already landed** in the current tree; the reshape is organizing/verifying partly-done work, not greenfield planning.
- Highest-value verifications to hand off: (a) per-package migration completeness (decorator-based vs not-migrated), (b) stage-order heuristic status on the actual epic branch, (c) existence/currency of the M7 import inventory, (d) whether `_pipeline/` relocation is already complete.
- Cross-cutting recommendations I expect to survive review: enforce single-source-of-truth fallback (E1-Q3), keep graph oracle as cross-check through Epic 2 (E2-Q2/Q5), forbid parity-suite deletion before M5 (E3-Q1), add a named e2e acceptance gate per epic (E3-Q10).
