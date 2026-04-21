# Migration From `reigh-megaplan-dev`

This runbook is human-executed. Do not automate the cleanup step or paste `rm -rf` commands into scripts. Copy the commands manually, verify each result, and keep `MIGRATED.md` as the pointer left behind in the retired folder.

## Goal

Move from `~/Documents/reigh-megaplan-dev/` to the built-in `megaplan cloud` workflow, verify parity with a tiny run, then retire the old folder without deleting the migration pointer.

## 1. Match The Existing Reigh Environment

From the main repo, create or update `cloud.yaml` so it matches the provider, repo, secrets, workspace path, and remote runner behavior you are currently using in `~/Documents/reigh-megaplan-dev/`.

Use the built-in runner from this repo:

```bash
cd /Users/peteromalley/Documents/megaplan
./.venv/bin/python -m megaplan cloud build
./.venv/bin/python -m megaplan cloud deploy
```

## 2. Run A Tiny Parity Check

Use a deliberately small idea or chain spec first.

Auto/bootstrap flow:

```bash
./.venv/bin/python -m megaplan cloud bootstrap path/to/tiny-idea.txt
./.venv/bin/python -m megaplan cloud status
./.venv/bin/python -m megaplan cloud logs --no-follow
```

Chain flow:

```bash
./.venv/bin/python -m megaplan cloud chain path/to/tiny-chain.yaml --idea-dir path/to/ideas
./.venv/bin/python -m megaplan cloud status --chain
./.venv/bin/python -m megaplan cloud logs --no-follow
```

Do not proceed to cleanup until the replacement flow is clearly working.

## 3. Write `MIGRATED.md` First

Create the pointer file before any deletion:

```bash
cat > ~/Documents/reigh-megaplan-dev/MIGRATED.md <<'EOF'
This folder has been retired in favor of the built-in megaplan cloud workflow.

Use:
  /Users/peteromalley/Documents/megaplan

See:
  /Users/peteromalley/Documents/megaplan/docs/cloud.md
  /Users/peteromalley/Documents/megaplan/docs/cloud-migration-from-reigh.md
EOF
```

Do not remove anything until that file exists and contains the pointer.

## 4. Clean Up While Preserving The Pointer

Once `MIGRATED.md` exists, remove every sibling except that file:

```bash
find ~/Documents/reigh-megaplan-dev -mindepth 1 ! -name MIGRATED.md -print0 | xargs -0 rm -rf
```

That ordering matters:

1. `MIGRATED.md` is written first.
2. Cleanup excludes `MIGRATED.md` with `! -name MIGRATED.md`.
3. The operator pastes the command manually after verifying the pointer file.

## 5. Final Check

Confirm the folder now contains only the pointer:

```bash
ls -la ~/Documents/reigh-megaplan-dev
```

Expected outcome: `MIGRATED.md` remains, the previous ad hoc files are gone, and future work happens from the built-in `megaplan cloud` flow in the main repo.
