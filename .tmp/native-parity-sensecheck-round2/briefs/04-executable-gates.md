# Lens 4 — executable-gate and false-pass adversary

You are an independent read-only implementation adversary. Work in `/Users/peteromalley/Documents/Arnold`; do not edit and do not read other round-2 outputs. Cite exact `path:line` evidence for every material claim.

Locked premise/end state: Custody M11 is already complete and accepted; Native Parity must yield one authored topology, one exact RA decision history, one exclusive current Custody owner, one durable WBC/effect history, disposable projections. Four identities remain distinct. WBC evidence, leases, and projections do not authorize. Positive action requires current RA grant/fence + current Custody lease/epoch + exact-version WBC evidence.

Read completely:

- revised README/NORTHSTAR/chain and s1–s7 briefs under `.megaplan/initiatives/megaplan-native-parity-corrective/`
- corrective plan, representation report, prior final audit, custody-overlap audit
- relevant m1–m10 briefs
- the actual chain schema/spec loader, precondition evaluator, completion-manifest implementation, chain runner/validator/CLI, and their tests
- current proof-map, scenario, conformance, replay, mutation-test, shadow/enforce, authority/custody negative-test code as needed

Enumerate every field in this epic's `chain.yaml` and prove whether the current loader supports it, rejects unknowns, validates type/value, and enforces its claimed semantics. Audit launch prerequisites (including completed Custody pinning/revalidation), per-sprint gates, S7 replay, proof maps, manifests, artifact/set equality, installed-artifact checks, runtime traces, mutation tests, shadow/enforce mode, and negative authority tests. Trace false-pass routes: prose-only gate, existence instead of content, self-authored oracle, stale/mismatched prerequisite manifest, nonblocking command, omitted scenario, missing set equality, or success state unrelated to North Star.

Output:

1. Verdict.
2. Complete chain-field audit table: YAML path/value, loader/schema support, validation behavior, runtime semantics, test evidence, false-pass risk.
3. Gate table for launch and s1–s7: command/artifact, actually executable?, semantics checked, false-pass route, status.
4. Ranked gaps with exact smallest amendments to chain/brief/plan assets.
5. Sound executable protections.

Take a position. Cap at roughly 6,000 words.
