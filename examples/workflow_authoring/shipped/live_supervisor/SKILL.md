# live-supervisor

V1 Python-shaped authoring scaffold for the shipped live-supervisor pipeline.

## Topology

- `classify`
- `diagnose`
- `repair_decision`
- `recheck_emit`

## Usage

```bash
arnold workflow check examples/workflow_authoring/shipped/live_supervisor/workflow.py
arnold workflow graph examples/workflow_authoring/shipped/live_supervisor/workflow.py --format mermaid
```
