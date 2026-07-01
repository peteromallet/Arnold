# M3: Human Interaction And Deliberation Package

## Outcome

Revisit human interaction and layered deliberation after package authoring is concrete.

If a reusable human interaction step still earns its place, re-author it against the current `ContractResult` / `Suspension` surface. Then bring deliberation back as a concrete package example that demonstrates layered critique/revise workflows without making critique a kernel semantic.

## Scope

IN:

- Decide whether human interaction belongs as a neutral pattern, a package helper, or evidence-pack-only behavior.
- If reusable, implement a current-shape human interaction step against `Suspension`, resume validation, and package-owned resume authority.
- Build or port a deliberation package only as a package example.
- Show a practical layered critique pipeline using the package authoring surface from M2.

OUT:

- No copy of stale quarry `arnold/pipeline/steps/human_gate.py`.
- No hard-coded Megaplan phase semantics in neutral Arnold.
- No generic replay/resume runtime.

## Locked Decisions

- The quarry human-gate file is stale and should not be copied.
- Deliberation is a package/example, not substrate.
- Resume authority remains package-local unless multiple packages prove a smaller neutral helper.

## Done Criteria

1. The human-interaction decision is documented with tests or explicit deferral.
2. If implemented, the step uses current `Suspension` semantics and package-owned resume.
3. Deliberation, if added, is a package example with no neutral-kernel semantic leakage.
4. `python -m pytest tests/arnold -q` passes.

## Megaplan Sizing

Recommended run: `partnered/full/medium`

Rationale: the work is design-heavy but bounded after M1/M2. It should not run before package authoring is settled.
