# B10 — Staging, replay, fault injection, green runs

## Environment reality

This box is a container, not the agentbox:
- `journalctl`/`systemd` unavailable (no agentbox-discord-resident.service)
- no ssh access to the Hetzner agentbox (`ssh root@localhost` refused)
- no Discord bot token in the environment (`.cloud-hot-env` carries
  DISCORD_BOT_TOKEN but no staging channel is reachable from here)

The live portions of B10 (deploy the migrated resident to the agentbox,
exercise Discord turns, restart/concurrency/cancellation recovery, three
green live phase runs, one green resident Discord run) therefore cannot be
executed from this box.

## What was executed and passed

```bash
python -m pytest -q tests/resident          # 597 passed
python -m pytest -q tests/cloud             # 3194 passed
python -m pytest -q tests/arnold_pipelines/megaplan/watchdog  # passed
python -m pytest -q tests/fixer_replay      # 22 passed, 1 skipped
ps -eo pid,ppid,pgid,args                   # no orphaned bun/codex/omp RPC children
```

## Deterministic substitutes (in-repo)

- RPC transcript replay across restart/retry/concurrent sessions/duplicate
  prompt: covered deterministically by the B2 error matrix
  (tests/workers/test_omp_adapter.py) and the B7 stateless-turn test
  (tests/resident/test_omp_stateless_turn.py) — omp resident turns are
  fresh stateless sessions (`no_session=True`, synthetic `omp-stateless:<turn>`
  identity), so there is no persisted session to replay or duplicate.
- Fault injection (launch/EOF/malformed-frame/timeout/429/5xx/auth/quota/
  context/schema): covered by the omp adapter error matrix and the resident
  provider-runtime tests.
- One-turn success semantics: tests/resident/test_omp_stateless_turn.py
  proves final text, evidence, usage, ledger shape, synthetic identity, and
  absence of a persisted omp session file.

## Staging evidence required at release time

The agentbox deploy, Discord turn, and three-green-run evidence must be
produced on the real agentbox before the release gate can certify B10 fully.
