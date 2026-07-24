# Arnold Skill Integration

Every Arnold module needs instructions that an agent can read before running or
editing the pipeline. In practice that means a sibling `SKILL.md` beside the
pipeline package. The skill is not just decoration: it is part of how package
behavior is explained, discovered, and hashed for static behavioral identity.

Generated facts about package and discovery surfaces live in
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).
This page explains how to write the authored skill content.

## What the Skill Should Say

Write the skill for the agent that will operate the module. It should answer:

- when to choose this module;
- what inputs the module expects;
- what outputs or artifacts it produces;
- what constraints matter for safety, cost, replay, or review;
- which commands validate or run the module;
- which files are prompts, fixtures, examples, or other resources.

Keep it operational. The skill should tell an agent how to use the package
correctly, not restate every schema field or CLI option.

## Frontmatter

Use normal skill frontmatter:

```markdown
---
name: my-module
description: Use when ...
---
```

The `name` should match the Arnold CLI slug. The `description` should be a
decision rule, not a marketing sentence. A good description lets an agent decide
whether the module is relevant before opening the rest of the file.

## Keep Instructions Near Resources

Store prompt files, examples, fixture notes, and package-specific references
under the sibling package directory when they are part of the module's behavior:

```text
megaplan/pipelines/my-module/
  SKILL.md
  prompts/
  examples/
  references/
```

Then write relative paths in `SKILL.md`. This keeps static discovery and human
review aligned: the module, instructions, and resources move together.

## Avoid Duplicating Generated Facts

Do not paste manifest-field tables, projection schema tables, full CLI command
inventories, or checker defect inventories into `SKILL.md`. Those are
code-owned facts and are generated in the Arnold projection reference.

It is fine to include the small command sequence an agent actually needs:

```bash
arnold workflow check --module arnold_pipelines.my_module:build_pipeline
arnold workflow run --module arnold_pipelines.my_module:build_pipeline --help
```

It is also fine to explain which generated reference to consult when an agent
needs exact schema details.

## Explain Replay Boundaries

If the module is intended to feed Capsules or Warrants, state that plainly.
Useful guidance includes:

- whether Evidence should be referenced by path and hash instead of copied into
  prompts or outputs;
- which runtime facts are true replay requirements;
- whether missing source facts should block signing or produce degraded output;
- what an agent must not invent when source inventory is incomplete.

For Warrant-oriented modules, be explicit that the source projection is
read-only over existing receipts, ledgers, rationale captures, and result refs.
The skill may tell an agent where those sources usually appear, but it should
not instruct the agent to mutate receipts to satisfy signing.

## Coordinate With Megaplan Skills

Megaplan's package-level skills under `megaplan/data/` have their own
distribution strategy and symlink-based install flow. Arnold module skills are
different: they live with the pipeline package and describe one module's
behavior. Do not add a module skill to the global Megaplan skill distribution
unless it is intentionally becoming a globally installed skill.

If a module skill refers to global Megaplan workflows, link to those docs rather
than copying their contents. This keeps package-specific guidance small and
prevents drift when global skills are regenerated or redistributed.

## Review Checklist

Before treating a module skill as ready, check that:

- the frontmatter slug matches the Arnold module name;
- the description says when to use the module;
- prompts and resources named by the pipeline are documented or obvious;
- validation commands point at current Arnold/Megaplan surfaces;
- replay, Capsule, or Warrant caveats are stated when relevant;
- exact field tables are linked, not copied.
