# hello-world

A minimal Python-shaped Arnold workflow that greets and responds.

## Purpose

Demonstrate a shipped, V1-grammar workflow that is authored as `workflow.py`
with typed component imports.

## Inputs

- `name` (str): who to greet.

## Outputs

- `respond` produces a greeting artifact.

## Capabilities

- `examples.workflow_authoring.hello.components:greet`
- `examples.workflow_authoring.hello.components:respond`

## Usage

```bash
arnold workflow check examples/workflow_authoring/hello/workflow.py
arnold workflow compile examples/workflow_authoring/hello/workflow.py --out manifest.json
arnold workflow explain examples/workflow_authoring/hello/workflow.py
arnold workflow graph examples/workflow_authoring/hello/workflow.py --format mermaid
```
