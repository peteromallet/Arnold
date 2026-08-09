The root divergence is lineage, not ledger semantics:

1. `cloud/template.py::_chain_command` launches `arnold-supervise chain arnold-chain …` from the tmux entrypoint, with no explicit pinned Python/runtime binding.
2. `cloud/cli.py::_chain_start_command` launches `python -P -m arnold_pipelines.megaplan chain start …`, binds `PYTHONPATH` through `MEGAPLAN_RUNTIME_SRC`/`engine_dir`, and sources `/workspace/.cloud-hot-env`.
3. `resident/runtime.py` handles `cloud_resume` through `profile.cloud_backend.run(...)`, reaching the cloud wrapper rather than proving the same runtime lineage as the chain launcher.
4. Recovery/status can join stale `phase_result.json` and marker data against newer `state.json` failures, producing divergent incident identity and potentially the wrong recovery transition.
5. The chain used pinned `c116`, while resident/foreground imports could resolve dirty editable `/workspace/arnold` or another live checkout. The legacy four ledger tests encode the wrong contract; the implementation’s divergent-key rejection is correct.

The smallest custody identity envelope is:

`session + plan + occurrence/failure fingerprint + job + container identity + PID + process-start identity + source revision/runtime code hash + marker lease fence`.

A process is authoritative only when that exact envelope is represented by a current marker-bound lease. PID, tmux presence, event heartbeats, or a sidecar alone are insufficient.

Four acceptance tests:

1. `test_chain_start_command_sources_cloud_hot_env_before_launch` must assert the chain command binds the selected runtime and emits the trusted-module invocation. Add the matching rendered-entrypoint assertion that template-generated chain launches use that same binding.
2. Lease acquisition failure must make startup fail closed: no chain execution, state mutation, worker dispatch, or `executing` projection.
3. A stale-owner takeover must require fenced compare-and-swap on session/container/PID-start identity; an observer must classify fresh unleased activity as a custody violation.
4. Recovery must accept only the newest VJ8 occurrence/fingerprint, reject stale `phase_result.json`, require one clean ledger+outbox+static suite pass, and preserve unresolved U1/quality blockers. The four stale tests should assert identical-content deduplication but divergent same-key `IdempotencyConflictError`.
