---
name: writing-panel-strict
description: Adversarial review of prose drafts by N reviewers, then revise. Not for code.
---

# Writing Panel (Strict)

A multi-reviewer pipeline for rigorous prose revision. Three independent
reviewers (pessimist, optimist, structuralist) critique a draft in parallel,
a synthesis editor reconciles their feedback into a revision brief, and a
revision editor produces the updated draft. A human gate lets you review
the result and loop back for another round or stop.

## Modes

| Mode | Description |
|------|-------------|
| `polish` | Light editing — tighten prose, fix errors, preserve structure |
| `restructure` | Reorganize sections, improve flow, may move content |
| `provoke` | Push the draft to be bolder, more opinionated, less safe |

## Inputs

- `draft` (file, required): Path to the markdown draft to review.

## Usage

```bash
# Run with default profile
megaplan run writing-panel-strict path/to/draft.md

# Run with a specific mode
megaplan run writing-panel-strict path/to/draft.md --mode polish

# Run with a specific profile
megaplan run writing-panel-strict path/to/draft.md --profile @writing-panel-strict:standard

# Resume after human gate
megaplan resume <plan-dir> --choice continue
megaplan resume <plan-dir> --choice stop
```

## Pipeline Flow

1. **Panel Review** (parallel) — pessimist, optimist, and structuralist review the draft independently.
2. **Synthesis** — editor reconciles the three reviews into a revision brief.
3. **Revise** — editor rewrites the draft incorporating the revision brief.
4. **Human Gate** — you inspect the revised draft. Choose `continue` to loop back for another round, or `stop` to finish.

## Profiles

| Profile | Description |
|---------|-------------|
| `@writing-panel-strict:standard` | Default — Claude low-effort for all stages |
| `@writing-panel-strict:premium` | Coming soon — Claude high-effort reviewers |
| `@writing-panel-strict:cheap` | Coming soon — DeepSeek for all stages |
