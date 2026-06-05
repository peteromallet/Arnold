# Forward-Port Ledger

Generated from live state on 2026-06-05 after M6 cleanup commit `081069d0` and run-artifact ignore commit `46f4a02f`.

- Target checkout: `/private/tmp/arnold-target`
- Target branch: `arnold-epic`
- Source checkout: `/Users/peteromalley/Documents/megaplan`
- Source branch: `working-branch`
- Merge base: `f14b1a5d6ed63051a752fdf674d951012f1e8ebc`
- M6 gate before forward-port: `8866 passed, 25 skipped, 244 warnings`

Status lifecycle: `pending` -> `ported` -> `verified`, or terminal `superseded` / `rejected`.

| # | SHA / item | one-line description | category | remapped target path(s) | STATUS | comment |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `008a5970` | Revert old Arnold merge | DISCARD | n/a | rejected | Reject: would undo the cleanup direction. |
| 2 | `b09d780a` | Restore planning pipeline registration defensively | PORT | `arnold/pipelines/megaplan/_pipeline/registry.py`, tests | verified | Re-derived for Arnold canonical `megaplan` registry: global lookup helpers reassert the built-in after singleton mutation; focused and registry discovery suites passed. |
| 3 | `c5b11eec` | Align verify-human list with worker capabilities | PORT | `arnold/pipelines/megaplan/handlers/verifiability.py`, tests | verified | List mode now classifies deferred human criteria using persisted worker capabilities; focused handler and override/verifiability suites passed. |
| 4 | `0f2b2f79` | Recoverably rerun review for unroutable execute rework | PORT | `arnold/pipelines/megaplan/execute`, `review`, tests | pending | Live re-derived commit. |
| 5 | `0d8992e0` | Cloud chain git-refresh tolerates divergence | PORT | `arnold/pipelines/megaplan/chain`, `cloud`, tests | pending | Live re-derived commit. |
| 6 | `a711b857` | Cloud chain git-refresh regenerated bundles | PORT | `arnold/pipelines/megaplan/_core/io.py`, cloud tests | pending | Live re-derived commit. |
| 7 | `0123880b` | Auto-driver progress-aware stall guard | PORT | `arnold/pipelines/megaplan/auto*`, chain/cloud tests | pending | Live re-derived commit. |
| 8 | `09ba01a9` | Cloud deploy emits honest deploy report | PORT | `arnold/pipelines/megaplan/cloud`, tests | pending | Live re-derived commit. |
| 9 | `4ab84530` | Do not ship unattributed or unresolved defects as done | PORT | `arnold/pipelines/megaplan/execute`, `review`, tests | pending | Live re-derived commit. |
| 10 | `d5220a97` | Make execute audit trail trustworthy | PORT | `arnold/pipelines/megaplan/orchestration`, `execute`, tests | pending | Live re-derived commit. |
| 11 | `275e70f1` | Avoid concurrent shared request-client recreation | PORT | `arnold/pipelines/megaplan/agent`, tests | pending | Live re-derived commit. |
| 12 | `70a95f63` | Avoid full state.json rewrite on heartbeat | PORT | `arnold/pipelines/megaplan/_core/state*`, observability tests | pending | Live re-derived commit. |
| 13 | `ab1c5c54` | Same-family codex gpt-5.x substitution is not blocking | SUPERSEDED | n/a | superseded | Source fixed obsolete `routing_degradations` model-mismatch blocker; Arnold target no longer has `_models_match` / routing-audit degradation blocking path. |
| 14 | `5bdefcfb` | Harden Shannon native Claude launch | PORT | `arnold/pipelines/megaplan/vendor/shannon`, workers tests | pending | Live re-derived commit. |
| 15 | `2bb6968c` | Per-step routing ledger across phases | PORT | `arnold/pipelines/megaplan/orchestration`, telemetry/tests | pending | Live re-derived commit. |
| 16 | `0e152156` | Tool-driven scoped review and second-rework escalation | PORT | `arnold/pipelines/megaplan/review`, handlers/tests | pending | Live re-derived commit. |
| 17 | `9bbb67eb` | Real rejection wins classifier and structured review status | PORT | `arnold/pipelines/megaplan/review`, tests | pending | Live re-derived commit. |
| 18 | `3bd55a2e` | Stable escalation identity for null flag_id rework | PORT | `arnold/pipelines/megaplan/auto_escalation.py`, tests | pending | Live re-derived commit. |
| 19 | `657f73ce` | Positional idea path content and BRIEF_MISSING fail-closed | PORT | `arnold/pipelines/megaplan/handlers/init.py`, tests | pending | Live re-derived commit. |
| 20 | `f16dc36f` | Merge review classifier/escalation/brief snapshot branches | SUPERSEDED | n/a | superseded | Merge commit; component commits are tracked separately. |
| 21 | `c88c283c` | Infra-marker rework items do not trip genuine-rejection | PORT | `arnold/pipelines/megaplan/review`, tests | pending | Live re-derived commit. |
| 22 | `3f94c5ea` | Structured infra signals win before rejection inference | PORT | `arnold/pipelines/megaplan/review`, tests | pending | Live re-derived commit. |
| 23 | `9063df70` | Context-aware tool caps and prep fanout tolerance | PORT | `arnold/pipelines/megaplan/orchestration/prep_research.py`, agent/prep tests | pending | Live re-derived commit. |
| 24 | `ee93b4f4` | DeepSeek-V4 context window metadata | PORT | `arnold/pipelines/megaplan/agent/agent/model_metadata.py` | verified | Ported DeepSeek-V4 1,048,576 context default with focused metadata regression; `test_model_metadata.py` passed. |
| 25 | `0b0581da` | Fork milestones from origin and count committed evidence | PORT | `arnold/pipelines/megaplan/chain`, tests | pending | Live re-derived commit. |
| 26 | `a17ddc21` | Worker stall fixes: stdin, session bloat, composer detection | PORT | `arnold/pipelines/megaplan/workers`, vendor/shannon, tests | pending | Live re-derived commit. |
| 27 | `7e5cdc86` | Tighten complexity rubrics against tier inflation | PORT | `arnold/pipelines/megaplan/data`, prompts/skills | pending | Live re-derived commit. |
| 28 | `4c223df0` | Active-step orphan clear and review-grounding core | PORT | `arnold/pipelines/megaplan/auto*`, review/tests | pending | Live re-derived commit. |
| 29 | `c3fe84a0` | Merge review rework redesign and audit fixes | SUPERSEDED | n/a | superseded | Merge commit; component commits are tracked separately. |
| 30 | `0e017861` | Add evidence-first epic briefs | PORT | `.megaplan/briefs/evidence-first-pipeline-semantics/**` | verified | Applied from committed range as docs/spec batch. |
| 31 | `ad988d18` | Resolve premium vendor funneling | PORT | `arnold/pipelines/megaplan/profiles`, routing/tests | pending | Live re-derived commit. |
| 32 | `c18e0aa8` | Shannon native launch hardening checkpoint | PORT | `arnold/pipelines/megaplan/vendor/shannon`, workers/tests | pending | Live re-derived commit. |
| 33 | `b489ade9` | Merge premium vendor routing funnel | SUPERSEDED | n/a | superseded | Merge commit; component commits are tracked separately. |
| 34 | `2b25128b` | Point evidence-first epic at working branch | PORT | `.megaplan/briefs/evidence-first-pipeline-semantics/chain.yaml` | verified | Ported as corrected value: `base_branch: arnold-epic`; grep confirms no stale `working-branch` references. |
| 35 | `13fb614f` | Resolve Megaplan from engine for phase subprocesses | PORT | `arnold/pipelines/megaplan/chain`, auto/tests | verified | Chain status/init subprocesses now run from the Arnold engine root with engine-first `PYTHONPATH`; auto phase dispatch is superseded by in-process Arnold pipeline dispatch. |
| 36 | `a18a2da5` | Idempotent restart, strict spec validation, checkout-free refresh | PORT | `arnold/pipelines/megaplan/chain`, tests | verified | Ported checkout-free base refresh and validated chain/prep/auto slice; broader fresh/reset pieces are already covered by current Arnold chain runtime or superseded. |
| 37 | `02b34ccb` | Harden Shannon native parity | PORT | `arnold/pipelines/megaplan/vendor/shannon`, workers/tests | pending | Live re-derived commit. |
| 38 | `7680cd81` | Create run artifact dir before empty MCP config | PORT | `arnold/pipelines/megaplan/workers`, vendor/shannon tests | pending | Live re-derived commit. |
| 39 | `e4a46d12` | Project prompt context for review and execute | PORT | `arnold/pipelines/megaplan/prompts`, execute/review/tests | verified | Applied prompt projection modules and tests; focused prompt suite and worker integration passed. |
| 40 | `c2007519` | Align native handoff and codex resume expectations | PORT | worker tests | pending | Live re-derived commit. |
| 41 | `6b2697ba` | Never hard-fail review on large diffs | PORT | `arnold/pipelines/megaplan/review`, tests | verified | Applied `base_ref` diff helpers and compact review prompt path; prompt, worker, and chain suites passed. |
| 42 | `e1170b05` | Invariant model floor routing | PORT | `arnold/pipelines/megaplan/profiles`, routing, CLI/tests | verified | Ported available-model floor, solo finalize/execute floor, `--max-execute-tier`, init/provenance persistence, and focused profile/execute tests. |
| 43 | `3aae6d0f` | Stop injecting technical-debt registry into prompts | PORT | `arnold/pipelines/megaplan/prompts`, prep/review/tests | verified | Removed prompt-side debt injection and updated assertions that debt registry stays out of prompts; focused prompt suite passed. |
| 44 | `78efcf4a` | Calibrate prompt caps to context windows | PORT | `arnold/pipelines/megaplan/prompts`, model metadata/tests | verified | Applied phase-aware prompt caps plus projection tests; focused prompt suite passed. |
| 45 | `e03c5206` | CLI status project-dir resolves plan from target | PORT | `arnold/pipelines/megaplan/cli`, tests | verified | Registered `--project-dir` on status/progress/watch and added CLI regression proving status reads the target plan, not cwd; parser snapshot passed. |
| 46 | `0e365bcb` | Submit large prompts via file reference | DISCARD | n/a | rejected | Reject: explicitly reverted by `fc2c1a8b`. |
| 47 | `fc2c1a8b` | Revert large-prompt file reference | DISCARD | n/a | rejected | Reject: only reverts rejected commit `0e365bcb`. |
| 48 | `958a669c` | Honor persisted phase model/vendor overrides | PORT | `arnold/pipelines/megaplan/profiles`, runtime/tests | verified | Persisted `phase_model` now dedupes by phase with latest entry winning ahead of profile defaults; regression in `tests/test_profiles.py` passed. |
| 49 | `df3440df` | Premium execute routing recognizes CLI subscription auth | PORT | `arnold/pipelines/megaplan/profiles`, workers/tests | verified | Premium floor now checks env, key-pool credentials, and local CLI-backed routes before degrading execute tiers; CLI-auth and no-premium regressions passed. |
| 50 | `5f8045f3` | Record loud model-floor routing degradations | PORT | `arnold/pipelines/megaplan/profiles`, status/tests | verified | Floor degradations are logged, stored in `state.config.routing_degradations`, and surfaced in status payload summaries; focused profile/config/execute slices passed. |
| 51 | `36cd544a` | Evidence-first v2 authority-kernel restructure | PORT | `.megaplan/briefs/evidence-first-pipeline-semantics/**` | verified | Applied from committed range as docs/spec batch. |
| 52 | `d3111214` | Evidence-first m0 write-isolation focus | PORT | `.megaplan/briefs/evidence-first-pipeline-semantics/**` | verified | Applied from committed range as docs/spec batch. |
| 53 | `c4e5a8ba` | Shannon readiness detector misses pane padding | PORT | `arnold/pipelines/megaplan/vendor/shannon`, tests | verified | Applied to vendored `index.ts`; `bun test pane_ready.test.ts` passed. |
| 54 | `57015c39` | Shannon fresh-config gates and v2.1.x transcript root | PORT | `arnold/pipelines/megaplan/vendor/shannon`, workers/tests | verified | Applied to vendored `index.ts` and `workers/shannon.py`; focused Shannon/Claude/tmux suite passed. |
| 55 | `74d439bc` | Register `--no-prep-clarify` and guard chain/init flag drift | PORT | `arnold/pipelines/megaplan/handlers/init.py`, chain/tests | verified | Registered init parser flag, removed masking handler default, added parser round-trip and chain/init long-option drift guard; focused chain/prep/auto slice passed. |
| 56 | dirty `.megaplan/briefs/evidence-first-pipeline-semantics/m0-engine-target-isolation.md` | Add L1 cwd and environment-contract evidence-first detail | PORT | same path | verified | Applied dirty doc patch on top of committed brief batch. |
| 57 | dirty `.megaplan/briefs/evidence-first-pipeline-semantics/m4-review-evidence-service.md` | Evidence-first review evidence-service addition | PORT | same path | verified | Applied dirty doc patch on top of committed brief batch. |
| 58 | dirty `.megaplan/briefs/evidence-first-pipeline-semantics/m5-objective-gates.md` | Evidence-first objective-gates addition | PORT | same path | verified | Applied dirty doc patch on top of committed brief batch. |
| 59 | dirty `.megaplan/briefs/evidence-first-pipeline-semantics/m6-provenance-and-workspace-assertions.md` | Worker-sweep ownership manifest requirement | PORT | same path | verified | Applied dirty doc patch on top of committed brief batch. |
| 60 | dirty `.megaplan/briefs/evidence-first-pipeline-semantics/m7-transition-validator-routing.md` | Verified GitHub merge transition requirement | PORT | same path | verified | Applied dirty doc patch on top of committed brief batch. |
| 61 | dirty `.megaplan/briefs/evidence-first-pipeline-semantics/m9-atomic-reset-reconcile.md` | Recoverable merge failure and worktree-safe merge fallback | PORT | same path | verified | Applied dirty doc patch on top of committed brief batch. |
| 62 | dirty `megaplan/chain/__init__.py` | Resolve spec-relative idea path against project root | PORT | `arnold/pipelines/megaplan/chain/__init__.py` | verified | Applied via remapped dirty patch; covered by focused init/prep/worker gate. |
| 63 | dirty `megaplan/chain/git_ops.py` | Worktree-safe `gh pr merge --delete-branch` fallback | PORT | `arnold/pipelines/megaplan/chain/git_ops.py` | verified | Applied via remapped dirty patch; no conflict. |
| 64 | dirty `megaplan/data/_codex_skills/babysit/SKILL.md` | Babysit skill hardening | PORT | `arnold/pipelines/megaplan/data/_codex_skills/babysit/SKILL.md` | verified | Applied via remapped dirty patch. |
| 65 | dirty `megaplan/data/babysit_skill.md` | Babysit skill hardening | PORT | `arnold/pipelines/megaplan/data/babysit_skill.md` | verified | Applied via remapped dirty patch. |
| 66 | dirty `megaplan/handlers/init.py` | High-fidelity missing idea-file diagnostic | PORT | `arnold/pipelines/megaplan/handlers/init.py` | verified | Applied via remapped dirty patch; `tests/test_handle_init_idea_file.py` passed. |
| 67 | dirty `megaplan/vendor/shannon/VENDOR.md` | Document and complete Shannon P16/P17 | PORT | `arnold/pipelines/megaplan/vendor/shannon/VENDOR.md`, implementation/tests | verified | VENDOR doc applied; P16/P17 implementation and tests verified via rows 53, 54, and 72. |
| 68 | dirty `megaplan/workers/_impl.py` | L1 cwd fix: Codex execute subprocess runs in `work_dir` | PORT | `arnold/pipelines/megaplan/workers/_impl.py` | verified | Applied via remapped dirty patch; `test_run_codex_execute_runs_subprocess_in_work_dir` passed. |
| 69 | dirty `tests/test_handle_init_idea_file.py` | Regression for init idea-file diagnostic | PORT | same path | verified | Applied via remapped dirty patch; focused test file passed. |
| 70 | dirty `tests/test_prep.py` | Prep regression update | PORT | same path | superseded | No net diff after M6; focused prep tests passed. |
| 71 | dirty `tests/test_workers_codex.py` | Regression for Codex execute cwd behavior | PORT | same path | verified | Added manually in M6 import layout; focused worker test passed. |
| 72 | untracked `megaplan/vendor/shannon/pane_ready.test.ts` | Shannon P16 pane-ready regression | PORT | `arnold/pipelines/megaplan/vendor/shannon/pane_ready.test.ts` | verified | Added under Arnold-hosted vendor path; Bun pane-ready test passed. |
| 73 | untracked `.hypothesis/**` | Hypothesis generated examples | DISCARD | n/a | rejected | Generated local test cache; not forward-ported. |
| 74 | untracked `runs/visual-understanding/**` | Generated visual-understanding crops | DISCARD | n/a | rejected | Generated local run output; not forward-ported. |
