# Questions for the Oracle

Answer all three questions independently. Use concrete counterexamples and cite
packet-relative file paths plus line numbers. Distinguish current local behavior,
the accepted-but-missing completed-M11 prerequisite, the Stage 1 Native Parity
target, and the Stage 2 Platformization target.

## 1. Can two conforming implementations still disagree?

Treat the revised representation report, Native Parity epic, golden trace
contract, and Platformization ticket as a specification given independently to
two implementation teams. Find every place where both teams could reasonably
claim compliance while producing incompatible observable behavior. Focus on
loop exits, root hosting, business versus lifecycle terminals, outcome
conditions, retries versus new generations, human suspension, agentic phases,
race/quorum precedence, cancellation, budget accounting, Custody release, trace
normalization, migration, and repair acceptance. For each ambiguity, provide two
conflicting compliant implementations and the smallest normative rule that
eliminates one.

## 2. Can a wrong implementation still pass every planned proof?

Design the smallest “green but wrong” implementation that passes every named
static check, golden scenario, negative mutation, local/installed comparison,
migration gate, and conformance receipt while still violating the North Star in
production. You may exploit missing scenario composition, proof adapters,
normalization, comparison provenance, omitted multiplicity, untested
interleavings, capability-profile exclusions, or differences between checkout,
wheel, cloud, and restored control-plane state. Identify exactly which current
gate falsely passes and propose one additional proof that makes the
implementation fail.

## 3. Is the plan executable on the real substrate in its current sequence?

Map every required contract and gate to the concrete current Arnold code and the
assumed completed-M11 interfaces. Identify hidden prerequisites, circular
dependencies, duplicate runtime planes, temporary dual authorities, unavailable
APIs, migration ordering hazards, and sprint workloads that cannot realistically
close within their assigned milestone. Determine whether any requirement
currently assigned to Native Parity S1–S7 or Platformization S1–S5 must move
earlier, split, or become a prerequisite. Do not propose a new sprint merely for
conceptual neatness; require evidence that the existing owner cannot safely
deliver it.
