# Implementation Breakdown: Replace All Agent Launching with Pi

---

## Executive Summary

**Goal:** Migrate all agent-launching paths from the current system (implicitly `/agent/launch`, `/agent/execute`, or similar) to **Pi** — a unified, observable, and policy-governed agent runtime.

**Scope:** Every code path that spawns, forks, schedules, or invokes an "agent" (AI worker, task runner, multi-step reasoner, etc.) must route through Pi instead. This includes:
- Direct API calls
- Queue-based dispatch
- Cron/scheduled agents
- Human-in-the-loop handoffs
- Internal tool-calling sub-agents

**Non-Goal (exclusions):** Agent *definition* format changes, model routing policy, prompt templating rewrites, or Pi infrastructure provisioning (assumed ready).

---

## Architecture Overview

```
┌──────────┐     ┌─────────────────┐     ┌──────────┐
│ Callers  │────▶│ AgentLauncher   │────▶│   Pi     │
│ (API,    │     │ (Migrated to    │     │ Runtime  │
│  Cron,   │     │  Pi Adapter)    │     │          │
│  Tools)  │     └─────────────────┘     └──────────┘
└──────────┘
```

| Concern | Old World | New World (Pi) |
|---------|-----------|----------------|
| Invocation | `POST /agent/launch` or SDK `agent.run()` | Pi adapter → Pi StartAgent RPC |
| Lifecycle | Ad-hoc polling / SSE | Pi Stream with heartbeats & status channel |
| Cancellation | `POST /agent/cancel/:id` | Pi StopAgent RPC |
| Observability | Scattered logs | Pi traces + structured events |
| Policy / Auth | Baked into callers | Pi policy layer (centralized) |
| Sub-agent spawning | Direct recursive call | Pi ChildAgent RPC |

---

## Ticket Plan

### Phase 1 — Discovery & Foundation (Week 1–2)

#### **TICKET-001: Agent Launch Inventory & Call Graph**
| Field | Detail |
|-------|--------|
| **Priority** | P0 — Blocks all downstream tickets |
| **Estimate** | 3 days |
| **Dependencies** | None |
| **Risk** | Low — purely investigative |
| **Description** | Grep/crawl the entire monorepo for every agent-launch codepath: direct HTTP calls, SDK invocations, queue enqueues, sub-agent spawns, and test fixtures. Produce a spreadsheet with: file, line, call pattern, whether it's sync/async, auth context, and expected concurrency. |
| **Acceptance Tests** | 1. Spreadsheet produced with ≥ 95% recall (validate via CI regex lint rule that no `agent.launch`/`agent.run` escapes the inventory). 2. Each entry classified: `sync`, `async`, `stream`, `scheduled`, `sub-agent`. 3. Reviewed by two senior engineers. |

#### **TICKET-002: Pi Client / Adapter Abstraction**
| Field | Detail |
|-------|--------|
| **Priority** | P0 — All migration tickets depend on this |
| **Estimate** | 5 days |
| **Dependencies** | Pi API spec / sandbox instance available |
| **Risk** | Medium — API mismatch between Pi and old system; needs tight feedback loop with Pi team |
| **Description** | Build a thin adapter (`pi-agent-adapter` package/module) that: wraps Pi's gRPC/HTTP StartAgent/StopAgent/StreamStatus into a simple in-process API mirroring the old launcher's interface; handles authentication (token exchange or mTLS); maps old payload schema → Pi schema; emits structured logs. The adapter must be a drop-in signature-compatible replacement where possible, or require minimal mechanical changes. |
| **Acceptance Tests** | 1. Unit tests for: StartAgent → Pi call succeeds (mock Pi server), StopAgent, StreamStatus chunk parsing, auth rotation, retry on transient failure. 2. Integration test against real Pi sandbox: launch a trivial "echo" agent, stream its output, cancel it. 3. Benchmark: adapter adds < 5ms p50 overhead on hot path. |

#### **TICKET-003: Feature Flag & Configuration Skeleton**
| Field | Detail |
|-------|--------|
| **Priority** | P0 |
| **Estimate** | 2 days |
| **Dependencies** | None (parallel with T-001, T-002) |
| **Risk** | Low |
| **Description** | Add a global feature flag (`agent.backend = "pi" | "legacy"`) plus per-call-site overrides. Wire it into config (env, config file, dynamic config if available). The flag gates the dispatch in the soon-to-be-migrated `AgentLauncher` — when `"legacy"`, old codepath executes unchanged; when `"pi"`, adapter is invoked. Add a `/health/pi` endpoint that reports connectivity. |
| **Acceptance Tests** | 1. Toggle `agent.backend=pi` and verify no callers break (they fall through to no-op / unimplemented). 2. `/health/pi` returns 200 when Pi is reachable, 503 when not. 3. Config reload changes flag without restart. |

---

### Phase 2 — Core Migration (Week 3–5)

#### **TICKET-004: Synchronous Agent Launch Migration**
| Field | Detail |
|-------|--------|
| **Priority** | P1 |
| **Estimate** | 5 days |
| **Dependencies** | T-002 (adapter), T-003 (feature flag) |
| **Risk** | Medium-High — this is the most common path; any regression is customer-facing immediately |
| **Description** | Migrate all synchronous (request-response) agent launches identified in T-001. For each: swap old `agent.run()` / `POST /launch` → adapter call; map any caller-specific response parsing; ensure timeout budgets are preserved; update integration tests. Run under feature flag with a 5% canary. |
| **Acceptance Tests** | 1. All existing unit+integration tests pass with flag set to `pi`. 2. Canary: 5% traffic → Pi for 48h with zero 5xx errors and p95 latency ≤ old p95 + 10%. 3. Rollback: flipping flag to `legacy` restores old behavior within one config reload cycle. 4. All agent inputs/outputs semantically identical (run a shadow-mode comparison harness). |

#### **TICKET-005: Streaming Agent Migration**
| Field | Detail |
|-------|--------|
| **Priority** | P1 |
| **Estimate** | 5 days |
| **Dependencies** | T-002, T-003 |
| **Risk** | High — streaming has different error modes (mid-stream failures, backpressure, partial responses) |
| **Description** | Migrate all SSE / WebSocket / chunked-transfer agent calls. Adapter must handle Pi's streaming protocol (likely bidirectional gRPC stream). Add tests for: mid-stream cancellation, network partition, slow consumer backpressure, replay/continuation. |
| **Acceptance Tests** | 1. Stream an agent that emits 1000 tokens; verify all chunks arrive in order with correct inter-chunk latency. 2. Cancel mid-stream; verify Pi receives StopAgent and caller gets clean close. 3. Kill Pi mid-stream; verify caller gets a connection error (not a hang). 4. Backpressure: slow consumer → verify Pi does not OOM. |

#### **TICKET-006: Scheduled & Queue-Driven Agent Migration**
| Field | Detail |
|-------|--------|
| **Priority** | P1 |
| **Estimate** | 3 days |
| **Dependencies** | T-002, T-003, T-004 |
| **Risk** | Medium — scheduling/queue systems have their own retry, dedup, and DLQ concerns |
| **Description** | Migrate cron-triggered agents and queue-worker-invoked agents. These often have: idempotency keys, concurrency limits, retry policies, and dead-letter queues. Ensure Pi's agent lifecycle is compatible — if Pi handles retries natively, disable the old retry layer; if not, wrap adapter. |
| **Acceptance Tests** | 1. Scheduled agent fires at correct time, completes, emits expected output. 2. Queue agent with idempotency key: retried with same key → Pi only executes once. 3. Concurrency limit honored (e.g., max 10 concurrent agents per queue). 4. DLQ: poison agent → lands in dead-letter queue after max retries. |

#### **TICKET-007: Sub-Agent & Recursive Launch Migration**
| Field | Detail |
|-------|--------|
| **Priority** | P1 |
| **Estimate** | 4 days |
| **Dependencies** | T-002, T-004 |
| **Risk** | High — recursive spawning risks unbounded fan-out under Pi; needs guardrails |
| **Description** | Migrate agents that spawn child agents (e.g., tool-calling agents that delegate sub-tasks). Use Pi's ChildAgent RPC (or equivalent) to preserve parent-child linkage in traces. Implement: max depth, max total descendants, timeout inheritance, and budget tracking. |
| **Acceptance Tests** | 1. Parent agent spawns 3 children; all complete; trace shows correct tree. 2. Parent spawns child beyond max depth → child rejected with clear error, parent can handle gracefully. 3. Budget: parent with 60s timeout → children collectively must finish within that window. 4. Fan-out storm: 1000 children attempted from one parent → Pi policy blocks, circuit opens. |

---

### Phase 3 — Hardening & Rollout (Week 6–7)

#### **TICKET-008: Observability Dashboards & Alerts**
| Field | Detail |
|-------|--------|
| **Priority** | P0 — must be done before full rollout |
| **Estimate** | 3 days |
| **Dependencies** | T-004 through T-007 (need real data) |
| **Risk** | Low |
| **Description** | Build Grafana / Datadog dashboards for Pi-launched agents: launch rate, success/failure/cancel rates, p50/p95/p99 latency (e2e and per-phase), Pi connectivity health, adapter error breakdown. Alerts: Pi unreachable > 1min, error rate > 1%, p99 latency > 2x baseline. |
| **Acceptance Tests** | 1. All panels populated with live canary data. 2. Simulated Pi outage triggers alert within < 2 min. 3. Dashboard is reviewed by on-call team and they can diagnose a failing agent from it. |

#### **TICKET-009: Full Traffic Migration & Legacy Code Removal**
| Field | Detail |
|-------|--------|
| **Priority** | P0 |
| **Estimate** | 3 days + bake |
| **Dependencies** | T-008, all Phase 2 tickets stable for 1 week at canary |
| **Risk** | Low (if canary was clean) |
| **Description** | Ramp feature flag: 5% → 25% → 100% over one week with 24h bake at each step. After 100% for 1 week with no incidents: delete all legacy agent-launch code paths, remove the feature flag, and archive old infrastructure configs. |
| **Acceptance Tests** | 1. 100% traffic on Pi for 1 week with zero Pi-specific incidents. 2. After cleanup: `rg "agent.launch\|agent/launch\|agent.run"` returns zero results outside of the Pi adapter itself. 3. Legacy infra is torn down / de-provisioned (verified by infra-as-code diff). |

#### **TICKET-010: Documentation & Runbooks**
| Field | Detail |
|-------|--------|
| **Priority** | P1 |
| **Estimate** | 2 days |
| **Dependencies** | T-004 through T-009 (needs final architecture) |
| **Risk** | Low |
| **Description** | Write: (1) Pi agent lifecycle explainer for developers, (2) how to add a new agent invocation in the new world, (3) on-call runbook: diagnosing Pi agent failures (common error codes, how to replay, how to check Pi dashboard), (4) incident response playbook: Pi outage/degredation. |
| **Acceptance Tests** | 1. A new hire can follow the "add a new agent invocation" doc and deploy a working agent within 1 hour. 2. On-call engineer can diagnose and resolve a simulated Pi agent failure using only the runbook in < 15 min. |

---

## Dependency Graph

```
T-001 (Inventory)
    │
    v
T-002 (Adapter) ◄── T-003 (Feature Flag)
    │                    │
    ├────── T-004 (Sync)─┤
    │        │           │
    │        ├── T-006 (Scheduled)
    │        │
    │        └── T-007 (Sub-Agent)
    │
    └────── T-005 (Streaming)
              │
              ▼
         T-008 (Dashboards)
              │
              ▼
         T-009 (Full Rollout)
              │
              ▼
         T-010 (Docs)
```

---

## Risk Matrix

| Ticket | Risk | Rationale | Mitigation |
|--------|------|-----------|------------|
| T-001 | 🟢 Low | Just code scanning | Cross-reference with APM traces |
| T-002 | 🟡 Medium | Pi API may drift | Weekly sync with Pi team; contract tests |
| T-003 | 🟢 Low | Standard feature-flag work | — |
| T-004 | 🟡 Medium-High | Touches every sync caller | Feature flag + 5% canary + shadow mode |
| T-005 | 🔴 High | Streaming edge cases are subtle | Extensive chaos testing (network partitions, slow consumers) |
| T-006 | 🟡 Medium | Queue semantics can diverge | Pair review with queue infra team |
| T-007 | 🔴 High | Unbounded fan-out | Hard limits in adapter layer + Pi policy |
| T-008 | 🟢 Low | Dashboarding is well-understood | — |
| T-009 | 🟢 Low | Gated on clean canary | Staged ramp with 24h bake per step |
| T-010 | 🟢 Low | Docs are additive | Review by on-call and new-hire simulation |

---

## Rollout Strategy

```
Week 1-2  : T-001, T-002, T-003  (foundations built in parallel)
Week 3-5  : T-004, T-005, T-006, T-007 (core migration — can parallelize by team)
Week 5    : T-008 (dashboards built as soon as T-004 has data)
Week 6    : Canary ramp: 5% → 25% → 100%
Week 7    : T-009 cleanup + T-010 docs
Week 8    : Buffer / bug fixes
```

---

## Success Criteria

1. **Zero** agent launches bypass Pi (enforced by static analysis lint rule post-cleanup).
2. p95 end-to-end agent latency ≤ legacy p95 + 5%.
3. No Sev-1 or Sev-2 incidents attributable to Pi migration during ramp or 30 days post-100%.
4. On-call team self-sufficient on Pi agent diagnosis (measured by incident resolution time ≤ baseline).
5. Legacy agent-launch code and infrastructure fully removed.

---

*Last updated: 2026-06-27 — v1.0*
