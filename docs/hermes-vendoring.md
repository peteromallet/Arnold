# Hermes Vendoring Checks

This repo vendors the Hermes runtime under `megaplan/agent/` with a `sys.path`
shim in `megaplan/agent/__init__.py`. The runtime integration can be validated
from source, but history-preserving vendoring still requires a real unlocked git
checkout because `git subtree` must write under `.git/`.

## Required subtree command

Run this from a checkout where `.git/` is writable:

```bash
git subtree add --prefix=megaplan/agent /Users/peteromalley/Documents/hermes-agent main
git log --oneline -- megaplan/agent/
```

Success means `git log -- megaplan/agent/` shows multiple Hermes commits, not a
single squash commit or an empty history.

## Tree audit

The repo now carries a source-of-truth audit helper for the vendored surface:

```bash
python - <<'PY'
from pathlib import Path
from megaplan.audits.hermes_vendoring import (
    audit_vendored_agent_history,
    audit_vendored_agent_tree,
)

repo_root = Path.cwd()
print(audit_vendored_agent_tree(repo_root))
print(audit_vendored_agent_history(repo_root))
PY
```

`audit_vendored_agent_tree()` checks:

- required runtime entries (`run_agent.py`, `hermes_state.py`, `hermes_cli/`, `model_tools.py`, `pyproject.toml`)
- Job B scope fences that must stay vendored
- dead-weight paths that must stay absent
- root-level `*.json` files under `megaplan/agent/`
- import sites that justify retaining `gateway/`, `cron/`, and `honcho_integration/`

## Fresh-environment Hermes smoke

After `[agent]` extras are installable, verify the vendored runtime in a fresh
environment instead of relying on the current interpreter state:

```bash
python -m venv /tmp/megaplan-agent-smoke
/tmp/megaplan-agent-smoke/bin/pip install -e '.[agent]'
HOME=$(mktemp -d) /tmp/megaplan-agent-smoke/bin/python - <<'PY'
from megaplan.workers.hermes import _import_hermes_runtime

AIAgent, SessionDB = _import_hermes_runtime()
import model_tools

print(AIAgent.__name__, SessionDB.__name__)
print(model_tools.__name__)
PY
```

For an end-to-end CLI run, initialize a scratch plan and execute a Hermes phase
in that same venv once the optional deps are present.
