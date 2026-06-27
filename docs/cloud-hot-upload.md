# Cloud Hot Upload

`scripts/cloud_hot_upload.py` updates narrow runtime files on an SSH-backed
Megaplan cloud container without rebuilding the Docker image. It is intended for
operator scripts, wrapper scripts, and emergency live-session env values.

The helper reads SSH connection details from `cloud.yaml` and dry-runs by
default.

```bash
python scripts/cloud_hot_upload.py \
  --cloud-yaml .megaplan-worktrees/workflow-manifest-runtime/cloud.yaml \
  --wrapper arnold-watchdog \
  --wrapper arnold-kimi-goal-operator \
  --verify
```

Add `--apply` to stream the files into the running Docker container and verify
their remote hashes:

```bash
python scripts/cloud_hot_upload.py --apply \
  --cloud-yaml .megaplan-worktrees/workflow-manifest-runtime/cloud.yaml \
  --wrapper arnold-watchdog \
  --wrapper arnold-kimi-goal-operator \
  --verify
```

For token-like values that should be available to sessions restarted through the
helper, export the value locally and upload only the named variable:

```bash
set -a; source ~/.hermes/.env; set +a
python scripts/cloud_hot_upload.py --apply \
  --cloud-yaml .megaplan-worktrees/workflow-manifest-runtime/cloud.yaml \
  --env-name KIMI_API_KEY \
  --restart-session watchdog \
  --verify
```

This writes `/workspace/.cloud-hot-env` inside the container with mode `600`.
It does not alter already-running process environments. Sessions restarted via
`--restart-session` source that file before running their command.

For full Docker environment replacement, pass a local env file outside the repo
and recreate the container from the already-built image:

```bash
python scripts/cloud_hot_upload.py --apply \
  --cloud-yaml .megaplan-worktrees/workflow-manifest-runtime/cloud.yaml \
  --env-file /secure/path/.env \
  --recreate-container \
  --verify
```

Use `megaplan cloud build && megaplan cloud deploy` instead when changing the
Dockerfile, entrypoint boot sequence, installed packages, base image contents,
or anything that must survive container recreation without another hot upload.
