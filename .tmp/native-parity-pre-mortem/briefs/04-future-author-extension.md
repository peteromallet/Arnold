# Isolated review 4 — future workflow author and extension test

Working directory: `/Users/peteromalley/Documents/Arnold`.

Read-only; do not edit repo/git. Do not read `.tmp/native-parity-sensecheck-round2/final-audit.md` or reviewer outputs. Read all mandated Native Parity primary sources and inspect actual authored workflow, compiler/lowering/runtime, components, handlers, auto/CLI, policy, proof, scenario, and tests. Cite exact `path:line`. Treat completed M11 generic substrate as locked and out of scope.

Imagine maintaining the completed system six months later. Walk six concrete changes: add a gate outcome, a dynamic review lens, a retry policy, a human decision, an override, and an external effect. For each, identify where a competent developer would naturally edit the current repository and where the completed design intends them to edit. Find API/ownership ambiguity that makes handlers, auto-drive, metadata, projections, or compatibility code easier than the Python topology. Demand extension tests proving the correct authored path is both easiest and the only authoritative route. Produce a future-extension table: change, intended edit point, likely bypass, why current gates miss it, anti-bypass proof, smallest amendment. Separate material long-term semantic-authority risks from ergonomic polish.
