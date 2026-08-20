# M11 plan v11 full-scope restoration

Work only in:

`/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/m11-cross-contract-acceptance-20260728-1035`

This is a manual structural-edit step after an explicit `override replan`. Do not run
any megaplan phase, do not change state.json, and do not execute implementation tasks.
Edit only `plan_v11.md`.

Problem: the first v11 revision accidentally collapsed the full v10 executable plan
(roughly 82+ tasks) to only Steps 1-9. The gate correctly rejected that scope loss.

Required result:

1. Treat `plan_v10.md` as the authoritative full-scope base. Preserve every executable
   phase, step, objective, declared path, selector, dependency, validation, proof,
   acceptance condition, and retirement/canary requirement that remains valid.
2. Incorporate the legitimate v11 fixes without deleting or summarizing executable
   work:
   - explicitly reconcile the active three-hour missed-event backstop with the older
     six-hour anchor and fail closed if the canonical source still contradicts it;
   - add native empty-program WBC terminal/close coverage;
   - split the greenfield delegation shim into a minimal typed contract, then adapters,
     then consumers;
   - split `arnold-repair-trigger` by concrete branch family rather than one god-task;
   - include M10 recovery-SLO and C01-C20 evidence generator/test migration;
   - include the module-specific RepairRunner test selector;
   - identify future-created validation selectors and sequence their collection after
     creation;
   - split oversized operator-document work;
   - give every Step section numbered substeps.
3. Materialize the entire remaining M11 scope as concrete bounded steps, including
   route-authority scanners, simple_fixer delegation, repair-trigger migration,
   schedule migration, recovery-SLO proof, WBC equality, installed canaries,
   full-suite gates, rollback, retirement eligibility, proof map, and manifest.
4. Satisfy the deterministic feasibility contract:
   - each task has one <=15-minute objective;
   - <=5 declared paths per task;
   - <=3 narrow selectors, <=120 seconds, <=2 runs;
   - every dependency cites a concrete consumed output, write-order reason, or human
     prerequisite;
   - eliminate routing-only dependencies;
   - order genuine write overlaps or split ownership so `write_overlap_unordered`
     cannot recur.
5. Do not claim work was removed merely because it moved. Add a concise preservation
   ledger at the end mapping every v10 phase/step to retained, split, or merged v11
   step identities. Every v10 step must appear exactly once in that ledger.

Before finishing, mechanically compare v10 and the edited v11 and prove:

- every v10 Step identity appears in the preservation ledger;
- all required scope families above have concrete step definitions;
- every Step has numbered substeps;
- no step exceeds five declared paths or three selectors;
- no dependency is described as routing-only.

Return a concise report, but the file edit is the deliverable. Do not commit, push,
launch, finalize, execute, or mutate cloud/runtime configuration.
