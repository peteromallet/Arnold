# North Star: Finite CL2 critique-ledger canary

This canary proves exactly one fresh CL2 planning lifecycle—init, plan,
critique, gate, finalize—while every resident, watchdog, repair, notification,
and relaunch authority remains absent. It does not execute implementation work,
declare CL2 complete, or establish durability beyond the finite receipt.

The canonical product North Star remains
`.megaplan/initiatives/critique-ledger/NORTHSTAR.md`. This canary is successful
only when custody is complete, the gate independently says PROCEED, the terminal
state is finalized, and all evidence is content-addressed to the accepted source
commit/tree and exact zero-recovery host/container/workspace identity.
