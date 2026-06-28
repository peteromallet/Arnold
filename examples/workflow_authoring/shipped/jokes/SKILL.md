# jokes

V1 Python-shaped authoring scaffold for the shipped jokes pipeline.

## Topology

- `draft`
- `tighten`
- `emit`

## Usage

```bash
arnold workflow check examples/workflow_authoring/shipped/jokes/workflow.py
arnold workflow graph examples/workflow_authoring/shipped/jokes/workflow.py --format mermaid
```
