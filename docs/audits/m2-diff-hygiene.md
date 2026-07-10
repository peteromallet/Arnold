# M2 Diff Hygiene

Date: 2026-05-24

This artifact classifies the dirty worktree seen during M2 review. The checkout
is an isolated epic worktree, not a per-milestone reset, so `git status` includes
chain setup and completed M1 work in addition to M2.

## Scope Split

### Chain setup baseline

These files were copied into the clean worktree before M1 so the chain could run.
They are implementation context for the epic, not generated output from M2:

- `docs/megaplan_chains/pristine_cleanup/README.md`
- `docs/megaplan_chains/pristine_cleanup/START_HERE.md`
- `docs/megaplan_chains/pristine_cleanup/chain.yaml`
- `docs/megaplan_chains/pristine_cleanup/audit/*.md`
- `docs/megaplan_chains/pristine_cleanup/ideas/*.md`

The only M2-relevant doc-path fact is negative: no production docs outside the
chain scaffold were changed.

### Completed M1 baseline

These paths were produced by M1 and are part of the already completed chain
baseline:

- `docs/audits/m1-safety-gate.md`
- `docs/megaplan_chains/pristine_cleanup/artifacts/m1-duplication-inventory.md`
- `tests/parity/test_p1_typed_handle_parity.py`
- `tests/parity/fixtures/flux2_klein_4b_image_edit_distilled_typed.py`
- `tests/parity/fixtures/flux2_klein_9b_gguf_t2i_typed.py`
- `tests/parity/fixtures/ltx2_3_i2v_typed.py`
- `tests/parity/fixtures/ltx2_3_t2v_typed.py`
- `tests/parity/fixtures/qwen_image_edit_typed.py`
- `tests/parity/fixtures/wan_i2v_typed.py`
- `tests/parity/fixtures/wan_t2v_typed.py`
- `tests/test_model_assets.py`
- `tests/test_testing_api.py`
- `vibecomfy/testing/__init__.py`
- `vibecomfy/testing/_pytest_plugin.py`
- `vibecomfy/testing/fixtures.py`

M2 did not generate or regenerate the parity fixtures. M2 consumed this baseline
while migrating duplicated helpers.

### M2 helper migration

These paths are the M2 shared-foundation change set:

- `docs/audits/m2-symbol-map.md`
- `docs/audits/m2-diff-hygiene.md`
- `scripts/__init__.py`
- `tests/conftest.py`
- `tests/test_foundation_utils.py`
- `tests/test_nodes_install.py`
- `tests/test_ready_templates.py`
- `vibecomfy/porting/parity.py`
- `tools/format_as_python.py`
- `vibecomfy/_git_utils.py`
- `vibecomfy/_graph_utils.py`
- `vibecomfy/analysis/graph.py`
- `vibecomfy/commands/doctor.py`
- `vibecomfy/commands/nodes.py`
- `vibecomfy/ingest/normalize.py`
- `vibecomfy/model_assets.py`
- `vibecomfy/node_packs_install.py`
- `vibecomfy/schema/validate.py`

`scripts/__init__.py` and `tests/conftest.py` are test-environment hygiene:
they make this checkout's namespace-style `scripts/` directory win over an
ambient external `/Users/peteromalley/Documents/agentkit/scripts` package during
pytest collection. They are not generated outputs.

## Generated-Output Negative Checks

The M2 success criterion is that the helper migration does not churn generated
or unrelated runtime/template assets. The relevant checks are:

```bash
git diff --name-only -- ready_templates tests/snapshots tests/fixtures ready_templates/sources
git ls-files --others --exclude-standard ready_templates tests/snapshots tests/fixtures ready_templates/sources
```

Both should produce no paths for M2. The parity fixtures under
`tests/parity/fixtures/` are intentionally excluded from this generated-output
negative check because they are M1 baseline test fixtures, not M2 outputs.

The expanded audit check for review visibility is:

```bash
git diff --name-only -- ready_templates tests/snapshots tests/fixtures tests/parity ready_templates/sources docs scripts tests/test_testing_api.py vibecomfy/testing
git ls-files --others --exclude-standard ready_templates tests/snapshots tests/fixtures tests/parity/fixtures ready_templates/sources docs scripts tests/test_testing_api.py vibecomfy/testing
```

Those commands are expected to show chain setup and M1 baseline paths in this
epic worktree. They are not evidence that M2 changed generated ready templates,
snapshots, workflow corpus files, or runtime assets.
