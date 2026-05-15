#!/usr/bin/env bash
set -euo pipefail

SPEC="${1:-/workspace/app/docs/megaplan_chains/readable_ready_templates/chain.yaml}"
BRANCH="${2:-megaplan/production-parity-templates}"
INTERVAL_SECONDS="${OPERATOR_INTERVAL_SECONDS:-3600}"
EARLY_SECONDS="${OPERATOR_EARLY_SECONDS:-900}"
LOG="${OPERATOR_LOG:-/workspace/app/.megaplan/cloud-operator-loop.log}"

cd /workspace/app
mkdir -p "$(dirname "$LOG")"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"
}

chain_status_json() {
  megaplan chain status --spec "$SPEC" 2>/dev/null | awk '
    BEGIN {json=0}
    /^\{/ {json=1}
    {if (json) print}
  '
}

completed_count() {
  chain_status_json | python -c 'import json,sys; print(len(json.load(sys.stdin)["chain_state"].get("completed") or []))'
}

current_plan_name() {
  chain_status_json | python -c 'import json,sys; print(json.load(sys.stdin)["chain_state"].get("current_plan_name") or "")'
}

commit_and_push_if_dirty() {
  local count="$1"
  if [[ -z "$(git status --porcelain)" ]]; then
    log "no worktree changes to push after completed_count=$count"
    return 0
  fi
  git checkout "$BRANCH"
  git add -A
  git commit -m "megaplan: readable ready templates sprint ${count}" || {
    log "commit failed; leaving worktree for human/operator inspection"
    return 1
  }
  git push origin "$BRANCH"
  log "pushed shared branch $BRANCH after completed_count=$count"
}

ensure_chain_running() {
  if tmux has-session -t megaplan-chain 2>/dev/null; then
    return 0
  fi
  log "megaplan-chain tmux session is not running; restarting chain"
  tmux new-session -d -s megaplan-chain -c /workspace/app \
    "MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec '$SPEC' --no-push >> /workspace/app/.megaplan/cloud-chain.log 2>&1"
}

log "operator loop starting for spec=$SPEC branch=$BRANCH"
sleep "$EARLY_SECONDS"

last_pushed_count="$(completed_count || echo 0)"
commit_and_push_if_dirty "$last_pushed_count" || true

while true; do
  ensure_chain_running || true
  count="$(completed_count || echo "$last_pushed_count")"
  plan="$(current_plan_name || true)"
  log "status: completed_count=$count current_plan=${plan:-none}"
  if [[ "$count" != "$last_pushed_count" ]]; then
    commit_and_push_if_dirty "$count" || true
    last_pushed_count="$count"
  fi
  sleep "$INTERVAL_SECONDS"
done
