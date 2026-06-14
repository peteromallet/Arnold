# Proposal: Generic Runtime Extraction — closing the m0 blind spot

**Source:** 5 independent DeepSeek read-only audits (slices A–E) of `arnold/pipelines/megaplan/`, 2026-06-09.
**Trigger:** hand-found seed gap — the agent/LLM runtime (`run_agent.py` + `key_pool.py`) is generic infra trapped under megaplan; `arnold/pipeline/steps/agent.py::AgentStep` is hollow, so Arnold-without-megaplan cannot run an agent.

## The meta-finding (all 5 slices agree)

`substrate-inventory-m0.md` classified the **pipeline DAG types** (Stage / Step / Context / ContractResult / ports) as "the substrate" and treated **everything the agent does at RUNTIME** as "the app." That is a structural blind spot. A whole class of generic *runtime* infrastructure — running an LLM, persisting state, journaling events, running an oracle, isolating a sandbox — is generic, carries zero planning vocabulary, and is trapped under `arnold/pipelines/megaplan/` only because the package moved wholesale. m0 lists none of it in either the generic table (§1) or the megaplan-owned table (§2). **Arnold today has contract *types* but no contract *runners*.**

Consequence: m6 ("second proof pipeline, ZERO megaplan imports") and m7 ("Megaplan is just one Arnold app") are not honestly achievable — the second pipeline would have to import megaplan's runtime or duplicate ~9k lines.

## Extraction candidates (deduped across slices, ranked)

### LAYER 1 — Agent execution runtime → `arnold/agent/`  *(THE load-bearing one)*
| Capability | Path | Risk | Coupling to sever |
|---|---|---|---|
| AIAgent core + streaming watchdogs/queue/heartbeat | `agent/run_agent.py` (esp. :136-399) | S (streaming) / L (whole) | only `runtime.sandbox.get_sandbox_cwd` (:732) in tool path |
| Tool registry + dispatch + model_tools + `tools/` dir | `agent/tools/registry.py`, `agent/model_tools.py` | M | some tools import `runtime.process` (kill_group/spawn) → lift or adapter |
| Provider/key layer | `runtime/key_pool.py`, `agent/hermes_cli/{env_loader,runtime_provider}.py`, `hermes_constants.py` | M | `_pipeline.envelope._envelope_ctx`, `runtime.governor.current_governor` (budget), `types.CliError` → inject as protocol/callback |
| 429→OpenRouter fallback | `_core/hermes_fanout.py:82-139` | S | follows key_pool; `CliError`→generic |
| Agent runtime contracts + protocols | `agent_runtime/contracts.py`, `adapters.py` (+ lift `AgentSpec`/`AgentMode` from `megaplan/types.py`) | S | preserve `parse/format_agent_spec` wire format |
| Tool-call sandbox (write/exec isolation) | `runtime/sandbox.py` | S | only `types.CliError`; `SandboxViolation` already defined |

**Why it must land before m6:** it is the runner `AgentStep` injects. Without it the "zero megaplan imports" rule is satisfied only by hiding the megaplan dependency behind DI.

### LAYER 2 — State / Event / WAL runtime → `arnold/runtime/`  *(also fixes the deepest known root)*
| Capability | Path | Risk | Note |
|---|---|---|---|
| Event journal engine (flock seq + NDJSON append + read) | `observability/events.py:262-393,469,563` | L | storage backend + EventKind vocab → injected; EventKind is ~40% planning, split it |
| State persistence engine (atomic lock→read→modify→write→WAL, CAS, snapshot/restore) | `_core/state.py:643-819` | M | pluggable `validate_state` + mode registry; modes carry heartbeat/legacy shapes |
| WAL fold/projection (pure `fold_events`) | `observability/fold.py:48-80` | S | already pure; only disentangle `read_events` import |
| Effect/replay type skeleton (Effect, ReplayClass) | `observability/effect_ledger.py:1-84` | S | docstring-only coupling |

**Strategic payoff:** this *is* the durable fix for the #1 deepest root issue on record (no engine-owned ground-truth authority; state derived from claims across ≥5 drifting stores → proposed "state-as-projection + atomic reset"). A generic event-sourced state runtime — append-only journal → state is a fold over events — gives Arnold one authoritative store with replay built in. Also unblocks m6's required "deterministic replay."

### LAYER 3 — Verification runners → fold into **m5** (additions)
m5 already does oracles/gates. Add the generic *runners* the substrate lacks:
- Typed subprocess oracle runner `orchestration/oracle.py:21-73` (**zero coupling**, Risk S) → `arnold/runtime/oracle.py`
- `SuiteDelta` + `compute_delta` test-suite structural diff `completion_contract.py:299-383` (Risk M) → `arnold/pipeline/suite_delta.py` via a minimal `SuiteRunProtocol`
- `EvidenceStatus` + `TrustClass` enums `evidence_contract.py:36-61` (Risk S) → `arnold/pipeline/types.py`

### LAYER 4 — Supervisor model + ladder → already **m4** (in-flight now)
Slice E *confirms* m4's scope is correct (RunNode/RunRecord/SupervisorState, ladder engine, driver protocol are genuinely generic). Discipline to enforce while m4 runs: inject `*_BUMP_ORDER` rather than hardcode; abstract transitions behind `arnold.control.interface`; sever the `.megaplan/plans/.supervisor` path root.

## FALSE POSITIVES (genuinely megaplan-owned — bounds the extraction)
Chain runtime (`chain/__init__.py`, welded to STATE_* + MilestoneSpec + git/PR) · CLI parser (`--vendor/--critic/--depth/...` planning vocab) · `verifiability.py` + bulk `completion_contract.py` (capability registry, plan/milestone subjects) · `worker_fanout.scatter_worker_units` (welded to step-schema/PlanState) · `observability/*` event *storage* (plan_dir-coupled) · supervisor `pr_merge.py` · gateway chat server. These stay. Good signal the audit didn't over-generalize.

## Recommended chain change
Insert two milestones **before m6**, fold runners into m5, hold m4 discipline:

```
m4 supervisor-extraction        (in-flight — enforce Layer-4 severance discipline)
m5 oracle-gated-strangler       (+ Layer-3 verification runners)
m6 NEW runtime-foundation       → arnold/runtime/  (RunEnvelope+join, ArnoldError, RunContext) ← own gate; m7/m8 build on it
m7 NEW agent-runtime-extraction → arnold/agent/    (Layer 1 + thin ProviderPool + sandbox)
m8 NEW state-lifecycle-runtime  → arnold/runtime/  (mechanisms-not-engines + suspend/resume + HumanGate)
m9 second-proof-pipeline        (was m6) zero-megaplan-import + deterministic replay + forges the public SPI
m10 megaplan-flagship-app       (was m7) + vocabulary decontamination; names the Typed Step-IO Envelope successor epic
```

Sequencing rationale (FINAL — implemented 2026-06-09, 11-milestone chain): the runtime
extractions silently re-couple unless the cross-cutting carriers (envelope/error/RunContext)
are generic first → m6-runtime-foundation is its own gated milestone before m7/m8. m9's three
hard premises (zero megaplan imports + deterministic replay + a *usable* SPI) are impossible
until the agent runtime (m7) and the state/lifecycle runtime (m8) are generic, so m9 depends on
both. Inserted after m5 (clean seam — not mid-m4). Restructured per own-judgment, not agent
consensus: the 10-lens audit's contrarian was right that extraction must move *mechanisms* not
megaplan-shaped *engines* (folded into m8), and its evidence_pack counter-argument was rejected
(evidence_pack is an untested, degenerate deterministic pipeline; m9 is an LLM reducer that
genuinely needs the runtime).
