# Batch 2 attempt 18 — legacy ambiguous reopen hold

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-17 reviews and
valid native/OMP/managed, lifecycle, terminal-transport, and handler roots.
The Sol ruling is explicit: reject any managed second-WBC authority or related
redesign; this attempt accepts only the legacy ambiguous reopen root.

- Repeated reopen of a legacy ambiguous reservation must emit no new
  `not_started` or other lifecycle records, preserve the same typed unresolved
  context, and reject before WBC/provider/relaunch effects.
- Normal empty reservations retain the canonical four-state lifecycle
  `not_started -> entered -> accepted -> closed`.

No frozen/index/status/execution-log changes, commit, push, merge, deploy, or
scope expansion.
