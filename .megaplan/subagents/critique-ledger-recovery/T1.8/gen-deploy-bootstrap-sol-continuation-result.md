# T1.8 GEN-DEPLOY Sol continuation result

## Candidate

- Commit: `69be00087f0d469b1e551fa8617c257f28783b7a`
- Message: `Implement fenced GEN-DEPLOY release authority`
- Worktree: clean after commit
- Scope: 20 task files; no deployment, SSH, cloud mutation, checklist edit, or
  claim of formal T1.8 completion

## Audit result

The complete staged-plus-unstaged candidate was inspected locally and by an
independent DeepSeek V4 Pro adversarial reviewer. The combined implementation
has no blocking gap for the nine requested concerns: external production
authority/provisioning, immutable owner-store pinning, executor permits and
signed receipts, selector-CAS serialization, fail-closed ambiguity/recovery,
durable and observable writer fencing, byte-bound offline custody, explicit
absence of production transport, and installed-wheel entrypoint/schema parity.

The continuation fixed the reviewer's concrete public-export defect in
`verifier.__all__`, added exact installed-wheel parity checks for all 12 public
schemas, and Ruff-formatted all task Python files before commit.

## Exact verification

- `uv run pytest -q tests/arnold_pipelines/release_authority`
  - `89 passed in 7.69s`
- `uv run --with pip pytest -q tests/installed_wheel/test_release_authority_entrypoint.py`
  - `2 passed in 11.37s`
  - The `--with pip` overlay is required because this worktree's `.venv` has no
    `pip`; an initial combined run had 89 source passes and two fixture setup
    errors for that environmental reason. Its 15 MB pytest temp output and the
    empty debug directory were removed before rerun.
- `uv run pytest -q tests/cloud/test_final_runtime_promotion_runbook.py tests/cloud/test_runtime_attestation.py tests/cloud/test_runtime_cutover.py tests/cloud/test_runtime_provenance.py tests/cloud/test_supervisor_runtime_isolation.py tests/cloud/test_m11_workflow_canary.py tests/m11/test_runtime_receipt.py tests/m11/test_acceptance_receipt.py tests/arnold_pipelines/megaplan/test_custody_canary.py`
  - `143 passed, 2 subtests passed in 80.57s`
- `uv run ruff check arnold_pipelines/release_authority tests/arnold_pipelines/release_authority tests/installed_wheel/test_release_authority_entrypoint.py tests/installed_wheel/conftest.py`
  - `All checks passed!`
- `uv run ruff format --check arnold_pipelines/release_authority tests/arnold_pipelines/release_authority tests/installed_wheel/test_release_authority_entrypoint.py tests/installed_wheel/conftest.py`
  - `17 files already formatted`
- `uv run mypy arnold_pipelines/release_authority`
  - `Success: no issues found in 9 source files`
- `uv lock --check`
  - `Resolved 81 packages`
- `git diff HEAD --check`
  - passed with no output before commit

## Unresolved limitations

- No production transport or adapter is shipped. Production deploy/recovery
  paths intentionally return `production_adapter_missing` until a separately
  bounded venue adapter is injected.
- Owner-installed genesis provisioning and accepted owner/cloud custody receipts
  remain external integration gates by design; this candidate proves only the
  source, hermetic, packaging, and regression contracts.
- The authority assumes filesystem custody plus owner/executor signing keys are
  not compromised. It does not formally prove arbitrary disk/WAL failure modes.
- This commit is an internally reviewable candidate, not formal T1.8 completion.

## Recommendation

**PASS for fresh independent adversarial review.**
