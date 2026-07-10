# Pristine Agent Architecture Follow-Up

This is a follow-up chain, not a replay of the old
`pristine-agent-architecture` chain. Current `origin/main` already contains
valuable M1/M3-M7 work and the M7 follow-up. The job now is to preserve and
harden that work while staying out of the messaging-boundary rerun's way.

## Base Decision

Use `origin/main` at or after `30e7990d` as the base. Do not use the current
dirty `epic/pristine-agent-architecture/m7-guardrails-artifact-hygiene`
checkout as a base. That dirty tree deletes current-main artifacts and tests
that should be preserved:

- `docs/architecture/ARTIFACTS.md`
- `docs/architecture/agent_panel.md`
- `docs/architecture/compatibility-ledger.md`
- `tests/test_pristine_architecture_guardrails.py`
- `vibecomfy/comfy_nodes/agent/OWNERSHIP.md`
- `vibecomfy/comfy_nodes/web/frontend_ownership_map.md`

## Run Setup

Use a fresh worktree and branch namespace:

```bash
git fetch origin
git worktree add /Users/peteromalley/Documents/.megaplan-worktrees/pristine-agent-architecture-followup origin/main
cd /Users/peteromalley/Documents/.megaplan-worktrees/pristine-agent-architecture-followup
git switch -c epic/pristine-agent-architecture-followup
```

Drive with the verified Arnold Megaplan launcher. In the current VibeComfy
environment, put the editable Arnold checkout first on `PYTHONPATH`; otherwise
the venv can resolve an older installed `arnold` package that lacks
`arnold.workflow`.

```bash
export PYTHONPATH=/Users/peteromalley/Documents/megaplan${PYTHONPATH:+:$PYTHONPATH}
python -m arnold_pipelines.megaplan config show
python -m arnold_pipelines.megaplan chain start --spec .megaplan/briefs/pristine-agent-architecture-followup/chain.yaml
```

If this worktree does not have the right Python environment:

```bash
PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python -m arnold_pipelines.megaplan chain start --project-dir "$PWD" --spec .megaplan/briefs/pristine-agent-architecture-followup/chain.yaml
```

## Parallel Ownership

This follow-up owns:

- backend contract/session/audit guardrails,
- non-message frontend ownership such as status poller, composer, and candidate
  action selectors,
- architecture docs, artifact manifest, ownership maps, compatibility ledger,
- root/artifact hygiene checks.

The messaging-boundary rerun owns transcript/detail/event safety and normal
render raw-data exclusion.

If both touch `vibecomfy_roundtrip.js`, this follow-up may touch only imports,
orchestration wiring, status/composer/candidate ownership, and compatibility
allowlists. It must not change transcript/detail semantics except to call
already-existing safe selectors.

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

Codex must resolve in the exact execution environment. If missing, block the
run as infrastructure failure.

## Completion Guard Expectations

Every implementation milestone must finish with:

- plan state `done`,
- authoritative execution evidence with completed task ids,
- non-empty semantic diff from milestone base,
- required validation passing,
- no deletion of current-main architecture artifacts without explicit replacement.

Intentional no-op audit-only milestones require a typed no-op waiver matching
plan, milestone label, and base SHA.
