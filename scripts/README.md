# Scripts

Repository-local operational scripts. These are normally run from the repository
root as direct paths:

```bash
uv run python scripts/<name>.py --help
```

Use `scripts/` for direct-run helpers, RunPod harnesses, local debugging, smoke
checks, shell loops, and one-off maintenance. Use `tools/` instead for importable
developer tools that are meant to run as `python -m tools.<name>`.

## RunPod

| Script | Purpose |
|---|---|
| `runpod_runner.py` | Shared RunPod pod, shipping, and artifact helpers. |
| `runpod_validate.py` | Cheap RunPod smoke validation entry point. |
| `runpod_corpus_matrix.py` | Corpus and ready-template RunPod matrix runner. |
| `runpod_e2e_matrix.py` | End-to-end RunPod matrix wrapper used by CI. |
| `runpod_matrix_plan.py` | Matrix planning and manifest helpers. |
| `runpod_matrix_remote.py` | Remote workflow preparation and compatibility patches. |
| `runpod_model_matrix.py` | Model-focused RunPod matrix runner. |
| `runpod_artifacts.py` | Artifact download and summary helpers used by RunPod scripts. |

## Agent / Editor

| Script | Purpose |
|---|---|
| `agentic_success_rate.py` | Agentic-evaluation success-rate harness. |
| `generate_agent_contract_js.py` | Regenerates the agent-edit JavaScript response contract. |
| `run_local_agent_comfy.sh` | Starts a local agent-edit ComfyUI session. |
| `sync_agent_skill.py` | Checks the canonical skill in `docs/agent-skill/` and installs it into local agent harnesses. |
| `vibecomfy_debug.py` | Debug helper for agent-edit sessions. |
| `_agent_edit_prompt_dump.py` | Private prompt-dump helper. |

## Maintenance / Smoke

| Script | Purpose |
|---|---|
| `regenerate_snapshots.py` | Rebuilds or checks compile-API snapshots. |
| `warm_session_smoke.py` | Runtime warm-session smoke helper. |
| `populate_model_hashes.py` | Model hash population helper. |
| `demo_wrapper_codegen.py` | Wrapper codegen demonstration script. |
| `roundtrip_fidelity_spike.py` | Round-trip fidelity spike. |
| `_catalog_size_probe.py` | Private catalog-sizing probe. |
| `maintenance/` | Historical one-off maintenance scripts kept out of the root. |

## Megaplan / Local Ops

| Script | Purpose |
|---|---|
| `megaplan_cloud_operator_loop.sh` | Megaplan cloud operator loop. |
| `megaplan_cloud_recovery_loop.sh` | Megaplan cloud recovery loop. |
| `patch_shannon_unattended_root.sh` | Local operator patch helper used by the cloud loops. |
