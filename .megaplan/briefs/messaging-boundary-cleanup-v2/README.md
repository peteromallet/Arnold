# Messaging Boundary Cleanup V2

This is the fresh rerun of the messaging-boundary work. It starts from current
`origin/main`, not from the old standalone `messaging-boundary-cleanup` branch,
not from `epic/pristine-agent-architecture/m2-messaging-boundary`, and not from
the dirty M7 checkout.

## Base Decision

Use `origin/main` at or after `30e7990d` as the base. Earlier messaging branches
are historical reference only:

- `messaging-boundary-cleanup` is an old worktree branch and is ancestor-shaped
  relative to current main.
- `epic/pristine-agent-architecture/m2-messaging-boundary` is an init-only branch.
- The old M2 mainline commit did not deliver a durable structural boundary by
  itself; useful surrounding work came through M1 and M3-M7 on main.

## Run Setup

Use a fresh worktree and branch namespace:

```bash
git fetch origin
git worktree add /Users/peteromalley/Documents/.megaplan-worktrees/messaging-boundary-cleanup-v2 origin/main
cd /Users/peteromalley/Documents/.megaplan-worktrees/messaging-boundary-cleanup-v2
git switch -c epic/messaging-boundary-cleanup-v2
```

Drive the chain with the verified Arnold Megaplan launcher, not a removed
`megaplan` console entrypoint. In the current VibeComfy environment, put the
editable Arnold checkout first on `PYTHONPATH`; otherwise the venv can resolve an
older installed `arnold` package that lacks `arnold.workflow`.

```bash
export PYTHONPATH=/Users/peteromalley/Documents/megaplan${PYTHONPATH:+:$PYTHONPATH}
python -m arnold_pipelines.megaplan config show
python -m arnold_pipelines.megaplan chain start --spec .megaplan/briefs/messaging-boundary-cleanup-v2/chain.yaml
```

If this worktree does not have the right Python environment, use the known
editable VibeComfy venv:

```bash
PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python -m arnold_pipelines.megaplan chain start --project-dir "$PWD" --spec .megaplan/briefs/messaging-boundary-cleanup-v2/chain.yaml
```

## Parallel Ownership

This epic owns:

- transcript/detail state compartments,
- `ExecutionEvent` separation from normal UI,
- chat/detail render safety,
- rehydrate projection into safe transcript/detail contracts,
- browser sentinel tests proving internal fields cannot render normally.

The architecture follow-up owns:

- backend/session/audit guardrails outside messaging projection,
- status poller, composer, and candidate-action ownership,
- artifact/document hygiene,
- compatibility-ledger enforcement.

If both touch `vibecomfy_roundtrip.js`, this epic may change only messaging
event intake and transcript/detail wiring. Do not perform broad frontend module
decomposition here.

## Required Preflight

```bash
git fetch origin
git rev-parse origin/main
git status --short --branch
git worktree list --porcelain
PYTHONPATH=/Users/peteromalley/Documents/megaplan python -m arnold_pipelines.megaplan config show
command -v codex
codex --version
node --version
python -m pytest --version
```

Codex must resolve in the exact execution environment. If it does not, block the
run as an infrastructure failure rather than falling back silently.

## Completion Guard Expectations

Every implementation milestone must finish with:

- plan state `done`,
- authoritative execution evidence with completed task ids,
- non-empty semantic diff from milestone base,
- required validation passing,
- compatibility-ledger entry for every retained mirror or raw-data exception.

Intentional no-op milestones require a typed no-op waiver matching plan,
milestone label, and base SHA.
