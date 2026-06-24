# Megaplan Anchors

Anchors are durable alignment artifacts that Megaplan snapshots into a plan and feeds to drift-sensitive stages. The first supported anchor type is `north_star`.

## `north_star`

A North Star captures the end state that should remain true across planning, execution, critique, gate, and review. Use it for epics, architecture migrations, public contract changes, and cross-cutting refactors where local milestone briefs are not enough to prevent drift.

## Standalone Plans

```bash
megaplan init --project-dir . --idea-file .megaplan/briefs/my-plan.md --north-star docs/NORTHSTAR.md
```

`--north-star` resolves relative to `--project-dir` unless an absolute path is provided.

## Chain Specs

```yaml
anchors:
  north_star: NORTHSTAR.md

milestones:
  - label: m1
    idea: m1.md
    anchors:
      north_star: m1-northstar.md
```

Chain anchor paths resolve relative to the `chain.yaml` directory. Milestone anchors extend the epic anchor; they do not silently override it.

Use `megaplan chain start --require-anchor --spec path/to/chain.yaml` to reject a chain that lacks a top-level `anchors.north_star`.

## Captured Files

At initialization, Megaplan copies anchors into the plan directory:

```text
anchors/north_star/epic.md
anchors/north_star/plan.md
anchors/north_star/combined.md
```

`state.json` stores metadata under `meta.anchors`: source path, captured artifact path, checksum, size, title, and capture time. It does not store full anchor prose. Later edits to source anchor files do not affect already-initialized plans.

## Prompt Behavior

When a plan has a North Star, prompts include a block titled:

```text
## Anchor Context: North Star
```

The block appears in standard plan, prep, critique, gate, finalize, execute, and review prompts, plus bypass prompts for execute batches, parallel critique, parallel review, and compact review.

## Inspection

```bash
megaplan anchors show --plan <name>
megaplan anchors show --plan <name> --json
```

`anchors show` prints captured metadata and combined content. `status`, `audit`, and `introspect` include compact anchor summaries.

## Common Mistakes

- Creating `NORTHSTAR.md` next to `chain.yaml` without declaring `anchors.north_star`. It is not auto-discovered.
- Editing source `NORTHSTAR.md` after plan initialization and expecting active plans to change. Plans use captured snapshots.
- Treating a milestone anchor as a replacement for the epic anchor. It is additional context.
