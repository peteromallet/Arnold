---
type: brief
slug: m8a-planner-compiler-and-executor-efficiency
title: Megaplan planner, compiler, launcher, and executor efficiency controls
epic: custody-control-plane
created_at: '2026-07-14T00:00:00+00:00'
---

# M8A — Planner/compiler and executor efficiency

## Outcome

Prevent the adjacent orchestration waste exposed by Transaction Spine and
Strategy Roadmap without expanding Run Authority: reject infeasible or
unjustified serial DAGs, split oversized work, compile deterministic validation
outside model calls, bound launcher/provider/compaction/rework loops, adopt
current verified repairs without replay, and open executor circuits before
repeated normalized failures consume another attempt. Scope is no more than two
weeks.

## In scope

- Require a semantic reason for every `depends_on`, represent non-semantic
  ordering as `routing_group`, and compute total work, critical path, maximum
  usable width, seriality, and expected turn demand before finalization.
- Reject unexplained 100% serialization for eight or more tasks and any plan
  whose critical path cannot fit configured turn/time budgets. Emit exact
  diagnostics and safe independent waves for the captured plans.
- For complexity >=7, split implementation from proof/validation or require an
  explicit larger budget and checkpoint contract. Preserve partial productive
  work when proof exhausts its budget.
- Compile no-file, deterministic checks into harness validation jobs with
  command, environment, output, exit, duration, and content-addressed evidence;
  ambiguous or mutating validation remains explicit model/human work.
- Validate a source ref once, suggest a valid audited ref, cap startup attempts,
  and prove source/install/runtime revision equality before worker launch.
- Resolve summary/model route before dispatch; isolate target/runtime imports;
  bound provider timeouts/failover, one compaction per turn by default, rework
  waves to the configured ceiling, and plan-level normalized failure circuits.
- Implement verify-only adoption of an M7 immutable repair receipt against the
  current grant, revision, task contract, tree/commit, tests, result hash, and
  fence. Mismatch quarantines the receipt and uses normal execution.
- Emit the M9 latency/work ledger inputs that distinguish productive work,
  necessary review/proof, queue/idle, retry wait, compaction, validation,
  repair/verification, and replay by task/batch/attempt.

## Out of scope

Run Authority schemas/acceptance semantics, WBC ledger ownership,
TransitionWriter or repair queue/custody policy, status reducer/projection
cutover, production deployment, active-plan rewriting, automatic profile/budget
expansion, or declaring legitimate implementation/review time waste.

## Locked decisions

- Megaplan owns DAG, task, routing, model, and retry policy. Run Authority only
  accepts the resulting exact attempts/claims under grants and fences.
- A dependency without a semantic reason is invalid; routing preference is not
  dependency authority.
- Deterministic validation does not consume a model call.
- Budget exhaustion creates a typed checkpoint/blocker. Two equivalent
  normalized `worker_budget_exhausted` occurrences open a plan circuit before a
  third blind retry, while exact task/attempt identity remains preserved.
- Invalid ref/model/import/provenance and exhausted timeout/compaction/rework
  budgets fail visibly. Ambient or implicit fallback cannot bypass the circuit.
- Repair adoption is verify-only and never trusts a receipt label or rewrites
  immutable attempt evidence.

## Open questions and baselines

- What false-positive rate does the eight-task/full-seriality gate produce on
  the historical corpus, and which explicit, reviewed exception shape is safe?
- What turn-budget estimator and complexity threshold best predicts proof
  exhaustion after the captured baseline? Complexity >=7 is the initial safety
  rule, not a mature empirical claim.
- Exact compaction time and the productive portion of Strategy's 50m20s GLM
  turn are unknown until this milestone emits timings.
- Productive-versus-replayed token/cost baselines are unknown until M9 joins
  these events to accepted outcomes.
- Which external provider outcomes support safe reconciliation versus mandatory
  human escalation?

## Constraints

Consume the M8 exact-version contract and M6 captured fixtures. Do not mutate,
restart, or normalize the investigated live/historical runs. Existing plans get
report-only diagnostics; enforcement starts with newly finalized canary plans.
Any explicit budget/serialization exception is versioned, scoped, evidence-
backed, and cannot grant authority outside the compiled plan.

## Concrete verification

- Replaying the 30-task/29-edge Transaction plan and Strategy plan reports the
  observed serial critical paths and emits safe parallel waves where semantics
  allow; repeated compilation is content-hash identical.
- Complexity-7 T7/T12 and later complexity-8/9 fixtures split implementation
  and proof or fail admission before execution; checkpoints survive budget end.
- Strategy-equivalent T10/T12/T15 validation jobs make zero model calls and
  preserve deterministic pass/fail evidence.
- Invalid `editible-install` ref, dirty/divergent checkout, invalid summary
  model, import leakage, repeated 300-second timeout, repeat compaction, and
  six-task rework fixtures converge within configured bounds with exact reasons.
- Two normalized budget failures open the plan circuit before a third retry;
  unrelated failure signatures do not collide.
- Valid T7/T12-style repair receipts use verify-only adoption and avoid full
  replay; altered revision/task/tree/test/fence fixtures quarantine and execute
  normally.
- Telemetry reconciles total elapsed/calls/tokens/cost to explicit work classes
  or an `unavailable_reason`; no missing measure becomes zero or “waste.”

## Rollout gates

1. Report-only feasibility, complexity, circuit, and work-class telemetry over
   the captured corpus and representative historical plans.
2. Deterministic replay with reviewed false positives and no semantic wave
   widening.
3. New-plan planner/compiler canary with rejection disabled, followed by an
   explicit promotion record for enforcing feasibility on the canary cohort.
4. Executor canary for deterministic validation, bounded retries/rework, and
   verify-only adoption under fake/provider-safe effects.
5. Handoff to M9 only when all counters/decisions carry exact attempt identity
   and M8 authority/conformance remains green.

## Stop and rollback conditions

Stop on unexplained semantic reordering, false repair adoption, duplicate
effect, missing attempt identity, circuit collision across unrelated failures,
unbounded retry/compaction, or source/runtime mismatch. Rollback disables new
plan rejection and executor promotion but preserves diagnostics, immutable
evidence, circuits opened under the new schema, and reconciliation. It may not
restore blind retry, overwrite attempts, or reinterpret old plans by write.

## Handoff and dependencies

Dependency: M8 exact-version runtime/adopter support manifest and M7 immutable
attempt/repair receipt contract. Handoff to M9: compiler feasibility reports,
captured replay hashes, validation-job receipts, circuit/retry/rework policy,
repair-adoption proof, source/runtime preflight receipts, and fully identified
latency/work events.

## Anti-scope

Do not put DAG feasibility or executor policy in the generic authority kernel;
do not increase a model/turn budget automatically to make a plan pass; do not
convert review or high-volume productive code changes into avoidable cost; do
not let a validation classifier execute arbitrary unreviewed effects.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. A bad feasibility or repair-
adoption rule can look efficient in local tests while silently changing task
semantics, accepting stale work, or hiding real cost, so adversarial planning and
review are warranted.
