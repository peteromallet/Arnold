# Status — Arnold SDK epic (event-sourced-ledger runtime)

**⚠️ NOT self-runnable as-is (pre-launch sense-check 2026-05-29 · ../validation/prelaunch/SYNTHESIS.md).** The triple is spec-valid but the chain HARNESS does not honor the autonomy ladder / require_clean_base, M0 is a bootstrap paradox as milestone #1, and auto-merge has no oracle in its path. Launch is NOT one t0 go yet.

**Pre-t0 fix path (the real M-1 / M0):** (1) engine-readiness PATCH on main (ladder+bump+bounded-retry-counter, parse require_clean_base, auto-handle clarify/tiebreaker) then pin; (2) operator pre-step — frozen venv from main@t0-sha + wire gate CI as base-branch REQUIRED CHECKS + external wallet ceiling (~$500-1200) + launch with --no-git-refresh; (3) chain milestone #1 becomes harness-code-only; add a real depends_on/gate field (M1) or treat ∥ as topo-sort-over-serial; fix the brief seams (RoutingKey in M2, M5b->M5c type+mapping, M5d owns auto-merge, M5-cal->M5-eval taint, M2.5 four-way resume, M4 "stop new path" not "kill", M5c method name). See EPIC "## ⚠️ PRE-LAUNCH" + prelaunch/SYNTHESIS.md.

---

# Status — Arnold SDK epic (event-sourced-ledger runtime)

**TRIPLE COMPLETE + VALIDATED (2026-05-29). Review-ready; launch = a single t0 "go".**
chain.yaml: success=true, 14 milestones, merge_policy: auto, failure/escalate = auto-ladders, require_clean_base.

**Single source of truth:** ../pipeline-unification-EPIC.md
  - The architecture: 11 organs (Activation, Conveyance, Governor+Capacity-Lease, Effect/Contract/
    Calibration/Evaluand Ledgers, Behavioral-Identity-Manifest, Replayable-Capsule, Warrant) + 7 reshapers
    (R1 event-sourced foundation = the floor) + the data model (Port = kind×content-type×schema, open registry).
  - The final sequenced program + strangler discipline + top risks.

**Sequenced milestones (chain order):** M0 keep-alive floor → M1 foundation+contract-checker+R1-seed →
M2 types+Port → M2.5 auto.py spike → **M3 THE HINGE** (Activation+realized-graph+Conveyance+R1-flip+Governor) →
M4 services+EffectLedger+RecoveryPolicy+one-Ledger → M5a node-lib(+Manifest) → M5b execute → M5-eval (the
spine) → M5-cal (gated on eval) → M5c control-plane (evict STATE_*) → **M6 THE STRANGLER SWAP** (atomic,
last) → M5d supervisor → M7 sinks (Capsule∥Warrant∥docs).

**Zero human blockers:** 172 decision-points pre-made (REGISTER.md), must_ask_peter = ∅. Every runtime gate
is a machine-gate or auto-escalation ladder; the only human act is the t0 go.

**Strangler safety:** a PINNED external engine drives the build (M0); old path default-ON, new organs behind
default-OFF flags; the behavioral-replay + substrate-swap ORACLE is the sole retirement authority; M6 is the
single atomic cutover (no broken window).

**Evidence base:** ../validation/{c1-c7,s1-s4,u1,u2} · /premortem · /confidence · /decision · /interrogation ·
/committed-uu · /human-blockers · /edges · /sequencing  (~90 agents, 11 swarms). deferred/ = superseded drafts.

**To launch (the t0 go):** commit the epic artifacts, then
  megaplan chain start --spec briefs/epic-pipeline-unification/chain.yaml --one
drive from a PINNED engine / --no-git-refresh off a frozen branch (NOT the live editable checkout) — M0
exists precisely to make that safe. M0 (the keep-alive floor) is the first PR.
