# Megado run staged — READY, not executed

Location: /Users/peteromalley/Documents/Arnold-oracle-nbf (branch megado-nbf-guard-0826 @ f8725af516)

## Prepared
- .oracle/northstar.md   — durable direction + anti-patterns
- .oracle/custody.md     — immutable baseline (base SHA f8725af516 == origin/main)
- .oracle/agent_goal.md  — frozen contract: worker_disposition control plane,
  three-door wiring, typed deaths, redispatch block, joint model admission,
  structural spy; model policy pinned: Grok4.6 planner/oracle/[XHARD],
  glm-5.3-flash everywhere else
- .oracle/briefs/planner-grok.md — Grok deep-plan brief

## Probes already green
- glm-5.3-flash via omp: verified live ("ok")
- grok CLI present at ~/.grok/bin/grok, headless --prompt-file supported
- fan.py available for parallel glm investigators/executors

## Fire sequence when you say go
1. `grok --prompt-file .oracle/briefs/planner-grok.md -m grok-4.6 --reasoning-effort high`
   → .oracle/plan.md  (the DEEP PLAN)
2. glm sense-check wave on the plan (fan.py, 2–3 lenses)
3. Freeze tasklist after Sol-style... no — oracle=Grok approves; then batched glm executors
4. Per-batch grok oracle gates → rework loop until PASS each batch
5. Final overall review (1–3 grok passes), push megado-nbf-guard-0826 branch,
   main-merge only with your explicit approval at completion review

Say "go" and I launch step 1.
