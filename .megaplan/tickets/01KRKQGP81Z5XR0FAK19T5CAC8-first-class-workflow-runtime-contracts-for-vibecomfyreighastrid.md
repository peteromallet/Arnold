---
id: 01KRKQGP81Z5XR0FAK19T5CAC8
title: First-class workflow runtime contracts for VibeComfy/Reigh/Astrid
status: open
source: human
tags:
- cross-repo
- workflow-contracts
- vibecomfy
- astrid
- runpod
- validation
codebase_id: null
created_at: '2026-05-14T17:10:59.073213+00:00'
last_edited_at: '2026-05-14T17:10:59.073213+00:00'
epics: []
---

We need a first-class workflow runtime contract abstraction for VibeComfy that is generated from, or attached to, each Python ready workflow and then consumed consistently by VibeComfy doctor/reconcile, the Reigh live-test harness, the worker runtime, and Astrid result validation.

Context from the current Wan2GP parity push:
- LTX Runexx first/last workflows were valid Python workflows and produced outputs, but were far slower than Wan2GP on the same 4090.
- The root cause was not just a bad sampler value: the workflow enabled a Comfy/KJNodes runtime path where speed depends on SageAttention, while the prebuilt validation environment was still treated as a generic portable environment.
- The contract/doctor layer could detect that uncontracted SageAttention was unsafe, but there was no generic way for the workflow to declare "this route requires SageAttention-ada and --use-sage-attention" and have every consumer install, validate, and run with that requirement.
- The fix in progress is a narrow slice: add `runtime_packages` metadata to the LTX Runexx template, enable `PathchSageAttentionKJ(auto)`, make prebuilt live-test install/verify SageAttention-ada before launching, and set the Sage attention env for the worker without mutating the route key. That solves the immediate case, but it is still bespoke.

The proper abstraction should be a single machine-readable runtime contract per workflow/template, not scattered checks. It should cover at least:
- Asset contract: model files, exact loader-facing paths/subdirs, input fixtures, output artifact names/prefixes, and expected media kinds.
- Node contract: required custom-node packs, lockfile pins, relevant node class versions or object_info compatibility requirements.
- Python package contract: runtime Python packages and install sources, e.g. SageAttention-ada, onnxruntime, opencv variants, audio deps, with install/verify probes.
- Runtime flag contract: memory profile, cache policy, reserve VRAM, `--use-sage-attention`, attention profile, Comfy/HiddenSwitch flags, and route-specific environment knobs.
- Schema/input contract: required node inputs, accepted widget names/values, missing connection detection, and family-specific override eligibility.
- Output contract: where generated media must land, what filenames/prefixes are valid, what the app/Astrid should fetch, and how to fail when a run succeeds but no artifact appears.
- Evidence contract: last validated GPU, RunPod pod/profile, wall clock, generation-only time, VRAM/RAM peaks, backend version/commit SHAs, output artifact paths, and media-understanding validation status.
- Policy contract: pure-Python workflow source only for app-active routes; raw JSON may remain source/reference material but must not be the runtime path.

Every relevant tool should consume the same contract:
- `vibecomfy doctor` should validate required inputs/connections, object_info compatibility, pure-Python policy, package requirements, model paths, output sinks, and runtime flags before execution.
- `vibecomfy reconcile` should stage/download assets, install/restore node packs, install declared Python packages, verify imports/kernels, and report what remains manual.
- Reigh live-test should refuse to queue app tasks until the runtime contract is satisfied; it should install/verify declared runtime packages on prebuilt consumers or fail early with actionable errors.
- Reigh worker should select templates/routes independently from runtime installation profiles. Runtime package needs must not mutate product route keys like `profile-default`.
- Astrid should consume the output/evidence section to fetch generated files and run image/video understanding checks against route-specific expectations.
- The contract should remain lightweight enough that adding/forking workflows is not bureaucratic: defaults should be inferred from the Python graph where possible, and authors should only declare what cannot be inferred.

Acceptance criteria for an implementation epic:
1. Add a typed/runtime-contract model in VibeComfy and expose it from ready workflows, preferably by normalizing existing `READY_METADATA`, `READY_REQUIREMENTS`, model asset declarations, and runtime configuration fields rather than inventing a parallel spreadsheet.
2. Migrate the LTX Runexx SageAttention requirement from bespoke metadata/harness logic into the generic contract model, while preserving the current SageAttention-ada behavior.
3. Teach doctor/porting analysis to report missing package/runtime flag requirements as first-class contract failures with clear remediation.
4. Teach reconcile/prebuilt build/consumer launch to install and verify declared Python packages and runtime flags before queueing work.
5. Teach output artifact validation to use the same contract so successful process exit without expected media fails clearly.
6. Record validation evidence back to a durable evidence artifact or contract-adjacent log after RunPod runs, including generation time and VRAM peak where available.
7. Add tests showing this would have prevented: uncontracted SageAttention, missing required node inputs/connections, missing model folders, wrong output path/prefix, JSON runtime source for app-active workflows, and route-key pollution from diagnostic runtime params.
8. Document the workflow authoring/onboarding checklist around this contract for new workflows, forked workflows, and workflows converted from upstream JSON.

This is cross-repo: VibeComfy should own the contract schema and doctor/reconcile behavior; Reigh worker/live-test should consume it; Astrid should consume output/evidence contracts for result validation.
