# Completion Verification Contract

The right fix is a reusable **completion contract**: an objective, typed predicate that sits between "a phase reports terminal" and "the driver accepts terminal." The phase may still say "I am done"; the state machine does not believe it until a contract validates independent evidence. This should not be a milestone-only patch. It should become the generic exit boundary for every pipeline phase and for aggregate boundaries such as a chain milestone.

The existing code already has the first half of this idea. `megaplan/orchestration/phase_result.py` defines `PhaseResult` as the explicit auto-to-phase boundary, and `auto.py` reads it after each handler run. But the terminal plan boundary bypasses that discipline: at `auto.py:1363-1389`, `STATE_DONE` is translated directly to `DriverOutcome(status="done")`; then `chain/__init__.py:1418-1426` persists that status into the completed milestone. The contract should extend `PhaseResult` from "how did the subprocess exit?" to "what objective evidence authorizes the transition?"

## Proposed Abstraction

Add `megaplan/orchestration/completion_contract.py`:

```python
@dataclass(frozen=True)
class CompletionSubject:
    kind: Literal["phase", "plan", "milestone"]
    name: str
    from_state: str | None
    to_state: str
    phase: str | None = None
    plan_name: str | None = None
    milestone_label: str | None = None

@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    status: Literal["pass", "fail", "waived", "not_applicable", "deferred_human"]
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CompletionVerdict:
    accepted: bool
    outcome: Literal["accepted", "blocked", "awaiting_human"]
    subject: CompletionSubject
    evidence: tuple[EvidenceRef, ...]
    failures: tuple[str, ...] = ()
    resume_cursor: dict[str, Any] | None = None

class CompletionContract(Protocol):
    id: str
    def required_evidence(self, ctx: CompletionContext) -> tuple[EvidenceSpec, ...]: ...
    def evaluate(self, ctx: CompletionContext) -> CompletionVerdict: ...
```

`CompletionContext` is the adapter layer: `root`, `project_dir`, `plan_dir`, optional `ChainSpec`, optional `Milestone`, current `PlanState`, latest `PhaseResult`, baseline commit, current git snapshot, and command runner. Evidence collection is factored:

```python
class EvidenceProvider(Protocol):
    kind: str
    def collect(self, ctx: CompletionContext, spec: EvidenceSpec) -> EvidenceRef: ...
```

The important design choice: contracts compose evidence providers, not bespoke checks. `PlanDoneContract` and `MilestoneDoneContract` are thin policies over shared evidence.

## Evidence Classes

Use these core providers:

1. **Phase coverage evidence.** Confirms the required phase boundary actually ran for the current invocation: fresh `phase_result.json`, matching `phase`, `exit_kind == success`, expected artifacts written, and state history contains the phase result for this plan iteration. This generalizes to "is critique really done?" or "did execute really finish?" without asking an LLM.

2. **Worker activity evidence.** For execution-like phases, proves the worker session did real work or explicitly produced a no-op decision. It should count durable activity, not just tokens: tool calls in the worker transcript/store, commands run, files read/edited, task status updates, or a typed no-op artifact. A 0-tool-call worker may pass for pure planning if the phase contract allows prose-only output, but cannot pass execute unless paired with no-op evidence.

3. **Landed diff evidence.** Compares a checkpoint captured at phase or milestone start with the current tree or PR head. It reports changed files, commits, PR number/state if present, and whether changed paths match executor claims. This should reuse and harden the existing `megaplan/orchestration/execution_evidence.py` logic, which already catches phantom file claims, unclaimed changes, pending tasks, blocked-without-notes, and hollow done tasks.

4. **Green suite evidence.** Runs the configured `test_command` after execution or before plan/milestone completion. `finalize.py:495-525` captures only a baseline; the new provider records `verification_test_command`, exit code, duration, truncated output reference, and failure summary. For docs-only or prose plans it can be `not_applicable`; for code plans with no detectable/configured test command it should be `deferred_human` or `blocked` depending on policy.

5. **Review disposition evidence.** Review can still be part of the story, but never sole authority. It validates `review.json` criteria and unresolved flags. If `review.py:248-252` force-proceeds after the rework cap, this evidence is `fail` with unresolved issues rather than being converted to success.

6. **Declared no-op evidence.** A signed, structured artifact such as `completion/noop.json`:

```json
{
  "kind": "noop",
  "reason": "Already satisfied by existing code",
  "scope_checked": ["tests/test_x.py", "src/x.py"],
  "commands_run": ["pytest tests/test_x.py -q"],
  "evidence": ["existing function handles case Y"],
  "accepted_by_phase": "execute"
}
```

This is how honest no-op work passes. Silent abandonment fails because it has neither landed-diff evidence nor a declared no-op with inspection and verification.

## Policy Without Brittleness

The default `PlanDoneContract` should be strict but mode-aware:

```python
PlanDoneContract = AllOf(
    PhaseCoverage(["plan", "critique", "gate", "finalize", "execute"], mode_aware=True),
    AnyOf(LandedDiff(), DeclaredNoop()),
    WorkerActivity(min_tool_calls=1, unless=DeclaredNoop()),
    GreenSuite(mode="required_for_code_changes"),
    ReviewDisposition(no_unresolved_must=True),
)
```

This avoids over-strictness by making evidence conditional, not optional-by-default. Docs-only work can satisfy `LandedDiff` with markdown/doc output and mark test evidence `not_applicable`. Config-only or generated-file work can pass with changed files plus a narrower verification command. A true "nothing to do" must say so in a typed no-op artifact and show what was checked. Intentionally deferred work does not become `done`; it becomes `awaiting_human` or `blocked` with a resume cursor and a visible `latest_failure`.

For `bare` robustness, `execute.py:211-222` currently writes `STATE_DONE` directly. Under this design, bare can select a lighter contract, but it cannot select no contract. It might skip review disposition, but it still needs phase coverage plus either diff or declared no-op.

## Architectural Placement and Hooks

Put the generic machinery under `megaplan/orchestration/`:

- `completion_contract.py`: dataclasses, interfaces, contract combinators.
- `completion_evidence.py`: provider implementations.
- `completion_policies.py`: `contract_for_transition(subject, ctx)`.
- `completion_io.py`: atomic write/read of `completion_verdict.json`.

Handlers may emit supporting evidence, but drivers own acceptance. That keeps the trust boundary outside the worker/LLM path.

Hook `auto.py` at the terminal transition block. Before `auto.py:1370` logs terminal and before `auto.py:1377` emits `PLAN_FINISHED`, call:

```python
if state == STATE_DONE:
    verdict = verify_completion(
        CompletionSubject(kind="plan", name=plan, from_state=last_state,
                          to_state=STATE_DONE, plan_name=plan),
        ctx,
    )
    write_completion_verdict(plan_dir, verdict)
    if not verdict.accepted:
        _record_lifecycle_failure(
            plan_dir=plan_dir,
            kind="completion_verification_failed",
            message="plan reached done without required evidence",
            current_state=STATE_BLOCKED,
            resume_cursor=verdict.resume_cursor,
            suggested_action="Inspect completion_verdict.json and satisfy or waive failed evidence.",
            metadata={"failures": verdict.failures, "evidence": [e.__dict__ for e in verdict.evidence]},
        )
        return _outcome("blocked", final_state=STATE_BLOCKED, iterations=iteration,
                        reason="completion verification failed", last_phase=last_phase,
                        blocking_reasons=list(verdict.failures))
```

Hook `chain/__init__.py` twice. At `chain/__init__.py:1231-1239`, before recording a PR-merged milestone as done, verify the milestone subject against the merged PR/head. At `chain/__init__.py:1417-1426`, replace the unconditional append with `verify_completion(kind="milestone")`; only append `status: "done"` when accepted. If blocked, return chain status `blocked`/`stopped` with the verifier's failures. This also fixes dead `merge_policy`: merge/PR evidence becomes one possible provider, not the enclosing condition for completion.

For phase boundaries, call the same verifier after `_run_phase` returns a successful `PhaseResult` and before letting status advance. A `CritiqueDoneContract` can require fresh critique artifact, configured critic count, and non-empty findings/explicit no-issue rationale. `ExecuteDoneContract` can require worker activity, task coverage, diff/no-op, and optional command evidence.

## Failure Surface

Verification failure must be loud and durable. It should:

- leave the plan non-terminal (`blocked`, not `done`);
- write `completion_verdict.json` with every evidence result;
- record `latest_failure.kind = "completion_verification_failed"`;
- emit an observability event such as `COMPLETION_VERIFICATION_FAILED`;
- expose failures in `megaplan status` and chain status;
- include an explicit override path requiring a human-authored waiver reason.

The override should not mutate failed evidence into pass. It should add `EvidenceRef(status="waived", kind="human_waiver", details={...})`, preserving the fact that objective verification failed. That matches the harness philosophy: failures can be accepted by humans, but they cannot disappear.

The core invariant becomes: **a terminal state is a claim; a completion verdict is the authority.** That single invariant closes the observed holes: abandoned planning has no diff/no-op and fails; red tests fail green-suite evidence; 0-tool-call execute fails worker-activity evidence unless it produced a real no-op artifact; and chain milestones can no longer advance by copying a self-reported string.
