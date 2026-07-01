# M4: Megaplan Package Hardening

## Outcome

Fold preserved Megaplan-package work into the package layer after the canonical bridge exists.

This milestone is for test-selection, attribution, execution-runtime hardening, and dirty conformance-gate leftovers that matter to Megaplan as a product, not to neutral Arnold.

## Scope

IN:

- Inspect `mp-tbr-merge`, `mp-milestone-attribution-ground-truth`, `fix/arnold-conformance-gate`, and related Megaplan-package branches/worktrees.
- Port only product/package hardening that still applies after M1-M3.
- Keep changes out of neutral Arnold unless a second package proves the need.
- Preserve or explicitly reject dirty worktree payloads before pruning.

OUT:

- No Arnold substrate refactor.
- No package authoring redesign.
- No Shannon ops/stream work unless explicitly adopted as a Megaplan worker milestone.

## Locked Decisions

- Test selection and attribution are Megaplan package concerns unless generalized by evidence from another package.
- Dirty branches are quarry sources, not merge bases.
- Full-suite Arnold remains the gate.

## Done Criteria

1. Every preserved Megaplan-package branch/worktree has a port/defer/reject disposition.
2. Useful package hardening is ported with tests.
3. Neutral Arnold remains free of product coupling.
4. `python -m pytest tests/arnold -q` passes.

## Megaplan Sizing

Recommended run: `directed/full/medium`

Rationale: once the package boundary is fixed, much of this is sequencing and selective porting. Premium planning is useful; full premium reasoning is probably unnecessary unless the branch audit finds a new architectural decision.
