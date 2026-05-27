# Sprint 6b — RunPod session + operational hardening (`premium/thorough/high +prep @codex`)

Shared context: read `docs/structural_audit_2026-05.md` (runtime/RunPod risk), `handoff-m2a.md`, `handoff-m2b.md`, and `handoff-m6a.md`. Runtime factory exists; this sprint makes RunPod a first-class session and hardens GPU-spend boundaries.

## Outcome
`run(wf, runtime="runpod")` works through the public runtime factory with fake/session coverage, preflight checks, cost guardrails, secret filtering, teardown safety, and explicit real-smoke evidence or release-blocker status.

## Scope (IN)
1. **Implement `RunPodSession(VibeSession)`** wrapping `runpod_lifecycle`: `start` provisions, `run` submits/polls, `stop` terminates. Keep `commands/runpod.py` for pod admin.
2. **Add fake RunPod boundary**: `FakeRunPodSession(VibeSession)` behind `VIBECOMFY_RUNPOD_FAKE=1`; all SDK/network calls are gated behind this boundary, while local temp dirs simulate start/run/stop.
3. **Add RunPod preflight** before provisioning: volume/mount availability, free disk, required credentials, staged-model integrity via `vibecomfy check --subset assets` and `--subset models`, and teardown safety.
4. **Enforce budget before spend**: `VIBECOMFY_RUNPOD_BUDGET_USD` checked in preflight and again before provisioning. Default follows existing RunPod helper convention unless intentionally changed with tests/workflows.
5. **Filter environments deny-by-default** for `RunPodSession` and embedded ComfyUI subprocesses before third-party custom-node code runs. Default allowed variables: `VIBECOMFY_RUNPOD_FAKE`, `VIBECOMFY_RUNPOD_BUDGET_USD`, `COMFYUI_PATH`, `PYTHONPATH`. Any additional variable requires `RunPodSession.ALLOWED_ENV` with a comment explaining why custom-node code needs it. `RUNPOD_API_KEY` and `HF_TOKEN` are never passed through.
6. **Teardown safety**: best-effort `atexit`/SIGTERM/SIGINT cleanup or equivalent. If termination cannot be confirmed, log the pod id prominently and record the orphan-cleanup path in `handoff-m6b.md`.
7. **Real RunPod evidence is operator-gated release evidence**: use real smoke only after fake/session tests pass. The sprint can complete without env/budget, but `handoff-m6b.md` must contain an operator-owned release blocker or explicit risk acceptance; quiet "env unavailable" is not done.
8. **Create `handoff-m6b.md`** recording fake/session tests, preflight behavior, cost spent, real-smoke evidence or blocker, env-filter decisions, teardown evidence, and sprint-7 compatibility notes.

## Locked decisions
- RunPod integrates through the sprint-6a runtime registry, not a parallel public path.
- Plugin collision policy and verb/router work remain sprint 7.
- RunPod real-smoke evidence is required before claiming the RunPod path release-ready.
- Warm-session invalidation remains string-semantic; staged model file hash/mtime invalidation is deferred and recorded in `handoff-m6b.md`.
- `warm_policy="never"` remains the escape hatch.

## Prep deliverables
- `prep-m6b.md` maps existing RunPod helper behavior, env vars, teardown paths, budget defaults, and fake/session boundaries before implementation.

## Constraints
- Sprint-6a protocol compatibility tests stay green.
- No test may leave pods running on failure.
- Model/staging preflight failures surface as structured `VibeComfyError` subclasses with actionable `next_action` where possible.
- No unbudgeted RunPod spend.

## Done criteria
- `run(wf, runtime="runpod")` works through fake/session tests.
- Preflight checks volume, disk, env, staged-model integrity, budget, and teardown behavior before provisioning.
- Env filtering is deny-by-default and tested.
- A capped real smoke is completed, or `handoff-m6b.md` records an operator-owned release blocker/risk acceptance.
- Existing embedded/server/dry-run runtime paths still pass compatibility tests.
- `handoff-m6b.md` satisfies the shared handoff contract.

## Touchpoints
`runtime/run.py`, `runtime/session.py`, new/updated RunPod runtime modules, `commands/runpod.py`, `commands/run.py`, tests, docs.

## Anti-scope
Do NOT redesign the runtime factory. Do NOT change plugin collision semantics or wire new verbs. Do NOT broaden model staging beyond preflight checks needed before GPU spend.
