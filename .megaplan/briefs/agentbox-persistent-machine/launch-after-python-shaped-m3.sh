#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SPEC="$ROOT/.megaplan/briefs/agentbox-persistent-machine/chain.yaml"
BASE_BRANCH="python-shaped-workflow-authoring-cleanup"
M3_PR="98"
REPO="peteromallet/Arnold"

cd "$ROOT"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh is required so this launch can verify PR #$M3_PR before starting AgentBox." >&2
  exit 2
fi

pr_json="$(gh pr view "$M3_PR" --repo "$REPO" --json state,isDraft,baseRefName,mergeCommit,url)"

state="$(python -c 'import json,sys; print(json.load(sys.stdin)["state"])' <<<"$pr_json")"
is_draft="$(python -c 'import json,sys; print(str(json.load(sys.stdin)["isDraft"]).lower())' <<<"$pr_json")"
base_ref="$(python -c 'import json,sys; print(json.load(sys.stdin)["baseRefName"])' <<<"$pr_json")"
merge_sha="$(python -c 'import json,sys; mc=json.load(sys.stdin).get("mergeCommit") or {}; print(mc.get("oid") or "")' <<<"$pr_json")"
url="$(python -c 'import json,sys; print(json.load(sys.stdin)["url"])' <<<"$pr_json")"

if [[ "$state" != "MERGED" || "$is_draft" != "false" ]]; then
  echo "Refusing to launch AgentBox: python-shaped M3 PR is not merged and non-draft yet." >&2
  echo "PR: $url" >&2
  echo "state=$state isDraft=$is_draft" >&2
  exit 1
fi

if [[ "$base_ref" != "$BASE_BRANCH" ]]; then
  echo "Refusing to launch AgentBox: PR #$M3_PR base is $base_ref, expected $BASE_BRANCH." >&2
  exit 1
fi

if [[ -z "$merge_sha" ]]; then
  echo "Refusing to launch AgentBox: PR #$M3_PR is merged but GitHub did not return a merge commit SHA." >&2
  exit 1
fi

git fetch origin "$BASE_BRANCH" --quiet

if ! git merge-base --is-ancestor "$merge_sha" "origin/$BASE_BRANCH"; then
  echo "Refusing to launch AgentBox: origin/$BASE_BRANCH does not contain M3 merge commit $merge_sha." >&2
  exit 1
fi

echo "Launching AgentBox from origin/$BASE_BRANCH after python-shaped M3 merge $merge_sha"
python -m arnold_pipelines.megaplan chain start --spec "$SPEC"
