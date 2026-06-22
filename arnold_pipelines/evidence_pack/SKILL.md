# Evidence-Pack Verifier Pipeline

Model-less verification of persisted evidence-pack JSON artifacts.

## Topology

```
ingest -> content_validators (fanout) -> reduce -> human_review -> emit_attestation
```

## Usage

```python
from arnold_pipelines.evidence_pack import build_pipeline
from arnold.workflow import compile_pipeline

manifest = compile_pipeline(build_pipeline())
```
