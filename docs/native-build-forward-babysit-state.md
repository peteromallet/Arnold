# native-build-forward — babysitter handoff state (2026-08-24)

## Mission
Native build-forward epic launched on the Hetzner agentbox (container
`megaplan-cloud-agent-resident-only`). Hourly pipeline-babysitting check-ins
drive it to `chain_complete: true`. Every sprint runs `partnered-5`; once the
chain is green and running, the profile switches to `native-ox-alpha`
(every slot `omp:stealth/ox-alpha` via OpenRouter).

## Current state
- Runtime: `/workspace/runtime-candidates/native-build-forward`
  - branch `fixer/native-build-forward-20260824` @ `461ae31c83099125cbe570ea428343c0787485cb`
    (= 04c3857d74 + one commit: omp registered in KNOWN_AGENTS for ox-alpha routing)
  - generation venv: `/workspace/runtime-venvs/05b40a47…` (uv + copy-mode, proof written)
  - runtime manifest (authoritative): `/workspace/.megaplan/native-build-forward.json`
    (epic.expected_head = 461ae31c83…)
  - session marker: `/workspace/.megaplan/cloud-sessions/native-build-forward.json`
    (runtime_binding.current_identity + editable_source_head = 461ae31c83…)
  - dispatch pointer: `/workspace/.megaplan/runtime-launch-seeds/native-build-forward-20260824/dispatch-current.json`
    → seed 1-461ae31c83… (recorded identity CORRECT: import_root = runtime root, rev = 461ae31c83)
- Chain: `.megaplan/initiatives/native-build-forward/chain.yaml` — 22 milestones
  (P0 MRC intake → P1 Custody M11 admission → P2 bootstrap → Native S1…S7 → Platform S1…S6),
  all `profile: partnered-5`, `merge_policy: auto`, `auto_approve: true`.
- Plan: `p0-mrc-closeout-intake-and-20260824-2221` — **BLOCKED**: phase `plan`
  failed 3× with `runtime_launch_attestation_mismatch: "chain execution binding
  does not match the live manifest-pinned runtime"`.

## The open blocker (next fire's job)
`_adopt_or_refuse_launch_identity` (arnold_pipelines/megaplan/cloud/runtime_attestation.py:1286,
call sites :1176 and :1754) fails on `rec_root != live_root`. Verified facts:
- The CURRENT seed's recorded identity is CORRECT (import_root =
  `/workspace/runtime-candidates/native-build-forward`, rev = 461ae31c83) —
  `dispatch-current.json` points at it.
- Live identity computed manually under the seed env is CORRECT (same root+rev;
  diagnostic script: `/tmp/diag-identity.py` on the box).
- Container-level env has `PYTHONPATH=/workspace/runtime-candidates/arnold-4ed98585fda8c76a8ebfba04b856b6aa9b685a47-live`
  (the OLD live tree) baked into docker Config.Env — cannot change without
  container recreate (forbidden: resident agent + live epics inside).
- The generation venv has NO arnold installed (imports resolve via container
  PYTHONPATH → old live tree — this is likely the poisoning path).
Next diagnostic: run the plan-phase attestation command manually with the exact
worker env (capture the worker stderr the driver suppresses) and print BOTH
identities at the failure point. Likely fix: scrub/override PYTHONPATH in the
worker spawn env (mirror runtime_attestation.py:433 which already pops it for
the supervisor probe), as an engine fix in the runtime worktree + commit on the
runtime branch + rebind (manifest expected_head + marker identity), then clear
the blocked plan dir and relaunch.

## Launch recipe (working)
```bash
tmux new-session -d -s native-build-forward \
  "export PYTHONPATH=/workspace/runtime-candidates/native-build-forward ARNOLD_RUNTIME_MANIFEST=/workspace/.megaplan/native-build-forward.json ARNOLD_CHAIN_SESSION=native-build-forward; \
   cd /workspace/runtime-candidates/native-build-forward && \
   arnold-chain .megaplan/initiatives/native-build-forward/chain.yaml >> .megaplan/cloud-chain-native-build-forward.log 2>&1"
```
After head advances: update manifest `epic.expected_head` AND marker
`runtime_binding.current_identity.source_revision` + `editable_source_head`
to the new HEAD (script pattern: /tmp/fix-heads2.py on the box).

## Rules
- NEVER restart the container (resident agent + live epics inside).
- NEVER touch `/workspace/runtime-candidates/arnold-4ed98585fda8c76a8ebfba04b856b6aa9b685a47-live`
  or the live epics' workspaces (megaplan-maintenance, astrid-first).
- Profile switch to `native-ox-alpha` ONLY after the chain is green and running
  (per operator: launch partnered-5 first, then switch).
- All sprint profile changes: `native-ox-alpha` profile is installed at
  `/root/.config/megaplan/profiles.toml` and
  `/workspace/runtime-candidates/native-build-forward/.megaplan/profiles.toml`.
- Escalation ladder: 1 failure = observe; same failure 2× = swarm + Codex;
  3 = park with ticket, keep driving the rest.
- MRC candidate 04c3857d74 is promotion-ready (SOL-3); promotion is the
  operator's decision — do not promote.

## Diagnostic update (2026-08-24 ~23:15Z) — narrowed
- Driver-side attestation PASSES with correct identity: ran the exact
  `runtime_provenance` command from the arnold-chain trace under the seed env —
  `ok: true`, import_root = runtime worktree, rev = 461ae31c83.
- The failure is at the WORKER dispatch adopt-or-refuse
  (runtime_attestation.py:1754): the worker's own live identity has
  import_root = the OLD live tree. Suspect path: the plan-phase worker is the
  Shannon tmux/Claude session; its bash tool calls re-resolve imports under the
  container's baked PYTHONPATH (old live tree).
- Candidate engine fix (next fire): add a guarded re-export in the container's
  /root/.bashrc — `if [ -n "$MEGAPLAN_ENGINE_ROOT" ]; then export
  PYTHONPATH="$MEGAPLAN_ENGINE_ROOT:$PYTHONPATH"; fi` (megaplan_engine_env sets
  MEGAPLAN_ENGINE_ROOT for manifest-pinned children only; live epics unaffected
  as they never set it), OR scrub PYTHONPATH in the worker-spawn env in the
  chain driver. Then clear the blocked plan dir + relaunch (relaunch5.sh
  pattern: reset chain driver state too).
