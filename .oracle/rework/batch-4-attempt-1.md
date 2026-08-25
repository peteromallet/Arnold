# Rework tasklist — batch-4 attempt 1 (from GateB4 P2)
1. [normal] T1 imports agentbox.onboarding.flow at top of try (~100ms chain load every launch).
   Fix: move should_offer verbatim into new stdlib-only leaf agentbox/onboarding/guards.py;
   flow.py imports it from guards (single source); arnold_agent.py imports only guards for the
   gate, offer_and_repreflight stays lazily imported inside the accepted branch; tighten block
   to <25 lines.
Acceptance: importing agentbox.arnold_agent does not import sqlite3/yaml/subprocess via
onboarding (assert in test via sys.modules probe after fresh interpreter? simpler: assert
"agentbox.onboarding.flow" not in sys.modules when guard branch not taken and guards import is
cheap); all suites green.
