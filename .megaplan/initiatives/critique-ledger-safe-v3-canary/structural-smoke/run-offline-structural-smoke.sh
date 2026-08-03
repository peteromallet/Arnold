#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <production-image-ref> <clean-repo-root> <receipt-output>" >&2
  exit 64
fi

production_image=$1
repo_root=$(cd "$2" && pwd -P)
receipt_parent=$(cd "$(dirname "$3")" && pwd -P)
receipt_output="$receipt_parent/$(basename "$3")"
evidence_dir="$receipt_output.evidence"
fixture_dir=$(cd "$(dirname "$0")" && pwd -P)

if [[ -e "$receipt_output" || -L "$receipt_output" ]]; then
  echo "refusing to overwrite smoke receipt: $receipt_output" >&2
  exit 66
fi
if [[ -e "$evidence_dir" || -L "$evidence_dir" ]]; then
  echo "refusing to overwrite smoke evidence: $evidence_dir" >&2
  exit 66
fi

mkdir -m 0700 "$evidence_dir"
stdout_log="$evidence_dir/stdout.log"
stderr_log="$evidence_dir/stderr.log"
inspect_output="$evidence_dir/container-inspect.json"
runtime_summary_output="$evidence_dir/container-runtime-summary.json"
install -m 0600 /dev/null "$stdout_log"
install -m 0600 /dev/null "$stderr_log"
printf '%s\n' '{"available":false}' > "$inspect_output"
chmod 0600 "$inspect_output"
printf '%s\n' '{"validated":false}' > "$runtime_summary_output"
chmod 0600 "$runtime_summary_output"

production_image_id=""
derived_image_id=""
container_id=""
container_name="arnold-zero-recovery-offline-smoke-$$"
source_commit=""
source_tree=""
smoke_root=""
workspace_child=""
smoke_status="failed"
smoke_exit_code=1
terminal_line=""

copy_partial_receipts() {
  if [[ -z "$workspace_child" ]]; then
    return
  fi
  local checkout="$workspace_child/Arnold"
  local run_root="$checkout/.megaplan/initiatives/critique-ledger-safe-v3-canary/receipts"
  local plan_root="$checkout/.megaplan/plans/critique-ledger-cl2-planning-canary"
  local path
  if [[ -d "$run_root" ]]; then
    mkdir -m 0700 "$evidence_dir/run-receipts"
    while IFS= read -r -d '' path; do
      install -m 0600 "$path" "$evidence_dir/run-receipts/$(basename "$path")"
    done < <(find "$run_root" -maxdepth 1 -type f -name '*.run-receipt.json' -print0)
    mkdir -m 0700 "$evidence_dir/phase-receipts"
    while IFS= read -r -d '' path; do
      install -m 0600 "$path" "$evidence_dir/phase-receipts/$(basename "$path")"
    done < <(find "$run_root" -maxdepth 1 -type f \
      \( -name '*.phase-receipt.json' -o -name '*.started.json' \
         -o -name 'phase-receipts-manifest.json' \) -print0)
  fi
  if [[ -d "$plan_root" ]]; then
    mkdir -m 0700 "$evidence_dir/privilege-receipts"
    while IFS= read -r -d '' path; do
      install -m 0600 "$path" "$evidence_dir/privilege-receipts/$(basename "$path")"
    done < <(find "$plan_root" -maxdepth 1 -type f \
      -name '.zero-recovery-*-privilege-receipt.json' -print0)
  fi
}

write_receipt() {
  SMOKE_STATUS="$smoke_status" \
  SMOKE_EXIT_CODE="$smoke_exit_code" \
  SMOKE_PRODUCTION_IMAGE_REF="$production_image" \
  SMOKE_PRODUCTION_IMAGE_ID="$production_image_id" \
  SMOKE_DERIVED_IMAGE_ID="$derived_image_id" \
  SMOKE_CONTAINER_ID="$container_id" \
  SMOKE_CONTAINER_NAME="$container_name" \
  SMOKE_SOURCE_COMMIT="$source_commit" \
  SMOKE_SOURCE_TREE="$source_tree" \
  SMOKE_TERMINAL_LINE="$terminal_line" \
  python3 - "$receipt_output" "$evidence_dir" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

receipt_path = Path(sys.argv[1])
evidence_dir = Path(sys.argv[2])

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory(directory: str) -> list[dict[str, str]]:
    root = evidence_dir / directory
    if not root.is_dir():
        return []
    return [
        {"path": str(path.relative_to(evidence_dir)), "sha256": sha256(path)}
        for path in sorted(root.iterdir())
        if path.is_file()
    ]

terminal = None
raw_terminal = os.environ.get("SMOKE_TERMINAL_LINE", "")
if raw_terminal:
    try:
        candidate = json.loads(raw_terminal)
        if isinstance(candidate, dict):
            terminal = candidate
    except json.JSONDecodeError:
        pass

payload = {
    "schema": "arnold.megaplan.zero_recovery_offline_structural_smoke_attempt.v1",
    "status": os.environ["SMOKE_STATUS"],
    "evidence_scope": "offline_structural_only_not_model_provider_proof",
    "exit_code": int(os.environ["SMOKE_EXIT_CODE"]),
    "production_image_ref": os.environ["SMOKE_PRODUCTION_IMAGE_REF"],
    "production_image_id": os.environ.get("SMOKE_PRODUCTION_IMAGE_ID") or None,
    "derived_image_id": os.environ.get("SMOKE_DERIVED_IMAGE_ID") or None,
    "container_id": os.environ.get("SMOKE_CONTAINER_ID") or None,
    "container_name": os.environ["SMOKE_CONTAINER_NAME"],
    "source_commit": os.environ.get("SMOKE_SOURCE_COMMIT") or None,
    "source_tree": os.environ.get("SMOKE_SOURCE_TREE") or None,
    "stdout_sha256": sha256(evidence_dir / "stdout.log"),
    "stderr_sha256": sha256(evidence_dir / "stderr.log"),
    "container_inspect_sha256": sha256(evidence_dir / "container-inspect.json"),
    "container_runtime_summary_sha256": sha256(
        evidence_dir / "container-runtime-summary.json"
    ),
    "container_runtime_summary": json.loads(
        (evidence_dir / "container-runtime-summary.json").read_text(
            encoding="utf-8"
        )
    ),
    "run_receipts": inventory("run-receipts"),
    "phase_receipts": inventory("phase-receipts"),
    "privilege_receipts": inventory("privilege-receipts"),
    "verifier_receipt": terminal,
}
payload["receipt_digest"] = hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
    stream.write("\n")
PY
}

cleanup() {
  local original_rc=$?
  set +e
  if [[ "$smoke_status" != "passed" && "$smoke_exit_code" -eq 1 \
    && "$original_rc" -ne 0 ]]; then
    smoke_exit_code=$original_rc
  fi
  if [[ -n "$container_id" ]]; then
    if docker inspect "$container_id" > "$inspect_output" 2>> "$stderr_log"; then
      if ! python3 "$fixture_dir/validate_container_inspect.py" \
        "$inspect_output" "$container_id" "$container_name" \
        "$derived_image_id" "$workspace_child" \
        > "$runtime_summary_output" 2>> "$stderr_log"; then
        printf '%s\n' '{"validated":false}' > "$runtime_summary_output"
        smoke_status="failed"
        smoke_exit_code=1
      fi
    else
      smoke_status="failed"
      smoke_exit_code=1
    fi
  fi
  copy_partial_receipts
  if ! write_receipt; then
    echo "failed to preserve typed smoke receipt: $receipt_output" >&2
    smoke_exit_code=70
  fi
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1
  fi
  if [[ -n "$smoke_root" && -d "$smoke_root" ]]; then
    find "$smoke_root" -depth -type f -delete 2>/dev/null
    find "$smoke_root" -depth -type l -delete 2>/dev/null
    find "$smoke_root" -depth -type d -exec rmdir {} \; 2>/dev/null
  fi
  if [[ "$smoke_status" == "passed" ]]; then
    echo "$receipt_output"
    exit 0
  fi
  if [[ "$smoke_exit_code" -eq 0 ]]; then
    smoke_exit_code=$original_rc
  fi
  if [[ "$smoke_exit_code" -eq 0 ]]; then
    smoke_exit_code=1
  fi
  exit "$smoke_exit_code"
}
trap cleanup EXIT

if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=all)" ]]; then
  echo "structural smoke requires a clean accepted checkout" >> "$stderr_log"
  smoke_exit_code=65
  exit "$smoke_exit_code"
fi

source_commit=$(git -C "$repo_root" rev-parse HEAD 2>> "$stderr_log")
source_tree=$(git -C "$repo_root" rev-parse 'HEAD^{tree}' 2>> "$stderr_log")
production_image_id=$(docker image inspect --format '{{.Id}}' "$production_image" \
  2>> "$stderr_log")
derived_tag="arnold-zero-recovery-offline-smoke-${source_commit:0:12}"
docker build --pull=false --network none \
  --build-arg "PRODUCTION_IMAGE=$production_image" \
  -t "$derived_tag" "$fixture_dir" >> "$stdout_log" 2>> "$stderr_log"
derived_image_id=$(docker image inspect --format '{{.Id}}' "$derived_tag" \
  2>> "$stderr_log")

smoke_root=$(mktemp -d "${TMPDIR:-/tmp}/arnold-zero-recovery-smoke.XXXXXX")
workspace_child="$smoke_root/workspace-child"
mkdir -m 0700 "$workspace_child"
mkdir -m 0700 "$workspace_child/Arnold"
cp -a "$repo_root/." "$workspace_child/Arnold/"

read -r -d '' inner <<'INNER' || true
set -euo pipefail
chown root:65532 /workspace
chmod 0750 /workspace
chown -R root:root /workspace/Arnold
chmod -R go-w /workspace/Arnold
# The real canary creates /workspace/Arnold with git clone (root-owned 0755).
# The smoke pre-creates that destination as 0700 before cp -a, so normalize
# only its top-level traversal mode to the production clone boundary. Source
# remains immutable to the finite-model UID.
chmod 0755 /workspace/Arnold
install -d -o root -g root -m 0700 /root/.codex
printf '%s\n' '{"auth_mode":"offline_structural_smoke","tokens":null}' > /root/.codex/auth.json
printf '%s\n' 'model = "gpt-5.6-sol"' 'model_reasoning_effort = "high"' > /root/.codex/config.toml
chown root:root /root/.codex/auth.json /root/.codex/config.toml
chmod 0600 /root/.codex/auth.json /root/.codex/config.toml
cd /workspace/Arnold
source_commit=$(git rev-parse HEAD)
source_tree=$(git rev-parse 'HEAD^{tree}')
manifest_b64=$(python3 -c 'import base64,hashlib,json,pathlib; paths=[".megaplan/initiatives/critique-ledger-safe-v3-canary/canary.yaml",".megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml",".megaplan/initiatives/critique-ledger-safe-v3-canary/proof-map.json",".megaplan/initiatives/critique-ledger-safe-v3-canary/traceability.json"]; value={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths}; print(base64.b64encode(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).decode())')
MEGAPLAN_ZERO_RECOVERY_CANARY=1 \
ZERO_RECOVERY_SOURCE_COMMIT="$source_commit" \
ZERO_RECOVERY_SOURCE_TREE="$source_tree" \
ZERO_RECOVERY_MANIFEST_SHA256_B64="$manifest_b64" \
PYTHONPATH=/workspace/Arnold PYTHONDONTWRITEBYTECODE=1 \
python3 -P .megaplan/initiatives/critique-ledger-safe-v3-canary/run_canary.py
PYTHONPATH=/workspace/Arnold PYTHONDONTWRITEBYTECODE=1 \
python3 -P /usr/local/bin/verify-zero-recovery-offline-smoke
INNER

container_id=$(docker create \
  --name "$container_name" \
  --restart no \
  --init \
  --network none \
  --cap-drop ALL \
  --cap-add CHOWN --cap-add DAC_READ_SEARCH --cap-add KILL \
  --cap-add SETGID --cap-add SETPCAP --cap-add SETUID \
  --security-opt no-new-privileges:true \
  --ipc none --pids-limit 256 --memory 4g --memory-swap 4g \
  --tmpfs /run/megaplan-zero-recovery:rw,noexec,nosuid,nodev,size=268435456,mode=0711 \
  -e MEGAPLAN_ZERO_RECOVERY_CANARY=1 \
  -e "STRUCTURAL_SMOKE_PRODUCTION_IMAGE_ID=$production_image_id" \
  -e "STRUCTURAL_SMOKE_DERIVED_IMAGE_ID=$derived_image_id" \
  -v "$workspace_child:/workspace" \
  --entrypoint /bin/bash \
  "$derived_image_id" -lc "$inner" 2>> "$stderr_log")

set +e
docker start -a "$container_id" >> "$stdout_log" 2>> "$stderr_log"
smoke_exit_code=$?
set -e
terminal_line=$(tail -n 1 "$stdout_log")
if [[ "$smoke_exit_code" -eq 0 ]] && python3 -c \
  'import json,sys; value=json.loads(sys.argv[1]); assert value["status"]=="passed"' \
  "$terminal_line"; then
  smoke_status="passed"
else
  if [[ "$smoke_exit_code" -eq 0 ]]; then
    smoke_exit_code=1
  fi
fi
exit "$smoke_exit_code"
