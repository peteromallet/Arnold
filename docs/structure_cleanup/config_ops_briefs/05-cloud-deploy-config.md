Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit deployment/cloud operational config.

Focus:
- `cloud.yaml`
- scripts with `megaplan_cloud` or RunPod/Railway/cloud naming
- docs under `docs/runpod/`, `docs/megaplan_chains/`, root README references

Use `rg -n "cloud.yaml|Railway|RunPod|runpod|cloud|megaplan_cloud|VIBECOMFY_RUNPOD" . --glob '!vendor/**'`.

Do not edit files.

Questions:
1. Does `cloud.yaml` earn root placement?
2. Is deployment config documented enough?
3. Should there be `deploy/` or `ops/` folder, or would that break tooling?
4. What safe docs changes are available?

Return exact recommendations.
