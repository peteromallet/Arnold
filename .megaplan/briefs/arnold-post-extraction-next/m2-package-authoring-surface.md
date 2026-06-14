# M2: Package Authoring Surface

## Outcome

Give agents a clean way to author new Arnold-backed pipeline packages after the Megaplan bridge proves the package boundary.

This milestone should make the "build a pipeline quickly on the fly" story concrete without promoting low-level graph machinery as the public authoring language.

## Scope

IN:

- Define the package authoring contract that sits above `Stage`, `Edge`, and `StepResult.next`.
- Add small Python helpers or templates only where they remove real authoring friction.
- Document how a package declares profiles, prompts, resources, adapters, typed ports, hooks, and run/resume ownership.
- Add examples/tests using existing evidence-pack and Megaplan package shapes.
- Keep generated YAML or duplicate declarative formats out unless they are purely derived artifacts.

OUT:

- No new universal runtime.
- No broad deliberation package port.
- No public YAML authoring format.
- No deletion of compatibility shims.

## Locked Decisions

- Python is the source of truth for package definitions.
- `PipelineBuilder`, `Stage`, `Edge`, and `StepResult.next` may remain backend/IR tools; they are not the polished agent-facing DSL by themselves.
- Package-owned semantics stay package-owned.
- Certified patterns may exist, but critique/review/judge/fact-check are not kernel concepts.

## Open Questions

- What is the minimum helper layer that makes package authoring feel obvious?
- Which concepts deserve certified patterns versus package-local examples?
- How much of evidence-pack should become a reference package?

## Done Criteria

1. A new package skeleton can be authored from docs and tests without reading Megaplan internals.
2. Evidence-pack and Megaplan examples both fit the same authoring contract.
3. No duplicate YAML/source-of-truth format is introduced.
4. `python -m pytest tests/arnold -q` passes.

## Megaplan Sizing

Recommended run: `partnered/full/medium`

Rationale: this has design judgment but less unknown substrate risk after M1. It should be a separate sprint because authoring UX decisions should be based on a working package bridge, not guessed in advance.
