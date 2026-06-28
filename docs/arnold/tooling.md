# Arnold Tooling

Arnold tooling falls into four groups: pipeline discovery, workflow validation
and execution, Capsule operations, and Warrant operations. This page explains
when to use each tool. Generated inventories for command surfaces, projection
schemas, defect templates, and vocabulary live in
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).

## Discovery Tools

Use discovery tools when you need to know which pipeline modules Arnold can see
and why a module was skipped or rejected.

```bash
python scripts/check_workflow_pipeline_inventory.py
python scripts/check_pipeline_id_registry.py --check-identity-report
```

`check_workflow_pipeline_inventory.py` is the author-facing disposition gate. It
fails when a shipped root is missing from the inventory, when a migrated root
contains forbidden legacy patterns, or when active docs reference deleted CLI
commands. Fix discovery errors before debugging the workflow graph itself.

Manifest-first discovery is gated separately from runtime builds. It lets
Arnold read stable module facts without importing the module. Trusted runtime
topology is a later projection, created only when a caller explicitly allows the
pipeline to be built.

## Scaffold and Check

Create new workflow-first packages by copying the canonical template:

```bash
cp -r arnold_pipelines/_template arnold_pipelines/my_pipeline
```

Then validate the canonical builder target:

```bash
arnold workflow check --module arnold_pipelines.my_pipeline:build_pipeline
```

The old `arnold pipelines *` commands and `arnold <module> *` module verbs are
deprecated and are deleted in M6. New packages target the `arnold workflow`
surface and the explicit-node authoring contract.

## Run and Describe

Workflow CLI commands operate on a builder target:

```bash
arnold workflow describe --module arnold_pipelines.my_module:build_pipeline
arnold workflow dry-run --module arnold_pipelines.my_module:build_pipeline
arnold workflow run --module arnold_pipelines.my_module:build_pipeline --backend fake
```

Use `--backend fake` for fast, deterministic fake-backend smoke tests. Omit the
flag to use the default local backend.

Retained operator commands (`arnold status`, `arnold trace`, `arnold inspect`,
`arnold override`) project from event journals, artifacts, and control
transitions rather than from pipeline module verbs.

Use the generated CLI facts for exact verb inventories. Authored docs should
show only the commands needed for a workflow.

## Capsule Tools

Capsule commands are default-off behind `MEGAPLAN_M7_SINKS=1`.

```bash
MEGAPLAN_M7_SINKS=1 megaplan epic capsule build EPIC_ID
MEGAPLAN_M7_SINKS=1 megaplan epic capsule list
MEGAPLAN_M7_SINKS=1 megaplan epic capsule inspect CAPSULE_HASH
MEGAPLAN_M7_SINKS=1 megaplan epic capsule fork CAPSULE_HASH
```

Use `build` after an epic has exportable state. By default, export errors are
loud and stop the build. Add `--allow-degraded` only when a degraded Capsule is
the intended artifact.

Use `inspect` before trusting a Capsule. It checks the stored Capsule and
declared Contract against supplied or available context and reports failures
and legal adaptations. A degraded Capsule or an unmet Contract is a failure at
the CLI layer.

Use `fork` to derive a child Capsule from an existing Capsule. The fork records
one parent edge to the source hash. Use `--definition-overrides-json` only for
small, explicit Definition changes that are part of the fork's intent.

Capsule records are content-addressed and flat. Evidence payloads are referenced
by path/hash metadata; they are not inlined into the Capsule records.

## Warrant Tools

Warrant construction is currently an API-level surface rather than a public CLI
subcommand. The workflow is:

1. inventory or build a `WarrantSourceProjection`;
2. verify that required source fields are present and signable;
3. call `build_warrant(...)` with an explicit key or configured resolver;
4. call `verify_warrant(...)` before relying on the signed output.

The inventory adapter is read-only over existing plan-directory sources. Missing
facts remain missing. Unsupported facts remain unsupported. Incomplete
projections raise `incomplete_warrant_source` before a signing key is resolved.

Set `MEGAPLAN_SIGNING_WARRANT_KEY` when using configuration-based signing. Keep
key IDs descriptive enough for operators to rotate keys, but do not include
secret material in projection metadata.

## Generated Reference Tooling

Run the Arnold docs generator when code-owned facts change:

```bash
python scripts/generate_arnold_docs.py --check
python scripts/generate_arnold_docs.py --write
```

`--check` is the drift gate. `--write` regenerates the reference page. The
generated file has a header that marks it as generated and should not be edited
by hand.

Use authored docs for decisions, caveats, and workflows. Use generated docs for
exact facts.

## Practical Debug Order

When a module does not work:

1. Run `python scripts/check_workflow_pipeline_inventory.py` to confirm
   disposition and scan for forbidden patterns.
2. Run `arnold workflow check --module <package.module>:build_pipeline` to
   validate the compiled manifest.
3. Run `arnold workflow dry-run --module <package.module>:build_pipeline` to
   inspect the route graph without executing.
4. Run `arnold workflow run --module <package.module>:build_pipeline --backend fake`
   for a deterministic smoke test.
5. If the issue is replay/export related, inspect the Capsule build or Contract
   failure before changing the module.
6. If the issue is signing related, inspect the Warrant source projection before
   changing receipts or signing code.
