# Briefs

Briefs are the committed source documents that create megaplan runs. Use them for
work you intend to execute now: a single plan idea, or an epic's `chain.yaml`
plus milestone idea files.

They deliberately sit beside tickets, but they are not tickets:

- **Briefs** are work inputs. They feed `megaplan init` or `megaplan chain start`.
- **Tickets** are problem notes. They are discovered later, linked to epics, and
  can auto-address when a resolving epic completes.

## Local format

Single-plan briefs live directly under:

```text
<repo>/.megaplan/briefs/<slug>.md
```

Epic briefs live in a directory:

```text
<repo>/.megaplan/briefs/<epic-slug>/chain.yaml
<repo>/.megaplan/briefs/<epic-slug>/<milestone>.md
```

Commit these files. `.megaplan/briefs/` is durable input material;
`.megaplan/plans/` is generated run state.

New briefs are markdown artifacts with YAML frontmatter. `megaplan init` strips
that frontmatter before snapshotting the idea text, so the metadata is useful
for listing/searching without contaminating the plan prompt.

## CLI

Create a single-plan brief:

```bash
megaplan brief new cleanup-runtime -b "Clean up runtime paths and tests"
megaplan brief new cleanup-runtime --from /path/to/idea.md
cat idea.md | megaplan brief new cleanup-runtime -
```

Create and immediately initialize a plan from it:

```bash
megaplan brief new cleanup-runtime -b "Clean up runtime paths and tests" --init
```

Create an epic scaffold:

```bash
megaplan brief epic artifact-store \
  --milestone m1-schema="Schema and invariants" \
  --milestone m2-storage="Storage layer" \
  --milestone m3-api="Public API"
```

That writes `.megaplan/briefs/artifact-store/chain.yaml` and milestone brief
stubs in the same directory.

Read and search briefs:

```bash
megaplan brief list
megaplan brief show cleanup-runtime
megaplan brief search runtime cleanup --all
```

These commands use the same local artifact substrate as tickets: common
`.megaplan/<kind>/` path handling, slug normalization, optional frontmatter
parsing, keyword filtering, and snippets. The lifecycle remains different:
tickets have status/link/auto-addressing; briefs are inputs to runs.

## Lifecycle

`megaplan init --idea-file <path>` reads the idea file and snapshots the text into
the plan state. It does not move arbitrary files into `.megaplan/briefs/`.

Use `megaplan brief new --init` when you want ticket-like ergonomics: first create
the canonical committed source file, then initialize from it.

For epics, run:

```bash
megaplan chain start --spec .megaplan/briefs/<epic-slug>/chain.yaml
```

When a chain spec is stored under `.megaplan/briefs/`, chain runtime state still
lives under root `.megaplan/plans/.chains/`; it does not create nested runtime
directories inside the brief tree.
