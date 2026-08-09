# North Star: Finite CL2 critique-ledger canary

This canary proves one fresh, finitely bounded CL2 planning lifecycle. It runs
init, plan, critique, and a first gate. `PROCEED` requires `gated` state and may
run finalize. One first-gate `ITERATE` requires `critiqued` state and admits
exactly one revise, one fresh critique, and one final gate; there is no second
revise. A second non-PROCEED, or any `ESCALATE`/`TIEBREAKER`, is a terminal
product block with infrastructure status preserved and no finalize. Every
resident, watchdog, repair, notification, execution, and relaunch authority
remains absent. The canary does not execute implementation work, declare CL2
complete, or establish durability beyond the finite receipt.

The canonical product North Star remains
`.megaplan/initiatives/critique-ledger/NORTHSTAR.md`. This canary is successful
only when custody is complete, the gate independently says PROCEED, the terminal
state is finalized, and all evidence is content-addressed to the accepted source
commit/tree and exact zero-recovery host/container/workspace identity.

For CL2, the accepted runtime source identity is an exact clean committed Git
commit and its tree. Dirty or uncommitted source is rejected. This is a settled
product decision shared by finalization, every execute entry path, and handoff;
the finite gate must not convert it into an `add_human_halt` action.
