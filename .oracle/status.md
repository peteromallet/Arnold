# NBF execution contract frozen — 2026-08-29

- State: `FROZEN`; implementation has not started.
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Proposed tasklist v8 SHA-256: `88adb2e2e849285c7f83c924ef32c4fab12f1d05d3d4820dab0813f40c445e43`
- Frozen tasklist v8 SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Luna gate receipt SHA-256: `2691b341c030e51056987f1aeb02fa130af75f22a901d5847cdf1c94b2d0f2f6`
- Sol freeze receipt SHA-256: `6e5a2b51c2b4954506a171884cbc2c2fe31bbf826b620ef13aa30ef1283f942e`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Next step: Batch 1 — execute `NBF-01` with GPT-5.6 Luna, then obtain its Sol Oracle gate before Batch 2.

# Prior status — Megado run resumed, custody/source reconciliation

Location: /Users/peteromalley/Documents/Arnold-oracle-nbf (branch megado-nbf-guard-0826)

Resume audit 2026-08-29: refreshed `origin/main` is `798c506192`; current branch
HEAD before rebase is `004540970f`. The checked-in `.oracle/tasklist.md` is a
foreign onboarding-run artifact and is NOT execution-ready for this NBF goal.
Next: preserve resume artifacts, rebase the five NBF-only commits onto the
refreshed source SHA, then have Sol produce/validate the NBF plan and tasklist.
Model policy: Luna normal; Sol planner/oracle/`[XHARD]`.

## Temporary execution-policy override — 2026-08-29

For the next 30 minutes, the user authorizes GPT-5.6 Sol subagents for obvious
fixes and normal implementation/validation work. Independent Sol oracle ownership,
the prohibition on direct main-agent implementation, no main merge, and all
existing delivery boundaries remain unchanged. The actual goal is unchanged and
no tasklist is frozen by this bookkeeping note.

## Authoritative model-policy update — 2026-08-29

From this instruction onward, Grok 4.6 is pinned for Oracle and any justified
`[XHARD]` work. Normal exploration, critique, execution, and independent review
remain GPT-5.6 Luna. This supersedes the earlier temporary Sol override for
future Oracle/`[XHARD]` dispatches; completed Sol planning and freeze receipts
remain historical evidence and are not invalidated. The frozen tasklist, goal
scope, and source code are unchanged.

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
