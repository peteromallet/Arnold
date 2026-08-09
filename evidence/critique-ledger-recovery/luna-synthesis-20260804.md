# Luna swarm synthesis — cloud megaplan control-plane audit

Six bounded Luna audits reviewed the Sol root-cause brief and exact source surfaces. No agent edited code or cloud state.

## 1. Runtime / CLI identity

`cloud resume` first calls remote `arnold status`, then `arnold resume`. The cloud container resolves this through `/root/.pyenv/shims/arnold` to legacy `arnold.cli:main`, which requires `--artifact-root`. The chain path instead uses `python -P -m arnold_pipelines.megaplan` with an explicit runtime/source binding. This is a pre-dispatch invocation-lineage mismatch. Patch boundary: centralize an absolute pinned interpreter + module command in the SSH provider and all remote status/resume operations. Acceptance: hostile PATH cannot affect status/resume; both commands carry identical runtime identity, workspace, plan, and safe quoting; container smoke test has no legacy `--artifact-root` error.

## 2. Lease-bound dispatch / liveness

Launch verification can treat tmux plus state advancement as success; watchdog tracking can treat marker/workspace/spec presence as “tracked.” Neither proves lease acquisition or a live process with matching PID/start identity, command, runtime, revision, and session. Lease/launcher exceptions can therefore be swallowed. Fail closed immediately after lease acquisition and before publishing dispatch success: require fresh lease ID, matching live process identity, command/runtime/source identity, and parseable verification within a deadline. Acceptance: injected lease failure, marker/tmux-only false positive, identity mismatch, and fresh matching lease paths all behave correctly.

## 3. Evidence ordering / recovery

The coherent order is: occurrence-bound repair identity → clean ledger/outbox/static suite → newest `state.latest_failure` and fingerprint → authoritative U1/quality resolutions → fresh fenced lease → recovery/resume. A remaining gap is that `override.py` may still let stale `phase_result.exit_kind == external_error` trigger generic resume even when a newer deterministic VJ8 failure is in state. Terminal states also need stale telemetry quarantine and observer freshness labels. Acceptance: old external phase result cannot override newer VJ8; exact/divergent idempotency behavior and outbox/public export pass; lease failure yields no executing projection.

## 4. Resident / chain / runtime lineage

The template-generated chain path can launch `arnold-supervise chain arnold-chain ...` without explicit pinned Python, while `_chain_start_command` uses `python -P -m arnold_pipelines.megaplan` and `MEGAPLAN_RUNTIME_SRC`. Resident cloud resume reaches a wrapper without proving equivalent lineage. Resident imports can resolve dirty `/workspace/arnold` while the chain uses pinned c116. Smallest custody envelope: session, plan, occurrence/fingerprint, job, container, PID/start identity, source revision, runtime hash, and marker lease fence. Acceptance: template and chain command use the same binding; mismatched/dirty lineage fails before dispatch; fenced takeover is required.

## 5. Provider credential/configuration authority

Cloud preflight reports hints but does not verify effective credentials, aliases, base URL, or authentication. Provider routing and aliases are duplicated across preflight, `KeyPool`, adapters, and Hermes. Create one provider registry consumed by all; perform a bounded secret-safe remote auth preflight before lease acquisition. Acceptance: Zhipu/GLM and other aliases resolve identically; missing/unsupported providers fail before dispatch; failed preflight or lease cannot emit executing state.

## 6. Observer / notification bounds

Resident should be snapshot-first. A live cloud query is an optional deadline-bounded fallback and must never delay or replace the cached snapshot. Current gaps: `load_cloud_status_snapshot` considers `generated_at` but not heartbeat/write-error sidecars, and `load_hot_context` can await live cloud status before responding. Acceptance: hung backend still returns cached state within deadline; stale snapshots show an explicit stale banner and no current progress; write-error sidecar immediately yields stale/unavailable; corrupted fallback cannot replace a valid snapshot.

## Cross-cutting conclusion

VJ8 is repaired and occurrence-scoped, but the shared control plane remains non-hermetic until every operation carries one immutable execution envelope (runtime interpreter/module, source/runtime hash, provider identity, plan/session/job, lease/process identity, occurrence, and monotonic evidence generation). Do not resolve U1/quality blockers or claim liveness from tmux/state/marker alone.
