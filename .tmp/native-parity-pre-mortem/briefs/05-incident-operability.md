# Isolated review 5 — incident responder and operability adversary

Working directory: `/Users/peteromalley/Documents/Arnold`.

Read-only. Do not edit repo/git and do not read `.tmp/native-parity-sensecheck-round2/final-audit.md` or reviewer output. Read all required Native Parity docs/initiative/briefs and inspect actual persistence, workflow runtime, handler, auto/CLI, suspension/resume, WBC/custody binding, proof, status, watchdog/auditor, scenario, and test surfaces. Cite exact `path:line`. M11 generic substrate is accepted; do not redesign it.

Start from concrete artifacts an operator would actually see. Simulate: stale coordinator; expired/reassigned custody; source/policy/WBC-version drift during suspension; crash before/after effect intent/outcome; ambiguous persistence; cross-host handoff; partial installed-version skew; forged/stale projections. Decide whether one composed history lets a human explain and safely repair the run without hidden handler state. Find missing diagnostics, causal joins, quarantine states, decision-consumption visibility, or repair invariants that must be plan-level acceptance requirements. For each gap cite permitting plan text and current code shape, show the incident failure, why proof can still be green, and smallest amendment. Mark generic M11 matters out of scope and distinguish sprint implementation details.
