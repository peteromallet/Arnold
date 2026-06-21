# Workflow Manifest Runtime Chain Notes

These notes are intentionally outside `chain.yaml` because the chain runner rejects unknown top-level keys.

## Review Artifacts

- Synthesis: `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- Initial analysis: `docs/arnold/workflow-manifest-runtime-review/initial-analysis.md`
- Wave 1 results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave1`
- Wave 2 results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave2`
- Wave 3 results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave3`
- Wave 4 results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave4`
- Wave 7 results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave7`
- Wave 9 results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave9`
- Load-bearing questions: `docs/arnold/workflow-manifest-runtime-review/load-bearing-questions.md`
- Load-bearing question results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/load-bearing-questions`
- Main-refresh review briefs: `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/main-refresh`
- Main-refresh review results: `docs/arnold/workflow-manifest-runtime-review/subagent-results/main-refresh`

Process rule: apply each review wave back into the milestone briefs before launching the next wave.

## Main Base Refresh

Checked `origin/main` on 2026-06-21 after fetch. The base moved from `9d8b2a4a` to `0035c231`.

Newly landed mainline commits from `9d8b2a4a..0035c231` are relevant to this epic and must be treated as baseline facts, not optional side-branch work:

- `bec80660` moved judge manifest primitives to neutral discovery packages. M1/M2/M5/M6 should inspect `arnold/pipeline/discovery/judge_manifest.py`, the Megaplan wrapper, and discovery-trust migration as current mainline.
- `1d008cb4` added StepContext/versioned artifact helpers. M1/M3/M4 should account for this artifact-helper shape when defining neutral artifact contracts, provenance, and product artifact migration.
- `9209ed48` added `arnold pipelines describe`. M5/M6 CLI inventories must include this command, parser snapshots, help text, installed-wheel smoke, and final migrate/delete disposition.
- `e6647a38` added evidence-pack resume fallback. M3/M4/M5 should treat legacy resume cursor translation/fallback as current shipped behavior to either migrate or explicitly quarantine.
- `9adb4323` expanded conformance allowlist semantics. M6 must burn down or re-charter the current allowlist behavior, including glob and `/**` patterns.
- `11a97974`, `91e54963`, and adjacent chain/harness fixes affect how the chain itself runs: spec validation rejects unknown keys; `manual` merge policy is accepted as a synonym for `review` while this chain already uses `review`; DeepSeek provider narrowing is limited to `direct`/`fireworks` and has no impact because all milestones use `vendor: codex`; `current_milestone_base_sha` is auto-recorded in state; `--fresh` resets stale worktree/branch state; automated pushes use `--no-verify`.
- Worker/engine-isolation fixes through `0035c231` affect execution harness reliability but do not change the six-sprint decomposition.

Operator checklist before launching M1:

1. Run `git fetch origin` and confirm `origin/main` is `0035c231` or newer.
2. Let the chain record `current_milestone_base_sha` when M1 starts, then verify state reflects the refreshed base.
3. If a prior chain run left a stale worktree or branch, pass `--fresh`.

Plan impact: no sprint split is required. The existing six milestones remain correct, but M1 baseline capture must run against `origin/main@0035c231` or newer and must not rely on conclusions from the pre-refresh `9d8b2a4a` baseline without rechecking touched files.

Concrete contract captures required:

- M1 freezes the neutral judge-manifest baseline, judge/workflow identity reconciliation, versioned `vN.<ext>` artifact convention, dual artifact-root model, and native-first/legacy-fallback cursor semantics.
- M3 executes artifact writes and resume against those conventions.
- M4 migrates Megaplan product call sites and parity tests against current-main gate, finalize, review, critique, plan-normalization, execution-evidence, task-status, and infrastructure-error behavior.
- M5/M6 explicitly disposition `arnold pipelines describe`.
- M6 expands allowlist globs to concrete files, audits `sys.modules`, scans installed CLI help/dispatch output, and blocks legacy-format skill/docs/discovery/template reads.

## Post-Merge Conformance Gate

After all six milestone branches are merged into one integration checkout:

1. Rebuild from a clean tree.
2. Reinstall from the merge-result wheel and sdist.
3. Regenerate generated artifacts.
4. Rerun the full M1-M6 contract/runtime/parity/conformance gate suites.
5. Verify M4/M5 delete-classified paths were not resurrected.
6. Prove canonical manifest hashes, identity registries, and CLI fixtures match the final compiler output.
7. If any downstream milestone amended M1/M2/M3 contracts, rerun the full upstream milestone gate suite before declaring merge-result conformance green.
