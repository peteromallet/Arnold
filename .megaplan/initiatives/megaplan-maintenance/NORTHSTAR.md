# Trustworthy automatic repair and six-hour feedback

Arnold's repair loop must measure and prove recovery, not merely orchestration or liveness. Detection, repair, verification, watchdog reporting, and the six-hour audit must consume coherent evidence, use one mutation authority, report every action truthfully, and fail closed when evidence is absent or contradictory.

Automatic mutation remains default-off behind one master gate until staged evidence supports promotion. A repair is complete only when an independent later observation proves the original blocker cleared. The six-hour auditor is a read-only evaluator whose findings enter the normal repair or ticket authority.

All model-backed automatic-repair and six-hour-audit work is pinned to `gpt-5.6-sol`. Runtime receipts must record the resolved model; configuration intent alone is not proof.

