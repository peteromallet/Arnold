# M5A Six-Review Regression Fixture

Synthetic artifacts mirroring seven historical M5 completion-authority failure
modes. Each sub-directory contains the minimal evidence files needed to trigger a
specific predicate failure in the atomic/enforce acceptance boundary. The
fixtures are designed to be consumed by provider ordering tests
(`tests/arnold_pipelines/megaplan/test_acceptance_transaction.py` and
`tests/orchestration/test_completion_contract_suite_selection.py`).

## Directory Map

| Directory | Historical Failure | Predicate(s) Exercised |
|-----------|-------------------|----------------------|
| `01_rejected_receipts/` | M5 review-1: receipt.json was rejected by the AcceptanceReceiptProvider because the snapshot hash didn't match or the receipt identity fields were inconsistent. | `acceptance_receipt` — stale/missing receipt |
| `02_divergence/` | M5 review-2: declared artifact hashes in execution batch records diverged from on-disk file content; batch file claims mismatched disk existence. | `divergence` — declared-vs-actual hash mismatch |
| `03_suite_collection_failure/` | M5 review-3: suite runner collected 312 generated selectors but only 21 lifecycle files existed on disk; collection errors caused an `unsatisfied` green-suite verdict. | `green_suite` — collection errors |
| `04_stale_metadata/` | M5 review-4: manifest metadata was stale relative to current chain state; batch ordering was non-sequential and content addresses didn't match the committed snapshot. | `manifest_freshness` — stale/out_of_order manifest |
| `05_premature_retired/` | M5 review-5: a `.retired` marker was written before predecessor evidence (receipt, plan-done marker) existed — premature retirement. | `retirement_order` — premature marker |
| `06_force_proceeded_review/` | M5 review-6: review.json recorded `force_proceed: true` at the rework cap with unresolved issues; review disposition was unsatisfied. | `review_disposition` — force-proceeded |

## Artifact Shapes

Each sub-directory is a self-contained `plan_dir` root. A test can point a
`CompletionContext(plan_dir=<sub_dir>, ...)` at it and run the corresponding
provider.

### Shared Context (implicit)

All six sub-directories assume:
- `project_dir` = the parent of `plan_dir` (standard Megaplan layout)
- `subject.kind` = `"plan"`, `subject.name` = `"m5a-regression-<N>"`
- `state` includes `config.project_dir` pointing at the project root
- `completion_contract_mode` = `"atomic"` / `"enforce"` (fail-closed)

### Artifact Inventory

```
01_rejected_receipts/
  receipt.json              — invalid receipt (hash mismatch)
  execution_batch_1.json    — batch claiming completion with receipt

02_divergence/
  execution_batch_1.json    — batch with declared hashes that don't match files
  src/app.py                — actual file whose hash diverges from declared

03_suite_collection_failure/
  execution_batch_1.json    — batch with suite collection errors
  finalize.json             — finalize with 312 collected selectors, 21 lifecycle
  suite_run_log.jsonl       — suite run log showing collection errors

04_stale_metadata/
  execution_batch_1.json    — batch with non-sequential ordering
  finalize.json             — stale manifest (outdated base_ref)
  plan.md                   — stale baseline metadata

05_premature_retired/
  .retired                  — retirement marker (timestamp before plan done)
  execution_batch_1.json    — batch that didn't complete predecessor evidence

06_force_proceeded_review/
  review.json               — review with force_proceed=true, unresolved issues
  execution_batch_1.json    — batch claiming completion after force-proceed
```

## Usage

```python
from pathlib import Path
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    CompletionContext,
    CompletionSubject,
    AcceptanceReceiptProvider,
    DivergenceProvider,
    GreenSuiteProvider,
    ManifestFreshnessProvider,
    RetirementOrderProvider,
    ReviewDispositionProvider,
)

FIXTURE = Path("tests/fixtures/m5a_six_review_regression")

def test_rejected_receipt():
    ctx = CompletionContext(
        plan_dir=FIXTURE / "01_rejected_receipts",
        project_dir=FIXTURE,
        state={"config": {"project_dir": str(FIXTURE)}},
        subject=CompletionSubject(kind="plan", name="m5a-regression-01", to_state="done"),
    )
    evidence = AcceptanceReceiptProvider().collect(ctx)
    assert evidence.status.name in ("unsatisfied", "unknown")
```

## Non-Goals

- These fixtures do NOT represent real M5 artifacts. They are synthetic
  minimal reproductions of the defect *shapes*.
- Fixtures are not runnable chains — no ChainState, chain spec, or journal
  exists. Tests construct minimal `CompletionContext` objects.
- Real M5 artifacts are optional and non-blocking (per plan).
