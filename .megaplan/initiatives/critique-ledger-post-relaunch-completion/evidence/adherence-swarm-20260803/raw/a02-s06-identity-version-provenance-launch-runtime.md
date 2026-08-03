# a02-s06-identity-version-provenance-launch-runtime: identity-version-provenance × launch-runtime

## Verdict

FAIL. Runtime provenance and process-incarnation primitives exist, but launch-runtime is not closed over the required identity tuple. Several launchers can start or report work without binding run, attempt, incarnation, runtime version, provider, and container provenance. The highest-risk gaps permit authority mutation under stale or unverified runtime identity.

## Intended canonical contract

The intended contract is the composition of:

- `run_authority.SubjectAttempt`, `Claim`, and `Decision`, which bind run, revision, attempt, coordinator attempt, fence, evidence, and idempotency: `arnold_pipelines/run_authority/contracts.py:233-337`.
- `build_runtime_launch_seed()` / `validate_runtime_launch_seed()`, which already content-address runtime files, imports, interpreter, wrappers, supervisor, hot selectors, marker, and chain spec: `arnold_pipelines/megaplan/cloud/runtime_attestation.py:516-684`, `:725-880`.
- `current_runner_incarnation()` and lease binding, which already distinguish PID reuse, PID namespaces, host, container, and runner fence: `arnold_pipelines/megaplan/_core/phase_runtime.py:63-112`, `:204-245`.
- Chain execution binding, which content-addresses the chain bundle and runtime identity: `arnold_pipelines/megaplan/chain/execution_binding.py:330-404`.

No single canonical launch contract currently composes these. Consolidate on the runtime seed plus process attestation, extended with the run/revision, attempt ordinal, runner incarnation/fence, provider/profile, container ID/image, and PID namespace. Do not create another provenance carrier.

## Evidence and complete path inventory

I searched with `rg --files` for launch/runtime/provenance/identity/version/container/resident/provider/profile/attempt/incarnation, then `rg -n` for `subprocess.Popen`, `tmux new-session`, Docker inspection, SSH, runtime selectors, seed/attestation, execution binding, markers, and all callers. I inspected writers, readers, callers, consumers, templates, wrappers, and tests.

Writers include:

- Runtime seeds and attestations: `cloud/runtime_attestation.py:516-684`, `:912-1048`.
- Chain bindings: `chain/execution_binding.py:1017-1049`.
- Cloud markers/provenance: `cloud/cli.py:2615-2676`, `:5070-5102`, `:5572-5591`, `:5797-5813`.
- Managed-agent manifests: `managed_agent.py:397-425`, `:448-526`.
- AgentBox operations/resources: `agentbox/operations.py:40-76`, `:140-162`; `agentbox/host.py:197-274`.

Readers/consumers include:

- Chain startup and reconciliation: `chain/__init__.py:6433-6441`; `chain/execution_binding.py:922-1014`.
- Worker runtime preflight: `megaplan/workers/_impl.py:7009-7035`.
- Resident runtime checks: `resident/cli.py:986-990`, `resident/runtime.py:142-147`.
- Cloud marker/tracking/launch verification: `cloud/cli.py:3393-3439`, `:4665-4844`.
- Local tmux status: `agentbox/tmux.py:138-199`.
- Provider container observation: `cloud/providers/ssh.py:770-777`, `:846-1070`.

Direct launch paths found include cloud chain/epic/bootstrap commands, rendered entrypoint mode runners, systemd resident/watchdog launchers, resident `Popen`, AgentBox tmux, and provider subprocess/SSH adapters: `cloud/cli.py:3562-3655`, `:4000-4045`, `:5816-5871`; `cloud/templates/entrypoint.sh.tmpl:190-247`; `cloud/systemd/ensure-megaplan-resident:80`; `resident/subagent.py:3311-3341`, `:4727-4733`; `agentbox/tmux.py:68-135`.

## Adherence gaps

- **P0 — authority mutation: runtime binding is opt-in.** Chain policy defaults to `execution_binding: optional`, and runtime enforcement additionally requires `require_editable_runtime_match`: `chain/execution_binding.py:86-121`. `assert_execution_binding()` returns immediately when binding is not required, while `bind_execution_identity()` does the same for optional policy: `:978-1023`. Since `run_chain()` calls this before state initialization, a default chain can mutate state without an immutable runtime binding: `chain/__init__.py:6433-6441`.

- **P1 — authority mutation: runtime attestation is fail-open by default.** `require_configured_runtime_launch()` returns `None` when no seed exists unless `MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED=1`: `cloud/runtime_attestation.py:994-1048`. Workers call it with `create=True`, but inherit this optional behavior: `megaplan/workers/_impl.py:7013-7035`. Standard cloud chain launch only performs the provenance check during refresh; the emitted command does not require a seed/process attestation: `cloud/cli.py:3562-3655`, `:3808-3815`. The repository therefore contains a canonical checker that ordinary launchers can bypass.

- **P1 — authority and status: the seed is not bound to the full launch identity.** Its marker binding contains session/workspace/spec/digest/run kind/relaunch/runtime identity, but no run ID, attempt ID/ordinal, incarnation, provider, container ID, or PID namespace: `cloud/runtime_attestation.py:488-513`, `:516-684`. Process attestation records PID, start ticks, executable, hash, and selectors, but not PID namespace/container identity: `:883-909`. Existing phase-runtime code proves these fields are available, but launch-runtime does not consume it: `phase_runtime.py:63-112`, `:204-245`. This permits stale evidence crossing restart, two-container, or foreign-PID boundaries.

- **P1 — authority mutation: epic refresh failure is explicitly ignored.** `_refresh_then_epic_chain_start_command()` executes refresh with `|| true` and then starts the epic chain: `cloud/cli.py:4029-4045`. The subsequent epic command accepts hot-env/runtime fallbacks without mandatory seed validation: `cloud/cli.py:4000-4025`. A failed refresh can therefore leave the old runtime eligible for new authority-bearing work.

- **P1 — authority mutation: bootstrap is a separate bypass.** Bootstrap writes a marker without identity digest or runtime binding, then directly invokes `arnold init --auto-start`: `cloud/cli.py:5797-5849`; `_run_bootstrap_wrapper()` launches it without chain execution binding or runtime attestation: `:5852-5871`.

- **P1 — authority mutation: resident delegation carries routing provenance, not runtime provenance.** The resident envelope allowlist ends at conversation/custody/root-run fields: `resident/provenance.py:32-55`. Managed supervisors and provider workers receive that environment and are launched with `Popen`, but no runtime seed, process attestation, attempt ordinal, or incarnation: `resident/subagent.py:3311-3341`, `:4709-4733`. Managed manifests bind model/backend/command/launch provenance, but not runtime version or process incarnation: `managed_agent.py:397-425`, `:448-526`.

- **P2 — status misreporting: local and normal-provider lifecycle records identify sessions, not processes.** AgentBox marks an operation running after tmux existence inspection and records only provider/session/state: `agentbox/host.py:214-274`; `agentbox/tmux.py:138-199`. Operation metadata has command/run directory/intent/state but no attempt/incarnation/runtime identity: `agentbox/operations.py:140-162`. The resident AgentBox profile reports the adapter result as `operation_running`: `agentbox/resident_profile.py:412-475`. The isolated SSH profile has strict container ID/image/lifecycle attestation, but that protection is specific to isolated runners: `cloud/providers/ssh.py:1035-1070`; ordinary `observe_container()` is only a classified observation: `:770-777`.

## Incident reachability and severity

Observed: optional chain/runtime binding, direct standard/epic/bootstrap launchers, incomplete seed fields, and tmux/provider status checks are present in code.

Inference: a stale editable checkout, failed refresh, restarted process with reused PID, replaced container, or resident child restart can be accepted as the same logical launch. The strongest authority paths are the optional chain binding, fail-open runtime gate, epic `|| true`, and bootstrap bypass. The AgentBox/provider findings primarily misreport status unless their operation state is later treated as authority; then they become P1.

## Minimal generalized remediation

1. Make launch binding mandatory for every authority-bearing chain, epic, bootstrap, worker, resident, and AgentBox launch. Migrate existing specs from optional policy and reject legacy unbound progressed state.
2. Extend the existing runtime seed—not a new parallel schema—with run ID/revision, attempt ID/ordinal, runner incarnation/lease fence, provider/profile, container ID/image, PID namespace, and launch-provenance hash.
3. Route every launcher through one canonical pre-exec function that builds/validates the seed and creates process attestation. Remove or make unreachable direct `_bootstrap_launch_command`, epic start, entrypoint mode, systemd resident, resident `Popen`, and AgentBox tmux launch implementations.
4. Delete `|| true` around refresh-before-launch. Provider attestation must be the shared backend for local, SSH, and container launches.

## Required tests and retirement proof

Add deterministic tests for:

- Concurrent same-session launches with different run/attempt identities: exactly one wins; the other is fenced.
- Restart/PID reuse: changed start identity or incarnation rejects stale evidence.
- Two containers with the same PID but different container/PID namespaces: reject the foreign process.
- Provider/container replacement, image/profile mutation, runtime selector mutation, hot-env mutation, marker mutation, chain-spec mutation, and failed refresh: all fail closed.
- Resident and AgentBox launches: child manifest, process attestation, and operation state contain the same canonical binding.
- Static/AST scan proving no direct launch primitive remains outside the canonical launcher; tests should fail on new `Popen`, `tmux new-session`, or chain-start command construction in bypass modules.
- Retirement proof: enumerate all current callers, delete duplicate writers, and assert each former path invokes the canonical launcher exactly once.

## Unknowns

No live services, cloud state, or deployment environment were inspected. An external deployment may set `MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED=1`, but repository templates do not make that mandatory. It is also unknown whether every production systemd/container profile uses the isolated provider path; the ordinary paths remain unbound in repository code.