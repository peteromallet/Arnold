# Megaplan Cloud Check-ins

This runbook is for the video-editor developer-platform chain running in the Railway Megaplan worker.

## Local Poller

The local helper is:

```bash
/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/check-cloud-status.sh
```

The two-hour watcher runs as a local background process and writes to:

```bash
/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/cloud-checkins.log
```

Check it locally:

```bash
cat /Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/cloud-checkins.pid
ps -p "$(cat /Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/cloud-checkins.pid)"
tail -200 /Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/cloud-checkins.log
```

Restart it:

```bash
cd /Users/peteromalley/Documents/reigh-workspace/reigh-app
if [ -f .megaplan/cloud-checkins.pid ]; then
  kill "$(cat .megaplan/cloud-checkins.pid)" 2>/dev/null || true
fi
nohup sh -c 'while true; do { echo; echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) ====="; ./.megaplan/check-cloud-status.sh || echo "check failed rc=$?"; } >> .megaplan/cloud-checkins.log 2>&1; sleep 7200; done' >/dev/null 2>&1 &
echo $! > .megaplan/cloud-checkins.pid
```

Run a one-off check:

```bash
cd /Users/peteromalley/Documents/reigh-workspace/reigh-app
./.megaplan/check-cloud-status.sh
```

## Cloud Access

Use the canonical local Megaplan checkout, not the old launcher clone:

```bash
cd /Users/peteromalley/Documents/reigh-workspace/reigh-app
PYENV_VERSION=3.11.11 PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  python -m megaplan cloud exec 'cd /workspace/reigh-app; pwd; git status --short --branch' \
  --cloud-yaml .megaplan/video-editor-cloud.yaml
```

Attach directly to the running Railway shell through Megaplan:

```bash
PYENV_VERSION=3.11.11 PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  python -m megaplan cloud attach --cloud-yaml .megaplan/video-editor-cloud.yaml
```

Inside the cloud machine, the project is:

```bash
cd /workspace/reigh-app
```

The active chain tmux session is:

```bash
tmux ls
tmux attach -t megaplan-chain
```

Detach from tmux with `Ctrl-b` then `d`.

## What To Check

Chain progress:

```bash
cd /workspace/reigh-app
python -m megaplan chain status --spec chain.yaml
```

Current plan status:

```bash
PLAN="$(python - <<'PY'
import json
from pathlib import Path
from megaplan.chain import _legacy_state_path_for, _state_path_for

spec = Path("chain.yaml")
for path in (_state_path_for(spec), _legacy_state_path_for(spec)):
    try:
        with path.open() as f:
            print(json.load(f).get("current_plan_name") or "")
            break
    except FileNotFoundError:
        continue
PY
)"
python -m megaplan status --plan "$PLAN"
python -m megaplan progress --plan "$PLAN"
```

Liveness:

```bash
ps -ef | grep "megaplan chain\|codex exec" | grep -v grep || true
tmux ls
```

Recent chain log:

```bash
tail -200 .megaplan/cloud-chain.log
```

Latest plan artifacts:

```bash
ls -lt ".megaplan/plans/$PLAN" | head -40
```

Git state and pushed milestone branches:

```bash
git status --short --branch
git log --oneline --decorate -8
git ls-remote origin "refs/heads/megaplan/video-editor-dx-sprint-*"
```

## Healthy Signals

- `megaplan chain status` shows one milestone `in_progress`.
- `megaplan status --plan "$PLAN"` has `health: healthy` when an active step is running.
- The active step moves through `plan`, `critique`, `gate`, `revise`, `finalize`, `execute`, and `review`.
- During execution, `megaplan progress --plan "$PLAN"` shows task and batch counters increasing.
- `ps` shows either `python -m megaplan chain start` alone between phases or both the chain process and a live `codex exec` process during agent work.

## Bad Signals

- Chain status has `last_state: stalled` and no live `codex exec` process.
- Plan status says `health: stale` and `lock_held: false`.
- `.megaplan/cloud-chain.log` shows repeated Python tracebacks or the same phase exiting non-zero.
- The same artifact timestamps do not change across multiple check-ins while an active step claims to be running.

## Current Cloud Friction Found

- The worker originally continued after git refresh failures; Megaplan now aborts refresh failures.
- Critique flag normalization crashed when agent evidence was structured as a list; Megaplan now coerces structured flag text.
- The Railway image does not have `gh`; Megaplan now skips PR creation when `gh` is unavailable and continues with branch commits/pushes.
- Runtime/schema files can dirty the app repo. Long term, Megaplan runtime state should live outside tracked app paths or under ignored runtime directories.
