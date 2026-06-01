# M8b: Scaffolder, Pipeline Check, Dry Run, And Docs

## Outcome

Make new pipeline authoring genuinely easy: `arnold new pipeline <name>`, `arnold pipeline check <name>`, `arnold run <name> --dry-run`, and concise docs/examples that let an agent author a useful pipeline quickly.

## Scope

In:
- Add or update `arnold new pipeline <name>` scaffolding.
- Generate `pipeline.py`, prompt files, `SKILL.md`, optional `profiles/`, and tests using the public API from M8a.
- Add or polish `arnold pipeline check`, `check --explain`, and `run --dry-run` output.
- Dry-run output includes resolved effective settings per stage with source: Arnold default, plugin default, profile, CLI override, or env override.
- `check` flags unknown stage keys in settings, impossible timeout pairs, invalid worker caps, and settings declared for stages the pipeline does not expose.
- Update one-page authoring guide and advanced recipes.
- Update `docs/arnold/package-contract.md` and `docs/arnold/authoring-guide.md` so manifest minimalism and public API docs do not conflict.
- Add examples:
  - linear agent pipeline
  - panel plus decision plus revise loop
  - dynamic research fanout plus reducer
  - human pause/resume
  - subpipeline promotion / discoverable child reference
  - minimal optional profile file
  - validation failure examples

Out:
- Do not rework runtime architecture.
- Do not expose operation carriers, run envelopes, trust tiers, or Megaplan internals in beginner docs.

## Locked Decisions

- Simple plugin mandatory manifest fields are `name`, `entrypoint`, and `arnold_api_version`; other fields have defaults unless M-1 kept a stricter contract.
- `SKILL.md` remains required as agent-facing contract.
- Profiles are optional; omit them unless model routing is needed.
- Typed ports, dynamic fanout, subpipelines, and profiles are progressive-disclosure recipes.

## Required Outputs

- Exact generated test shape.
- Command-shape decision for explain output: either separate `arnold pipeline explain` or `check --explain`, documented in CLI help and docs.

## Constraints

- Generated examples must be internally consistent: prompt files exist, reads/writes are declared, imported helpers exist, decision prompts define route vocabulary.
- Generated decision routes use `HALT` from `arnold.pipeline`, not string termination.
- `SKILL.md` is required: scaffolds generate it and `pipeline check` fails loudly when absent.
- Generated tests should assert build, check, dry-run, prompt existence, and one intentional dataflow failure case.
- Scaffolded tests assert the generated pipeline does not import `arnold.pipelines.megaplan` or old `megaplan`.

## Done Criteria

- `arnold new pipeline my-reviewer` creates a runnable plugin.
- `arnold pipeline check my-reviewer` validates manifest, prompts, decision routes, route/flow targets, edges, artifact reads/writes, profile keys, runtime-settings stage keys, timeout pairs, worker caps, and resources.
- `arnold run my-reviewer --dry-run` prints realized graph, input contract, prompt/resource resolution, reads/writes, decisions, profile status, and resolved effective settings per stage with sources.
- Beginner guide explains the first 10 minutes without Megaplan internals.
- Advanced recipes cover dynamic fanout, profiles, typed ports, and subpipelines.

## Touchpoints

- CLI scaffolding
- `docs/arnold/authoring-guide.md`
- `docs/arnold/package-contract.md`
- examples
- tests

## Anti-Scope

- Do not make authors implement plugin operations for simple pipelines.
- Do not require static markdown prompts when callable prompts are needed.
- Do not expose `prompt_key`, `PromptRegistry`, import-side-effect prompt registration, or direct `Edge` construction in scaffolds.
