# Write a "blocked-recovery" runbook

I want a one-page operator runbook at `docs/ops/blocked-recovery.md` covering what
to do when a megaplan run goes into the `blocked` state. It should walk through
reading `valid_next` and the recovery decision tree.

Please drive this through megaplan — pick whatever profile and robustness fit a doc
deliverable. The doc should be a real reference, not a stub.

Done = the file exists, covers the decision tree, and the megaplan run reaches
state `done` or `reviewed`.
