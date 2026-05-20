# Slot-First M0 Audit 06: Prior Art And Worktree Reconciliation

Generated: 2026-05-20T09:27:35Z

## Scope

This document records the external evidence probes for M0 batch T2. It inventories the visible reigh-app worktrees, sibling repository availability, and the prior slot-first-adjacent planning run. Missing expected paths are recorded as blocked evidence, not inferred success.

## User-Action Gate

T15 resolved U1 as satisfied for the mounted/symlinked evidence set. This batch re-ran the mechanical probes before writing conclusions.

Command:
```bash
sed -n '1,260p' .megaplan/plans/slot-first-redesign-milestone-20260519-2026/user_actions.md
```

Output:
```
# User Actions

## Before Execute

- **U1**: Provide mounted access to sibling repositories and prior-art paths, if full external-audit success is required instead of `BLOCKED` audit exceptions.
  Rationale: The executor can probe available paths, but cannot fabricate missing `/Users/...`, `reigh-worker`, `reigh-worker-orchestrator`, or standalone `Astrid` checkouts.
- **U2**: Provide local/staging database connection details or Supabase CLI environment if M0 should run real pgTAP/schema catalog checks instead of explicit audit-mode skips.
  Rationale: The pgTAP runner and schema drift script can be scaffolded without credentials, but real DB execution requires a reachable database and secrets.

## After Execute

- **U3**: Manually review the Playwright smoke page in a browser after implementation if visual confidence is required beyond the automated page-load assertion.
  Rationale: Automated Playwright covers load/crash behavior; subjective UI rendering judgment remains human-only.

## Resolution (2026-05-20, cloud-run)

- **U1**: SATISFIED. Prior-art plan dir uploaded to /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/. Sibling repos available via symlinks at /Users/peteromalley/Documents/reigh-workspace/{reigh-app, reigh-worker, reigh-worker-orchestrator, Astrid} -> /workspace/<name>.
- **U2**: ACCEPTED-BLOCKED. The cloud worker has no Supabase/psql installation by design. Per the M0 brief, BLOCKED audit exceptions are explicitly permitted in lieu of full external-audit success. The pgTAP/schema-drift script scaffolding may be completed without DB execution; mark live DB checks as audit-mode skips and proceed.
```

## Repository Status At Audit Time

Command:
```bash
git status --short --branch
```

Output:
```
## megaplan/slot-first-m0-preflight...origin/megaplan/slot-first-m0-preflight
 M .megaplan/schemas/finalize.json
 M chain.yaml
 D chain_state.json
 A docs/slot-first-audits/01-grep-ledger.md
?? .megaplan/schemas/feedback.json
```

Unrelated dirty files were not modified by this task. The markdown audit files are force-added with intent because repository ignore rules ignore `*.md`.

## reigh-app Worktree Inventory

Command:
```bash
git -C /Users/peteromalley/Documents/reigh-workspace/reigh-app worktree list --porcelain 2>&1
```

Output:
```
worktree /workspace/reigh-app
HEAD f3f550e4456400cdead7e2616e27afc08bd694ea
branch refs/heads/megaplan/slot-first-m0-preflight
```

Disposition:

| Worktree | Branch | Disposition |
| --- | --- | --- |
| `/workspace/reigh-app` | `megaplan/slot-first-m0-preflight` | Current M0 checkout. It is the only worktree returned by the visible repository metadata. |
| `/Users/peteromalley/Documents/reigh-workspace/reigh-app` | symlink to `/workspace/reigh-app` | Same checkout as current M0 workspace. The branch differs from the historical brief text because this harness exposes the active M0 branch. |
| `/Users/peteromalley/Documents/reigh-workspace/reigh-app-cloud-chain` | unavailable | BLOCKED: external evidence unavailable. The expected PR #14 reference worktree is not mounted in this harness. |
| `/workspace/reigh-app-cloud-chain` | unavailable | BLOCKED: external evidence unavailable. M4 must re-probe and either remove, rebase, or close that branch before cutover if it exists in the operator workspace. |

## Sibling Repository And Prior-Art Probes

Command:
```bash
for p in \
  /Users/peteromalley/Documents/reigh-workspace/reigh-app \
  /Users/peteromalley/Documents/reigh-workspace/reigh-app-cloud-chain \
  /Users/peteromalley/Documents/reigh-workspace/reigh-worker \
  /Users/peteromalley/Documents/reigh-workspace/reigh-worker-orchestrator \
  /Users/peteromalley/Documents/reigh-workspace/Astrid \
  /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913 \
  /workspace/reigh-app \
  /workspace/reigh-app-cloud-chain \
  /workspace/reigh-worker \
  /workspace/reigh-worker-orchestrator \
  /workspace/Astrid; do
  if [ -L "$p" ]; then
    target=$(readlink "$p")
    prefix="SYMLINK $p -> $target"
  else
    prefix="$p"
  fi
  if [ -e "$p" ]; then
    if git -C "$p" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      branch=$(git -C "$p" branch --show-current 2>/dev/null || true)
      top=$(git -C "$p" rev-parse --show-toplevel 2>/dev/null || true)
      head=$(git -C "$p" rev-parse --short HEAD 2>/dev/null || true)
      echo "FOUND $prefix; git=inside branch=${branch:-detached} top=$top head=$head"
    else
      echo "FOUND $prefix; git=not-a-worktree"
    fi
  else
    echo "MISSING $prefix"
  fi
done
```

Output:
```
FOUND SYMLINK /Users/peteromalley/Documents/reigh-workspace/reigh-app -> /workspace/reigh-app; git=inside branch=megaplan/slot-first-m0-preflight top=/workspace/reigh-app head=f3f550e44
MISSING /Users/peteromalley/Documents/reigh-workspace/reigh-app-cloud-chain
FOUND SYMLINK /Users/peteromalley/Documents/reigh-workspace/reigh-worker -> /workspace/reigh-worker; git=inside branch=main top=/workspace/reigh-worker head=3bfe7ac
FOUND SYMLINK /Users/peteromalley/Documents/reigh-workspace/reigh-worker-orchestrator -> /workspace/reigh-worker-orchestrator; git=inside branch=main top=/workspace/reigh-worker-orchestrator head=fcec14f
FOUND SYMLINK /Users/peteromalley/Documents/reigh-workspace/Astrid -> /workspace/Astrid; git=inside branch=main top=/workspace/Astrid head=8741e18
FOUND /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913; git=not-a-worktree
FOUND /workspace/reigh-app; git=inside branch=megaplan/slot-first-m0-preflight top=/workspace/reigh-app head=f3f550e44
MISSING /workspace/reigh-app-cloud-chain
FOUND /workspace/reigh-worker; git=inside branch=main top=/workspace/reigh-worker head=3bfe7ac
FOUND /workspace/reigh-worker-orchestrator; git=inside branch=main top=/workspace/reigh-worker-orchestrator head=fcec14f
FOUND /workspace/Astrid; git=inside branch=main top=/workspace/Astrid head=8741e18
```

External evidence notes:

- `reigh-worker`, `reigh-worker-orchestrator`, and standalone `Astrid` are mounted as git checkouts and can be audited by T13.
- `reigh-app-cloud-chain` is absent from both the `/Users/...` symlink tree and `/workspace`. This task cannot verify its live legacy code paths; M4's zero-ref gate must scan sibling worktrees again before cutover.
- The prior-art run directory is available and contains the expected non-empty files.

## Prior-Art File Probe

Command:
```bash
for f in plan_v1.md plan_v2.md final.md critique_v1.json critique_v2.json gate_signals_v1.json gate_signals_v2.json execution_audit.json; do
  p="/Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/$f"
  if [ -s "$p" ]; then
    printf 'FOUND_NONEMPTY %s bytes=%s\n' "$p" "$(wc -c < "$p")"
  elif [ -e "$p" ]; then
    printf 'FOUND_EMPTY %s\n' "$p"
  else
    printf 'MISSING %s\n' "$p"
  fi
done
```

Output:
```
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/plan_v1.md bytes=8034
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/plan_v2.md bytes=11832
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/final.md bytes=10573
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/critique_v1.json bytes=3272
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/critique_v2.json bytes=1085
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/gate_signals_v1.json bytes=7864
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/gate_signals_v2.json bytes=8849
FOUND_NONEMPTY /Users/peteromalley/Documents/reigh-workspace/.megaplan/plans/redesign-the-segment-position-20260330-1913/execution_audit.json bytes=1299
```

Directory file list:
```
._critique_v1.json
._critique_v2.json
._execution_audit.json
._execution_batch_1.json
._execution_trace.jsonl
._faults.json
._final.md
._finalize.json
._gate.json
._gate_signals_v1.json
._gate_signals_v2.json
._plan_v1.md
._plan_v1.meta.json
._plan_v2.md
._plan_v2.meta.json
._state.json
critique_v1.json
critique_v2.json
execution_audit.json
execution_batch_1.json
execution_trace.jsonl
faults.json
final.md
finalize.json
gate.json
gate_signals_v1.json
gate_signals_v2.json
plan_v1.md
plan_v1.meta.json
plan_v2.md
plan_v2.meta.json
state.json
```

## Prior-Art Reconciliation

The 2026-03-30 prior run tried a narrower segment-position repair centered on `pair_shot_generation_id`: push pair identity through worker fan-out, remove index/`child_order` fallback routing in frontend and edge completion, validate bad positional backfills, and document predecessor invariants. Its strongest surviving lessons are that worker fan-out is the authoritative handoff layer, completion-time index fallback is unsafe, and `_applied_20260225000000_backfill_pair_shot_generation_id.sql` can produce plausible but wrong same-shot links that a cross-shot-only diagnostic misses. The run did not finish cleanly: fallback-removal and test tasks were left pending, and its execution audit reported claimed changes missing from git plus missing sense-check acknowledgments. The current M0-M4 plan supersedes that approach by deleting the legacy generation/pair identity model instead of repairing it in place; M3 must still carry forward the worker/edge contract lesson, while M1/M4 must treat positional backfill data as suspect migration input rather than a reliable source of slot identity.

## BLOCKED: external evidence unavailable

Expected historical path: `/Users/peteromalley/Documents/reigh-workspace/reigh-app-cloud-chain/`

Observed probe result:
```
MISSING /Users/peteromalley/Documents/reigh-workspace/reigh-app-cloud-chain
MISSING /workspace/reigh-app-cloud-chain
```

Impact: this M0 audit cannot inspect the PR #14 `megaplan/vibecomfy-sprint-09-control-rail-travel-matrix` worktree. M4 must not rely on this harness result as proof that the worktree is gone in the operator workspace; it must run the sibling-worktree zero-ref grep gate from the real workspace and record removal, rebase, or branch closure before slot-first cutover.
