---
name: folder-audit
description: |
  Walk a directory tree and audit whether each folder's children belong at the
  right level of abstraction. Produces a structured JSON audit plus a nested
  Markdown annotated tree.
---

# folder-audit

## What it does

The `folder-audit` pipeline inspects a target directory, builds a tree of
folders up to a configurable depth, and asks an LLM auditor to classify every
immediate child as `fit`, `misplaced`, `duplicate`, `naming_mismatch`, etc.

It emits two artifacts in the plan directory:

- `audit.json` — machine-readable audit with summary and per-folder entries
- `audit.md` — human-readable nested annotated tree

## Running it

The pipeline is built around the native Arnold `AgentStep`. The `audit` stage
injects a worker callable that dispatches to Codex by default. A local profile
is provided at `profiles/standard.toml`.

### Default mode (Codex worker)

```bash
python -m arnold run folder-audit \
  --inputs target_dir=/path/to/repo,max_depth=2,chunk_size=5,max_workers=3 \
  --plan-dir /tmp/folder-audit-plan
```

The default profile resolves the `audit` stage to `codex`. If you want to use a
different model, override the profile:

```bash
python -m arnold run folder-audit \
  --inputs target_dir=/path/to/repo,max_depth=2,chunk_size=5,max_workers=3 \
  --profile @folder-audit:standard \
  --plan-dir /tmp/folder-audit-plan
```

### Using pre-generated subagent results

For faster iteration or when you want to supply audits from another agent
harness, pass an `agent_results` JSON file:

```bash
python -m arnold run folder-audit \
  --inputs target_dir=/path/to/repo,agent_results=/tmp/agent_results.json \
  --plan-dir /tmp/folder-audit-plan
```

The `agent_results` file must be a JSON object with a top-level `folders`
array. The pipeline will compute a summary and reconcile the entries with the
real filesystem tree when rendering `audit.md`.

## Inputs

| Key | Default | Description |
|---|---|---|
| `target_dir` | required | Directory to audit |
| `max_depth` | `8` | How many levels deep to walk |
| `chunk_size` | `5` | Folders per Codex call |
| `max_workers` | `3` | Parallel Codex calls per level |
| `agent_results` | none | Path to external audit JSON |

## Taxonomy

- `fit` — belongs here and at this level
- `too_granular` — should live one level deeper
- `wrong_level_of_abstraction` — belongs at a higher or lower level
- `mixed_concerns` — contains unrelated things that should split
- `misplaced` — belongs under a sibling folder
- `orphaned` — doesn't obviously belong anywhere
- `naming_mismatch` — name doesn't match actual contents
- `overpacked` — too many concerns crammed into one folder
- `underpacked` — folder adds no value, should collapse upward
- `duplicate` — redundant with another item
- `unclear` — cannot determine

## Worker injection

`AuditStep` subclasses Arnold's `AgentStep`. The worker is supplied at pipeline
construction time:

```python
from arnold.pipelines.folder_audit import build_pipeline

pipeline = build_pipeline(worker=my_worker)
```

If no worker is supplied, `build_pipeline()` uses a default worker that calls
`codex exec`. In tests, pass a fake worker to avoid network calls.

## Testing

```bash
python -m pytest tests/pipelines/test_folder_audit.py -v
```
