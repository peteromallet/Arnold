# Root-cause (config/policy lens): why critique rounds were unbounded

**Verdict:** No config knob — at any robustness, profile, or depth — sets a
numeric ceiling on critique rounds. The round count is driven entirely by how
many times the LLM **gate** emits `ITERATE`. Robustness only changes the *shape*
of the workflow graph (whether the iterate-back edge exists at all), not a count.
`thorough`/`extreme` do not "uncap" — they simply inherit the base graph's
already-uncapped loop, while `light`/`bare` structurally remove the loop, which
is why those milestones ran exactly 1 round.

## Knob inventory

| Knob | Default | What it actually toggles | file:line |
|---|---|---|---|
| `robustness` (bare/light/full/thorough/extreme) | `full` | Selects a workflow override dict + level chain. `thorough`={} and `extreme`={} → **inherit base WORKFLOW unchanged** (uncapped loop). `light` replaces `STATE_CRITIQUED` with a single `revise→STATE_GATED` edge (no loop). `bare` skips critique entirely. | `_core/workflow_data.py:91-122` |
| (base loop) `STATE_CRITIQUED` graph | — | `revise→STATE_PLANNED` on `gate_iterate` with **no count condition** → re-critique loop runs while gate says ITERATE | `_core/workflow_data.py:56-66` (esp. L58) |
| `robustness_critique_instruction` | — | Only `light` gets a "pragmatic, fewer flags" prompt; **thorough/full/extreme share the identical "balanced judgment" string** — thorough does not even raise critique strictness | `_core/workflow.py:87-90` |
| `adaptive_critique` (bool) | `False` | Routes the critique **evaluator** to pick lenses + a per-lens `critic_model` from the 9-lens roster. Changes WHO critiques / WITH WHAT model — **not** round count | `_core/workflow.py:72-74`; `audits/critique_evaluator.py:37,73` |
| `critic_model` (pin) | `""` | Pins the critic model for adaptive lenses; `""` = dynamic. No effect on rounds | `types.py:686,696-703` |
| `strict_adaptive_critique` | `False` | Raises instead of silently falling back to static lenses. No effect on rounds | `types.py:688-689` |
| `profile` (e.g. premium/apex) | none | Stored in config; rewrites **per-phase model/effort routing** only | `handlers/init.py:227-228`; `profiles/__init__.py` |
| `depth` (low/high) | none | Rewrites model/effort for **author-side phases only** (plan/revise/tiebreaker); critique/gate/review explicitly excluded | `handlers/init.py:233-234`; `profiles/__init__.py:63-73` |
| `max_iterations` (driver) | `200` | Hard cap on **whole-state-machine** driver iterations (covers execute/review too), not critique rounds. 9 rounds is far under 200 → never trips | `auto.py:64,1232`; `_pipeline/executor.py:343` |
| `max_review_rework_cycles` | `3` | Caps **post-execute** review↔execute rework, a different loop | `auto.py:115`; `types.py:678` |
| `max_blocked_retries` / `max_context_retries` | `1` / `2` | Retry caps for blocked/context-overflow, unrelated to critique | `auto.py:76,110` |
| gate iteration warnings | — | Soft advisory text at `iteration>=5` and `>=12` injected into the gate prompt; **advisory only, no enforcement** | `orchestration/gate_signals.py:208-213` |
| `build_orchestrator_guidance(robustness=...)` | — | `robustness` param is accepted then **`del`-eted unused** — guidance never varies by robustness | `orchestration/gate_checks.py:91,150-151` |

## Does any knob bound rounds?
No. The only structural bound is `light`/`bare` removing the iterate edge
(`workflow_data.py:103-113`). The only numeric bound is the driver's
`max_iterations=200`, which counts the entire pipeline, not critique rounds.
At `thorough`/`extreme`/`full` the loop continues purely on the gate LLM's
`ITERATE` judgment, modulated by soft warnings the model may ignore.

## Intentional or oversight?
**Oversight in the count dimension, intentional in the shape dimension.** The
design philosophy ("higher robustness = keep iterating until the gate is
satisfied") is deliberate — there is intentionally no `thorough`-specific cap.
But the absence of *any* numeric backstop on a non-deterministic LLM gate is a
gap: M2's 9 rounds and M4's 8 show the gate can fail to converge and there is no
policy-level circuit breaker. Evidence it was unintended: the soft warnings at
iter 5/12 (`gate_signals.py:208-213`) plus the plateau/recurring-critique
force-proceed *hint* (`gate_checks.py:125-129`) show the authors anticipated
runaway loops but only ever **suggested** stopping, never enforced it.

## Config-level fix that bounds without losing thoroughness
Add a robustness-scoped `max_critique_rounds` (e.g. full=4, thorough=6,
extreme=8) checked at the `gate_iterate` transition / in the driver loop: when
exceeded, downgrade the effective recommendation from `ITERATE` to `ESCALATE`
(or auto force-proceed under `auto`). This preserves "thorough iterates more"
while guaranteeing termination. Cheapest hook: enforce the existing iter>=12
warning as a hard `ESCALATE` in `build_gate_signals`/the gate handler instead of
a prompt string the LLM can ignore.
