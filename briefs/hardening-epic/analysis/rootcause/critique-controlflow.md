# Root cause — critique/review non-convergence (control-flow / loop-termination lens)

## TL;DR
The plan-critique loop (`critique → gate → revise → critique`) has **no round
ceiling anywhere**. The execute-review loop *does* (`review.py:248`), and the
driver mirrors that review cap (`auto.py:1477`). The critique loop was left out
of both. The exact missing guard belongs in
`megaplan/handlers/gate.py:360-361`.

## 1. There is no single "loop" — the loop is the state machine
`run_parallel_critique` (`orchestration/parallel_critique.py:165-233`) is
**one-shot**: it scatters N checks, gathers, returns. No iteration inside it.

The actual round-driver is the auto loop in `auto.py:1232`:

```python
iteration = 0
while iteration < max_iterations:          # auto.py:1232  (max_iterations=200)
    ...
    next_step = status.get("next_step")     # auto.py:1291
    ...
    cmd = _phase_command(next_step) + ["--plan", plan]   # auto.py:1757
```

Each pass dispatches one phase subprocess. The *handlers* decide the next
state, so the rounds are produced by the state cycle:

`critique` → `STATE_CRITIQUED` → `gate` →(ITERATE)→ `revise` →
`revise_transition.next_state` = **`STATE_PLANNED`** (`critique.py:598`,
`_resolve_revise_transition` gate.py:149) → `critique` again. Forever.

## 2. CONTINUE vs EXIT — and why every existing cap missed
The gate's branch table (`_apply_gate_outcome`, gate.py:294-368) is the only
place that can break the cycle, by returning `finalize` instead of `revise`:

```python
if gate_summary["recommendation"] == "ITERATE":     # gate.py:360
    return result, "revise", summary, []            # gate.py:361  <-- unconditional
```

There is **no counter, no ceiling, no convergence check** on this branch. As
long as the gate keeps saying ITERATE (M2: 9 rounds; M4: identical 9 check_ids),
it keeps returning `revise`.

Why the existing guards didn't fire:
- **`max_iterations=200`** (auto.py:64,1232): a hard *subprocess* cap, not a
  per-loop cap. 9 critique rounds ≈ 27+ phase dispatches — nowhere near 200.
- **Stall detection** (auto.py:1505 `if state == last_state`): the critique loop
  *changes* state every round (CRITIQUED→PLANNED→CRITIQUED), so `state ==
  last_state` is false and `stall_count` never accrues. Stall detection is
  structurally blind to a *progressing-but-non-converging* loop.
- **`rework_cycles_observed` cap** (auto.py:1477-1502): keyed **only** on
  `review.json` mtime (`_get_review_marker`, auto.py:1462). It counts
  *execute-review* cycles, never critique/gate. Comment at auto.py:1457 confirms
  the scope: "a fresh review.json means a real review pass completed."
- **add-note escalation** (auto.py:1720): only reachable when the gate returns
  **ESCALATE** (gate.py:362-363). A gate stuck on **ITERATE** never routes here.

## 3. Plan-critique vs execute-review: DIFFERENT termination logic
They are governed by completely separate code, and only one is capped:

| Loop | Cap location | Mechanism |
|------|-------------|-----------|
| execute→review→rework | `review.py:244-254` | counts `prior_rework_count` from `state["history"]`, force-proceeds to DONE at `max_review_rework_cycles` (=3) |
| | `auto.py:1477` | driver belt-and-braces mirror |
| **plan→critique→gate→revise** | **none** | gate returns `revise` unconditionally |

The review path even has a robustness-tiered cap key
(`max_robust_review_rework_cycles`, review.py:238-243). The critique path has no
equivalent at all.

## 4. Exact missing-guard location + minimal fix
**File:line: `megaplan/handlers/gate.py:360-361`** (inside `_apply_gate_outcome`).

This is the symmetric partner of `review.py:248`. The minimal correct guard
counts prior ITERATE gate rounds (same pattern review uses) and, at the cap,
stops looping — escalate to a human (ESCALATE → add-note) rather than silently
proceeding, since the plan never converged:

```python
if gate_summary["recommendation"] == "ITERATE":
    cap = get_effective("orchestration", "max_critique_iterations")  # NEW config
    prior = sum(
        1 for e in state.get("history", [])
        if e.get("step") == "gate" and e.get("result") in ("blocked", "success")
        and e.get("recommendation") == "ITERATE"        # or count revise steps
    )
    if prior >= cap:
        gate_summary["rationale"] += f" [critique cap {cap} reached — escalating]"
        return result, "override add-note", summary, []   # break the cycle
    return result, "revise", summary, []
```

A belt-and-braces driver mirror should also be added near `auto.py:1477`, keyed
on `critique_v*.json` / `gate_signals_v*.json` version count the same way the
review cap is keyed on `review.json` mtime — so config drift on the handler cap
still can't spin indefinitely.

**Defaults note:** `execution.max_review_rework_cycles=3` exists in
`types.py:677`; there is **no** `max_critique_iterations` default in
`types.py:676-723` — the config knob itself does not exist, which is the deepest
form of "unset by default."
