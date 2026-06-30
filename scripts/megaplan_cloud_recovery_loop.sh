#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${MEGAPLAN_CLOUD_WORKSPACE:-/workspace/vibecomfy-readable-ready-templates}"
CHAIN_SESSION="${MEGAPLAN_CHAIN_SESSION:-megaplan-chain}"
ARNOLD_ENGINE_DIR="${ARNOLD_ENGINE_DIR:-/workspace/arnold}"
SPEC="${1:-$WORKSPACE/docs/megaplan_chains/readable_ready_templates/chain.yaml}"
BRANCH="${2:-main}"
INTERVAL_SECONDS="${RECOVERY_INTERVAL_SECONDS:-3600}"
LOG="${RECOVERY_LOG:-$WORKSPACE/.megaplan/cloud-recovery-loop.log}"
CHAIN_LOG="${CHAIN_LOG:-$WORKSPACE/.megaplan/cloud-chain.log}"
MODEL="${RECOVERY_CODEX_MODEL:-gpt-5.5}"
MAX_REPAIR_SECONDS="${RECOVERY_MAX_REPAIR_SECONDS:-3300}"

cd "$WORKSPACE"
mkdir -p "$(dirname "$LOG")" .megaplan/manual-backups .megaplan/recovery-prompts

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

chain_field() {
  local expr="$1"
  chain_status_json | python -c "import json,sys; data=json.load(sys.stdin); print($expr)"
}

completed_count() {
  chain_field 'len(data["chain_state"].get("completed") or [])'
}

current_plan_name() {
  chain_field 'data["chain_state"].get("current_plan_name") or ""'
}

current_label() {
  chain_field '(data["summary"].get("current_milestone") or {}).get("label") or ""'
}

current_index() {
  chain_field '(data["summary"].get("current_milestone") or {}).get("index")'
}

last_state() {
  chain_field 'data["chain_state"].get("last_state") or ""'
}

chain_state_file() {
  find "$(dirname "$SPEC")/.megaplan/plans/.chains" -type f -name 'chain-*.json' | head -1
}

backup_dirty_diff() {
  local label="$1"
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  if [[ -n "$(git status --porcelain)" ]]; then
    git diff --binary > ".megaplan/manual-backups/${label}-${ts}.diff"
    log "backed up dirty diff to .megaplan/manual-backups/${label}-${ts}.diff"
  fi
}

commit_and_push_if_dirty() {
  local message="$1"
  if [[ -z "$(git status --porcelain)" ]]; then
    return 0
  fi
  git add -A
  git commit -m "$message" || {
    log "commit failed for message: $message"
    return 1
  }
  git push origin "$BRANCH"
}

ensure_clean_latest_branch() {
  backup_dirty_diff "pre-recovery-dirty"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git reset --hard "origin/$BRANCH"
  git clean -fd .
}

ensure_chain_running() {
  if tmux has-session -t "$CHAIN_SESSION" 2>/dev/null; then
    return 0
  fi
  ./scripts/patch_shannon_unattended_root.sh >> "$LOG" 2>&1 || {
    log "failed to patch Shannon for unattended root execution"
    return 1
  }
  log "$CHAIN_SESSION tmux session is not running; starting chain"
  tmux new-session -d -s "$CHAIN_SESSION" -c "$WORKSPACE" \
    "cd '$WORKSPACE' && PYTHONSAFEPATH=1 PYTHONPATH='$ARNOLD_ENGINE_DIR':\${PYTHONPATH:-} MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start --spec '$SPEC' --project-dir '$WORKSPACE' --no-push >> '$CHAIN_LOG' 2>&1"
}

mark_current_milestone_done() {
  local label="$1"
  local index="$2"
  local plan="$3"
  local sha="$4"
  local state_file
  state_file="$(chain_state_file)"
  if [[ -z "$state_file" ]]; then
    log "cannot mark milestone done: chain state file not found"
    return 1
  fi
  python - "$state_file" "$label" "$index" "$plan" "$sha" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
label = sys.argv[2]
index = int(sys.argv[3])
plan = sys.argv[4]
sha = sys.argv[5]
data = json.loads(path.read_text())
completed = data.setdefault("completed", [])
if not any(item.get("label") == label for item in completed):
    completed.append({
        "label": label,
        "plan": f"operator-recovery-{sha}",
        "status": "done",
        "pr_number": None,
        "pr_state": None,
    })
data["current_milestone_index"] = index + 1
data["current_plan_name"] = None
data["last_state"] = "done"
data["pr_number"] = None
data["pr_state"] = None
path.write_text(json.dumps(data, indent=2) + "\n")
PY
}

reset_current_milestone_for_retry() {
  local label="$1"
  local index="$2"
  local plan="$3"
  local state_file
  state_file="$(chain_state_file)"
  if [[ -z "$state_file" ]]; then
    log "cannot reset milestone for retry: chain state file not found"
    return 1
  fi
  python - "$state_file" "$label" "$index" "$plan" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
_label = sys.argv[2]
index = int(sys.argv[3])
_plan = sys.argv[4]
data = json.loads(path.read_text())
data["current_milestone_index"] = index
data["current_plan_name"] = None
data["last_state"] = None
data["pr_number"] = None
data["pr_state"] = None
path.write_text(json.dumps(data, indent=2) + "\n")
PY
}

write_recovery_prompt() {
  local prompt_path="$1"
  local label="$2"
  local plan="$3"
  cat > "$prompt_path" <<PROMPT
You are running unattended on the VibeComfy cloud worker to keep a megaplan chain moving end to end.

Repository: $WORKSPACE
Branch: $BRANCH
Current milestone: $label
Current plan: $plan
Chain spec: $SPEC

Goal: repair the current blocked/stopped milestone so the chain can continue.

Rules:
- Work only on the current shared branch: $BRANCH.
- Do not create or push other branches.
- Do not revert other agents' committed work.
- Treat dirty work as milestone output; inspect it before changing it.
- Back up any dirty diff before destructive cleanup.
- Read the current plan artifacts in .megaplan/plans/$plan, especially final.md, review.json, faults.json, phase_result.json, execution_audit.json, and execution.json.
- Fix the substantive blocker, not only the symptom.
- Run focused tests that prove the blocker is fixed. Run broader tests if the touched code is shared.
- It is acceptable to note unrelated existing branch-level test failures, but do not chase unrelated failures indefinitely.
- Commit and push a clear recovery commit to origin/$BRANCH when repaired.
- If the milestone is genuinely repaired, update the chain state so this milestone is completed and the next milestone can start.
- Restart or leave the $CHAIN_SESSION tmux session running so progress continues.
- If the failure is an infrastructure/auth/process failure rather than a code-quality failure, fix the runner environment, reset only the failed current plan/milestone state, and restart the chain.
- If a product/architecture decision is truly ambiguous, stop and write a clear blocker summary to .megaplan/recovery-prompts/latest-blocker.md.

Useful status commands:
- python -P -m arnold_pipelines.megaplan chain status --spec "$SPEC"
- tail -n 160 "$CHAIN_LOG"
- git status --short
- PYENV_VERSION=3.11.11 python -m pytest <focused tests> -q

Do the repair now. Keep the chain moving.
PROMPT
}

run_recovery_agent() {
  local label="$1"
  local plan="$2"
  local prompt_path=".megaplan/recovery-prompts/recover-${label}-$(date +%Y%m%d-%H%M%S).md"
  write_recovery_prompt "$prompt_path" "$label" "$plan"
  ln -sf "$(basename "$prompt_path")" .megaplan/recovery-prompts/latest.md
  log "starting Codex recovery agent for label=$label plan=$plan prompt=$prompt_path"
  if command -v timeout >/dev/null 2>&1; then
    timeout "$MAX_REPAIR_SECONDS" codex exec --dangerously-bypass-approvals-and-sandbox -m "$MODEL" -C "$WORKSPACE" - < "$prompt_path" \
      >> .megaplan/recovery-prompts/recovery-agent.log 2>&1 || return $?
  else
    codex exec --dangerously-bypass-approvals-and-sandbox -m "$MODEL" -C "$WORKSPACE" - < "$prompt_path" \
      >> .megaplan/recovery-prompts/recovery-agent.log 2>&1 || return $?
  fi
}

recover_if_needed() {
  local state label index plan before after
  state="$(last_state || true)"
  label="$(current_label || true)"
  index="$(current_index || echo -1)"
  plan="$(current_plan_name || true)"

  if [[ "$state" != "blocked" && "$state" != "worker_blocked" && "$state" != "failed" ]]; then
    return 0
  fi
  if [[ -z "$label" || -z "$plan" || "$index" == "None" ]]; then
    log "recoverable terminal state detected but current label/plan/index missing; leaving for inspection"
    return 1
  fi

  log "recovery needed: state=$state label=$label plan=$plan index=$index"
  ensure_clean_latest_branch
  before="$(git rev-parse --short HEAD)"
  run_recovery_agent "$label" "$plan" || log "recovery agent exited non-zero for $label"
  commit_and_push_if_dirty "megaplan: recover ${label}" || true
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
  after="$(git rev-parse --short HEAD)"

  if [[ "$after" != "$before" ]]; then
    state="$(last_state || true)"
    plan_after="$(current_plan_name || true)"
    if [[ "$plan_after" == "$plan" && ( "$state" == "blocked" || "$state" == "worker_blocked" || "$state" == "failed" ) ]]; then
      log "branch advanced during recovery: $before -> $after; resetting failed $label plan for retry"
      reset_current_milestone_for_retry "$label" "$index" "$plan" || true
    else
      log "branch advanced during recovery: $before -> $after; chain state no longer points at failed plan"
    fi
  else
    log "branch did not advance during recovery for $label; not marking complete"
  fi
  tmux kill-session -t "$CHAIN_SESSION" 2>/dev/null || true
  ensure_chain_running
}

log "recovery loop starting for spec=$SPEC branch=$BRANCH interval=${INTERVAL_SECONDS}s"

while true; do
  ensure_chain_running || true
  recover_if_needed || true
  log "status: completed_count=$(completed_count || echo unknown) current_plan=$(current_plan_name || echo none) last_state=$(last_state || echo unknown)"
  sleep "$INTERVAL_SECONDS"
done
