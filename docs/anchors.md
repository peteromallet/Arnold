# Megaplan Anchors

Anchors are durable alignment artifacts that Megaplan snapshots into a plan and feeds to drift-sensitive stages. The first supported anchor type is `north_star`.

## `north_star`

A North Star captures the end state that should remain true across planning, critique, gate, finalize, and review. Use it for epics, architecture migrations, public contract changes, and cross-cutting refactors where local milestone briefs are not enough to prevent drift.

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

Chain runs require a top-level `anchors.north_star` by default. Milestone anchors do not satisfy that epic-level requirement; they only extend the top-level North Star for a local milestone.

Opt out only when the chain has no durable destination beyond its milestone briefs:

```bash
megaplan chain start --spec path/to/chain.yaml \
  --no-require-anchor \
  --missing-anchor-ack "Mechanical cleanup chain; no cross-milestone destination."
```

The same decision can live in the spec:

```yaml
driver:
  require_anchor: false
  missing_anchor_ack: "Mechanical cleanup chain; no cross-milestone destination."
```

## Captured Files

At initialization, Megaplan copies anchors into the plan directory:

```text
anchors/north_star/epic.md
anchors/north_star/plan.md
anchors/north_star/combined.md
```

`state.json` stores metadata under `meta.anchors`: source path, captured artifact path, checksum, size, title, and capture time. It does not store full anchor prose. Later edits to source anchor files do not affect already-initialized plans.

## Prompt Behavior

When a plan has a North Star, prompt assembly chooses one of three render modes by stage:

- `full` includes the complete bounded anchor context. It is used for decision-heavy stages: plan, prep, prep triage/distill, critique, critique evaluator, revise, gate, and finalize.
- `check` includes only a terse conflict-check reminder with captured artifact paths and scope labels. It is used for review, compact review, parallel review, and parallel critique.
- `none` injects no anchor context. Execute, execute-batch, and feedback use this mode because execution acts on an already-approved plan.

Full mode prompts include a block titled:

```text
## Anchor Context: North Star
```

Check mode prompts include a block titled:

```text
## Anchor Check: North Star
```

The check block tells the agent not to restate the North Star and to raise an explicit anchor conflict or deviation only if the current step would visibly violate it.

Execution prompts intentionally receive no anchor context. Executors should follow the approved `finalize.json` boundary and report normal execution deviations; they should not reinterpret the epic or sprint destination from anchor prose.

## Inspection

```bash
megaplan anchors show --plan <name>
megaplan anchors show --plan <name> --json
```

`anchors show` prints captured metadata and combined content. `status`, `audit`, and `introspect` include compact anchor summaries.

## Common Mistakes

- Creating `NORTHSTAR.md` next to `chain.yaml` without declaring `anchors.north_star`. It is not auto-discovered.
- Opting out of the epic North Star requirement without a written acknowledgement. Use `--missing-anchor-ack` or `driver.missing_anchor_ack`.
- Editing source `NORTHSTAR.md` after plan initialization and expecting active plans to change. Plans use captured snapshots.
- Treating a milestone anchor as a replacement for the epic anchor. It is additional context.
