# a01-s06-authority-ownership-launch-runtime: authority-ownership × launch-runtime

## Verdict

**FAIL.** The canonical building blocks exist, but launch callers bypass them.

Observed gaps: one **P0 authority-mutation** bypass, six **P1 authority-mutation** gaps, and one **P2 status-misreporting** gap. The highest-risk path is `arnold-chain`: malformed or failed acceptance-gate output is interpreted as permission to launch.

I searched with `rg --files` and `rg -n` across `arnold_pipelines/megaplan`, `tests`, templates, wrappers, systemd units, schemas, and call sites for `tmux new-session`, `chain start`, `managed_agent`, `status_payload`, JSON decoding, marker/state paths, provider factories, reset/unlink operations, runtime bindings, and resident launchers.

## Intended canonical contract

- `managed_agent.py` owns durable execution identity, manifest, process evidence, logs, lineage, and terminal state; callers must not create manifests for processes launched elsewhere (`arnold_pipelines/megaplan/managed_agent.py:1-9`).
- Managed launch reservation is lock-protected and idempotent (`managed_agent.py:529-570`); execution is separately locked (`:750-760`).
- Chain `state.json` is the authority; projections are supplemental (`chain/spec.py:1866-1885`). Canonical writes are atomic and record projections only after the authority write (`chain/spec.py:2073-2124`).
- Operator marker mutation has the strongest existing runtime contract: read/modify/write under a lock, SHA-checked CAS, fsync, and atomic replace (`cloud/operator_control.py:159-205`).
- Resident background providers converge on `launch_managed_subagent_detached`; Codex, Hermes, and Claude background launches share the durable lifecycle (`resident/subagent.py:7509-7626`).
- Provider selection is centralized for `local` and `ssh` (`cloud/providers/base.py:174-199`), with an explicitly restricted `OnBoxProvider` path (`cloud/cli.py:1390-1406`).
- Isolated SSH runners have strong image, command, mount, lifecycle, PID/IPC, and container-ID attestation (`cloud/providers/ssh.py:938-1033`, `:1035-1070`).

## Evidence and complete path inventory

Writers and launchers:

- Canonical chain-state writer: `chain/spec.py:2073-2124`.
- Direct state reset writer: `cloud/cli.py:4175-4229`, called by chain launch at `:5156-5163`; epic reset at `:5378-5388`, called at `:5629-5633`.
- Canonical operator marker writer: `cloud/operator_control.py:170-205`.
- Duplicate remote marker writer: `cloud/cli.py:3359-3390`, aliased by `_write_session_marker_command` at `:3659-3660`.
- Chain and epic launchers use that duplicate writer before `tmux new-session` (`cloud/cli.py:3926-3940`, `:4083-4097`).
- Local `last_chain.json` is written directly and non-CAS after launch (`cloud/cli.py:5277-5301`, `:5750-5770`).
- Entrypoint and systemd independently launch watchdog/resident sessions (`cloud/templates/entrypoint.sh.tmpl:210-232`; `cloud/systemd/ensure-megaplan-watchdog:24-51`; `cloud/systemd/ensure-megaplan-resident:56-90`).
- Direct chain wrapper launch: `cloud/wrappers/arnold-chain:14-48`.
- Watchdog relaunches through `arnold-supervise`, but its materializer gate failure is tolerated (`cloud/wrappers/arnold-watchdog:9031-9060`).
- Repair-loop has the same tolerated relaunch-gate failure (`cloud/wrappers/arnold-repair-loop:6809-6819`).
- Watchdog child-agent authority gates are ignored on helper failure or malformed output (`cloud/wrappers/arnold-watchdog:2190-2217`, `:5116-5122`, `:5904-5911`).
- Synchronous Hermes compatibility launches bypass the durable manifest path (`resident/subagent.py:7628-7687`).

Readers and consumers:

- Local/remote status consumers parse provider stdout directly (`cloud/providers/local.py:188-196`; `cloud/providers/ssh.py:2746-2754`).
- Cloud status and resume call those methods without a JSON-decode boundary (`cloud/cli.py:1178-1185`, `:1201-1222`, `:5936-5957`).
- Local marker projection controls status mode, resume workspace, remote spec, and pause/resume routing (`cloud/cli.py:1376-1387`, `:2374-2394`, `:5874-5898`, `:7021-7115`, `:7128-7141`, `:1224-1249`).
- Existing wrapper static coverage audits only four wrappers and omits `arnold-chain` (`tests/cloud/test_wrapper_authority_bypass_gating.py:9-15`, `:54-74`).

## Adherence gaps

1. **P0 — authority mutation: acceptance gate fails open.**  
   `wrapper_acceptance_gate.py` explicitly opens when the spec is unreadable (`cloud/wrapper_acceptance_gate.py:161-168`). `arnold-chain` additionally converts helper failure, empty output, malformed JSON, and missing `gate_open` into success (`cloud/wrappers/arnold-chain:14-31`), then directly executes `chain start` (`:43-48`).  
   **Inference:** an acceptance-required successor can be relaunched without valid acceptance evidence, potentially duplicating mutation.

2. **P1 — authority mutation: duplicate marker writers and launch race.**  
   The remote writer merges invalid JSON as `{}` and has no expected-version/CAS check (`cloud/cli.py:3359-3379`). Chain launch performs “check session → write marker → create session” without a cross-process lock (`cloud/cli.py:3929-3938`, `:4086-4095`). Entrypoint and systemd also independently materialize the same sessions.  
   **Inference:** concurrent callers can overwrite launch identity or leave a marker describing a launch that did not win the tmux race.

3. **P1 — authority mutation/status routing: projection becomes control authority.**  
   `last_chain.json` is treated as the preferred source for resume workspace and remote spec (`cloud/cli.py:2374-2394`, `:5874-5898`) and supplies arguments to pause/resume mutation (`:1224-1249`). Invalid JSON is silently converted to “absent” (`:7128-7141`), while marker existence alone selects chain status (`:1376-1387`).  
   **Inference:** stale or corrupt sidecar data can misroute pause/resume or misclassify runtime state.

4. **P1 — authority mutation: cloud launcher deletes canonical chain state.**  
   `_chain_state_reset_command` directly unlinks authority state and plan directories (`cloud/cli.py:4189-4215`), despite `chain/spec.py` defining the chain module as the authority.  
   **Inference:** a concurrent runner or restart can lose resumable state without chain-owner CAS or lifecycle validation.

5. **P1 — authority mutation: relaunch gate is advisory.**  
   Watchdog and repair-loop call the relaunch materializer gate, but `authority_gap_continue` permits launch after gate failure (`cloud/wrappers/arnold-watchdog:9042-9045`; `cloud/wrappers/arnold-repair-loop:6811-6815`).  
   **Observed distinction:** the code classifies relaunch as non-authoritative for accepted repair; it does not prove a valid owner for the actual runtime mutation.

6. **P1 — authority mutation: child-agent gate failure is fail-open.**  
   Watchdog only rejects the exact `zero_authority_rejected` result; helper failure, empty output, and malformed JSON leave the managed-agent launch enabled (`cloud/wrappers/arnold-watchdog:2190-2195`).  
   The subsequent managed-agent manifest is canonical execution evidence, but it does not repair the missing launch-authorization decision.

7. **P1 — authority ownership: synchronous Hermes bypass.**  
   Non-Discord synchronous Hermes calls execute `launch_hermes_agent.py` directly with arbitrary `project_dir` and no managed manifest (`resident/subagent.py:7628-7687`). The code proves only that Discord custody is inapplicable (`:7638-7641`), not that the task is mutation-free.  
   **Inference:** a mutation-bearing non-Discord call can execute outside the canonical durable owner.

8. **P2 — status misreporting: malformed provider JSON escapes as raw `JSONDecodeError`.**  
   Both providers call `json.loads(result.stdout)` without translating decode failure into `CliError` (`cloud/providers/local.py:188-196`; `cloud/providers/ssh.py:2746-2754`).  
   **Inference:** status can crash rather than report “unknown/unavailable”; a recovery caller may incorrectly interpret that as runtime failure.

## Incident reachability and severity

The watchdog JSON-decode incident is reachable through provider status and marker readers, but the raw provider decode is primarily a **P2 observability defect**. The more severe independent path is `arnold-chain`, where malformed gate output reaches a real chain mutation launch (**P0**).

Restart and concurrency increase exposure: entrypoint/systemd duplicate session materializers, and chain launch has a check-then-write-then-start sequence. Provider selection itself is not an observed gap: `local`, `ssh`, and restricted on-box paths are explicit and tested. Isolated SSH two-container replacement and PID/IPC drift are already fail-closed by attestation.

## Minimal generalized remediation

Consolidate launch authorization and marker mutation on one shared, lock/CAS-protected implementation based on `cloud/operator_control._write_marker` semantics.

- Make unreadable/malformed acceptance evidence fail closed.
- Delete inline marker heredocs, direct `last_chain.json` writes, and direct state unlink/reset logic; route through canonical chain/session APIs with owner identity and expected digest.
- Make `arnold-chain`, watchdog, and repair-loop abort on gate/helper failure.
- Restrict synchronous Hermes to explicitly read-only/non-mutating tasks, or route it through managed background execution.
- Convert provider JSON failures to typed `provider_failed`/unknown status without triggering launch.

No broad rewrite is needed: existing CAS marker mutation, managed-agent reservation, chain state persistence, and isolated runtime attestation already provide the required primitives.

## Required tests and retirement proof

Add deterministic tests for:

- empty, nonzero, malformed, and schema-invalid acceptance-gate output: zero `tmux new-session` calls;
- two concurrent launches: one owner, one collision/no-op, marker remains bound to the winner;
- marker corruption, restart, pause/resume CAS conflict, and stale sidecar: fail closed and never route mutation from projection;
- chain-state reset racing with resume: authority preserved or explicit CAS conflict;
- local, SSH, and on-box provider selection; malformed status JSON produces typed unknown status;
- runtime/profile drift, provider revision drift, container replacement between two observations, private PID/IPC namespace, and two-container same-name scenarios;
- resident provider matrix: all background providers share one managed launcher; mutation-bearing synchronous Hermes is rejected;
- restart of entrypoint plus systemd ensure jobs: exactly one watchdog/resident owner.

Retirement proof must include repository-wide `rg` assertions showing no duplicate marker writer, direct `last_chain.json` mutation, direct chain-state unlink, or fail-open relaunch gate remains reachable. Tests must invoke the canonical implementation, not merely wrap the old helpers.

## Unknowns

- Whether non-Discord synchronous Hermes is contractually guaranteed read-only is undocumented; current code does not enforce it.
- The exact operational relationship between local `last_chain.json` and remote session markers is not formally declared; this ambiguity itself enables projection authority drift.
- No live/cloud state was inspected, by instruction; concurrency and restart impacts above are code-derived inferences.