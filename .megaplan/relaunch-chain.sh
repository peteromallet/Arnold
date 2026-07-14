#!/bin/bash
set -e

SRC=/workspace/arnold-custody-runtime
REPO=https://github.com/peteromallet/Arnold.git
REF=editible-install
RUNTIME_SRC=/workspace/custody-control-plane-20260714/Arnold/.megaplan/runtime/editable-engine
UPSTREAM_URL="$REPO"

if [ -n "$UPSTREAM_URL" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
  case "$UPSTREAM_URL" in
    https://github.com/*) UPSTREAM_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${UPSTREAM_URL#https://github.com/}" ;;
  esac
fi

if [ -n "$REPO" ] && [ ! -e "$SRC/.git" ]; then
  mkdir -p "$(dirname "$SRC")"
  git clone --branch "$REF" "$UPSTREAM_URL" "$SRC"
fi

if [ -e "$SRC/.git" ]; then
  git -C "$SRC" fetch origin "$REF"
  BRANCH="$(git -C "$SRC" branch --show-current)"
  if [ "$BRANCH" != "$REF" ]; then git -C "$SRC" checkout "$REF"; fi
  if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]; then
    if [ -n "$RUNTIME_SRC" ]; then
      echo "[megaplan-refresh] source checkout dirty; using clean runtime mirror at $RUNTIME_SRC"
      rm -rf "$RUNTIME_SRC"
      mkdir -p "$(dirname "$RUNTIME_SRC")"
      git clone --shared --no-checkout "$SRC" "$RUNTIME_SRC"
      MIRROR_REMOTE="$UPSTREAM_URL"
      if [ -z "$MIRROR_REMOTE" ]; then MIRROR_REMOTE="$(git -C "$SRC" remote get-url origin)"; fi
      git -C "$RUNTIME_SRC" remote set-url origin "$MIRROR_REMOTE"
      git -C "$RUNTIME_SRC" fetch origin "+refs/heads/$REF:refs/remotes/origin/$REF"
      git -C "$RUNTIME_SRC" checkout --detach "refs/remotes/origin/$REF"
      export MEGAPLAN_RUNTIME_SRC="$RUNTIME_SRC"
    else
      echo "[megaplan-refresh] refusing editable install refresh: tracked changes in source checkout at $SRC"
      exit 19
    fi
  else
    if ! git -C "$SRC" merge-base --is-ancestor HEAD "origin/$REF"; then
      echo "[megaplan-refresh] source checkout has local commits not contained in origin/$REF; attempting push"
      git -C "$SRC" log --oneline --max-count=5 "origin/$REF..HEAD" || true
      if git -C "$SRC" push origin "$REF"; then
        git -C "$SRC" fetch origin "$REF"
      else
        echo "[megaplan-refresh] refusing editable install refresh: $SRC has unpushed local commits not contained in origin/$REF"
        exit 20
      fi
    fi
    git -C "$SRC" pull --ff-only origin "$REF"
    export MEGAPLAN_RUNTIME_SRC="$SRC"
  fi
  if ! git -C "$MEGAPLAN_RUNTIME_SRC" merge-base --is-ancestor HEAD "origin/$REF"; then
    echo "[megaplan-refresh] refusing editable install refresh: $MEGAPLAN_RUNTIME_SRC has local commits not contained in origin/$REF"
    git -C "$MEGAPLAN_RUNTIME_SRC" log --oneline --max-count=5 "origin/$REF..HEAD" || true
    exit 20
  fi
  pip install -e "$MEGAPLAN_RUNTIME_SRC" >/dev/null 2>&1
  RUNTIME_REVISION="$(git -C "$MEGAPLAN_RUNTIME_SRC" rev-parse HEAD)"
  PYTHONSAFEPATH=1 PYTHONPATH="$MEGAPLAN_RUNTIME_SRC:${PYTHONPATH:-}" python -P -m arnold_pipelines.megaplan.cloud.runtime_provenance --expected-root "$MEGAPLAN_RUNTIME_SRC" --expected-revision "$RUNTIME_REVISION"
fi

export MEGAPLAN_LAUNCH_RUNTIME_SRC="${MEGAPLAN_RUNTIME_SRC:-}"
ENGINE_DIR="${MEGAPLAN_LAUNCH_RUNTIME_SRC:-${MEGAPLAN_RUNTIME_SRC:-}}"
if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR=/workspace/arnold-custody-runtime; fi

if [ -f /workspace/.cloud-hot-env ]; then set -a; . /workspace/.cloud-hot-env; set +a; fi

cd /workspace/custody-control-plane-20260714/Arnold
PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR:${PYTHONPATH:-}" MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start --spec /workspace/custody-control-plane-20260714/Arnold/.megaplan/initiatives/custody-control-plane/chain.yaml --project-dir /workspace/custody-control-plane-20260714/Arnold --no-git-refresh >> /workspace/custody-control-plane-20260714/Arnold/.megaplan/cloud-chain-custody-control-plane-20260714.log 2>&1
