# Excellence Epic Operator Guide

Run this chain from the VibeComfy repository root so relative `idea` paths in
`chain.yaml` resolve consistently:

```bash
command -v megaplan >/dev/null || { echo "Install megaplan before running this chain"; exit 1; }
cd "$(git rev-parse --show-toplevel)" || { echo "Must run from a VibeComfy git checkout"; exit 1; }
megaplan chain start --spec docs/megaplan_chains/excellence_epic/chain.yaml
```

This chain intentionally targets `base_branch:
fix/emitter-revert-block-a-regressions`, because the current local codebase
already contains the wrapper/emitter fixes the epic should build on. Before
running, commit the chain docs and structural audit on that branch and push it
to `origin`; otherwise the chain runner cannot refresh the base branch or open
milestone PRs against it.

Branch convention: each sprint should work on `epic/excellence/<milestone-label>`
unless the operator supplies a more specific branch name. The branch names are
also declared directly in `chain.yaml` so the runner can create/reuse milestone
branches and draft PRs.

The chain is configured with `merge_policy: auto`. After a milestone succeeds,
the runner pushes its branch, opens/updates the PR, merges it into the configured
base branch, refreshes that branch, and starts the next milestone from the
updated base. If a milestone fails or escalates, the chain halts with state
preserved.

Valid profiles used by this chain: `premium`, `partnered`, and `directed`.
Confirm these are available in the installed megaplan profile set before the
first run.

## Prior Prep Inputs

The sprint briefs already fold in the review decisions from the DeepSeek/Codex
sense-check passes. Before starting the chain, operators should skim these
durable prep artifacts so they understand why the chain is split and why each
profile was chosen:

- `docs/structural_audit_2026-05.md`
- `docs/megaplan_chains/excellence_epic/review-adjustments-2026-05-27.md`
- `out/subagent_reviews/excellence_epic_balance_decision/synthesis.md`
- `out/subagent_reviews/excellence_epic_codex_vs_deepseek/comparison.md`
- `out/subagent_reviews/excellence_epic_unknown_unknowns/synthesis.md`

The split from 7 to 10 milestones is intentional: the cheaper/mechanical parts
of old M2/M4/M6 were separated from the contract/security/runtime-boundary work
so each sprint could receive its own `megaplan-decision` profile. The profiles
are discounted for the substantial prep already done; only the kernel-breaking
safety-net sprint, IR contract sprint, and RunPod/security-spend sprint remain
`premium`.

Each sprint creates its own handoff artifact under this directory:

- `handoff-m1.md`
- `handoff-m2a.md`
- `handoff-m2b.md`
- `handoff-m3.md`
- `handoff-m4a.md`
- `handoff-m4b.md`
- `handoff-m5.md`
- `handoff-m6a.md`
- `handoff-m6b.md`
- `handoff-m7.md`

The handoff is part of the done state. Do not mark a sprint complete without it.
Every `handoff-*.md` must contain at minimum:

- Exact command(s) to reproduce the sprint's gate evidence
- Files created, deleted, renamed, or intentionally regenerated
- Any intentional deviations from the sprint's done criteria with rationale
- Deferred risks with severity (`low`/`medium`/`high`) and proposed owning sprint/workstream
- CI job name(s), if any, that enforce this sprint's gates

## Recovery

Check persisted progress without driving the chain:

```bash
megaplan chain status --spec docs/megaplan_chains/excellence_epic/chain.yaml
```

After fixing a failed sprint, rerun `megaplan chain start --spec ...`; the chain
runner reads persisted state and continues from the next pending milestone. Do
not delete handoff artifacts or chain state unless intentionally restarting the
epic from scratch.
