# Workflow Authoring Examples

This document provides four concise author-facing examples that demonstrate
the native composition contract defined in
`docs/arnold/native-composition-contract.md` and the V2 authoring syntax
defined in `docs/arnold/python-shaped-authoring-contract.md`.

All examples use decorators, function calls, ordinary control flow, and typed
metadata only. They do not use manual graph nodes, manual path strings, trace
schema objects, or validator directives.

The canonical imports for these examples are:

```python
from arnold.pipeline import step, workflow
```

The compatibility aliases `phase` and `pipeline` may be used in place of `step`
and `workflow`. All decorators accept the additive metadata parameters `id`,
`inputs`, `outputs`, and `description` as described in
`docs/arnold/native-composition-metadata-plan.md`.

---

## Example 1 — Single Workflow

A standalone workflow with three sequential steps: plan, execute, and review.
This is the simplest composition form.

```python
from arnold.pipeline import step, workflow


@step(id="plan", inputs={"brief"}, outputs={"plan_doc"})
def plan(brief: str) -> str:
    """Produce a plan document from a brief."""
    ...


@step(id="execute", inputs={"plan_doc"}, outputs={"output"})
def execute(plan_doc: str) -> str:
    """Execute the plan and produce output."""
    ...


@step(id="review", inputs={"output"}, outputs={"verdict"})
def review(output: str) -> str:
    """Review the output and return a verdict."""
    ...


@workflow(id="simple_pipeline", inputs={"brief"}, outputs={"verdict"})
def simple_pipeline(brief: str) -> str:
    plan_doc = plan(brief)
    output = execute(plan_doc)
    verdict = review(output)
    return verdict
```

**Contract points:**

- Each `@step` declares a stable `id`, declared `inputs`, and declared `outputs`.
- `@workflow` declares its own stable identity and IO schema independently of
  its children.
- The workflow body is ordinary imperative Python: each step is a function call
  whose return value feeds the next call.
- The compiler derives a tree-shaped call-site path from the authored call
  sequence. For this example the step paths are `simple_pipeline/plan`,
  `simple_pipeline/execute`, and `simple_pipeline/review`.

---

## Example 2 — Child Workflow Invocation

A parent workflow calls a child `@workflow` as a nested composition unit. The
child workflow is a reusable review sub-process.

```python
from arnold.pipeline import step, workflow


# ── Child workflow ───────────────────────────────────────────────────────


@step(id="critique", inputs={"draft"}, outputs={"findings"})
def critique(draft: str) -> str:
    ...


@step(id="score", inputs={"findings"}, outputs={"score"})
def score(findings: str) -> float:
    ...


@workflow(id="review_subprocess", inputs={"draft"}, outputs={"score"})
def review_subprocess(draft: str) -> float:
    findings = critique(draft)
    return score(findings)


# ── Parent workflow ──────────────────────────────────────────────────────


@step(id="plan_parent", inputs={"brief"}, outputs={"plan_doc"})
def plan_parent(brief: str) -> str:
    ...


@step(id="finalize_parent", inputs={"score"}, outputs={"final"})
def finalize_parent(score: float) -> str:
    ...


@workflow(id="parent_pipeline", inputs={"brief"}, outputs={"final"})
def parent_pipeline(brief: str) -> str:
    plan_doc = plan_parent(brief)
    child_score = review_subprocess(plan_doc)
    return finalize_parent(child_score)
```

**Contract points:**

- `review_subprocess` is a `@workflow` that is called like an ordinary function
  from within `parent_pipeline`.
- The child workflow call introduces a distinct call-site identity. The path
  for the nested steps is `parent_pipeline/review_subprocess/critique` and
  `parent_pipeline/review_subprocess/score`.
- Input mapping is explicit: the parent passes `plan_doc` (which corresponds to
  the child's declared `inputs={"draft"}`) by parameter position.
- Output merge is deterministic: the child's declared `outputs={"score"}`
  becomes the return value at the parent call site.

---

## Example 3 — Same Child Workflow At Two Distinct Call Sites

The same `@workflow` is invoked twice within a single parent, producing two
distinct call-site identities and two distinct tree paths.

```python
from arnold.pipeline import step, workflow


# ── Shared child workflow ────────────────────────────────────────────────


@step(id="review_step", inputs={"draft"}, outputs={"findings"})
def review_step(draft: str) -> str:
    ...


@step(id="verdict_step", inputs={"findings"}, outputs={"verdict"})
def verdict_step(findings: str) -> str:
    ...


@workflow(id="review", inputs={"draft"}, outputs={"verdict"})
def review(draft: str) -> str:
    findings = review_step(draft)
    return verdict_step(findings)


# ── Step used between the two review sites ───────────────────────────────


@step(id="revise", inputs={"draft", "findings"}, outputs={"revised_draft"})
def revise(draft: str, findings: str) -> str:
    ...


# ── Parent workflow with two review call sites ───────────────────────────


@workflow(id="multi_review", inputs={"draft"}, outputs={"verdict"})
def multi_review(draft: str) -> str:
    first_verdict = review(draft)
    revised = revise(draft, first_verdict)
    second_verdict = review(revised)
    return second_verdict
```

**Contract points:**

- The child workflow `review` (stable ID `"review"`) appears at two distinct
  call sites within `multi_review`.
- Each call site receives a distinct path segment. The compiled paths are
  `multi_review/review[0]/review_step`, `multi_review/review[0]/verdict_step`
  for the first invocation, and `multi_review/review[1]/review_step`,
  `multi_review/review[1]/verdict_step` for the second.
- Repeated invocable IDs are not an error. Ambiguity is resolved by the full
  tree path, not by requiring unique invocable IDs.
- The compiler distinguishes call sites by authored call position. No manual
  path strings are used.

---

## Example 4 — Review/Revise Loop

A bounded loop that reviews a draft, breaks on approval, and revises otherwise.
Loop exits are explicit in source via ordinary Python `break`.

```python
from arnold.pipeline import step, workflow


@step(id="review_loop_step", inputs={"draft"}, outputs={"findings", "passed"})
def review_loop_step(draft: str) -> dict:
    """Review a draft. Returns findings and a boolean passed flag."""
    ...


@step(id="revise_loop_step", inputs={"draft", "findings"}, outputs={"revised"})
def revise_loop_step(draft: str, findings: str) -> str:
    """Revise the draft based on review findings."""
    ...


@workflow(
    id="review_loop",
    inputs={"draft"},
    outputs={"final_draft"},
)
def review_loop(draft: str, max_attempts: int = 3) -> str:
    for _ in range(max_attempts):
        result = review_loop_step(draft)
        if result["passed"]:
            break
        draft = revise_loop_step(draft, result["findings"])
    return draft
```

**Contract points:**

- Loop control uses ordinary Python `for` with `break`. No magic-string handler
  return values or hidden router logic.
- Each iteration of `review_loop_step` and `revise_loop_step` produces a
  path coordinate beneath the static body path. The compiler appends a
  monotonic iteration coordinate (e.g. `review_loop/review_loop_step[0]`,
  `review_loop/review_loop_step[1]`) for each loop iteration at runtime.
- `max_attempts` is a typed parameter visible in the workflow signature. The
  compiler does not need to execute the body to discover the loop bound.
- Replay preserves the static path plus recorded iteration coordinates. The
  replay runtime re-executes steps at the same iteration positions rather than
  inventing new topology.

---

## Cross-Reference

| Concept                    | Contract Document                                              |
|----------------------------|----------------------------------------------------------------|
| Import paths, stable IDs   | `docs/arnold/native-composition-contract.md`                   |
| V2 accepted/rejected syntax| `docs/arnold/python-shaped-authoring-contract.md`              |
| Decorator/IR metadata      | `docs/arnold/native-composition-metadata-plan.md`              |
