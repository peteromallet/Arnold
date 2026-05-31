# B — Completion-Verification Contract

**Problem (settled):** "done" is a self-reported plan-state string trusted verbatim.
`chain/__init__.py:1418-1426` copies `DriverOutcome.status` into the milestone record;
`status` is `"done"` whenever `state.json current_state == "done"` (`auto.py:1363-1369`).
No phase boundary checks *objective* evidence that work happened, the suite is green, or
the milestone's own coverage was met. `merge_policy:auto` is dead config — the PR/merge
block is gated on `use_pr = push_enabled and bool(milestone.branch)` (`chain/__init__.py:1211`),
so a branchless milestone never reaches the merge code where policy is read.

The fix is **not** four strictness patches. It is one reusable abstraction that sits at
*every* terminal transition and demands evidence. megaplan already has the bones:
`PhaseResult` (`orchestration/phase_result.py`) is the canonical phase-exit record, and
evidence collectors already exist — `validate_execution_evidence` (landed-diff vs claimed,
`orchestration/execution_evidence.py:15`), `_latest_execution_batch_all_tasks_done`
(`chain/__init__.py:968`), `_capture_test_baseline` (`handlers/finalize.py:495`). They are
*uncomposed and advisory*. We compose them behind one predicate and make the state machine
**refuse** the terminal transition until it passes.

## 1. The abstraction: `CompletionContract`

A phase declares the evidence it owes; a verifier gathers it; the state machine accepts the
terminal transition only on a satisfied verdict. New module
`megaplan/orchestration/completion_contract.py`.

```python
class EvidenceVerdict(str, Enum):
    satisfied = "satisfied"        # objective evidence present
    unsatisfied = "unsatisfied"    # evidence absent or contradicts the claim  -> FAIL LOUD
    not_applicable = "not_applicable"  # honestly waived for THIS work (see §3)

@dataclass(frozen=True)
class EvidenceResult:
    evidence: str                  # e.g. "landed-diff"
    verdict: EvidenceVerdict
    detail: str                    # human-readable, surfaced on failure
    facts: dict[str, Any]          # the raw observed numbers (diff paths, fail count...)
    waiver: "Waiver | None" = None # populated iff not_applicable

class Evidence(Protocol):           # one instance per evidence class
    name: str
    def collect(self, ctx: "CompletionContext") -> EvidenceResult: ...

@dataclass(frozen=True)
class CompletionContext:            # everything an Evidence needs; no LLM, no plan-state trust
    plan_dir: Path
    project_dir: Path
    state: dict[str, Any]           # read-only snapshot
    phase: str                      # "execute" | "review" | milestone-"done"
    git_base_ref: str | None        # branch point / baseline commit for landed-diff
    baseline: dict[str, Any]        # finalize.json baseline_test_failures et al.

@dataclass(frozen=True)
class CompletionContract:
    phase: str
    required: tuple[Evidence, ...]
    def verify(self, ctx: CompletionContext) -> "CompletionReport": ...

@dataclass(frozen=True)
class CompletionReport:
    phase: str
    results: tuple[EvidenceResult, ...]
    @property
    def passed(self) -> bool:
        return all(r.verdict != EvidenceVerdict.unsatisfied for r in self.results)
    def to_phase_result_deviations(self) -> tuple[Deviation, ...]: ...  # reuse phase_result.Deviation
```

The contract is **purely a function of observable facts** (git, artifacts, the suite). It
never reads `current_state` or `review_verdict` as proof — those are the *claims* being
checked, not evidence.

## 2. Evidence classes (composable, phase-agnostic)

Each is an `Evidence` implementation wrapping a helper that already exists:

- **`landed_diff`** — wraps `validate_execution_evidence` + a `git diff --stat <base_ref>..HEAD`.
  `satisfied` iff the working tree / branch carries a non-empty diff *and* claimed
  `files_changed` are covered by it (kills the "abandoned after planning, zero diff" case).
- **`green_suite`** — runs the configured `test_command` (reusing `_capture_test_baseline`'s
  runner) and diffs failures against `baseline_test_failures`. `satisfied` iff
  `current_failures ⊆ baseline_failures` (no *new* RED). This is the gate that does not exist
  anywhere today; it compares against baseline so a pre-existing-red repo isn't blamed.
- **`phase_coverage`** — every planned unit terminal: `_latest_execution_batch_all_tasks_done`
  for execute; for milestone-done, every success criterion is `pass` or carries a typed
  `deferred_human`/waiver (reusing `verifiability.classify_criteria`, `handlers/execute.py:224`).
- **`worker_did_work`** — `cli_provenance` / batch records show ≥1 tool call OR a non-empty
  diff. `unsatisfied` for a 0-tool-call session that also produced no diff (kills "0 tool
  calls accepted").

**Composition:** an `Evidence` is independent and returns one `EvidenceResult`; a
`CompletionContract` is just an ordered tuple of them. Contracts are *additive* across phase
types — `EXECUTE_CONTRACT = (worker_did_work, phase_coverage, landed_diff)`;
`MILESTONE_DONE_CONTRACT = EXECUTE_CONTRACT + (green_suite, criteria_coverage)`. New phases
(critique-done) declare their own tuple. The same `Evidence` instance is reused verbatim
across phases — that is the generalization.

## 3. Anti-brittleness: honest no-op PASSES, silent abandonment FAILS

The discriminator is **declared intent vs observed fact**, never strictness alone. We add a
typed `Waiver`, authored by the plan/finalize artifact (not by free-text LLM prose):

```python
@dataclass(frozen=True)
class Waiver:
    evidence: str          # which evidence is waived: "landed-diff" | "green-suite"
    reason_code: str       # enum: docs_only | intentionally_deferred | no_op_by_design | external_blocker
    declared_in: str       # artifact + field that authored it, e.g. "finalize.json:tasks[2].deferral"
    note: str
```

An `Evidence` returns `not_applicable` **only** when it finds a matching typed `Waiver` in the
plan's *own committed artifacts* — i.e. the plan declared up front "this milestone is
docs-only / deferred", and that declaration is itself evidence on disk. So:

- **Docs-only milestone:** `landed_diff` still requires a diff (the docs!), but `green_suite`
  finds a `docs_only` waiver in finalize.json → `not_applicable`. Passes honestly.
- **Intentionally deferred:** a `deferred_human` / `intentionally_deferred` criterion with a
  typed deferral record → `phase_coverage` counts it satisfied. Passes.
- **Silent abandonment** (planned then quit): no waiver, no diff, no tool calls →
  `landed_diff` + `worker_did_work` both `unsatisfied`. **Fails loud.** There is no waiver to
  hide behind, because abandonment never *declares* itself — that asymmetry is the whole
  defense. Strictness is uniform; what differs is whether the plan put an honest, typed,
  on-disk intent record next to the missing evidence.

This also makes the contract *self-documenting*: every `not_applicable` carries the artifact
path that justified it, so a reviewer can audit waivers.

## 4. Architecture & hooks

`completion_contract.py` lives in `orchestration/` (no deps on `auto`/`chain`), so both
drivers and any future pipeline import it. It consumes only `plan_dir`, `project_dir`,
artifacts, and git — the same inputs the helpers already take.

- **Single-plan driver (`auto.py`).** Before stamping a terminal `"done"` at
  `auto.py:1363-1369`, build `CompletionContext` and run `MILESTONE_DONE_CONTRACT.verify(ctx)`.
  If `not report.passed`, do **not** return `status="done"`; return a new terminal
  `status="verification_failed"` (add to the `DriverOutcome.status` literal set at
  `auto.py:135` and the dispatch table at `auto.py:2450+`). Emit the deviations into the final
  `PhaseResult`.
- **Phase boundaries.** Wrap the two existing self-promotions: `handlers/execute.py:211-272`
  (execute stubbing an approved review → DONE) and `handlers/review.py:248-252` (force-proceed
  at rework cap) call `EXECUTE_CONTRACT.verify`/`MILESTONE_DONE_CONTRACT.verify` before writing
  `STATE_DONE`. The rework-cap force-proceed becomes "force to a *blocked/awaiting-human*
  terminal", never to `done`, when evidence is unsatisfied.
- **Chain (`chain/__init__.py`).** At `1418-1426`, do not trust `outcome.status`. Re-verify:
  `report = MILESTONE_DONE_CONTRACT.verify(ctx_for(plan_dir))`; record
  `status = "done" if report.passed else "verification_failed"` plus the report into
  `state.completed`. This is also where the **dead `merge_policy`** is fixed: gate the PR block
  on `report.passed`, not on `bool(milestone.branch)` — a branchless milestone still gets
  verified, and `merge_policy:auto` becomes reachable because verification, not branch
  presence, drives advancement.

Reuse, not reinvention: `landed_diff`→`execution_evidence.validate_execution_evidence`;
`phase_coverage`→`_latest_execution_batch_all_tasks_done` (`chain/__init__.py:968`);
`green_suite`→refactor `_capture_test_baseline` (`finalize.py:495`) into a shared
`run_suite(project_dir, config)` both baseline-capture and the evidence call;
`criteria`→`verifiability.classify_criteria`.

## 5. Compose with fail-loud

Today the default is **silent success**: absent a check, you get `done`. The contract inverts
the default to **fail-closed**: a terminal transition is *denied* unless every required
evidence is `satisfied` or honestly `not_applicable`. A failure surfaces as:

1. A typed terminal `verification_failed` outcome (never silently downgraded — cf. the gate
   TIEBREAKER→ITERATE silent-downgrade memo), carrying the `CompletionReport`.
2. Each `unsatisfied` becomes a `phase_result.Deviation` (`phase=…, kind="completion_evidence",
   message=detail`) written to `phase_result.json`, so the existing auto-driver routing and
   `megaplan-observe` already render it.
3. A human-readable block: which evidence failed, the observed facts (diff paths, new
   failures, tool-call count), and — critically — *"to pass honestly, declare a typed Waiver
   in finalize.json"*. The remedy is named, so deferral stays a first-class, auditable act
   rather than a silent escape.

The contract turns "done" from a string the plan asserts into a verdict the harness *earns*.

---

### 5-line design summary

1. One `CompletionContract` = ordered tuple of composable `Evidence` collectors; verified at every terminal transition from objective facts (git/suite/artifacts), never from `current_state` or LLM verdicts.
2. Four reusable evidence classes — `landed_diff`, `green_suite`, `phase_coverage`, `worker_did_work` — each wrapping an *existing* helper; contracts are additive per phase (execute ⊂ milestone-done).
3. Honest no-ops pass via typed on-disk `Waiver`s (docs_only / intentionally_deferred) authored by plan artifacts; silent abandonment has no waiver and so fails loud — the asymmetry is the defense.
4. Lives in `orchestration/completion_contract.py`; hooked at `auto.py:1363`, `chain/__init__.py:1418`, `execute.py:211`, `review.py:248`; fixes dead `merge_policy` by gating advancement on `report.passed` instead of `bool(milestone.branch)`.
5. Fail-closed default: terminal transition denied unless all evidence `satisfied`/`not_applicable`; failures surface as a typed `verification_failed` outcome + `phase_result.Deviation`s naming the missing facts and the waiver remedy.
