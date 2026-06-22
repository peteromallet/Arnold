# Arnold Package Contract

An Arnold package is a discoverable workflow module plus its adjacent agent
instructions. The contract is intentionally small: the package must expose
stable metadata for no-import discovery, return a valid ``Pipeline`` from its
entrypoint, and keep human/agent-facing guidance in ``SKILL.md``.

Generated details for manifest fields, discovery facts, schemas, and CLI
inventories are maintained in
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).
The authoritative field-level contract is at
[`package-authoring-contract.md`](package-authoring-contract.md).
This page describes the authoring contract around those facts.

## Layout

The normal package shape is:

```text
arnold_pipelines/megaplan/pipelines/
  my_module.py
  my-module/
    SKILL.md
    prompts/
      review.md
```

The Python filename uses underscores because it is a module. The CLI name uses
hyphens because that is what users and agents type. Discovery canonicalizes the
name, so choose one readable slug and keep the module, package directory, and
metadata aligned.

Sibling-file modules are also supported for simpler packages. In either shape,
``SKILL.md`` should live where discovery can associate it with the module.

## Required Module Shape

A package module should keep these concepts visible at top level:

- the public Arnold name and description;
- the Arnold API version;
- the driver declaration;
- the entrypoint function name;
- optional supported modes, default profile, and capability labels;
- an entrypoint that returns a ``Pipeline``.

Keep these values static. Discovery must be able to inspect the package without
executing arbitrary code. Runtime work belongs inside stages, not in module
metadata.

## Entrypoint Rules

The entrypoint should be nullary from the registry's perspective. CLI-specific
values belong at the command boundary, not in the registry builder signature.
That preserves a stable package identity: the module can be discovered, checked,
and included in identity projections without knowing which runtime flags a user
will pass later.

When a workflow needs mode-specific behavior, prefer prompt variants or explicit
state inputs over changing the graph at import time.

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
do that work inside the stage's execution method and make the relevant file paths
explicit inputs.

## Resource Ownership

Prompts, local helper files, and package instructions are part of package
behavior. Keep them under the sibling package directory when possible. This
makes author intent clear and lets static identity include the files that
actually shape execution.

Do not duplicate package facts in multiple places. The module owns executable
metadata. ``SKILL.md`` owns agent-facing guidance. Generated references own exact
field inventories.

## Validation Contract

``arnold workflow check --module <package>:build_pipeline`` is the package's
basic compatibility gate. It must be able to load the package, build the graph,
and validate graph structure.

## Runtime Contract Interaction

Package identity is consumed by Capsule Contracts and replay tooling but the
package contract is the floor. A runtime projection may record static behavioral
hash, runtime topology hash, manifest ABI, capability expectations, evidence
refs, repo commit, tool versions, model versions, environment variable
requirements, and secret-shape declarations. Optional requirements are checked
only when the caller supplies matching runtime context.

The practical rule for authors is simple: declare requirements only when they
are real replay constraints. Do not read process environment or secret values
inside package metadata to make a projection look more complete.

## Compatibility Policy

The canonical surface is ``arnold.workflow`` and the ``arnold workflow`` CLI.
Legacy ``arnold.pipeline`` graph-builder surfaces and ``arnold pipelines``
commands are scheduled for deletion in M6 and must not be used for new authoring.
