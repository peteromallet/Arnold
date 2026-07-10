#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${MEGAPLAN_CLOUD_WORKSPACE:-/workspace/vibecomfy-readable-ready-templates}"
CHAIN_SESSION="${MEGAPLAN_CHAIN_SESSION:-megaplan-chain}"
CHAIN_LOG="${CHAIN_LOG:-$WORKSPACE/.megaplan/cloud-chain.log}"
ARNOLD_ENGINE_DIR="${ARNOLD_ENGINE_DIR:-/workspace/arnold}"
SPEC="${1:-$WORKSPACE/docs/megaplan_chains/readable_ready_templates/chain.yaml}"
BRANCH="${2:-main}"
INTERVAL_SECONDS="${OPERATOR_INTERVAL_SECONDS:-3600}"
EARLY_SECONDS="${OPERATOR_EARLY_SECONDS:-900}"
LOG="${OPERATOR_LOG:-$WORKSPACE/.megaplan/cloud-operator-loop.log}"

cd "$WORKSPACE"
mkdir -p "$(dirname "$LOG")"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"
}

run_megaplan() {
  (
    cd "$WORKSPACE"
    PYTHONSAFEPATH=1 PYTHONPATH="$ARNOLD_ENGINE_DIR:${PYTHONPATH:-}" \
      python -P -m arnold_pipelines.megaplan "$@"
  )
}

chain_status_json() {
  run_megaplan chain status --spec "$SPEC" 2>/dev/null | awk '
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
  if [[ "$count" == "0" ]]; then
    log "not pushing before first completed milestone"
    return 0
  fi
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
  if tmux has-session -t "$CHAIN_SESSION" 2>/dev/null; then
    return 0
  fi
  ./scripts/patch_shannon_unattended_root.sh >> "$LOG" 2>&1 || {
    log "failed to patch Shannon for unattended root execution"
    return 1
  }
  log "$CHAIN_SESSION tmux session is not running; restarting chain"
  tmux new-session -d -s "$CHAIN_SESSION" -c "$WORKSPACE" \
    "cd '$WORKSPACE' && PYTHONSAFEPATH=1 PYTHONPATH='$ARNOLD_ENGINE_DIR':\${PYTHONPATH:-} MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start --spec '$SPEC' --project-dir '$WORKSPACE' --no-push >> '$CHAIN_LOG' 2>&1"
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
