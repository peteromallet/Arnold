# M8a: Public Handle/Flow Authoring API And Validation UX

## Outcome

Design and land the public pipeline authoring API: named handles plus explicit `p.flow(...)`, `HALT` sentinel, clear `reads`/`writes`, decision routes, and validation messages that make new pipelines easy to compose without Megaplan internals.

## Scope

In:
- Implement or finalize the public API around `Pipeline`, `HALT`, `p.input`, `p.agent`, `p.panel`, `p.decision`, `p.flow`, `reads`, `writes`, and `prompt`.
- `prompt=` accepts `str` (`.md` bundle-relative file path or inline literal) or `Callable[[StepContext], str]`. `prompt_key`, `PromptRegistry`, import-side-effect `register_prompt()`, and global mutable registries are not part of the public API.
- Clarify whether `p.input(...)` is an input node, artifact handle, or both, and make the API unambiguous.
- Ensure decision steps declare prompt/schema/output contract sufficient for route validation.
- Implement author-facing validation for missing prompts, unknown routes, route bypassing required reads, unguarded cycles, duplicate node names, invalid profile keys, invalid runtime settings, and halt semantics.
- Ensure `arnold pipeline check --explain` or equivalent explains validation failures in useful language.
- Keep advanced concepts as second-page recipes.

Out:
- Do not implement scaffolder/docs tooling beyond what is required to prove the API; that is M8b.
- Do not show custom operations, run envelopes, trust tiers, quarantine, dynamic fanout, typed ports, or subpipeline references in the first 10-minute guide.

## Locked Decisions

- Public docs and scaffolds should prefer named handles plus explicit `p.flow(...)` once implemented.
- Node handles, not string names, should be route targets wherever possible.
- `HALT` is a typed sentinel, not a string.
- Dataclass graph literals and direct `Edge` construction are not the happy-path public style.
- The graph happy path should stay about composition. Per-stage operational settings such as wall timeout, idle timeout, heartbeat interval, poll cadence, retry budget envelope, deadline, isolation, and cost caps are configured through plugin defaults, profile settings, and run/CLI overrides, not required as noisy kwargs in `p.agent(...)`.
- Execution-shape settings that are part of topology, such as `max_workers` on a panel/fanout node, may appear on the relevant public node constructor when they are intrinsic to that node's behavior.
- Existing `PipelineBuilder` docs may remain until the new API exists and at least two real pipelines migrate, then become legacy or are rewritten.
- M8a implements the validation engine and structured errors/warnings. CLI rendering for `--explain` and `--dry-run` polish lands in M8b.

## Required Outputs

- Exact syntax for dynamic fanout and subpipeline recipes that should appear outside the first guide.
- Exact syntax for an advanced runtime-settings recipe, including per-stage timing overrides and dry-run display of effective values with their sources.
- Public join/reducer export decision for `majority_vote` and related helpers.

## Constraints

- Keep the first-guide API small.
- Do not expose Megaplan decision labels.
- Validation must teach authors what to fix without sending them into Megaplan internals.

## Done Criteria

- A linear pipeline and a panel/revise loop can be authored using only public APIs.
- Validation catches unknown route/flow targets, missing decision routes, implicit `p.flow()` successors on decision nodes, unguarded cycles, unstable duplicate names, unsatisfied `reads`, route-bypass-producer cases, invalid runtime-settings stage keys, impossible timeout pairs, unsupported isolation modes, invalid worker caps, and settings for undeclared stages.
- The API example in the cleanup plan is runnable or has a runnable equivalent test.
- At least two real or fixture pipelines migrate to the public style.

## Touchpoints

- `arnold/pipeline/`
- authoring docs
- pipeline validation tests
- non-Megaplan toy fixtures

## Anti-Scope

- Do not build all M8 scaffolding here.
- Do not require typed ports for simple pipelines.
