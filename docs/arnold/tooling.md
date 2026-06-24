# Arnold Tooling

Arnold tooling falls into four groups: module discovery, graph validation,
Capsule operations, and Warrant operations. This page explains when to use each
tool. Generated inventories for command surfaces, projection schemas, defect
templates, and vocabulary live in
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).

## Discovery Tools

Use discovery tools when you need to know which pipeline modules Arnold can see
and why a module was skipped or rejected.

```bash
arnold pipelines list
arnold pipelines list --json
arnold pipelines doctor
megaplan pipelines doctor
```

`list` is for operator-facing selection. `doctor` is for author-facing
diagnosis. When a package appears in `doctor` as rejected, fix discovery before
debugging the graph itself.

Manifest-first discovery is gated separately from runtime builds. It lets
Arnold read stable module facts without importing the module. Trusted runtime
topology is a later projection, created only when a caller explicitly allows the
pipeline to be built.

## Scaffold and Check

Create new native-first modules with:

```bash
arnold pipelines new my-module
```

The `--driver graph` switch is deprecated and should only be used for temporary
compatibility baselines.

Validate with the canonical Arnold namespace when documenting a public flow:

```bash
arnold pipelines check my-module
```

The Megaplan namespace remains a legacy compatibility path during the migration
but new packages target the Arnold namespace and the native-first contract.

## Run and Describe

Arnold dispatches module verbs through the pipeline registry:

```bash
arnold my-module describe
arnold my-module run --help
arnold my-module run [module-specific args]
```

Planning remains special only where the legacy planning workflow has additional
control verbs:

```bash
arnold planning auto
arnold planning override force-proceed
```

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

1. Run `arnold pipelines doctor` to confirm discovery.
2. Run `arnold pipelines check NAME` to validate the graph or judge manifest.
3. Run the module's `describe` or `run --help` path to confirm CLI dispatch.
4. If the issue is replay/export related, inspect the Capsule build or Contract
   failure before changing the module.
5. If the issue is signing related, inspect the Warrant source projection before
   changing receipts or signing code.
