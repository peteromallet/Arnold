Working directory: /Users/peteromalley/Documents/Arnold

You are the review/fix agent. Inspect the current working-tree diff for the SSH/Hetzner native cloud migration. You may edit files directly, but only to fix concrete bugs or test/doc mismatches in this migration.

Context:
- A previous DeepSeek implementation wave changed the cloud provider path so active providers are SSH and local.
- Railway support should be removed from active code/docs/tests.
- SSH should be the native Hetzner path with persistent host storage mounted into `/workspace` and cache mounts for pip/npm.
- Focused tests currently pass:
  `python -m pytest tests/characterization/test_import_surface.py tests/cloud -q`
  `python -m compileall -q arnold/pipelines/megaplan/cloud arnold_pipelines/megaplan/cloud`

Review targets:
- `git diff -- arnold/pipelines/megaplan/cloud arnold_pipelines/megaplan/cloud docs/cloud.md README.md tests/cloud tests/characterization/test_import_surface.py arnold/pipelines/megaplan/data arnold_pipelines/megaplan/data arnold_pipelines/megaplan/skills`

Look for:
1. Bugs in SSH deploy command generation, quoting, or mount behavior.
2. Missing spec validation or default behavior for `workspace_dir` and `cache_dir`.
3. Broken imports after deleting Railway provider/spec/template.
4. Stale active Railway docs or skill instructions.
5. Tests that are too weak, brittle, or not exercising `load_spec`.
6. Any accidental broad/unrelated changes in the scoped files.

Do:
- Patch concrete issues directly.
- Run focused tests after patching.

Return:
- Findings fixed.
- Findings left unfixed, if any.
- Tests run.
