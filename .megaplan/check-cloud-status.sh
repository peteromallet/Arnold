#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/Users/peteromalley/Documents/reigh-workspace/reigh-app}"
MEGAPLAN_DIR="${MEGAPLAN_DIR:-/Users/peteromalley/Documents/megaplan}"
CLOUD_YAML="${CLOUD_YAML:-.megaplan/video-editor-cloud.yaml}"

cd "$PROJECT_DIR"

PYENV_VERSION=3.11.11 PYTHONPATH="$MEGAPLAN_DIR" python -m megaplan cloud exec '
cd /workspace/reigh-app

echo "---time---"
date -Is

echo "---megaplan---"
python - <<'"'"'PY'"'"'
import inspect
from megaplan.flags import normalize_flag_record
from megaplan.chain import _ensure_milestone_pr
print("normalize_flag_record:", "coerce" if "_coerce_flag_text" in inspect.getsource(normalize_flag_record) else "old")
print("gh fallback:", "shutil.which" if "shutil.which" in inspect.getsource(_ensure_milestone_pr) else "old")
PY

echo "---chain---"
python -m megaplan chain status --spec chain.yaml || true

PLAN="$(python - <<'"'"'PY'"'"'
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
else:
    print("")
PY
)"

if [ -n "$PLAN" ]; then
  echo "---plan:$PLAN---"
  python -m megaplan status --plan "$PLAN" || true
  echo "---progress:$PLAN---"
  python -m megaplan progress --plan "$PLAN" || true
  echo "---artifacts:$PLAN---"
  ls -lt ".megaplan/plans/$PLAN" 2>/dev/null | head -30 || true
fi

echo "---processes---"
ps -ef | grep "megaplan chain\|codex exec" | grep -v grep || true

echo "---git---"
git status --short --branch
git log --oneline --decorate -5

echo "---branches---"
git branch --show-current
git ls-remote origin "refs/heads/megaplan/video-editor-dx-sprint-*" | tail -20 || true

echo "---chain-log-tail---"
tail -120 .megaplan/cloud-chain.log 2>/dev/null || true
' --cloud-yaml "$CLOUD_YAML"
