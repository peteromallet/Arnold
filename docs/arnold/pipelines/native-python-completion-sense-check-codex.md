# Codex Verdict: Native Python Completion Epic Reshape

*Judge: GPT-5.5 (codex exec, read-only sandbox). Persisted by Claude — codex could not write this file itself under read-only sandbox.*

**Top-line ruling.** DeepSeek is right on the branch-state/readiness-prep direction, with one correction: `editible-install` currently has only `deliberation` and `folder_audit` under `arnold/pipelines`, while `native-python-working-tree` has the M1–M7 migration commits, canonical `megaplan`, migrated subpackages, M7 import inventory, and retained `_pipeline` compatibility shims. The reshape must not say "create `native-python-working-tree` from `editible-install`." That would overwrite or sideline the donor work. Change readiness prep to: rebase or otherwise refresh `native-python-working-tree` onto current `editible-install`, reconcile conflicts and donor decisions, then land/review the already-executed migration as sequential epics. This is not greenfield planning from `editible-install`; it is organizing and landing completed donor work onto the current base.

## Divergence Table

| Question ID | Bucket | Who's right | Recommended edit or ignore |
| --- | --- | --- | --- |
| Master / readiness | REAL | DeepSeek | Replace "create `native-python-working-tree` from `editible-install`" with "refresh/rebase `native-python-working-tree` onto current `editible-install`, preserving M1–M7 donor commits and reconciling current branch fixes." |
| Master / migration state | REAL | DeepSeek | State explicitly that `editible-install` is only partially migrated, while `native-python-working-tree` is the donor branch with the completed migration payload. |
| E1-Q3 fallback source of truth | PARTIAL | DeepSeek on repo facts; Claude on ambiguity | Clarify runtime precedence: `Pipeline.native_program` wins for package execution; resource bundles are fallback only when absent; state markers and env flags are resume/compatibility inputs, not competing package-selection truth, except documented explicit legacy force paths. |
| E1-Q4 `arnold.pipeline.legacy` | PARTIAL | DeepSeek | Do not blindly create `arnold.pipeline.legacy` in M1. Change M1 to create/retain it only if import inventory shows real callers; otherwise document that the donor branch proved it can be deleted/absent. |
| E1-Q5 manifest-first safety | MISGUIDED | DeepSeek | Existing discoverable packages have manifests and the plan keeps compatibility; do not change the plan beyond branch-state wording. |
| E1-Q6 M1+M2 bundling | MISGUIDED | DeepSeek | Keep M1→M2 in Epic 1. Do not split or add parallel-start wording. |
| E1-Q7 rename stale imports | REAL | Claude | Add an M2 completion gate: repo-wide `rg` for old `select-tournament`, single-file `writing_panel_strict.py`, stale registrations, docs, and tests; every survivor must be an intentional shim recorded for later removal. |
| E1-Q8 writing-panel gate semantics | MISGUIDED | DeepSeek | Donor code preserves the gate and M2/M3 already name e2e/parity tests; do not add a separate M2 behavioral gate beyond ensuring the existing e2e still runs. |
| E1-Q10 validator red-lining | MISGUIDED | DeepSeek | The plan already permits transitional `resource_bundles`; do not weaken validator requirements. |
| E2-Q2 / E3-Q1 parity safety net | REAL | Both | Add a cross-epic rule: old graph/parity oracle suites may be narrowed or archived only in M5; M3/M4 may add native-truth tests but must not erase the cross-check signal before M5. |
| E2-Q3 stage-order heuristics | PARTIAL | DeepSeek | Replace stale "remove heuristics from `routing.py`" wording with "verify no Megaplan-specific stage-order heuristics remain; remove any old Megaplan-specific routing remnants found during rebase." |
| E2-Q4 / E3-Q2 golden diffs | REAL | Both | Require every golden rebaseline to include graph-baseline capture, native-vs-graph diff, and a short semantic explanation for each intentional diff before blessing native goldens. |
| E2-Q5 shared resume contract | PARTIAL | DeepSeek on existence; Claude on gate | Add an Epic 2 exit gate proving `canonical Megaplan`, `writing_panel_strict`, `deliberation`, and `evidence_pack` all route through the shared `arnold.pipeline.resume` / native checkpoint contract, with package-local resume code limited to adapters. |
| E2-Q6 `folder_audit` guard | MISGUIDED | DeepSeek | The guard is gone except documentation text; remove the stale risk note saying `folder_audit` still contains explicit guard logic. Do not add new migration work for this. |
| E2-Q7 `live_supervisor` split-brain | REAL | Both | Strengthen M3 acceptance: `live_supervisor.__init__` must export the native `build_pipeline`, and `pipelines.py` must have no public builder role except private compatibility. |
| E2-Q8 `evidence_pack` attestation resume | PARTIAL | Both | Add an M4 test/gate that exercises suspend-for-human-review, resume-on-attestation, and final emission through the shared resume contract. |
| E2-Q10 Epic 2 size/split | MISGUIDED | DeepSeek | Do not split Epic 2. The internal M3→M3.5→M4 gates already provide review seams; splitting the epic adds overhead without changing dependencies. |
| E3-Q3 one legacy baseline suite | MISGUIDED | Both mostly agree | Treat the legacy baseline as a tripwire and the M7 import inventory as the hard gate; the plan already does this. Do not change the plan. |
| E3-Q4 M6 composition docs gap | PARTIAL | DeepSeek on intentional gap; Claude on clarity | Keep M6 subtractive, but name/link the native composition follow-up epic so the deferred positive authoring story is explicit. |
| E3-Q5 M6 no-shims vs M7 retained shims | MISGUIDED | DeepSeek | The M6 brief already distinguishes new authoring from retained internal compatibility; do not reorder M6/M7 and do not change the plan. |
| E3-Q8 `_pipeline` absence/relocation | REAL | DeepSeek | Correct any summary implying `_pipeline/` is absent or must be fully deleted. Donor M7 retained `_pipeline` shims because inventory found live callers; M7's outcome may be documented retention, not deletion. |
| E3-Q9 `_pipeline/resume.py` deletion | REAL | DeepSeek | Keep the M7 gate explicit: `_pipeline/resume.py` stays until persisted resume files either load through `arnold.pipeline.resume` or fail with tested migration diagnostics. |
| E3-Q10 final e2e verification | REAL | Both | Add a named final acceptance gate: run canonical Megaplan on native end-to-end, force a human suspension, resume it, and verify final output/artifacts and trace shape. |

## Prioritized Edit List

1. Rewrite readiness prep to refresh/rebase `native-python-working-tree` onto `editible-install`, not create it from `editible-install`.
2. Add a branch-state note: `editible-install` is partial; `native-python-working-tree` carries the M1–M7 donor implementation and inventory decisions.
3. Add an explicit Epic 2/Epic 3 oracle rule forbidding deletion/archive of graph/parity cross-check suites before M5.
4. Add golden rebaseline rules requiring graph baseline capture, native-vs-graph diff review, and semantic explanation for each blessed diff.
5. Add final e2e acceptance: native canonical Megaplan run, human suspend, resume, final output/artifacts, and trace verification.
6. Clarify M7 can retain `_pipeline` compatibility shims when inventory proves live callers; final purge means "delete or intentionally shim," not "delete everything."
7. Change M1 `arnold.pipeline.legacy` wording to create/retain only when inventory proves callers, otherwise allow absence/deletion.
8. Add an Epic 2 shared-resume exit gate covering canonical Megaplan, `writing_panel_strict`, `deliberation`, and `evidence_pack`.
9. Add M2 repo-wide stale-import/registration grep gate for the package renames, with intentional shim survivors recorded.
10. Strengthen M3 `live_supervisor` acceptance to prove only the native `build_pipeline` is public.
11. Add M4 attestation-resume coverage for `evidence_pack`.
12. Replace stale `folder_audit` guard-risk wording with a verification-only note.
13. Replace stale M3.5 routing wording with verification that no Megaplan-specific stage-order heuristics survive after rebase.
14. Name/link the native composition follow-up epic from M6, while keeping M6 subtractive.
