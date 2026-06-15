## Shared context (read first)

You are one of 10 independent investigators examining the megaplan codebase at the
current working directory (`--project-dir`). A large ~2–3 month refactor is being
*considered* — its design is in `.megaplan/briefs/pipeline-unification-planning-as-pack.md`.
**READ THAT BRIEF FIRST** (it's ~675 lines; read it fully). In one line: it collapses
megaplan's *dual* control flow — the legacy `COMMAND_HANDLERS` dispatch + `auto.py`
subprocess-shelling path, versus the `run_pipeline`/`run_pipeline_with_policy` executor
path — into a SINGLE execution path, relocates "planning" into a discovered pipeline
*pack*, and later generalizes to a capabilities model + pluggable execution "realizers".

**YOUR JOB IS NOT TO CRITIQUE OR IMPROVE THAT REFACTOR.** Assume it WILL happen.
Your job: scrutinize the **foundational subsystem assigned to you below** — the *ground
this refactor will stand on* — and find structural weakness, rot, hidden coupling,
fragility, or design debt that is **more foundational than the refactor itself** and
that would **bite us if we build the refactor on top of it as-is**. The question to
keep asking: "if we pour the unification concrete on top of THIS, what cracks?"

Concretely hunt for, in your subsystem:
- Hidden global/implicit state, singletons, import-time side effects, ordering deps.
- Leaky or absent abstractions, God objects, things that "work" only by coincidence.
- Untested or untestable code paths (no tests = a foundation you can't refactor safely).
- Inconsistent contracts / multiple sources of truth / silent fallbacks that mask bugs.
- Coupling that the brief's authors did NOT notice (they did 3 investigation waves +
  a 10-agent claim-verification ledger — §13 — so the obvious stuff is known; find what
  they MISSED or under-weighted).
- "Fix-this-first" candidates: cheap, decoupled hardening that de-risks the big refactor.

Method: investigate the actual code FIRST (use your file/search tools; cite real
`path:line` evidence). Try to FALSIFY your own concerns before reporting them — do not
hand back speculation. Distinguish "confirmed in code" from "suspected".

Output (STRICT, < 600 words, no preamble, no flattery):
1. A ranked list (most → least foundational-risk) of issues in YOUR subsystem.
2. For each: `path:line` evidence • severity (BLOCKER / SHOULD-FIX-FIRST / WATCH) •
   one sentence on *why it undermines the unification* • a concrete fix-first action.
3. End with: the single thing in your subsystem you'd fix BEFORE touching the refactor,
   and one coupling/risk you suspect the brief MISSED.
