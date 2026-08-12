# Megaplan prep — auto-repair and six-hour feedback

Source: `research/codex-5-6-sol-autofix-six-hour-feedback-audit.md` (2026-07-10).

## Sizing

This is an epic, not one megaplan. The audit contains immediate containment, authority/schema migration, independent delayed verification, and a feedback-product rebuild. Each is independently reviewable and approximately sprint-sized; combining them would obscure rollback boundaries and mix default-off containment with later enforcement work.

## Dial choices

- M1 overall plan difficulty: 5/5; selected profile: `partnered-5`; because a bad safety-gate or receipt plan could remain locally green while allowing hidden mutation or false reporting. Robustness `full`, depth `high`.
- M2 overall plan difficulty: 5/5; selected profile: `partnered-5`; because authority migration and read coherence have cross-consumer failure modes and direct-write hazards. Robustness `thorough`, depth `high`, with directed prep.
- M3 overall plan difficulty: 5/5; selected profile: `partnered-5`; because custody closure, independent verification, canary install, and rollback are production-safety contracts. Robustness `thorough`, depth `high`.
- M4 overall plan difficulty: 4/5; selected profile: `partnered-5`; because exact-window aggregation and rollout policy require careful event-ordering and provenance reasoning. Robustness `full`, depth `high`.

The operator profile is `partnered-5`, so every milestone pins `profile: partnered-5` and follows that profile's model routing without a vendor override.

## Locked editorial decisions

- L3 is read-only and routes findings through normal repair/ticket authority.
- Independent later observation is the only terminal verifier.
- Mutation remains default-off; this chain prepares rollout but does not authorize launch or autonomy enablement.
- Existing `megaplan-maintenance` is reused because it already owns the source audit and closely matches the requested work.

## Human gates retained

- Before resolver enforcement: approve drift threshold, runtime identity, production incident store, and retention.
- Before canary launch: approve numeric SLOs, minimum follow-up coverage, promotion percentages, and rollback ownership.

## Launch state

Prepared only. No `megaplan init`, `chain start`, cloud launch, gate approval, or scheduled babysit action has been invoked.
