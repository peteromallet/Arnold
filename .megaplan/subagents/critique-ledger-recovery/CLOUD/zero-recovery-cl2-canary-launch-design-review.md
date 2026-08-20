# Zero-recovery Critique Ledger CL2 canary launch design review

Date: 2026-08-03  
Reviewer: `/root/canary_launch_review`  
Scope: read-only design review of `/private/tmp/arnold-critique-recovery-cloud-observation-preflight-20260802`

## Verdict

The current candidate cannot yet run the requested cloud canary safely or from
the exact candidate source.

The zero-recovery entrypoint intentionally runs only `healthserver.py`. That is
the right containment baseline, but it also means it performs none of the normal
entrypoint's repository checkout, Megaplan ref refresh, Codex OAuth restore, or
Codex configuration. `cloud deploy` also deliberately skips
`seed_codex_oauth()` for a zero-recovery spec. The image therefore contains the
PyPI-installed Arnold version baked by the Dockerfile, not necessarily the
approved candidate commit.

The shortest real path is one new dedicated CLI/provider operation. It must
perform a fixed, transaction-bound launch rather than reopening generic
`cloud exec`, chain, tmux, watchdog, resident, notification, or recovery
surfaces.

## Evidence

- `arnold_pipelines/megaplan/cloud/template.py::render_entrypoint()` returns the
  health-server-only `_ZERO_RECOVERY_ENTRYPOINT` when
  `zero_recovery_canary=true`.
- `arnold_pipelines/megaplan/cloud/cli.py` skips `seed_codex_oauth()` after a
  successful zero-recovery deploy.
- `arnold_pipelines/megaplan/cloud/templates/Dockerfile` installs
  `arnold[agent]` from PyPI. `SshProvider._build_direct()` supplies no
  `MEGAPLAN_INSTALL_SPEC` build argument. The normal entrypoint's runtime ref
  refresh is absent from the zero-recovery entrypoint.
- `cloud/cli.py::_ensure_repo_checkout()` delegates to
  `render_ensure_repos_block()`, which is clone-if-missing only. It neither
  requires a fresh target nor resets/verifies the checkout against an approved
  commit.
- `seed_codex_oauth()` seeds both Codex and Hermes through generic
  `provider.ssh_exec()`. The bounded canary needs Codex only and must not reopen
  a Hermes surface.
- Ordinary `cloud status --all` expects the normal container collector/snapshot.
  A health-server-only container has neither, so a dedicated fixed canary status
  reader is required.
- A single phase-model value does not currently guarantee one model attempt:
  `_run_step_with_worker_legacy()` retries Codex once for several transient
  errors, `run_codex_step()` can redispatch JSON repair, gate can reprompt or
  dispatch tiebreakers, and adaptive critique can add evaluator/lens calls.
- `--robustness bare` rejects critique and `light` omits gate. The requested
  sequence requires `full`.

## Required dedicated surface

Add exactly these zero-profile operations:

```text
python3 -P -m arnold_pipelines.megaplan cloud run-zero-recovery-canary \
  .megaplan/initiatives/critique-ledger-safe-v3-canary/canary.yaml \
  --cloud-yaml .megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml

python3 -P -m arnold_pipelines.megaplan cloud zero-recovery-canary-status \
  .megaplan/initiatives/critique-ledger-safe-v3-canary/canary.yaml \
  --cloud-yaml .megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml
```

These commands do not exist yet; the names above are the recommended closed
contract. They should accept no arbitrary remote command, phase list, model,
workspace, session, recovery policy, or notification arguments.

The canary YAML should have a strict, closed schema and bind only:

- public HTTPS GitHub repository URL and advertised branch;
- a repository-relative CL2 brief and North Star;
- a fixed plan name/slug;
- the exact phase sequence shown below;
- the sole allowed model spec `codex:gpt-5.6-sol:high`;
- `robustness: full` and `adaptive_critique: false`;
- fixed receipt locations.

The launch command should derive the expected 40-hex source SHA from the clean,
tracked local launching checkout, prove that SHA is advertised by the configured
public branch, and bind it into a fresh expiring launch transaction. It must not
ask the operator to type a SHA that the command can derive and attest itself.

## Provider implementation map

1. **Local admission before SSH**

   - Require SSH provider, idle mode, `zero_recovery_canary: true`, ChatGPT auth,
     no `extra_repos`, no secrets, and a strict canary YAML.
   - Require a clean launching checkout and tracked brief, North Star, canary
     YAML, cloud YAML, runner, and engine files.
   - Require a public `https://github.com/<owner>/<repo>[.git]` URL with no
     user-info, query, fragment, token, SSH form, or alternate host.
   - Compute and bind source HEAD, canary-spec hash, input hashes, target
     container/mount identity, fence identity, and capacity observation.
   - Require capacity GO with enough reserve for clone, plan artifacts, receipts,
     and final container stop evidence.

2. **Fresh, fenced provider transaction**

   - Immediately before the first launch mutation, re-observe the exact
     container, bind mount, host capacity, and fixed systemd fence.
   - Reject expiry, replay, target drift, branch/SHA drift, stopped/missing wrong
     container, writable-mount mismatch, or fence mismatch before cloning or
     seeding auth.
   - Use an external durable consumed-grant record or equivalent monotonic
     authority. An in-memory Python set alone is not replay protection across
     processes.

3. **Minimal Codex OAuth**

   - Read only local `~/.codex/auth.json`.
   - Parse strict JSON (duplicate keys rejected) and require ChatGPT auth.
   - Send credential bytes on stdin to a fixed provider installer; never put
     them in argv, command text, logs, receipts, WBC details, or error strings.
   - Atomically install mode `0600` copies at
     `/root/.codex/auth.json` and `/workspace/.creds/codex-auth.json`.
   - Create `/root/.codex/config.toml` with
     `preferred_auth_method="chatgpt"`, `forced_login_method="chatgpt"`,
     model `gpt-5.6-sol`, high reasoning, `approval_policy="never"`, and the
     container sandbox policy. Remove `OPENAI_API_KEY` from the runner
     environment.
   - Do not read or seed Hermes auth. At terminal exit, atomically persist any
     Codex-refreshed `/root/.codex/auth.json` back to the volume without
     exposing its contents.

4. **Fresh public checkout and exact source**

   - Derive a new workspace from canary identity plus transaction/source digest.
   - Refuse any pre-existing target; do not reset, clean, reuse, or delete it.
   - Clone the configured public branch without GitHub credentials, then require
     `git rev-parse HEAD == expected_source_sha` before any Megaplan phase.
   - Run the checked-out candidate source using
     `PYTHONPATH=<fresh-workspace> python3 -P -m arnold_pipelines.megaplan`.
     Calling `arnold` from `PATH` is not acceptable because the zero image may
     contain stale PyPI code.
   - Record the imported module path and source SHA before init, proving imports
     resolve inside the fresh checkout.

5. **Single-use deterministic runner**

   - Acquire an O_EXCL single-use run lock and retain it after all outcomes.
   - Set only fixed environment values:
     `MEGAPLAN_ZERO_RECOVERY_CANARY=1`,
     `MEGAPLAN_TRUSTED_CONTAINER=1`, `PYTHONNOUSERSITE=1`, `HOME=/root`, and
     the exact `PYTHONPATH`; explicitly remove notification/resident/recovery
     and API-key variables.
   - Invoke the exact argv below, once each and in order.
   - After every subprocess, require exit zero and the exact expected state.
     On the first non-zero, timeout, malformed output, unexpected state, or
     route away from the next fixed phase, write a terminal failed receipt and
     stop. Never call `auto`, `resume`, `revise`, an override, or the failed
     phase again.
   - Under the zero-recovery environment, disable Codex transient retry, JSON
     repair redispatch, gate reprompt, gate tiebreaker dispatch, adaptive
     evaluator/lenses, configured model fallback, and ambient agent fallback.
   - Write an atomic receipt after every phase and a final strict terminal
     receipt containing phase order, state transitions, source/import identity,
     selected and actual model identity, artifact hashes, timestamps, exit
     status, and proof that forbidden surfaces were absent.

6. **Natural stop and reconciliation**

   - The foreground runner exits after finalized or first failure. It creates no
     tmux session, marker, watchdog entry, resident, repair grant, or notifier.
   - The provider should stop the `--restart=no` container after consuming the
     terminal receipt. If SSH drops, the runner's per-phase hard timeouts ensure
     finite exit; `zero-recovery-canary-status` reads only the fixed receipt and
     host/container observations from the bind mount, never generic exec.
   - Keep the host recovery units masked. A failure does not unmask, redeploy,
     relaunch, or notify.

## Exact phase argv

The dedicated runner should construct argv arrays directly. It must not render a
shell string and must not accept additional arguments from the canary brief or
operator.

The paths below are resolved inside the fresh checkout. The recommended fixed
plan name is `critique-ledger-cl2-planning-canary`.

```text
python3 -P -m arnold_pipelines.megaplan init
  --project-dir <fresh-workspace>
  --name critique-ledger-cl2-planning-canary
  --auto-approve
  --robustness full
  --no-adaptive-critique
  --phase-model plan=codex:gpt-5.6-sol:high
  --phase-model critique=codex:gpt-5.6-sol:high
  --phase-model gate=codex:gpt-5.6-sol:high
  --phase-model finalize=codex:gpt-5.6-sol:high
  --idea-file .megaplan/initiatives/critique-ledger-safe-v3-canary/briefs/cl2-planning-canary.md
  --north-star .megaplan/initiatives/critique-ledger-safe-v3-canary/NORTHSTAR.md

python3 -P -m arnold_pipelines.megaplan plan
  --plan critique-ledger-cl2-planning-canary
  --fresh

python3 -P -m arnold_pipelines.megaplan critique
  --plan critique-ledger-cl2-planning-canary
  --fresh

python3 -P -m arnold_pipelines.megaplan gate
  --plan critique-ledger-cl2-planning-canary
  --fresh

python3 -P -m arnold_pipelines.megaplan finalize
  --plan critique-ledger-cl2-planning-canary
  --fresh
```

Expected states are, respectively:

```text
initialized -> planned -> critiqued -> gated -> finalized
```

`--no-adaptive-critique` is a required small CLI addition. Without it, an
explicit user config can turn adaptive critique on and add model calls despite
the canary's intended contract.

If gate recommends ITERATE, ESCALATE, TIEBREAKER, requires a reprompt, or leaves
state other than `gated`, the canary has failed. The runner must not force
finalize. This preserves the meaning of a real planning canary.

## Zero-profile action denylist

When a loaded cloud spec has `zero_recovery_canary: true`, reject the following
at the CLI boundary before constructing or invoking a provider mutation:

- `quickstart --launch`, `chain`, `launch-epic`, `epic-chain`, and `bootstrap`;
- `sync-megaplan`, `exec`, `resume`, `pause-chain`, `resume-chain`, and
  `supervise-tick`;
- `attach`, `chains`, retirement mutations, ordinary repair/recovery/resident
  launchers, and `destroy`;
- any auto, execute, review, revise, feedback, Git publication, PR, merge,
  notification, Discord, resident, watchdog, progress-auditor, or fixer action.

The safe zero-profile allowlist should be closed and small: fixed capacity
inventory/reclaim, build, transactional deploy, zero-recovery preflight, the
dedicated canary run/status, fixed logs, and down. Ordinary chain-oriented
`preflight` and `status --all` are not substitutes for their zero-recovery
counterparts.

## Commands that cannot work as proposed today

- `cloud exec`: explicitly forbidden and generic.
- `cloud chain`, `launch-epic`, `epic-chain`, or `bootstrap`: introduce normal
  session/marker/driver/supervision behavior and are not bounded to the five
  phases.
- `cloud sync-megaplan`: generic upload into a workspace that the zero
  entrypoint never checked out.
- `_ensure_repo_checkout()`: clone-if-missing; it can silently reuse stale
  bytes and does not verify HEAD.
- `seed_codex_oauth()`: skipped by zero deploy, seeds Hermes as well as Codex,
  and uses generic exec.
- bare `arnold ...` in the container: may import stale PyPI Arnold rather than
  the approved candidate.
- `cloud status --all`: depends on the normal collector/snapshot absent from
  the zero entrypoint.
- `--robustness bare`: skips/rejects critique.
- `--robustness light`: omits gate.
- a single phase-model pin by itself: does not suppress worker-internal retry,
  repair, gate reprompt/tiebreaker, or adaptive critique fan-out.

## Hostile test matrix

1. Reject zero profile unless provider is SSH and mode is idle.
2. Reject secrets, extra repos, API-key Codex auth, non-public/credentialed URL,
   non-normalized paths, unknown keys, duplicate YAML/JSON keys, and any model
   other than the single allowlisted spec.
3. For every denied cloud action, prove rejection occurs before provider
   creation/call and no SSH/upload/process effect is recorded.
4. Prove rendered zero entrypoint contains no marker, heartbeat, watchdog,
   resident, agent, tmux, notification, Discord, recovery, chain, auto, or model
   launcher.
5. Prove ordinary `ssh_exec()` is never called by canary run/status; only the
   fixed provider methods/surfaces are reachable.
6. Wrong container name/image/bind, RW mismatch, capacity NO-GO, missing or
   unmasked fence, stale observation, expired transaction, and replayed
   transaction must fail before auth seed, clone, or phase invocation.
7. A pre-existing target workspace must fail without deletion or cleanup.
8. A branch that moves between local admission and remote clone must fail on
   HEAD mismatch before init.
9. Prove the imported `arnold_pipelines.megaplan` path is under the fresh
   checkout even when a deliberately stale package is installed on PATH.
10. Missing, malformed, duplicate-key, wrong-mode, or unreadable Codex auth must
    fail without remote mutation; no Hermes file may be read or written.
11. Prove auth bytes never occur in argv, stdout/stderr, receipts, WBC evidence,
    process metadata, or redacted failure output.
12. With `OPENAI_API_KEY` present in the parent environment, prove the runner
    removes it and Codex config still forces ChatGPT auth.
13. Success case: record exactly the five phase argv in order, with zero calls
    to auto/chain/resume/revise/execute/review/override.
14. For each phase, inject non-zero exit, timeout, malformed response, and wrong
    state; prove no later phase or repeat invocation occurs.
15. Inject Codex timeout/stall/connection/worker error; prove exactly one model
    dispatch, not the ordinary transient retry.
16. Inject malformed model JSON; prove no JSON-repair redispatch.
17. Inject gate blockers, reprompt recommendation, and tiebreaker recommendation;
    prove no second gate/tiebreaker call and terminal failure.
18. Set user config `adaptive_critique=true`; prove explicit canary false wins and
    no evaluator/lens dispatch occurs.
19. Attempt configured and ambient agent fallback; prove both are disabled.
20. Re-run the same consumed canary; prove status/reconciliation only and no
    second grant, clone, auth seed, or model call.
21. Kill SSH after each phase boundary; prove atomic receipt recovery, finite
    runner exit, no relaunch, and status from the stopped-container host path.
22. Prove terminal success requires source SHA, import root, phase/state sequence,
    selected/actual model, required artifact hashes, fence/predeploy identities,
    and stopped/no-recovery evidence.
23. Prove terminal failure also leaves the container restart policy `no`, host
    recovery units masked, no sessions/markers/notifiers, and the failure receipt
    readable after container stop.

## No-mutation statement

The review inspected local source and diffs using read-only `git status`,
`git log`, `rg`, and `sed`. It did not contact the cloud host, browse the
network, run a model, create or change Git refs, invoke a provider mutation, or
modify implementation code. At the main agent's explicit request, the only
local mutation made by this reviewer is this Markdown evidence file.
