Working directory: /Users/peteromalley/Documents/Arnold

You are the implementation agent. Edit files directly.

Goal:
Finish the cloud migration so SSH/Hetzner is the native cloud provider with persistent host storage, and the Railway provider path is removed entirely from active code/docs/tests.

Current state:
The main agent already started partial edits. Treat the current working tree as source of truth. Do not revert unrelated dirty files. Stay scoped to:
- arnold/pipelines/megaplan/cloud/**
- arnold_pipelines/megaplan/cloud/**
- docs/cloud.md
- README.md
- tests/characterization/test_import_surface.py
- new focused cloud tests under tests/cloud or tests/arnold_pipelines/megaplan
- .megaplan/briefs/hetzner-cloud-migration/** if you need notes

Required implementation:
1. SSH persistent storage:
   - `provider` default should be `ssh`; valid active providers should be `ssh` and `local`.
   - `SshSpec` should include `workspace_dir` and `cache_dir`.
   - Default SSH paths should be:
     - `remote_dir: /opt/megaplan-cloud/deploy`
     - `workspace_dir: /opt/megaplan-cloud/workspace`
     - `cache_dir: /opt/megaplan-cloud/cache`
   - `SshProvider.deploy()` must create remote deploy/workspace/cache dirs and run Docker with:
     - `-v <workspace_dir>:/workspace`
     - `-v <cache_dir>/pip:/root/.cache/pip`
     - `-v <cache_dir>/npm:/root/.npm`
   - Keep `remote_dir` separate from workspace so Docker build context does not include cloned repos/node_modules/.venv.

2. Remove Railway active path:
   - `provider: railway` must be invalid.
   - Remove provider registration/imports/classes/templates/docs as active support.
   - Delete or stop referencing `providers/railway.py` and `railway.toml.tmpl` in both package trees.
   - Current docs/templates should not instruct users to use Railway.
   - Historical changelog/archive references can remain.

3. Keep local provider working.

4. Add/repair tests:
   - Test SSH spec defaults and explicit `workspace_dir`/`cache_dir`.
   - Test `provider: railway` fails spec validation.
   - Test SSH deploy command includes persistent mounts and creates dirs. Mock/subclass provider to capture remote commands; do not require real SSH/Docker.
   - Test materialized deploy dir no longer emits `railway.toml`.
   - Update import-surface characterization so Railway is not public surface.

5. Run focused tests if possible:
   - python -m pytest tests/characterization/test_import_surface.py tests/cloud -q
   - plus any new test file you add.
   - python -m compileall arnold/pipelines/megaplan/cloud arnold_pipelines/megaplan/cloud

Return:
- Summary of files changed.
- Tests run and results.
- Any remaining blockers.

Do not make broad unrelated refactors.
