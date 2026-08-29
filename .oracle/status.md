# Megado run resumed — custody/source reconciliation

Location: /Users/peteromalley/Documents/Arnold-oracle-nbf (branch megado-nbf-guard-0826)

Resume audit 2026-08-29: refreshed `origin/main` is `798c506192`; current branch
HEAD before rebase is `004540970f`. The checked-in `.oracle/tasklist.md` is a
foreign onboarding-run artifact and is NOT execution-ready for this NBF goal.
Next: preserve resume artifacts, rebase the five NBF-only commits onto the
refreshed source SHA, then have Sol produce/validate the NBF plan and tasklist.
Model policy: Luna normal; Sol planner/oracle/`[XHARD]`.

## Prepared
- .oracle/northstar.md   — durable direction + anti-patterns
- .oracle/custody.md     — immutable baseline (base SHA f8725af516 == origin/main)
- .oracle/agent_goal.md  — frozen contract: worker_disposition control plane,
  three-door wiring, typed deaths, redispatch block, joint model admission,
  structural spy; model policy pinned: Sol planner/oracle/[XHARD],
  Luna everywhere else
- .oracle/briefs/planner-grok.md — Grok deep-plan brief

## Probes already green
- glm-5.3-flash via omp: verified live ("ok")
- grok CLI present at ~/.grok/bin/grok, headless --prompt-file supported
- fan.py available for parallel glm investigators/executors

## Resume sequence now authorized
1. Rebase preserved NBF artifacts onto refreshed `origin/main`.
2. Sol plans/revises and produces the NBF execution contract.
3. Luna settled-plan sense-check wave; Sol freezes classifications/tasklist only
   after a fresh independent Luna contract review passes.
4. Batched Luna execution, with any exceptional `[XHARD]` kernel routed to Sol.
5. Per-batch Sol oracle gates → rework loop until PASS each batch.
6. Final overall review (1–3 independent Luna passes), push megado-nbf-guard-0826 branch,
   main-merge only with your explicit approval at completion review

## Plan evolution log
- Entry 13 -> T7 cooldown-aware scheduling conditions (codex ADD; criterion 7)
- Entry 14 -> T8 typed provider_degraded scheduling condition (grok ADD;
  criterion 8; full spec .oracle/findings/evolution-entry14.txt)
- Foundation commits on main: a9e1c7d0d6, af370f5ec6 (cooldown/deferral), plus
  catalog/pin/timeout fixes f8725af516..ff4c64835b
