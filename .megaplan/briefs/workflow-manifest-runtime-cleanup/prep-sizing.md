# Workflow Manifest Runtime Cleanup: Prep Sizing

## Decision

This remediation should run as an epic chain, not one megaplan.

The work is larger than one sprint because it crosses public API contract, package/import topology, archived pipeline deletion, load-bearing runtime imports, tests that currently normalize legacy behavior, wheel/sdist conformance, generated artifacts, and final merge-result verification. The remediation plan already has five PR-shaped steps with sequential dependencies; each step has a distinct failure mode and handoff artifact.

## Milestones

1. `m1-public-api-clean-break`: make the public contract explicit and remove legacy constructors/exports from the supported API surface.
2. `m2-archive-delete-epic-blitz`: delete the archived `epic_blitz` shipped pipeline and remove it from active discovery and CLI expectations.
3. `m3-burn-down-legacy-imports`: migrate load-bearing `_pipeline` and `stages` imports to surviving Arnold workflow/runtime or Megaplan-local non-legacy modules.
4. `m4-physical-deletion-conformance-gates`: delete `_pipeline/`, `stages/`, compatibility shims, and strengthen source/wheel absence gates.
5. `m5-generated-assets-merge-result-conformance`: regenerate docs/registries/assets and prove the integrated merge result from wheel/sdist, including the newly implemented prevention gates.

## Rubric

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because a bad plan can pass local tests while damaging public contracts, installed consumers, import topology, generated artifacts, or final merge-result conformance.

Robustness: `thorough`; because this touches public API removal, package/import topology, installed-wheel behavior, and final release gates. The review/attack findings from the prior epic must be converted into hard gates, not advisory notes.

Depth: `high`; because the planner must reason through cross-module import replacement order, dynamic imports, packaging metadata, generated assets, and merge-result verification without reintroducing compatibility shims.

Vendor: `codex`; this matches the user-provided example and keeps the remediation run in the same tool family that produced the attached analysis.

Shorthand for every milestone: `partnered-5/thorough/high @codex`.

## Handoff Discipline

Each milestone must produce a concrete handoff:

- M1: public API contract and tests that reject legacy constructor/export resurrection.
- M2: deleted/archive-only `epic_blitz` state plus discovery/CLI absence tests.
- M3: import-family migration ledger proving no production code imports legacy paths.
- M4: physical deletion plus source, test, wheel, sdist, dynamic-import, and `sys.modules` absence gates.
- M5: regenerated assets, clean second regeneration, final manifest identity ledger, and merge-result conformance report.

`execute` must not be run from this setup session. The initialized plan may be prepped, reviewed by a human, and only then executed with explicit approval.
