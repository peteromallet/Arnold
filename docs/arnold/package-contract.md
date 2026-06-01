# Arnold Package Contract

An Arnold package is a discoverable pipeline module plus its adjacent agent
instructions. The contract is intentionally small: the package must expose
stable metadata for no-import discovery, return a valid `Pipeline` from its
entrypoint, and keep human/agent-facing guidance in `SKILL.md`.

Generated details for manifest fields, discovery facts, dispositions, schemas,
and CLI inventories are maintained in
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).
This page describes the authoring contract around those facts.

## Layout

The normal package shape is:

```text
megaplan/pipelines/
  my_module.py
  my-module/
    SKILL.md
    prompts/
      review.md
      revise.md
```

The Python filename uses underscores because it is a module. The CLI name uses
hyphens because that is what users and agents type. Discovery canonicalizes the
name, so choose one readable slug and keep the module, package directory, and
metadata aligned.

Sibling-file modules are also supported for simpler packages. In either shape,
`SKILL.md` should live where discovery can associate it with the module. The
generated package contract reference records the exact reader behavior.

## Required Module Shape

A package module should keep these concepts visible at top level:

- the public Arnold name and description;
- the Arnold API version;
- the driver declaration;
- the entrypoint function name;
- optional supported modes, default profile, and capability labels;
- an entrypoint that returns a `Pipeline`.

Keep these values static. Discovery must be able to inspect the package without
executing arbitrary code. Runtime work belongs inside stages, not in module
metadata.

## Entrypoint Rules

The entrypoint should be nullary from the registry's perspective. CLI-specific
values belong at the command boundary or in `StepContext`, not in the registry
builder signature. That preserves a stable package identity: the module can be
discovered, checked, and included in Capsule Definition identity without knowing
which run-time flags a user will pass later.

When a workflow needs mode-specific behavior, prefer prompt variants,
`ctx.mode`, profile slots, or explicit state inputs over changing the graph at
import time.

## Static Identity

Arnold distinguishes static behavioral identity from trusted runtime topology.
Static identity is discovered without importing the package and includes source,
skill, resource, helper, declared-input, and unresolved-dynamic-input
projections. Runtime topology is produced only when a trusted caller explicitly
builds the pipeline.

Package authors should therefore make two things easy:

- no-import discovery can find enough stable metadata to name and describe the
  package;
- trusted builds can construct the same graph repeatedly from the same package
  bytes and declared resources.

Avoid top-level side effects, global mutation, environment-dependent metadata,
and network or filesystem probes during import. If a stage needs the filesystem,
do that work inside the stage's `run()` method and make the relevant file paths
explicit inputs.

## Resource Ownership

Prompts, local helper files, and package instructions are part of package
behavior. Keep them under the sibling package directory when possible. This
makes author intent clear and lets static identity include the files that
actually shape execution.

Do not duplicate package facts in multiple places. The module owns executable
metadata. `SKILL.md` owns agent-facing guidance. Generated references own exact
field inventories.

## Validation Contract

`megaplan pipelines check NAME` is the package's basic compatibility gate. It
must be able to load the package, build the graph, and validate graph
structure. `arnold pipelines check NAME` reaches the same check through the
Arnold namespace.

`megaplan pipelines doctor` and `arnold pipelines doctor` are discovery tools.
Use them when a package is skipped or rejected before graph validation begins.

## Capsule Contract Interaction

Capsule Contracts consume package identity facts but do not relax the package
contract. A Capsule may record static behavioral hash, runtime topology hash,
manifest ABI, port expectations, Evidence refs, repo commit, tool versions,
model versions, environment variable requirements, and secret-shape
declarations. Optional environment requirements are checked only when the
Capsule declares them and the caller supplies matching runtime context.

The practical rule for authors is simple: declare requirements only when they
are real replay constraints. Do not read process environment or secret values
inside package metadata to make a Capsule look more complete.

## Compatibility Policy

Forward-compatible projection schemas ignore unknown keys, but package modules
should not rely on that to smuggle behavior through undocumented metadata. Add
new public package facts deliberately, update the generator when they are
code-owned, and keep authored docs focused on intent and workflow.
