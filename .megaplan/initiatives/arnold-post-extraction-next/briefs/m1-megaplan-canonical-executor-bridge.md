# M1: Megaplan Canonical Executor Bridge

## Outcome

Move the Megaplan package onto the neutral Arnold executor surface for a representative execution path, through package-owned adapters and hooks, while preserving the current public Megaplan CLI/import behavior.

The reviewer should be able to see that Megaplan is consuming the Arnold substrate built in Slices 1-32 rather than carrying a second hidden pipeline runtime for the same responsibility.

## Scope

IN:

- Build or complete package-owned conversion between Megaplan pipeline/context shapes and `arnold.pipeline` pipeline/context shapes.
- Wire Megaplan lifecycle, state merge, budget/governor, artifact, schema-registry, and Step-IO policy behavior through `ExecutorHooks` or package adapters where those concerns are genuinely Megaplan-specific.
- Characterize the existing Megaplan executor behavior before replacing any load-bearing path.
- Move one representative Megaplan pipeline/run path through `arnold.pipeline.run_pipeline`.
- Preserve compatibility for public `megaplan` imports, CLI invocation, plan artifacts, and status/trace expectations.
- Keep `python -m pytest tests/arnold -q` green.
- Add focused tests proving the package bridge uses the neutral executor without importing old quarry code wholesale.

OUT:

- No deletion of the old Megaplan executor until the representative bridged path is proven.
- No broad port of `arnold-generalized-pipeline` `hooks.py` / `adapter.py` as-is.
- No broad `arnold/agent/**`, Hermes CLI, Honcho, or tool-registry transplant.
- No generic human-gate redesign.
- No deliberation package resurrection.
- No branch deletion or stash pruning.

## Locked Decisions

- The Arnold substrate is Slices 1-32 on `feat/arnold-clean-extraction`; it is full-suite green.
- Resume authority remains package-local unless a second concrete package proves a smaller neutral helper.
- Megaplan behavior lives under `arnold.pipelines.megaplan` / the public `megaplan` compatibility surface, not in neutral `arnold.pipeline`.
- Product-specific policies such as plan-dir schema roots, Step-IO policy defaults, lifecycle events, budget/governor semantics, and compatibility shims belong in Megaplan adapters/hooks.
- The quarry branch is evidence only. Copying its bridge files wholesale is explicitly out of scope.

## Open Questions

- Which single representative Megaplan run path is the smallest honest proof of the bridge?
- Which existing executor behaviors must be characterized before being delegated to hooks?
- Does the package bridge need a new adapter module, or should it extend existing Megaplan `_pipeline` modules?
- What compatibility telemetry or warnings are needed before later deleting old paths?
- Which tests should define "public Megaplan behavior preserved" for this first sprint?

## Constraints

- Do not work on top of the editable install or dirty repo root; use the clean extraction worktree.
- Use `python -m pytest`, not an ambient `pytest` executable.
- Maintain import-coupling and semantic-coupling conformance gates.
- Keep Arnold neutral: no new generic Arnold imports of Megaplan package code.
- Prefer package-owned adapters over widening neutral dataclasses.
- Avoid adding a YAML or duplicate declarative format.

## Done Criteria

1. A representative Megaplan pipeline path can run through `arnold.pipeline.run_pipeline` via package-owned bridge code.
2. Existing public Megaplan CLI/import behavior for that path remains compatible.
3. Characterization tests capture the old behavior before any replacement.
4. New tests prove lifecycle/state/artifact/schema/policy hooks are invoked at the package boundary.
5. No broad quarry bridge files are copied wholesale.
6. `python -m pytest tests/arnold -q` passes.
7. Plan docs state which old Megaplan executor paths remain and what must happen before deletion.

## Touchpoints

- `arnold.pipeline.executor`
- `arnold.pipeline.hooks`
- `arnold.pipeline.types`
- `arnold.pipelines.megaplan._pipeline.executor`
- `arnold.pipelines.megaplan._pipeline.run_cli`
- `arnold.pipelines.megaplan._pipeline.envelope`
- `arnold.pipelines.megaplan._pipeline.registry`
- `arnold.pipelines.megaplan._pipeline.step_io_policy`
- `arnold.pipelines.megaplan.model_seam`
- `megaplan/*` compatibility imports and CLI entrypoints
- tests under `tests/arnold/` and Megaplan package tests that exercise execution

## Anti-Scope

- Do not turn the canonical executor into a Megaplan-shaped runtime.
- Do not move Megaplan package semantics into `arnold.pipeline`.
- Do not revive the old broad neutral `run_pipeline_resume()`.
- Do not solve all package authoring UX in this sprint.
- Do not prune branches or stashes.

## Megaplan Sizing

Recommended run: `partnered/full/high +prep`

Suggested command:

```text
megaplan init .megaplan/initiatives/arnold-post-extraction-next/briefs/m1-megaplan-canonical-executor-bridge.md --profile partnered --robustness full --depth high --with-prep --prep-direction "Start from the full-suite-green Slices 1-32. Focus on the smallest representative Megaplan path that can run through arnold.pipeline.run_pipeline via package-owned adapters/hooks. Compare existing Megaplan executor behavior to the neutral executor hook surface before proposing replacements. Do not copy quarry bridge files wholesale."
```

Rationale: the work is cross-cutting and integration-heavy, but not a new kernel contract. Premium reasoning across plan/critique/review is useful; execution can remain routed by task complexity. Prep earns its place because the planner must trace the current Megaplan executor, CLI, hook, artifact, and compatibility surfaces before choosing the representative bridge path.
